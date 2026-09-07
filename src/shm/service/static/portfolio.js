/* Private data stays in memory. No browser persistence, demo values or generated trades. */
window.Portfolio = (() => {
  'use strict';
  const $=s=>document.querySelector(s), e=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const money=v=>v==null?'待补齐':'$'+Number(v).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
  const pct=v=>v==null?'不可计算':(Number(v)*100).toFixed(2)+'%';
  const pages={personal:'个人账户',performance:'资产表现','ai-review':'AI 复盘','ai-settings':'AI 设置'};
  const labels={ledger:'持仓账本',broker:'券商净资产',unselected:'未选定',complete:'完整',partial:'部分缺失',matched:'一致',difference:'有差额',unavailable:'不可计算',limited:'报告受限',queued:'排队中',running:'生成中',failed:'失败',open:'待处理',accepted:'已采纳',done:'已完成',dismissed:'不采纳'};
  const label=x=>labels[x]||x;
  const b=(text,action,extra='')=>`<button class="p-button" data-p="${action}" ${extra}>${text}</button>`;
  const field=(name,title,value='',type='text',extra='')=>`<label class="p-field">${title}<input name="${name}" type="${type}" value="${e(value)}" ${extra}></label>`;
  const select=(name,title,options,value)=>`<label class="p-field">${title}<select name="${name}">${options.map(([v,l])=>`<option value="${e(v)}" ${v===value?'selected':''}>${e(l)}</option>`).join('')}</select></label>`;
  const area=(name,title,value='')=>`<label class="p-field wide">${title}<textarea name="${name}">${e(value)}</textarea></label>`;
  const check=(name,title,value=false)=>`<label class="p-check"><input type="checkbox" name="${name}" ${value?'checked':''}>${title}</label>`;
  const badge=(v,warn=false)=>`<span class="personal-badge ${warn?'warn':''}">${e(v)}</span>`;
  const insLabel=i=>i.kind==='option'?`${i.symbol} ${i.expiry} ${i.strike}${i.right} ×${i.multiplier}`:i.symbol;
  const localNow=()=>{
    const d=new Date(), f=new Intl.DateTimeFormat('sv-SE',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(d);
    const off=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',timeZoneName:'longOffset'}).formatToParts(d).find(x=>x.type==='timeZoneName').value.replace('GMT','');
    return f.replace(' ','T')+off;
  };
  const state={page:null,account:null,events:[],valuations:[],settings:null,reports:[],suggestions:[],reportSubject:'personal',reportId:null,comparisonStrategy:'S500-C3',comparisonCost:'10'};
  const drafts={trade:{at:localNow(),type:'equity',symbol:'',action:'BUY',quantity:'',price:'',fee:'',legs:[],plan:''},account:null,valuation:null};
  let modal=null, preview=null, activeRequest=null, previousFocus=null;
  async function api(path,body){
    const r=await fetch(path,{method:body?'POST':'GET',cache:'no-store',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});
    const j=await r.json();if(!r.ok){if(r.status===409){preview=null;activeRequest=null;const fresh=await fetch('/api/personal/account',{cache:'no-store'});if(fresh.ok)state.account=await fresh.json();}throw new Error(j.error||'请求失败')}return j;
  }
  function fail(err){const target=$('#p-error')||$('#p-page-error');if(target)target.textContent=err.message;}
  function shell(content){$('#page-content').innerHTML=`<div id="p-page-error" class="p-error" role="alert"></div>${content}`;}
  async function show(page,force=false){
    if(!pages[page])return false;
    if(state.page===page&&!force)return true;
    state.page=page;
    $('#page-title').textContent=pages[page];$('#crumb-name').textContent=pages[page];$('#heading-sub').textContent='手动记账 · USD · 真实费用与模型成本分别披露';$('#page-actions').innerHTML=b('刷新','refresh');$('#data-notice').hidden=true;
    $('.top-actions .pill').textContent='PERSONAL · 手动账本';$('#footer-note').textContent='私人数据仅通过认证入口读取；页面草稿只保留到本页关闭';
    document.querySelectorAll('[data-page]').forEach(x=>{x.classList.toggle('active',x.dataset.page===page);if(x.dataset.page===page)x.setAttribute('aria-current','page');else x.removeAttribute('aria-current')});
    shell('<div class="personal-card">正在读取…</div>');
    try{
      if(page==='personal'){
        [state.account,state.events,state.valuations]=await Promise.all([api('/api/personal/account'),api('/api/personal/events'),api('/api/personal/valuations')]);
        if(state.page===page)personal();
      }else if(page==='performance'){
        const result=await api('/api/comparison?'+new URLSearchParams({strategy_id:state.comparisonStrategy,cost_bps:state.comparisonCost}));
        if(state.page===page)performance(result);
      }else if(page==='ai-settings'){
        state.settings=await api('/api/ai/settings');if(state.page===page)settings();
      }else{
        [state.reports,state.suggestions,state.settings]=await Promise.all([api('/api/ai/reports'),api('/api/ai/suggestions'),api('/api/ai/settings')]);
        if(state.page===page)reports();
      }
    }catch(err){if(state.page===page)shell(`<section class="personal-card"><h3>私人功能暂不可用</h3><p>${e(err.message)}</p><p class="personal-muted">原模拟持仓、交易、运行日志和调度可继续使用。</p></section>`)}
    return true;
  }
  function holdings(){
    const lots=state.account?.state?.lots||[], values={};
    for(const l of lots){const k=l.instrument.key;if(!values[k])values[k]={instrument:l.instrument,quantity:0};values[k].quantity+=Number(l.quantity)}
    const latest=state.valuations.filter(v=>v.valid).sort((a,b)=>b.at.localeCompare(a.at))[0];
    return Object.values(values).map(h=>({...h,value:latest?.holdings.find(x=>x.instrument.key===h.instrument.key&&Number(x.quantity)===h.quantity)?.value??null,quote_at:latest?.at}));
  }
  function personal(){
    if(!state.account.account){shell(`<section class="personal-card"><h3>建立你的观察起点</h3><p class="personal-muted">填写期初现金、持仓及同一时点的券商净资产。从这里开始计算新观察期收益；原始成本未知可以留空。</p>${b('建立 USD 账户','account')}</section>`);return}
    const a=state.account, hs=holdings(),v=state.valuations.filter(v=>v.valid).sort((a,b)=>b.at.localeCompare(a.at))[0];
    const row=(h,i)=>`<tr><td><strong>${e(insLabel(h.instrument))}</strong><small>${h.instrument.kind==='option'?'期权 · 每股报价':'股票 / ETF'}</small></td><td>${e(h.quantity)}</td><td>${money(h.value)}<small>${e(h.quote_at||'尚无估值')}</small></td><td>${b('记录操作','row-trade',`data-index="${i}"`)}</td></tr>`;
    shell(`<div class="personal-toolbar"><strong>${e(a.account.name)}</strong>${badge(a.account.type==='margin'?'保证金账户':'现金账户')}${badge('账本 v'+a.version)}${b('记录交易 / 事件','trade')}${b('录入估值','valuation')}${b('修订期初','account')}</div>
      <div class="personal-grid"><section class="personal-card"><h3>已记账净现金</h3><div class="personal-value">${money(a.state.cash)}</div><p class="personal-muted">负现金表示实际融资；不计算券商购买力。</p></section><section class="personal-card"><h3>收益依据</h3><div class="personal-value">${money(v?.nav)}</div>${badge(label(v?.source||'unselected'))}<p class="personal-muted">${e(v?.at||'请录入首份收盘估值')}</p></section><section class="personal-card"><h3>持仓归因与对账</h3>${badge('归因：'+label(v?.attribution||'partial'),v?.attribution!=='complete')}${badge('对账：'+label(v?.reconciliation||'unavailable'),v?.reconciliation!=='matched')}<p>差额 ${money(v?.difference)}</p><p class="personal-muted">选择券商净资产不会自动完成持仓对账。</p></section></div>
      <section class="personal-card" style="margin-top:18px"><h3>个人持仓</h3><div class="p-desktop-positions personal-table-wrap"><table class="personal-table"><thead><tr><th>证券 / 完整合约</th><th>数量（空头为负）</th><th>净市值</th><th>操作</th></tr></thead><tbody>${hs.map(row).join('')||'<tr><td colspan="4">当前无持仓</td></tr>'}</tbody></table></div><div class="p-mobile-positions">${hs.map((h,i)=>`<div class="p-row"><strong>${e(insLabel(h.instrument))}</strong><p>数量 ${e(h.quantity)} · 净市值 ${money(h.value)}</p>${b('记录操作','row-trade',`data-index="${i}"`)}</div>`).join('')||'当前无持仓'}</div></section>
      <section class="personal-card" style="margin-top:18px"><h3>个人事件流水</h3><p class="personal-muted">历史修订保存冲正关系，并使受影响的估值等待重新确认。</p><div class="personal-table-wrap"><table class="personal-table"><thead><tr><th>发生时间 · 纽约</th><th>事件 / 组合</th><th>状态</th><th>操作</th></tr></thead><tbody>${state.events.map(r=>`<tr><td>${e(r.payload.at)}<small>录入 ${e(r.created_at)}</small></td><td>${r.payload.legs.map(l=>`${e(l.action)} ${e(l.instrument?insLabel(l.instrument):l.note)} ${e(l.quantity||l.amount)}`).join('<br>')}<small>组合 ${e(r.payload.group_id||r.id)}</small></td><td>${badge(r.reversed_by?'已被冲正':'有效')}${r.replaces?'<small>替代 #'+r.replaces+'</small>':''}</td><td>${!r.reversed_by?b('修订','revise',`data-id="${r.id}"`):''}</td></tr>`).join('')||'<tr><td colspan="4">尚无事件</td></tr>'}</tbody></table></div></section>
      <details class="personal-card" style="margin-top:18px"><summary>估值历史与失效记录</summary>${state.valuations.map(x=>`<p>${e(x.at)} ${badge(x.valid?'有效':'账本修订后待重核',!x.valid)} ${e(label(x.source))} · ${money(x.nav)} · 对账 ${e(label(x.reconciliation))}</p>`).join('')||'<p>尚无估值</p>'}</details>`);
  }
  function performance(r){
    const options=['S500-C3','S500-C0','S500-C1','S500-C2','S500-C4','C0','C1','C2','C3','C4','V04'];
    shell(`<div class="personal-toolbar">${select('compare_strategy','模拟账户',options.map(x=>[x,x]),state.comparisonStrategy)}${select('compare_cost','模型成本',[['10','10 bps'],['25','25 bps']],state.comparisonCost)}${b('应用','compare')}</div><div class="personal-card"><h3>同区间净值 · 起点 100</h3><p>${e(r.start||'等待共同起点')} — ${e(r.end||'')}</p>${badge(r.simulation_status==='waiting'?'模拟等待前向记录':'包含模拟前向表现')}${badge(r.complete?'区间完整':'区间不完整',!r.complete)}<p class="personal-muted">${e(r.cost_note)}</p><svg class="p-chart" id="p-chart" viewBox="0 0 900 260" role="img" aria-label="个人、模拟与 SPY 同区间净值"></svg><div class="personal-toolbar"><span style="color:#14785e">● 个人</span><span style="color:#4583ce">● 模拟</span><span style="color:#b4995b">● SPY 含息</span></div>${r.warnings.map(x=>`<p class="personal-muted">${e(x)}</p>`).join('')}</div><div class="personal-grid" style="margin-top:16px">${Object.entries(r.metrics).map(([k,v])=>`<section class="personal-card"><h3>${{personal:'个人账户',simulation:'模拟账户',spy:'SPY'}[k]}</h3><div class="personal-value">${pct(v.cumulative_return)}</div><p>累计收益 · 最大回撤 ${pct(v.max_drawdown)}</p></section>`).join('')}</div>`);
    const svg=$('#p-chart'), vals=r.rows.flatMap(p=>['personal','simulation','spy'].map(k=>p[k]).filter(x=>x!=null).map(Number));if(!vals.length)return;
    const lo=Math.min(98,...vals)-1,hi=Math.max(102,...vals)+1,x=i=>50+i*810/Math.max(1,r.rows.length-1),y=v=>225-(v-lo)/(hi-lo)*190;
    let out=[lo,(lo+hi)/2,hi].map(v=>`<line x1="50" y1="${y(v)}" x2="860" y2="${y(v)}" stroke="#e6ece8"/><text x="4" y="${y(v)+4}" fill="#75827b" font-size="12">${v.toFixed(1)}</text>`).join('');
    for(const [key,color] of [['personal','#14785e'],['simulation','#4583ce'],['spy','#b4995b']]){let line='',broken=true; r.rows.forEach((p,i)=>{if(p[key]==null){broken=true;return}line+=(broken?'M':'L')+x(i)+','+y(Number(p[key]))+' ';broken=false});out+=`<path d="${line}" fill="none" stroke="${color}" stroke-width="2"/>`}
    out+=`<text x="50" y="254" font-size="12" fill="#75827b">${e(r.start)}</text><text x="775" y="254" font-size="12" fill="#75827b">${e(r.end)}</text>`;svg.innerHTML=out;
  }
  function openModal(title,body,footer=''){
    previousFocus=document.activeElement;
    if(!$('#p-overlay'))document.body.insertAdjacentHTML('beforeend','<div class="p-overlay" id="p-overlay" hidden><section class="p-dialog" role="dialog" aria-modal="true" aria-labelledby="p-title"></section></div>');
    $('#p-overlay .p-dialog').innerHTML=`<header class="p-dialog-head"><h2 id="p-title">${title}</h2>${b('关闭','close')}</header><form id="p-form" class="p-form" autocomplete="off" onsubmit="return false">${body}<div id="p-error" class="p-error" role="alert"></div></form><div class="p-confirm" id="p-confirm">${footer}</div>`;
    $('#p-overlay').hidden=false;$('#p-overlay input, #p-overlay select, #p-overlay button')?.focus();
  }
  function capture(){
    if(!modal||!$('#p-form'))return;
    const values=Object.fromEntries(new FormData($('#p-form')));
    $('#p-form').querySelectorAll('input[type=checkbox]').forEach(x=>values[x.name]=x.checked);
    if(modal==='trade')Object.assign(drafts.trade,values);
    else if(modal==='account')Object.assign(drafts.account,values);
    else if(modal==='valuation')Object.assign(drafts.valuation,values);
  }
  function close(){capture();if($('#p-overlay'))$('#p-overlay').hidden=true;modal=null;previousFocus?.focus()}
  function instrumentFields(d){
    return field('symbol','标的代码',d.symbol)+ (d.type==='equity'?'':select('right','Call / Put',[['C','Call'],['P','Put']],d.right||'P')+field('expiry','到期日',d.expiry,'date')+field('strike','行权价',d.strike)+`<details><summary>合约乘数、结算及调整信息</summary><div class="p-fields">${field('multiplier','合约乘数',d.multiplier||'100')}${select('settlement','结算方式',[['physical','实物交割'],['cash','现金结算']],d.settlement||'physical')}${field('occ','OCC 合约代码（可选）',d.occ)}${field('series','调整系列',d.series||'standard')}${check('adjusted','非标准调整合约（禁止自动交割）',d.adjusted)}</div></details>`);
  }
  function readInstrument(d){return d.type==='equity'?{kind:'equity',symbol:d.symbol}:{kind:'option',symbol:d.symbol,right:d.right||'P',expiry:d.expiry,strike:d.strike,multiplier:d.multiplier||'100',settlement:d.settlement||'physical',occ:d.occ||'',series:d.series||'standard',adjusted:!!d.adjusted}}
  function trade(row=null){
    modal='trade';const d=drafts.trade;
    if(row){Object.assign(d,row.instrument,{type:row.instrument.kind,quantity:String(Math.abs(row.quantity)),action:row.instrument.kind==='option'?(row.quantity>0?'STC':'BTC'):(row.quantity>0?'SELL':'BUY_TO_COVER')});d.legs=[];delete d.replaces;delete d.reason;preview=null;activeRequest=null}
    const cash=d.type==='cash',life=d.type==='lifecycle',corp=d.type==='corporate_action';
    let options=cash?[['DEPOSIT','入金'],['WITHDRAW','出金'],['DIVIDEND','分红收入'],['INTEREST','利息收入'],['FINANCING_INTEREST','融资利息'],['FEE','费用支出']]:life?[['EXERCISE','多头行权'],['ASSIGN','空头指派'],['EXPIRE','确认到期失效'],['SETTLE','现金结算']]:corp?[['PENDING','公司行动待核'],['SPLIT','确认拆股'],['EXCHANGE','确认换股/合约替换']]:d.type==='equity'?[['BUY','买入开多'],['SELL','卖出平多'],['SELL_SHORT','卖出开空'],['BUY_TO_COVER','买回平空']]:[['BTO','买入开多 BTO'],['STO','卖出开空 STO'],['STC','卖出平多 STC'],['BTC','买回平空 BTC']];
    if(!options.some(x=>x[0]===d.action))d.action=options[0][0];
    const existing=holdings().filter(h=>h.instrument.kind==='option');
    const body=`<div class="p-tabs">${[['equity','正股 / ETF'],['option','期权'],['cash','现金'],['lifecycle','期权事件'],['corporate_action','公司行动']].map(([k,t])=>b(t,'type',`data-type="${k}" class="${d.type===k?'active':''}"`)).join('')}</div><div class="p-fields">${field('at','发生时间 · 纽约（含时区偏移）',d.at)}${select('action','明确操作方向',options,d.action)}${!cash&&d.type!=='equity'&&!corp&&existing.length?select('existing','带入已有合约',[['','手动填写'],...existing.map((h,i)=>[String(i),insLabel(h.instrument)])],d.existing||''):''}${!cash?instrumentFields({...d,type:corp?'equity':d.type}):''}${cash?field('amount','金额（分红为税前金额）',d.amount)+field('tax','分红扣税（无则 0）',d.tax||'0')+area('note','事件说明',d.note):corp?field('ratio','拆股 / 换股比例',d.ratio||'1')+area('target_json','换股或调整后完整证券（EXCHANGE 专用 JSON）',d.target_json||''):field('quantity',life?'本次关闭张数':d.type==='equity'?'股数（允许碎股）':'张数（整数）',d.quantity)+(!life?field('price',d.type==='equity'?'成交单价':'每股权利金 · 非每张总金额',d.price):field('settlement_amount','现金结算总额（未扣本次费；空头支出为负）',d.settlement_amount||''))}${field('fee','本次总费用（必填，允许 0）',d.fee)}${life||corp?area('evidence','券商确认 / 公司行动依据',d.evidence):''}<details><summary>组合关联与操作计划（选填）</summary><div class="p-fields">${field('group_id','组合编号 / 展期关联',d.group_id)}${area('plan','理由、目的、退出条件、预计持有期、计划风险',d.plan)}</div><p class="personal-muted">补录时间自动保留，补写不会作为事前计划。</p></details></div>${check('confirm_financing','净现金为负时，我已核对实际融资事实',d.confirm_financing)}${d.replaces?area('reason','修订原因（原事件 #'+d.replaces+'）',d.reason):''}<div class="personal-toolbar">${b('加入本次组合','add-leg')}</div><div>${d.legs.map((l,i)=>`<div class="p-row">${e(l.action)} · ${e(l.instrument?insLabel(l.instrument):l.note)} · ${e(l.quantity||l.amount)} ${b('移除','remove-leg',`data-index="${i}"`)}</div>`).join('')}</div>`;
    openModal(d.replaces?'冲正与替代记录':'记录已发生交易 / 事件',body,`<p class="personal-muted">先预览，核对原持仓 → 本次变化 → 成交后持仓。预览不记账。</p><div id="p-summary"></div><div class="personal-toolbar">${b('预览本次记账','preview')}${b('确认记账','commit','disabled')}</div>`);
  }
  function makeLeg(){const d=drafts.trade,kind=d.type==='cash'?'cash':d.type==='lifecycle'?'lifecycle':d.type==='corporate_action'?'corporate_action':'trade';
    const l={kind,action:d.action,fee:d.fee};if(kind==='cash')Object.assign(l,{amount:d.amount,tax:d.tax||'0',note:d.note});else Object.assign(l,{instrument:readInstrument({...d,type:kind==='corporate_action'?'equity':d.type}),quantity:d.quantity,price:d.price,evidence:d.evidence,settlement_amount:d.settlement_amount,ratio:d.ratio});
    if(d.action==='EXCHANGE')l.target=JSON.parse(d.target_json);return l;
  }
  async function tradePreview(){capture();const d=drafts.trade,legs=d.legs.length?d.legs:[makeLeg()];
    const request={version:state.account.version,event:{at:d.at,timezone:'America/New_York',legs,group_id:d.group_id||'',plan:d.plan||'',confirm_financing:!!d.confirm_financing}};
    if(d.replaces)Object.assign(request,{replaces:d.replaces,reason:d.reason});
    preview=await api('/api/personal/events/preview',request);activeRequest={...request,preview_hash:preview.preview_hash,idempotency_key:crypto.randomUUID()};
    const s=preview.summary,keys=[...new Set([...Object.keys(s.before),...Object.keys(s.after)])];
    $('#p-summary').innerHTML=`${keys.map(k=>`<p><strong>${e(k)}</strong> ${e(s.before[k]||'0')} → ${e(Number(s.after[k]||0)-Number(s.before[k]||0))} → ${e(s.after[k]||'0')}</p>`).join('')}<strong>净现金变化 ${money(s.cash_change)} · 成交后 ${money(s.cash_after)}</strong><p>交割金额变化 ${money(s.delivery_change)} · 交割总额 ${money(s.delivery_total)}</p><p class="personal-muted">${s.warnings.map(e).join('；')}</p>${preview.duplicate?check('confirm_duplicate','我已核对，这不是误重复录入'):''}`;
    $('[data-p="commit"]').disabled=false;
  }
  function accountModal(){modal='account';if(!drafts.account)drafts.account={...(state.account.account||{name:'',type:'cash',cash:'',broker_nav:'',at:localNow()}),positions:structuredClone(state.account.account?.positions||[]),opening_type:'equity'};const d=drafts.account;
    openModal('期初账户 · USD',`<div class="p-fields">${field('name','账户名称',d.name)}${select('type','账户类型',[['cash','现金账户'],['margin','保证金账户']],d.type)}${field('at','期初日期与时点 · 纽约 ISO 时间',d.at)}${field('cash','净现金（融资为负）',d.cash)}${field('broker_nav','同一时点券商净资产',d.broker_nav)}${field('receivable','有依据的应收',d.receivable||'0')}${field('payable','有依据的应付',d.payable||'0')}${field('balance_note','应收应付依据',d.balance_note)}${check('confirm_financing','已确认负现金对应实际融资',d.confirm_financing)}</div><h3>期初持仓</h3>${d.positions.map((p,i)=>`<div class="p-row">${e(insLabel(p.instrument))} · ${e(p.quantity)} · ${money(p.mark)} ${b('移除','opening-remove',`data-index="${i}"`)}</div>`).join('')}<details open><summary>添加期初持仓</summary><div class="p-fields">${select('opening_type','证券类型',[['equity','正股 / ETF'],['option','期权']],d.opening_type)}${instrumentFields({...d,type:d.opening_type||'equity'})}${field('opening_quantity','有符号数量（空头填负数）',d.opening_quantity)}${field('opening_mark','单位估值（期权每股权利金）',d.opening_mark)}${field('opening_source','估值来源',d.opening_source)}${field('original_cost','原始单位成本（未知留空）',d.original_cost)}${field('original_opened_at','原建仓 ISO 时间（未知留空）',d.original_opened_at)}</div><div class="personal-toolbar">${b('加入期初持仓','opening-add')}</div></details>${state.account.account?area('reason','修订期初原因',d.reason):''}`,`<p class="personal-muted">服务端按期初现金＋净持仓＋应收－应付对账。容差为 $1 与券商净资产 0.01% 中较大者。</p>${b('校验并建立 / 修订','save-account')}`);
  }
  async function valuationModal(){modal='valuation';if(!drafts.valuation){const q=await api('/api/personal/quotes');drafts.valuation={at:q.at,coverage:'截至此时点，包含所有已发生并已录入的交易与资金流',source:'unselected',marks:q.marks||{}}}const d=drafts.valuation,hs=holdings();
    openModal('每日估值与收益来源',`<div class="p-fields">${field('at','快照覆盖时点 · 纽约 ISO 时间',d.at)}${field('broker_nav','券商净资产（可留空）',d.broker_nav)}${area('coverage','覆盖说明',d.coverage)}</div><h3>单位估值</h3><p class="personal-muted">空白表示缺价。正股用名义价格；期权用券商每股报价。没有最新报价时保留缺失。</p>${hs.map((h,i)=>`<div class="p-row"><strong>${e(insLabel(h.instrument))}</strong><div class="p-fields">${field('mark_'+i,'单位估值',d['mark_'+i]??d.marks[h.instrument.key]?.price??'')}${field('source_'+i,'来源',d['source_'+i]??d.marks[h.instrument.key]?.source??'')}</div></div>`).join('')}<div class="p-fields">${select('source','账户收益依据',[['unselected','暂存待核对'],['ledger','采用持仓账本'],['broker','采用券商净资产']],d.source)}${area('reason','来源选择依据 / 差异待核说明',d.reason)}</div>${check('flows_complete','我已确认此快照之前的入出金全部录入',d.flows_complete)}`,`<div id="p-summary"></div><div class="personal-toolbar">${b('预览估值','preview-value')}${b('保存估值版本','save-value','disabled')}</div>`);
  }
  function settings(){const s=state.settings;shell(`<section class="personal-card"><h3>OpenAI 兼容接口</h3><p class="personal-muted">密钥加密保存在 NAS；发送去标识化交易数据。连接测试仅发送无持仓短样例。</p><form id="p-settings" autocomplete="off"><div class="p-fields">${field('base_url','Base URL（含 /v1）',s.base_url,'url')}${field('model','精确模型 ID',s.model)}${field('key',s.has_key?'替换密钥（留空保留已有密钥）':'API 密钥','','password')}${field('auto_limit','每月自动尝试上限（含重试）',s.auto_limit,'number','min="1" max="8"')}${field('manual_limit','每日手动尝试上限',s.manual_limit,'number','min="1" max="4"')}${field('max_completion_tokens','单次 completion token 上限',s.max_completion_tokens,'number','min="1" max="6000"')}${field('input_limit','输入字符上限',s.input_limit,'number','min="1" max="200000"')}</div>${check('scope_personal','允许发送去标识化个人账本指标与持仓',s.scope.includes('personal'))}${check('scope_simulation','允许发送模拟策略证据',s.scope.includes('simulation'))}${check('automatic','开启自动发送与报告生成',s.automatic)}${check('weekly','每周六 08:00 生成上周简报（北京时间）',s.weekly)}${check('monthly','每月 1 日 08:15 生成上月复盘（北京时间）',s.monthly)}<p id="p-test-status">${badge(s.tested?'当前连接测试通过':'尚未通过当前连接测试',!s.tested)} ${e(s.compatibility||'')}</p><div class="personal-toolbar">${b('保存设置','save-settings')}${b('测试已保存连接','test-ai')}</div><div id="p-error" class="p-error" role="alert"></div></form><p class="personal-muted">最多重试一次；失败也计入额度。费用未知时只显示用量。接口、模型或密钥变化会使原连接测试失效。</p></section>`)}
  function reports(){
    const rows=state.reports.filter(r=>r.payload.subject===state.reportSubject),chosen=rows.find(r=>String(r.id)===String(state.reportId))||rows[0];if(chosen)state.reportId=chosen.id;
    const result=chosen?.result?.report;
    shell(`<div class="personal-toolbar">${select('report_subject','所属账户',[['personal','个人账户'],['simulation','模拟账户']],state.reportSubject)}${b('手动生成报告','new-report')}${b('刷新作业','refresh')}</div><div class="personal-card">${select('report_select','报告类型 · 区间 · 状态',rows.map(r=>[String(r.id),`${r.payload.type} · ${r.payload.start}—${r.payload.end} · v${r.payload.version} · ${label(r.status)}`]),String(chosen?.id||''))}${chosen?`<p>${badge(label(chosen.status),chosen.status!=='complete')}${badge(chosen.payload.subject==='personal'?'个人账本样本':'模拟账户样本')} ${e(chosen.payload.model)} · ${e(chosen.payload.package.strategy_id)}</p>`:'<p>尚无报告。配置接口并通过测试后可生成。</p>'}${chosen?.error?`<p class="p-error">${e(chosen.error)}</p>`:''}${result?`<h3>${e(result.title)}</h3><p class="p-report">${e(result.summary)}</p>${result.limitations.map(x=>`<p class="personal-muted">${e(x)}</p>`).join('')}<p class="personal-muted">用量 ${e(JSON.stringify(chosen.result.usage))} · 费用未知 · 账本版本 ${chosen.payload.package.ledger_version}</p>`:''}</div>${result?state.suggestions.filter(s=>s.report_id===chosen.id).map(s=>`<section class="personal-card" style="margin-top:16px"><h3>${e(s.payload.title)}</h3>${badge(label(s.status))}<p>建议：${e(s.payload.action)}</p><p>范围：${e(s.payload.scope)}</p><p>替代解释：${e(s.payload.alternatives)}</p><p>不确定性：${e(s.payload.uncertainty)}</p><p>验收：${e(s.payload.acceptance)}</p><p>停止条件：${e(s.payload.stop_condition)}</p><div class="p-evidence">${e(JSON.stringify(s.payload.facts,null,2))}</div><div class="personal-toolbar">${b('采纳为待办','suggestion',`data-id="${s.id}" data-status="accepted"`)}${b('标记完成','suggestion',`data-id="${s.id}" data-status="done"`)}${b('不采纳','suggestion',`data-id="${s.id}" data-status="dismissed"`)}${b('导出实施任务','export-suggestion',`data-id="${s.id}"`)}</div><p class="personal-muted">采纳仅更新状态，不改代码、账本或订单。</p></section>`).join(''):''}${chosen?`<details class="personal-card" style="margin-top:16px"><summary>程序证据与输入快照 · ${e(chosen.payload.input_hash.slice(0,12))}</summary><pre class="p-evidence">${e(JSON.stringify(chosen.payload.package.evidence,null,2))}</pre></details>`:''}`);
  }
  function newReport(){modal='report';const today=localNow().slice(0,10),start=today.slice(0,8)+'01';openModal('生成报告',`<div class="p-fields">${select('subject','所属账户',[['personal','个人账户'],['simulation','模拟账户']],state.reportSubject)}${select('type','报告类型',[['manual','手动报告'],['weekly','周简报'],['monthly','月复盘']],'manual')}${field('start','开始日期',start,'date')}${field('end','截止日期',today,'date')}${select('strategy_id','模拟版本',['S500-C3','S500-C0','S500-C1','S500-C2','S500-C4','C0','C1','C2','C3','C4','V04'].map(x=>[x,x]),'S500-C3')}${select('cost_bps','模型成本',[['10','10 bps'],['25','25 bps']],'10')}</div><p class="personal-muted">生成前会校验发送范围、输入上限与调用额度。历史修订产生新报告版本。</p>`,b('创建报告作业','create-report'))}
  async function act(action,target){
    if(action==='refresh'){state.page=null;return show(location.hash.slice(1),true)}
    if(action==='close')return close();
    if(action==='trade')return trade();
    if(action==='row-trade')return trade(holdings()[Number(target.dataset.index)]);
    if(action==='type'){capture();drafts.trade.type=target.dataset.type;preview=null;return trade()}
    if(action==='add-leg'){capture();drafts.trade.legs.push(makeLeg());preview=null;return trade()}
    if(action==='remove-leg'){capture();drafts.trade.legs.splice(Number(target.dataset.index),1);preview=null;return trade()}
    if(action==='preview')return tradePreview();
    if(action==='commit'){if(!activeRequest||!preview)throw new Error('请先预览');if(preview.duplicate)activeRequest.confirm_duplicate=!!$('[name=confirm_duplicate]')?.checked;await api('/api/personal/events',activeRequest);close();drafts.trade={at:localNow(),type:'equity',symbol:'',action:'BUY',quantity:'',price:'',fee:'',legs:[]};preview=null;activeRequest=null;return show('personal',true)}
    if(action==='revise'){const row=state.events.find(r=>r.id===Number(target.dataset.id));drafts.trade={...drafts.trade,...row.payload,type:'equity',legs:structuredClone(row.payload.legs),replaces:row.id,reason:''};preview=null;return trade()}
    if(action==='account')return accountModal();
    if(action==='opening-add'){capture();const d=drafts.account;d.positions.push({instrument:readInstrument({...d,type:d.opening_type}),quantity:d.opening_quantity,mark:d.opening_mark,source:d.opening_source,original_cost:d.original_cost||null,original_opened_at:d.original_opened_at||null});return accountModal()}
    if(action==='opening-remove'){capture();drafts.account.positions.splice(Number(target.dataset.index),1);return accountModal()}
    if(action==='save-account'){capture();const d=drafts.account;await api('/api/personal/account',{version:state.account.version,account:{name:d.name,currency:'USD',type:d.type,at:d.at,cash:d.cash,broker_nav:d.broker_nav,positions:d.positions,receivable:d.receivable||'0',payable:d.payable||'0',balance_note:d.balance_note,confirm_financing:!!d.confirm_financing},reason:d.reason});close();drafts.account=null;return show('personal',true)}
    if(action==='valuation')return valuationModal();
    if(action==='preview-value'){capture();const d=drafts.valuation,marks={};holdings().forEach((h,i)=>{if(d['mark_'+i]!==''&&d['mark_'+i]!=null)marks[h.instrument.key]={price:d['mark_'+i],source:d['source_'+i],at:d.at,basis:h.instrument.kind==='equity'?'nominal':'broker'}});activeRequest={version:state.account.version,at:d.at,coverage:d.coverage,broker_nav:d.broker_nav,source:d.source,reason:d.reason,flows_complete:!!d.flows_complete,marks};preview=await api('/api/personal/valuations',activeRequest);activeRequest.preview_hash=preview.preview_hash;$('#p-summary').innerHTML=`<p>账本 ${money(preview.ledger_nav)} · 券商 ${money(preview.broker_nav)} · 差额 ${money(preview.difference)}</p>${badge('收益依据 '+label(preview.source))}${badge('归因 '+label(preview.attribution))}${badge('对账 '+label(preview.reconciliation))}<p class="personal-muted">缺价 ${e(preview.missing.join('、')||'无')}</p>`;$('[data-p="save-value"]').disabled=false;return}
    if(action==='save-value'){await api('/api/personal/valuations',{...activeRequest,save:true});close();drafts.valuation=null;preview=null;activeRequest=null;return show('personal',true)}
    if(action==='compare'){state.comparisonStrategy=$('[name=compare_strategy]').value;state.comparisonCost=$('[name=compare_cost]').value;return show('performance',true)}
    if(action==='save-settings'){const form=$('#p-settings'),v=Object.fromEntries(new FormData(form));['auto_limit','manual_limit','max_completion_tokens','input_limit'].forEach(k=>v[k]=Number(v[k]));['automatic','weekly','monthly'].forEach(k=>v[k]=form.elements[k].checked);v.scope=['personal','simulation'].filter(k=>form.elements['scope_'+k].checked);delete v.scope_personal;delete v.scope_simulation;state.settings=await api('/api/ai/settings',v);form.elements.key.value='';settings();return}
    if(action==='test-ai'){target.disabled=true;try{await api('/api/ai/test',{});return show('ai-settings',true)}finally{target.disabled=false}}
    if(action==='new-report')return newReport();
    if(action==='create-report'){const p=Object.fromEntries(new FormData($('#p-form')));const r=await api('/api/ai/reports',p);state.reportId=r.id;state.reportSubject=p.subject;close();return show('ai-review',true)}
    if(action==='suggestion'){await api('/api/ai/suggestions',{id:target.dataset.id,status:target.dataset.status});return show('ai-review',true)}
    if(action==='export-suggestion'){const s=state.suggestions.find(s=>s.id===target.dataset.id),p=s.payload;const text=`# SHM 改进任务：${p.title}\n\n来源报告：${s.report_id}\n状态：${s.status}\n\n建议：${p.action}\n\n修改范围：${p.scope}\n\n事实与证据：\n${JSON.stringify(p.facts,null,2)}\n\n替代解释：${p.alternatives}\n\n不确定性：${p.uncertainty}\n\n验收：${p.acceptance}\n\n停止条件：${p.stop_condition}\n\n此文档为待评审任务，不授权自动调参或下单。\n`;const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([text],{type:'text/markdown'}));a.download=`shm-suggestion-${s.id.replace(':','-')}.md`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
  }
  document.addEventListener('click',event=>{const t=event.target.closest('[data-p]');if(!t)return;event.preventDefault();Promise.resolve(act(t.dataset.p,t)).catch(fail)});
  document.addEventListener('input',event=>{if(event.target.closest('#p-form')&&event.target.name!=='confirm_duplicate'){preview=null;activeRequest=null;const c=$('[data-p=commit]')||$('[data-p=save-value]');if(c)c.disabled=true}if(event.target.closest('#p-settings')&&['base_url','model','key'].includes(event.target.name))$('#p-test-status').textContent='连接配置已修改；保存并重新测试后生效';});
  document.addEventListener('change',event=>{const n=event.target.name;if(n==='existing'){capture();preview=null;activeRequest=null;const hs=holdings().filter(h=>h.instrument.kind==='option'),row=hs[Number(event.target.value)];if(event.target.value!==''&&row){Object.assign(drafts.trade,row.instrument,{quantity:String(Math.abs(row.quantity))});trade()}}if(n==='opening_type'){capture();accountModal()}if(n==='report_subject'){state.reportSubject=event.target.value;reports()}if(n==='report_select'){state.reportId=event.target.value;reports()}});
  document.addEventListener('keydown',event=>{if(!modal)return;if(event.key==='Escape')close();if(event.key==='Tab'){const xs=[...$('#p-overlay').querySelectorAll('button:not([disabled]),input,select,textarea,summary')].filter(x=>x.offsetParent!==null);if(event.shiftKey&&document.activeElement===xs[0]){xs.at(-1).focus();event.preventDefault()}else if(!event.shiftKey&&document.activeElement===xs.at(-1)){xs[0].focus();event.preventDefault()}}});
  return {show,handles:page=>!!pages[page],leave:()=>{if(modal)close();state.page=null;},pages};
})();
