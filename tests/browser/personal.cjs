const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const {chromium}=require('playwright');
const {assertToolbarLayout}=require('./toolbar-layout.cjs');
const {startFixture,stopFixture}=require('./fixture.cjs');
let fixture,browser;
const layoutChecks=[];
(async()=>{
 await fs.mkdir('.browser-artifacts/personal',{recursive:true});
 fixture=await startFixture('tests/personal_browser_fixture.py');
 const base=fixture.url;
 browser=await chromium.launch({channel:process.env.SHM_BROWSER_CHANNEL||undefined});
 const context=await browser.newContext({viewport:{width:1440,height:1050}}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 assert.equal((await context.request.get(base+'/api/personal/account')).status(),401);
 assert.equal((await context.request.get(base+'/api/personal/account',{headers:{'X-Authenticated-User':'admin'}})).status(),401);
 await context.route('**/api/**',route=>route.continue({headers:{...route.request().headers(),'X-SHM-Gateway-Token':'fixture-gateway-token-32-characters',Origin:'https://shm.test'}}));
 for(const width of [1440,1024,768,390,320]) {
  await page.setViewportSize({width,height:1050});
  for(const route of ['ai-review','performance']) {
   await page.goto(base+'/#'+route);
   const toolbar=page.locator('#page-content > .personal-toolbar');
   await toolbar.waitFor();
   await toolbar.screenshot({path:`.browser-artifacts/personal/${route}-toolbar-${width}.png`});
   layoutChecks.push(await assertToolbarLayout(page,'#page-content > .personal-toolbar',route+' at '+width+'px'));
  }
 }
 await page.setViewportSize({width:1440,height:1050});
 await page.goto(base+'/#personal');
 await page.locator('[data-p=account]').click();
 const fill=(name,val)=>page.locator('#p-form [name='+name+']').fill(val);
 await fill('name','独立验收账户');await fill('at','2026-08-03T16:00:00-04:00');await fill('cash','90000');await fill('broker_nav','100000');
 await fill('symbol','MSFT');await fill('opening_quantity','100');await fill('opening_mark','100');await fill('opening_source','验收券商');
 await page.locator('[data-p=opening-add]').click();await page.locator('[data-p=save-account]').click();
 await page.locator('#p-overlay').waitFor({state:'hidden'});
 await page.locator('.p-desktop-positions [data-p=row-trade]').click();assert.equal(await page.locator('[name=symbol]').inputValue(),'MSFT');assert.equal(await page.locator('[name=action]').inputValue(),'SELL');
 await fill('at','2026-08-04T10:00:00-04:00');await fill('quantity','10');await fill('price','110');await fill('fee','1');
 await page.locator('[data-p=type][data-type=option]').click();assert.equal(await page.locator('[name=symbol]').inputValue(),'MSFT');await page.locator('[data-p=type][data-type=equity]').click();
 await page.locator('[data-p=close]').click();await page.locator('[data-p=trade]').click();assert.equal(await page.locator('[name=symbol]').inputValue(),'MSFT');assert.equal(await page.locator('[name=quantity]').inputValue(),'10');
 await page.locator('[name=action]').selectOption('SELL');await page.locator('[data-p=preview]').click();await page.locator('[data-p=commit]:not([disabled])').waitFor();
 assert.match(await page.locator('#p-summary').innerText(),/100 → -10 → 90/);
 await page.screenshot({path:'.browser-artifacts/personal/trade.png',fullPage:true});
 await page.locator('[data-p=commit]').click();await page.locator('#p-overlay').waitFor({state:'hidden'});await page.getByText('$91,099.00',{exact:true}).waitFor();
 await page.locator('[data-p=valuation]').click();await fill('at','2026-08-04T16:00:00-04:00');await fill('broker_nav','100999');await fill('mark_0','110');await fill('source_0','验收券商');await page.locator('[name=source]').selectOption('ledger');await page.locator('[name=flows_complete]').check();
 await page.locator('[data-p=preview-value]').click();await page.locator('[data-p=save-value]:not([disabled])').waitFor();assert.match(await page.locator('#p-summary').innerText(),/对账 一致/);await page.locator('[data-p=save-value]').click();await page.locator('#p-overlay').waitFor({state:'hidden'});
 await page.getByText('$100,999.00',{exact:true}).waitFor();await page.screenshot({path:'.browser-artifacts/personal/account.png',fullPage:true});
 await page.locator('[data-page=ai-settings]').click();await page.locator('[name=base_url]').fill('https://test.invalid/v1');await page.locator('[name=model]').fill('acceptance-model');await page.locator('[name=key]').fill('local-fake-key');await page.locator('[data-p=save-settings]').click();await page.locator('[data-p=test-ai]').click();await page.getByText('当前连接测试通过',{exact:true}).waitFor();
 await page.locator('[data-page=ai-review]').click();await page.locator('[data-p=new-report]').click();await fill('start','2026-08-01');await fill('end','2026-08-31');await page.locator('[data-p=create-report]').click();await page.locator('#p-overlay').waitFor({state:'hidden'});
 for(let n=0;n<12;n++){await page.waitForTimeout(2000);await page.locator('[data-p=refresh]').first().click();if(await page.getByText('个人账户复盘 · 区间或数据受限',{exact:true}).count())break;}
 await page.getByText('个人账户复盘 · 区间或数据受限',{exact:true}).waitFor();await page.screenshot({path:'.browser-artifacts/personal/report.png',fullPage:true});
 await page.locator('[data-page=ai-settings]').click();assert.equal(await page.locator('[name=model]').inputValue(),'acceptance-model');assert.equal(await page.locator('[name=key]').inputValue(),'');await page.locator('[name=model]').fill('model-changed');await page.locator('[data-p=save-settings]').click();await page.getByText('尚未通过当前连接测试',{exact:true}).waitFor();
 await page.locator('[data-page=personal]').click();await page.setViewportSize({width:390,height:844});await page.locator('.p-mobile-positions [data-p=row-trade]').waitFor();await page.screenshot({path:'.browser-artifacts/personal/mobile.png',fullPage:true});
 assert.equal(await page.evaluate(()=>localStorage.length),0);assert.deepEqual(errors,[]);
 const checks=['AI 复盘和资产表现：5 个宽度共 10 组控件边缘、等高、换行、遮挡和页面溢出检查','私人接口拒绝未认证和伪造标记','期初建账与持仓对账','MSFT 行操作、切换及关闭重开保留草稿','预览再提交与真实余额','每日估值来源和对账','AI 设置保存、密钥不回显、测试失效','独立报告作业闭环（替身模型）','手机直接操作持仓、旧菜单保留'];
 await fs.writeFile('.browser-artifacts/personal/acceptance.json',JSON.stringify({status:'PASS',checks,layoutChecks,errors},null,2));console.log(JSON.stringify({status:'PASS',checks}));
})().catch(e=>{console.error(e);process.exitCode=1}).finally(async()=>{
 if(browser)await browser.close();
 if(fixture){
  const cleanup=await stopFixture(fixture);
  await fs.writeFile('.browser-artifacts/personal/cleanup.json',JSON.stringify(cleanup,null,2));
  console.log('Fixture database, fake key and temporary files removed');
 }
}).catch(error=>{console.error(error);process.exitCode=1});
