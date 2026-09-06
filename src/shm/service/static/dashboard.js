'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const fmt = (value, digits = 2) => Number(value).toLocaleString('en-US', {minimumFractionDigits:digits,maximumFractionDigits:digits});
const money = value => value == null ? '—' : '$' + fmt(value);
const signed = value => value == null ? '—' : (value > 0 ? '+' : value < 0 ? '−' : '') + '$' + fmt(Math.abs(value));
const percent = value => value == null ? '—' : (value > 0 ? '+' : value < 0 ? '−' : '') + fmt(Math.abs(value)) + '%';
const tone = value => value < 0 ? 'negative' : value > 0 ? 'positive' : '';
const glyphs = {
  grid:'<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  layers:'<path d="m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5"/>',
  arrows:'<path d="M4 7h15m-4-4 4 4-4 4M20 17H5m4-4-4 4 4 4"/>',
  activity:'<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  file:'<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6Z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
  settings:'<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3" fill="currentColor" stroke="none"/><circle cx="15" cy="17" r="3" fill="currentColor" stroke="none"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',
  check:'<path d="m5 12 4 4L19 6"/>',
  down:'<path d="m6 9 6 6 6-6"/>',
  download:'<path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4"/>',
  close:'<path d="m6 6 12 12M18 6 6 18"/>',
  info:'<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
  wallet:'<rect x="3" y="5" width="18" height="15" rx="3"/><path d="M3 8h18M17 13h4M16 13h.01"/>',
  pause:'<path d="M8 5v14M16 5v14"/>'
};
const icon = name => '<svg class="icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' + (glyphs[name] || glyphs.file) + '</svg>';
let data=null,chartObserver,toastTimer,returnFocus;
const titles={overview:'账户总览',holdings:'当前持仓',trades:'交易记录',logs:'运行日志',reports:'策略报告'};
const state={page:titles[location.hash.slice(1)]?location.hash.slice(1):'overview',chartMode:'assets',tradeFilter:'all',logFilter:'all',sort:'value'};
const statusText={success:'成功',failed:'失败',running:'运行中',queued:'排队中',skipped:'跳过'};
const statusTone={failed:'bad',running:'warn',queued:'warn',skipped:'gray'};
const time=value=>{
  if(!value)return '—';
  return new Intl.DateTimeFormat('sv-SE',{timeZone:data?.schedule.timezone||'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date(value));
};
const duration=(start,end)=>{
  if(!start)return '—';
  const seconds=Math.max(0,Math.round(((end?new Date(end):new Date())-new Date(start))/1000));
  return seconds>=60?Math.floor(seconds/60)+' 分 '+seconds%60+' 秒':seconds+' 秒';
};
const badge=(label,kind='')=>'<span class="pill '+kind+'"><span class="dot"></span>'+esc(label)+'</span>';
const statusBadge=status=>badge(statusText[status]||status,statusTone[status]||'');
const button=(label,action)=>'<button class="button" data-action="'+action+'">'+label+'</button>';
const a=()=>({...data.account,holdings:data.holdings,next:data.progress.next});
const stockLabel=h=>'<div class="holding-symbol"><span class="stock-mark">'+esc(h.symbol.slice(0,2))+'</span><span class="stock-name"><strong>'+esc(h.symbol)+'</strong><small>'+h.qty+' 股</small></span></div>';
const empty=(title,body,graphic='layers')=>'<div class="empty"><div class="empty-graphic">'+icon(graphic)+'</div><h3>'+esc(title)+'</h3><p>'+esc(body)+'</p></div>';
const miniStats=items=>'<div class="mini-stats">'+items.map(item=>'<div class="mini-stat"><span>'+item[0]+'</span><strong class="num '+(item[2]||'')+'">'+item[1]+'</strong></div>').join('')+'</div>';
async function api(path,options={}){
  const response=await fetch(path,{cache:'no-store',...options});
  const result=await response.json();
  if(!response.ok)throw new Error(result.error||'服务暂时不可用');
  return result;
}
async function refresh(manual=false){
  try{
    data=await api('/api/dashboard');
    if($('#overlay').hidden)render();
    if(manual)showToast('已读取最新账户与运行记录');
  }catch(error){
    if(!data){
      $('#data-notice').hidden=true;
      $('#page-content').innerHTML='<section class="panel">'+empty('暂时无法读取账户数据',error.message,'info')+'<div style="text-align:center;padding-bottom:24px">'+button('重新读取','refresh')+'</div></section>';
    }
    showToast('读取失败：'+error.message);
  }
}
function metrics(account){
  const previous=account.total!=null&&account.day!=null?account.total-account.day:null;
  return '<div class="metrics">'+
    '<div class="metric"><div class="metric-label">总资产 <span class="currency">USD</span><button class="text-button" data-action="method" aria-label="资产计算口径">'+icon('info')+'</button></div><div class="metric-value num">'+money(account.total)+'</div><div class="metric-foot">'+(account.day!=null?'<b class="'+tone(account.day)+'">当日 '+signed(account.day)+'</b><span>('+percent(previous?account.day/previous*100:null)+')</span>':'<span>账户起点 '+esc(account.start)+'</span>')+'</div></div>'+
    '<div class="metric"><div class="metric-label">累计盈亏</div><div class="metric-value num '+tone(account.gain)+'">'+signed(account.gain)+'</div><div class="metric-foot"><b class="'+tone(account.gain)+'">'+percent(account.gain_percent)+'</b><span>初始资金 '+money(account.initial)+'</span></div></div>'+
    '<div class="metric"><div class="metric-label">持仓浮动盈亏</div><div class="metric-value num '+tone(account.unrealized)+'">'+signed(account.unrealized)+'</div><div class="metric-foot"><span>已实现</span><b class="'+tone(account.realized)+'">'+signed(account.realized)+'</b></div></div>'+
    '<div class="metric"><div class="metric-label">可用现金</div><div class="metric-value num">'+money(account.cash)+'</div><div class="metric-foot"><span>占总资产</span><b>'+(account.total?fmt(account.cash/account.total*100,1)+'%':'—')+'</b></div></div></div>';
}
function chartPanel(account){
  const benchmark=data.chart.some(point=>point.benchmark!=null);
  return '<section class="panel chart-panel"><div class="panel-head"><div><h2>资产表现</h2><div class="panel-sub">'+esc(account.start)+' — '+esc(account.valuation_date)+'</div></div><div class="segments" aria-label="图表指标">'+['assets','return'].map((key,i)=>'<button data-chart="'+key+'" class="'+(state.chartMode===key?'active':'')+'" aria-pressed="'+(state.chartMode===key)+'">'+(i?'收益率':'总资产')+'</button>').join('')+'</div></div><div class="legend"><span><i></i>SHM 模拟账户</span>'+(benchmark?'<span><i class="benchmark"></i>SPY · 同额起点参考</span>':'')+'</div><div class="chart-container" id="asset-chart"><svg id="equity-svg" role="img" aria-label="模拟账户总资产历史曲线，缺少行情的日期留空"></svg><div class="chart-tip" id="chart-tip"></div></div><div class="chart-footer"><span>累计收益 <b class="'+tone(account.gain)+'">'+percent(account.gain_percent)+'</b></span><span>基于已完成交易日 · 初始资金 '+money(account.initial)+'</span></div></section>';
}
function allocationPanel(account){
  const weight=account.total?account.market/account.total*100:null;
  return '<section class="panel allocation-panel"><div class="panel-head"><h2>资产分布</h2><span class="small muted">'+account.holdings.length+' 只股票</span></div><div class="allocation"><div class="donut" style="--angle:'+(weight||0)*3.6+'deg"><div class="donut-hole"><small>股票仓位</small><strong class="num">'+(weight!=null?fmt(weight,1)+'<span style="font-size:14px">%</span>':'—')+'</strong></div></div></div><div class="alloc-rows"><div class="alloc-row"><i class="swatch"></i>股票市值<strong class="num">'+money(account.market)+'</strong><span>'+(weight!=null?fmt(weight,1)+'%':'—')+'</span></div><div class="alloc-row"><i class="swatch cash"></i>可用现金<strong class="num">'+money(account.cash)+'</strong><span>'+(weight!=null?fmt(100-weight,1)+'%':'—')+'</span></div></div></section>';
}
function schedulePanel(account){
  const last=data.runs[0],progress=data.progress;
  return '<section class="panel schedule-panel"><div class="panel-head"><h2>自动运行</h2><button class="text-button" data-action="schedule" aria-label="修改每日检查时间">'+icon('settings')+'</button></div><div class="schedule-status">'+(last?statusBadge(last.status):badge('尚无运行记录','gray'))+'</div><div class="schedule-time"><small>下次调仓信号日</small><strong class="num">'+esc(account.next.slice(5).replace('-',' 月 '))+' 日 <span>'+account.next.slice(0,4)+'</span></strong><span>每 20 个美股交易日 · 收盘后检查</span></div><div class="timeline"><div class="timeline-item"><i class="timeline-dot"></i><div><strong>'+progress.completed+' / 3 换仓周期 · '+progress.months+' / 3 月报</strong><small>等待成交 '+progress.pending+' 个 · 错过窗口 '+progress.missed+' 个</small></div></div><div class="timeline-item"><i class="timeline-dot next"></i><div><strong>每日检查 · '+esc(data.schedule.time)+'</strong><small>'+esc(data.schedule.timezone)+' · '+(data.schedule.due?'等待调度检查':'下次 '+time(data.schedule.next_at))+'</small></div></div></div><div class="schedule-foot"><button class="text-button" data-page="logs">查看运行日志 '+icon('arrow')+'</button></div></section>';
}
function holdingRows(rows,compact=false){
  return rows.map(h=>'<tr class="clickable" data-holding="'+esc(h.symbol)+'"><td>'+stockLabel(h)+'</td>'+
    (compact?'':'<td class="right num">'+h.qty+'</td><td class="right num">'+money(h.cost)+'</td>')+
    '<td class="right num">'+money(h.price)+'</td><td class="right num'+(compact?' optional-col':'')+'">'+money(h.value)+'</td><td class="right two-line num '+tone(h.pnl)+'">'+signed(h.pnl)+'<small>'+percent(h.pnl_percent)+'</small></td>'+
    (compact?'':'<td class="right num">'+(h.weight!=null?'<span class="weight-bar"><i style="width:'+h.weight+'%"></i></span>'+fmt(h.weight,1)+'%':'—')+'</td><td><button class="text-button" data-holding="'+esc(h.symbol)+'" aria-label="查看 '+esc(h.symbol)+'">'+icon('arrow')+'</button></td>')+'</tr>').join('');
}
function overview(account){
  return metrics(account)+'<div class="chart-grid">'+chartPanel(account)+allocationPanel(account)+'</div><div class="lower-grid"><section class="panel holdings-preview"><div class="panel-head"><div><h2>当前持仓 <span class="muted small">/ '+account.holdings.length+'</span></h2><div class="panel-sub">按市值排序 · 点击持仓查看明细</div></div><button class="text-button" data-page="holdings">全部持仓 '+icon('arrow')+'</button></div>'+
    (account.holdings.length?'<div class="table-scroll"><table><thead><tr><th>股票</th><th class="right">最新价</th><th class="right optional-col">市值</th><th class="right">持仓盈亏</th></tr></thead><tbody>'+holdingRows(account.holdings.slice(0,4),true)+'</tbody></table></div><div class="table-bottom"><span>估值使用已完成交易日的收盘价 · USD</span><span>显示 '+Math.min(4,account.holdings.length)+' / '+account.holdings.length+' 只</span></div>':empty('尚无持仓','下一调仓信号日为 '+account.next+'。调仓单生成后，等待下一交易日模拟成交。'))+'</section>'+schedulePanel(account)+'</div>';
}
function holdingsPage(account){
  const rows=[...account.holdings].sort((x,y)=>(y[state.sort]??-Infinity)-(x[state.sort]??-Infinity));
  return miniStats([['股票市值',money(account.market)],['持仓浮动盈亏',signed(account.unrealized),tone(account.unrealized)],['持仓数量',account.holdings.length+' 只']])+
    '<section class="panel"><div class="toolbar"><h2>股票持仓</h2><label class="small muted">排序 <select id="holding-sort" aria-label="持仓排序"><option value="value" '+(state.sort==='value'?'selected':'')+'>市值从高到低</option><option value="pnl" '+(state.sort==='pnl'?'selected':'')+'>盈亏从高到低</option></select></label></div>'+
    (rows.length?'<div class="table-scroll"><table class="table-full"><thead><tr><th>股票</th><th class="right">持有股数</th><th class="right">成本均价</th><th class="right">最新价</th><th class="right">持仓市值</th><th class="right">持仓盈亏</th><th class="right">资产占比</th><th></th></tr></thead><tbody>'+holdingRows(rows)+'</tbody></table></div><div class="table-bottom"><span>成本采用加权平均法，含买入佣金；缺失依据的指标显示为 —</span><span>USD</span></div>':empty('资金尚未建仓','现金 '+money(account.cash)+'；持仓、成本和盈亏将在模拟成交后展示。'))+'</section>';
}
function tradesPage(account){
  const rows=data.trades.filter(t=>state.tradeFilter==='all'||t.side===state.tradeFilter);
  return miniStats([['累计成交',data.trades.length+' 笔'],['累计成交金额',money(data.trades.reduce((sum,t)=>sum+t.amount,0))],['已实现盈亏',signed(account.realized),tone(account.realized)]])+
    '<section class="panel"><div class="toolbar"><div class="tabs" aria-label="成交方向">'+[['all','全部'],['buy','买入'],['sell','卖出']].map(([key,label])=>'<button data-trade-filter="'+key+'" class="'+(state.tradeFilter===key?'active':'')+'">'+label+' <small>'+data.trades.filter(t=>key==='all'||t.side===key).length+'</small></button>').join('')+'</div><button class="text-button" data-action="tickets">查看调仓单 '+icon('arrow')+'</button></div>'+
    (rows.length?'<div class="table-scroll"><table class="table-full"><thead><tr><th>成交交易日</th><th>股票</th><th>方向</th><th class="right">股数</th><th class="right">成交价</th><th class="right">金额</th><th class="right">已实现盈亏</th><th>记录</th><th></th></tr></thead><tbody>'+rows.map(t=>'<tr class="clickable" data-trade="'+t.id+'"><td class="num">'+esc(t.date)+'</td><td>'+esc(t.symbol)+'</td><td><span class="direction '+(t.side==='sell'?'sell':'')+'">'+(t.side==='sell'?'卖出':'买入')+'</span></td><td class="right num">'+t.qty+'</td><td class="right num">'+money(t.price)+'</td><td class="right num">'+money(t.amount)+'</td><td class="right num '+tone(t.realized_pnl)+'">'+signed(t.realized_pnl)+'</td><td>'+badge('模拟账户','gray')+'</td><td><button class="text-button" data-trade="'+t.id+'" aria-label="查看 '+esc(t.symbol)+' 成交详情">'+icon('arrow')+'</button></td></tr>').join('')+'</tbody></table></div><div class="table-bottom"><span>来自已落账的成交文件 · 点击查看信号日期、交易原因与佣金</span><span>'+rows.length+' 条</span></div>':empty('尚无模拟成交','已落账的买卖、成交价格和卖出盈亏将在这里展示。','arrows'))+'</section>';
}
function logsPage(){
  const rows=data.runs.filter(r=>state.logFilter==='all'||r.status===state.logFilter);
  return miniStats([['每日检查时间',esc(data.schedule.time)],['最近运行',data.runs[0]?statusText[data.runs[0].status]:'尚无记录',data.runs[0]?.status==='success'?'positive':''],['下次调仓信号',esc(data.progress.next.slice(5).replace('-',' / '))]])+
    '<section class="panel"><div class="toolbar"><div class="tabs" aria-label="运行状态">'+[['all','全部运行'],['success','成功'],['failed','失败']].map(([key,label])=>'<button data-log-filter="'+key+'" class="'+(state.logFilter===key?'active':'')+'">'+label+'</button>').join('')+'</div><span class="muted small">近 90 天 · '+esc(data.schedule.timezone)+'</span></div>'+
    (rows.length?'<div class="table-scroll"><table class="logs-table"><thead><tr><th>运行 / 开始时间</th><th>状态</th><th>市场交易日</th><th>耗时</th><th>结果摘要</th><th></th></tr></thead><tbody>'+rows.map(r=>'<tr class="clickable" data-run="'+r.id+'"><td class="two-line num"><strong style="font-weight:500">#'+r.id+'</strong> &nbsp; '+time(r.started_at||r.created_at)+'<small class="muted">'+(r.trigger==='scheduled'?'定时触发':r.trigger==='manual-retry'?'失败重试':'手动触发')+'</small></td><td>'+statusBadge(r.status)+'</td><td class="num small">'+esc(r.market_session||'—')+'</td><td class="two-line small">'+duration(r.started_at,r.finished_at)+'<small class="muted">尝试 '+r.attempts+' 次</small></td><td class="small log-summary">'+esc((r.summary||r.error||'等待执行').slice(0,160))+'</td><td><button class="text-button" data-run="'+r.id+'" aria-label="查看运行 '+r.id+' 详情">'+icon('arrow')+'</button></td></tr>').join('')+'</tbody></table></div><div class="table-bottom"><span>展开记录查看真实步骤、错误与输出</span><span>'+rows.length+' 条</span></div>':empty('暂无符合条件的运行记录','运行记录保存在调度服务中，当前展示最近 90 天。','activity'))+'</section>';
}
function reportsPage(){
  if(!data.reports.length)return '<section class="panel">'+empty('尚无策略报告','月末自动生成模拟盘月报；成交后生成的期权覆盖评估也会在此展示。','file')+'</section>';
  return '<div class="report-grid">'+data.reports.map(report=>'<article class="panel report-card"><div class="report-top"><span class="report-icon">'+icon('file')+'</span>'+badge('已生成')+'</div><h2>'+esc(report.title)+'</h2><p>'+(report.kind==='monthly'?'模拟盘与同参数模型的收益、执行成本和偏差归因。':'备兑看涨与现金担保卖出看跌的候选方案、资金占用和跳过原因。')+'</p><div class="report-bottom" style="margin-top:24px"><span>'+time(report.updated_at)+'</span><button class="text-button" data-report="'+esc(report.id)+'">阅读报告 '+icon('arrow')+'</button></div></article>').join('')+'</div>';
}
function openDialog(title,subtitle,body,wide=false){
  returnFocus=document.activeElement;
  $('#dialog').className='dialog'+(wide?' wide':'');
  $('#dialog').innerHTML='<div class="dialog-head"><div><h2 id="dialog-title">'+title+'</h2><p>'+subtitle+'</p></div><button class="close-button" data-action="close" aria-label="关闭弹窗">'+icon('close')+'</button></div><div class="dialog-body">'+body+'</div>';
  $('#overlay').hidden=false;document.body.style.overflow='hidden';$('#dialog .close-button').focus();
}
function closeDialog(){
  $('#overlay').hidden=true;document.body.style.overflow='';
  if(returnFocus?.isConnected)returnFocus.focus();
}
function showToast(message){
  clearTimeout(toastTimer);$('#toast').textContent=message;$('#toast').hidden=false;
  toastTimer=setTimeout(()=>$('#toast').hidden=true,5000);
}
const detailRow=(label,value)=>'<div class="detail-row"><span>'+label+'</span><strong>'+value+'</strong></div>';
const dialogStats=items=>'<div class="dialog-stats">'+items.map(item=>'<div><label>'+item[0]+'</label><strong class="num '+(item[2]||'')+'">'+item[1]+'</strong></div>').join('')+'</div>';
function showHolding(symbol){
  const h=data.holdings.find(row=>row.symbol===symbol);if(!h)return;
  openDialog(esc(h.symbol),'持仓明细 · 估值交易日 '+esc(h.quote_date||'价格待补齐'),
    dialogStats([['持仓市值',money(h.value)],['浮动盈亏',signed(h.pnl),tone(h.pnl)],['持仓收益率',percent(h.pnl_percent),tone(h.pnl)]])+
    detailRow('持有股数',h.qty+' 股')+detailRow('成本均价',money(h.cost))+detailRow('最新收盘价',money(h.price))+detailRow('资产占比',h.weight!=null?fmt(h.weight,2)+'%':'—')+
    '<h3 class="section-title">相关成交</h3><div class="table-scroll"><table><thead><tr><th>日期</th><th>方向</th><th class="right">股数</th><th class="right">成交价</th></tr></thead><tbody>'+data.trades.filter(t=>t.symbol===symbol).map(t=>'<tr><td>'+t.date+'</td><td>'+(t.side==='sell'?'卖出':'买入')+'</td><td class="right">'+t.qty+'</td><td class="right">'+money(t.price)+'</td></tr>').join('')+'</tbody></table></div>');
}
function showTrade(id){
  const t=data.trades.find(row=>row.id===id);if(!t)return;
  openDialog(esc(t.symbol)+' · '+(t.side==='sell'?'卖出':'买入'),'模拟账户成交记录 · '+esc(t.date),
    dialogStats([['成交股数',t.qty+' 股'],['成交价',money(t.price)],['成交金额',money(t.amount)]])+
    detailRow('成交时间（'+esc(data.schedule.timezone)+'）',time(t.filled_at))+detailRow('信号日期',esc(t.signal_date))+detailRow('交易原因',esc(t.reason))+detailRow('佣金',money(t.commission))+
    (t.side==='sell'?detailRow('卖出部分成本',money(t.cost!=null?t.qty*t.cost:null))+detailRow('已实现盈亏','<span class="'+tone(t.realized_pnl)+'">'+signed(t.realized_pnl)+'</span>'):'')+
    '<p class="field-help">数据来自已记录的模拟成交文件。已实现盈亏包含卖出费用。</p>');
}
function showTickets(){
  const rows=data.tickets;
  openDialog('调仓计划','信号日生成计划，下一交易日结束后再记录模拟成交。',
    rows.length?'<div class="table-scroll"><table><thead><tr><th>信号日</th><th>股票</th><th>方向</th><th class="right">股数</th><th>原因</th></tr></thead><tbody>'+rows.map(t=>'<tr><td>'+esc(t.signal_date)+'</td><td>'+esc(t.symbol)+'</td><td>'+(t.side==='sell'?'卖出':'买入')+'</td><td class="right">'+t.qty+'</td><td class="reason-cell">'+esc(t.reason)+'</td></tr>').join('')+'</tbody></table></div>':empty('尚无调仓单','下一信号日为 '+data.progress.next,'file'),true);
}
function stepName(name){
  const labels={'data-update':'更新行情','validate-price-cache':'检查数据完整性','recover-rebalance-audit':'恢复调仓审计','missed-rebalance':'记录错过的调仓窗口','missed-fill':'记录错过的成交窗口','missed-option-overlay':'记录错过的期权窗口','simulate-fills':'模拟成交与账户更新','option-overlay':'期权覆盖评估','monthly-report':'生成月度报告','paper-status':'更新验证进度','rebalance':'生成调仓单'};
  for(const [prefix,label] of Object.entries(labels))if(name===prefix||name.startsWith(prefix+'-'))return label;
  return name;
}
async function showRun(id){
  try{
    const result=await api('/api/runs/'+id),r=result.run;
    openDialog('运行 #'+r.id+' &nbsp; '+statusBadge(r.status),'SHM 调度 · '+esc(data.schedule.timezone),
      dialogStats([['开始时间',time(r.started_at).split(' ').at(-1)],['总耗时',duration(r.started_at,r.finished_at)],['尝试次数',r.attempts+' 次']])+
      '<p class="report-text">'+time(r.started_at||r.created_at)+' · 市场交易日 '+esc(r.market_session||'—')+'</p><p class="report-text run-summary">'+esc(r.summary||r.error||'任务正在运行')+'</p>'+
      '<h3 class="section-title">真实运行步骤</h3>'+result.steps.map(step=>'<details class="log-step" '+(step.status==='failed'?'open':'')+'><summary><span class="step-title">'+esc(stepName(step.name))+'</span><span class="step-result"><span class="muted small">尝试 '+step.attempt+' · '+duration(step.started_at,step.finished_at)+'</span>'+statusBadge(step.status)+icon('down')+'</span></summary><pre>'+esc(step.output||'无文本输出')+'</pre></details>').join('')+
      (result.steps.length?'':'<p class="field-help">尚无步骤记录。</p>'),true);
  }catch(error){showToast(error.message)}
}
function markdown(source){
  // Escape first: reports are data, never executable HTML.
  const lines=esc(source).split('\n');let html='',table=false;
  for(const line of lines){
    if(line.trim().startsWith('|')){
      if(/^\|[\s:|\-]+\|$/.test(line.trim()))continue;
      if(!table){html+='<div class="table-scroll"><table>';table=true}
      html+='<tr>'+line.trim().slice(1,-1).split('|').map(cell=>'<td>'+cell.trim()+'</td>').join('')+'</tr>';continue;
    }
    if(table){html+='</table></div>';table=false}
    if(/^#{1,3} /.test(line)){html+='<h3 class="section-title">'+line.replace(/^#{1,3} /,'')+'</h3>';continue}
    if(line.trim())html+='<p class="report-text">'+line.replace(/^- /,'• ').replace(/`([^`]+)`/g,'<code>$1</code>')+'</p>';
  }
  return html+(table?'</table></div>':'');
}
async function showReport(id){
  try{
    const report=await api('/api/reports/'+id),meta=data.reports.find(r=>r.id===id);
    const body=report.kind==='monthly'?markdown(report.content):optionReport(JSON.parse(report.content));
    openDialog(esc(meta?.title||'策略报告'),'读取已保存的报告正文',body,true);
  }catch(error){showToast(error.message)}
}
function optionReport(plan){
  return dialogStats([['候选订单',plan.orders.length+' 个'],['资金占用',money(plan.summary.cash_usage)],['合计最大亏损',money(plan.summary.max_loss)]])+
    '<p class="report-text">信号日 '+esc(plan.signal_date)+' · 评估日 '+esc(plan.as_of)+' · 仅生成模拟盘方案草稿</p>'+
    '<h3 class="section-title">候选方案</h3>'+
    (plan.orders.length?'<div class="table-scroll"><table><thead><tr><th>标的 / 结构</th><th>到期日</th><th class="right">行权价</th><th class="right">张数</th><th class="right">买价 / 卖价</th><th class="right">现金占用</th></tr></thead><tbody>'+plan.orders.map(o=>'<tr><td>'+esc(o.underlying)+' / '+esc(o.strategy)+'</td><td>'+esc(o.expiration)+'</td><td class="right">'+money(o.strike)+'</td><td class="right">'+o.contracts+'</td><td class="right">'+money(o.bid)+' / '+money(o.ask)+'</td><td class="right">'+money(o.cash_usage)+'</td></tr>').join('')+'</tbody></table></div>':'<p class="report-text">本轮没有满足条件的期权方案。</p>')+
    '<h3 class="section-title">跳过原因</h3>'+
    (plan.skipped.length?'<div class="table-scroll"><table><thead><tr><th>股票</th><th>结构</th><th>原因</th></tr></thead><tbody>'+plan.skipped.map(s=>'<tr><td>'+esc(s.ticker)+'</td><td>'+esc(s.strategy)+'</td><td class="reason-cell">'+esc(s.reason)+'</td></tr>').join('')+'</tbody></table></div>':'<p class="report-text">没有跳过记录。</p>');
}
function showSchedule(){
  openDialog('每日检查时间','统一调度 · '+esc(data.schedule.timezone),
    '<form id="schedule-form"><label for="check-time" class="form-label">每天何时运行 SHM 检查</label><input class="time-field" id="check-time" name="daily_time" type="time" value="'+esc(data.schedule.time)+'" required><p class="field-help">保存后写入服务设置，重启后仍保留。</p><div class="schedule-note"><strong>业务节奏沿用策略规则</strong><br>调仓：每 20 个美股交易日的信号日收盘后。<br>模拟成交：下一交易日结束后。<br>月报：当月最后一个交易日结束后。</div><p class="field-help">请将检查时间安排在目标美股交易日收盘之后、下一次收盘之前。系统每日只创建一条定时运行记录。</p><div class="form-actions">'+button('取消','close')+'<button class="button primary" type="submit">保存时间</button></div></form>');
}
function showMethod(){
  openDialog('资产与盈亏口径','USD · 模拟账户',
    detailRow('总资产','可用现金 + 股票市值')+detailRow('股票市值','持仓股数 × 已完成交易日收盘价')+detailRow('持仓浮动盈亏','股票市值 − 剩余持仓成本')+detailRow('已实现盈亏','卖出收入 − 对应平均成本 − 卖出费用')+detailRow('累计盈亏','总资产 − 初始资金')+
    '<p class="field-help">成本采用含买入佣金的加权平均法。当前账户模型无外部入出金；缺少价格或成本依据时显示 —，不估造收益。</p>');
}
function renderChart(){
  const svg=$('#equity-svg');if(!svg)return;
  const container=$('#asset-chart'),width=Math.max(230,container.clientWidth-23),height=container.clientHeight-10;
  const left=61,right=19,top=21,bottom=31,w=width-left-right,h=height-top-bottom;
  const rows=data.chart,initial=data.account.initial,isReturn=state.chartMode==='return';
  const val=value=>value==null||isReturn&&!initial?null:isReturn?(value/initial-1)*100:value;
  const values=rows.flatMap(p=>[val(p.equity),val(p.benchmark)]).filter(v=>v!=null);
  if(!values.length){svg.innerHTML='<text x="50%" y="50%" text-anchor="middle" fill="#6b8272" font-size="12">价格待补齐，暂无可用曲线</text>';return}
  const low=Math.min(...values),high=Math.max(...values),span=Math.max(high-low,isReturn?1:1000);
  const min=low-span*.13,max=high+span*.15;
  const x=i=>left+(rows.length>1?i/(rows.length-1):.5)*w;
  const y=v=>top+(max-val(v))/(max-min)*h;
  let html='<defs><linearGradient id="equity-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#268e67" stop-opacity=".13"/><stop offset="100%" stop-color="#268e67" stop-opacity="0"/></linearGradient></defs>';
  for(let i=0;i<4;i++){
    const v=min+(max-min)*i/3,py=top+h-i*h/3;
    html+='<line x1="'+left+'" y1="'+py+'" x2="'+(width-right)+'" y2="'+py+'" stroke="#edf2ee"/><text x="'+(left-12)+'" y="'+(py+4)+'" text-anchor="end" fill="#829487" font-size="10.5">'+(isReturn?fmt(v,1)+'%':fmt(v/1000,1)+'k')+'</text>';
  }
  html+='<text x="'+(left-12)+'" y="11" text-anchor="end" fill="#829487" font-size="10">'+(isReturn?'收益率':'USD')+'</text>';
  for(const key of ['benchmark','equity']){
    let path='',started=false;
    rows.forEach((p,i)=>{if(val(p[key])==null){started=false;return}path+=(started?'L':'M')+x(i)+','+y(p[key])+' ';started=true});
    html+='<path d="'+path+'" stroke="'+(key==='equity'?'#21825e':'#b5c4ba')+'" stroke-width="'+(key==='equity'?2.2:1.6)+'" '+(key==='benchmark'?'stroke-dasharray="3 4"':'')+' fill="none"/>';
  }
  const ticks=[...new Set([0,Math.floor((rows.length-1)/2),rows.length-1])];
  ticks.forEach(i=>html+='<text x="'+x(i)+'" y="'+(height-9)+'" text-anchor="'+(rows.length===1?'middle':i===0?'start':i===rows.length-1?'end':'middle')+'" fill="#829487" font-size="10.5">'+rows[i].date.slice(5).replace('-','/')+'</text>');
  rows.forEach((p,i)=>{if(p.equity!=null&&(rows.length===1||i===rows.length-1))html+='<circle cx="'+x(i)+'" cy="'+y(p.equity)+'" r="4" fill="#21825e" stroke="#fff" stroke-width="2"/>'});
  if(rows.length===1&&rows[0].equity!=null)html+='<text x="'+x(0)+'" y="'+(y(rows[0].equity)-23)+'" fill="#486e53" font-size="12" text-anchor="middle">账户起点 · '+money(rows[0].equity)+'</text>';
  html+='<g id="chart-hover" visibility="hidden"><line id="chart-guide" x1="0" y1="'+top+'" x2="0" y2="'+(top+h)+'" stroke="#b9cbbf" stroke-dasharray="3 3"/></g><rect x="'+left+'" y="'+top+'" width="'+w+'" height="'+h+'" fill="transparent" id="chart-hit"/>';
  svg.setAttribute('viewBox','0 0 '+width+' '+height);svg.innerHTML=html;
  const hit=$('#chart-hit'),tip=$('#chart-tip');
  function hover(event){
    const rect=svg.getBoundingClientRect(),pos=(event.clientX-rect.left)*width/rect.width;
    const i=rows.length===1?0:Math.max(0,Math.min(rows.length-1,Math.round((pos-left)/w*(rows.length-1))));
    $('#chart-hover').setAttribute('visibility','visible');$('#chart-guide').setAttribute('x1',x(i));$('#chart-guide').setAttribute('x2',x(i));
    tip.innerHTML='<div class="tip-date">'+rows[i].date+'</div><div>SHM <b>'+(isReturn?percent(val(rows[i].equity)):money(rows[i].equity))+'</b></div><div>SPY <b>'+(isReturn?percent(val(rows[i].benchmark)):money(rows[i].benchmark))+'</b></div>';
    tip.style.left=Math.max(5,Math.min(container.clientWidth-tip.offsetWidth-10,x(i)-tip.offsetWidth/2))+'px';
    tip.style.top='15px';tip.style.opacity='1';
  }
  hit.addEventListener('pointermove',hover);hit.addEventListener('pointerdown',hover);
  hit.addEventListener('pointerleave',()=>{tip.style.opacity='0';$('#chart-hover').setAttribute('visibility','hidden')});
}
function render(){
  if(!data)return;
  if(chartObserver)chartObserver.disconnect();
  const account=a();
  $('#page-title').textContent=titles[state.page];$('#crumb-name').textContent=state.page==='overview'?'总览':titles[state.page];
  $('#heading-sub').textContent=state.page==='logs'?'定时执行与结果追溯 · '+data.schedule.timezone:state.page==='reports'?'已保存的月度报告与期权评估':'账户快照 '+account.asof+' · 行情 '+account.market_session+' 收盘 · USD';
  $('#page-actions').innerHTML=['trades','holdings'].includes(state.page)?button(icon('download')+'导出记录','export'):button(icon('clock')+'调度设置','schedule');
  const notice=$('#data-notice');notice.hidden=!data.warnings.length;
  notice.innerHTML=data.warnings.length?icon('info')+'<span>'+data.warnings.map(esc).join('；')+'</span>':'';
  $('#footer-note').textContent='数据读取于 '+time(data.generated_at)+' · '+data.schedule.timezone;
  $$('#main-nav button').forEach(b=>{b.classList.toggle('active',b.dataset.page===state.page);if(b.dataset.page===state.page)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});
  const pages={overview,holdings:holdingsPage,trades:tradesPage,logs:logsPage,reports:reportsPage};
  $('#page-content').innerHTML=pages[state.page](account);
  if(state.page==='overview'){chartObserver=new ResizeObserver(renderChart);chartObserver.observe($('#asset-chart'));renderChart()}
}
function navigate(page){
  state.page=page;closeDialog();history.pushState(null,'','#'+page);render();window.scrollTo(0,0);
}
function exportRecords(){
  const holdings=state.page==='holdings';
  const items=holdings?data.holdings:data.trades.filter(t=>state.tradeFilter==='all'||t.side===state.tradeFilter);
  if(!items.length){showToast('暂无可导出的记录');return}
  const rows=holdings?[['股票','股数','成本均价_USD','收盘价_USD','市值_USD','浮动盈亏_USD'],...items.map(h=>[h.symbol,h.qty,h.cost,h.price,h.value,h.pnl])]:[['交易日','股票','方向','股数','成交价_USD','金额_USD','佣金_USD','已实现盈亏_USD'],...items.map(t=>[t.date,t.symbol,t.side,t.qty,t.price,t.amount,t.commission,t.realized_pnl])];
  const csv='\uFEFF'+rows.map(row=>row.map(value=>'"'+String(value??'').replaceAll('"','""')+'"').join(',')).join('\r\n');
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})),link=document.createElement('a');
  link.href=url;link.download='shm-'+(holdings?'holdings':'trades')+'.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
document.addEventListener('click',event=>{
  const el=event.target.closest('[data-page],[data-action],[data-holding],[data-trade],[data-run],[data-report],[data-trade-filter],[data-log-filter],[data-chart]');
  if(!el)return;
  if(el.dataset.action==='refresh'){refresh(true);return}
  if(!data)return;
  if(el.dataset.page){navigate(el.dataset.page);return}
  if(el.dataset.holding){showHolding(el.dataset.holding);return}
  if(el.dataset.trade){showTrade(el.dataset.trade);return}
  if(el.dataset.run){showRun(el.dataset.run);return}
  if(el.dataset.report){showReport(el.dataset.report);return}
  if(el.dataset.tradeFilter){state.tradeFilter=el.dataset.tradeFilter;render();return}
  if(el.dataset.logFilter){state.logFilter=el.dataset.logFilter;render();return}
  if(el.dataset.chart){state.chartMode=el.dataset.chart;render();return}
  const actions={schedule:showSchedule,close:closeDialog,export:exportRecords,tickets:showTickets,method:showMethod};
  if(actions[el.dataset.action])actions[el.dataset.action]();
});
document.addEventListener('change',event=>{if(event.target.id==='holding-sort'){state.sort=event.target.value;render()}});
document.addEventListener('submit',async event=>{
  if(event.target.id!=='schedule-form')return;
  event.preventDefault();
  const input=$('#check-time'),save=event.target.querySelector('[type="submit"]');
  save.disabled=true;
  try{
    await api('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({daily_time:input.value})});
    closeDialog();await refresh();showToast('每日检查时间已保存为 '+data.schedule.time);
  }catch(error){showToast(error.message);save.disabled=false}
});
$('#overlay').addEventListener('click',event=>{if(event.target===$('#overlay'))closeDialog()});
document.addEventListener('keydown',event=>{
  if($('#overlay').hidden)return;
  if(event.key==='Escape'){event.preventDefault();closeDialog()}
  if(event.key==='Tab'){
    const items=$$('button,a,input,select,summary',$('#dialog')).filter(el=>!el.disabled),first=items[0],last=items.at(-1);
    if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
    else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
  }
});
window.addEventListener('popstate',()=>{state.page=titles[location.hash.slice(1)]?location.hash.slice(1):'overview';closeDialog();render()});
$$('[data-icon]').forEach(el=>el.outerHTML=icon(el.dataset.icon));
refresh();
setInterval(()=>{if(!document.hidden)refresh()},30000);
