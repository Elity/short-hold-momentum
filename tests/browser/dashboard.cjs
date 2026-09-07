const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {startFixture,stopFixture} = require('./fixture.cjs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const artifacts = process.env.SHM_BROWSER_ARTIFACTS || '.browser-artifacts';
const checks = [];
const money = n => n == null ? '—' : '$' + n.toLocaleString('en-US', {minimumFractionDigits:2,maximumFractionDigits:2});
let fixture, browser, context, page, base, originalTime, restoreSettings = false;
const errors = [];
async function readDashboard() {
  const response = await context.request.get(base + '/api/dashboard');
  assert.equal(response.status(), 200);
  return response.json();
}
async function nav(route) {
  await page.locator('#main-nav [data-page="'+route+'"]').click();
  await page.locator('#main-nav [data-page="'+route+'"][aria-current="page"]').waitFor();
}
async function close() {
  await page.keyboard.press('Escape');
  await page.locator('#overlay').waitFor({state:'hidden'});
}
async function screenshot(name) {
  await page.screenshot({path:path.join(artifacts,name+'.png'),fullPage:true,animations:'disabled'});
}
(async () => {
  await fs.mkdir(artifacts,{recursive:true});
  base = process.env.SHM_BROWSER_URL;
  if (!base) {
    fixture = await startFixture('tests/browser_fixture.py');
    base = fixture.url;
  }
  base=base.replace(/\/$/,'');
  browser=await chromium.launch({headless:process.env.SHM_BROWSER_HEADED!=='1',channel:process.env.SHM_BROWSER_CHANNEL||undefined});
  context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
  page=await context.newPage();
  page.on('pageerror',error=>errors.push(error.message));
  page.on('response',response=>{if(response.status()>=500)errors.push('HTTP '+response.status()+' '+response.url())});
  const expected=await readDashboard();
  originalTime=expected.schedule.time;
  await page.goto(base);
  await page.locator('.metric-value').first().waitFor();
  assert.equal(await page.locator('.metric-value').first().innerText(),money(expected.account.total));
  assert.equal(await page.locator('.scenario').count(),0);
  assert.doesNotMatch(await page.locator('body').innerText(),/示例账户|原型演示/);
  checks.push('真实 API 与总资产显示一致，无演示账户');
  await screenshot('overview');
  await page.locator('[data-chart="return"]').click();
  assert.match(await page.locator('#equity-svg').textContent(),/%/);
  await page.locator('[data-chart="assets"]').click();
  await page.locator('#chart-hit').hover();
  assert.equal(await page.locator('#chart-tip').evaluate(el=>getComputedStyle(el).opacity),'1');
  checks.push('资产/收益图表切换与日期提示');
  await nav('holdings');
  if (expected.holdings.length) {
    assert.equal(await page.locator('#page-content tbody tr').count(),expected.holdings.length);
    const holding=expected.holdings.find(h=>h.pnl<0)||expected.holdings[0];
    await page.locator('[data-holding="'+holding.symbol+'"]').first().click();
    await page.locator('#dialog-title').waitFor();
    assert.match(await page.locator('#dialog').innerText(),/成本均价/);
    await close();
    await page.locator('#holding-sort').selectOption('pnl');
  } else {
    assert.match(await page.locator('#page-content').innerText(),/资金尚未建仓/);
  }
  checks.push('持仓明细、排序或真实空仓状态');
  await screenshot('holdings');
  await nav('trades');
  const sells=expected.trades.filter(t=>t.side==='sell');
  await page.locator('[data-trade-filter="sell"]').click();
  assert.equal(await page.locator('#page-content tbody tr').count(),sells.length);
  if(sells.length) {
    await page.locator('[data-trade="'+sells[0].id+'"]').first().click();
    assert.match(await page.locator('#dialog').innerText(),/已实现盈亏/);
    await close();
    const pending=page.waitForEvent('download');
    await page.locator('[data-action="export"]').click();
    const download=await pending;
    await download.saveAs(path.join(artifacts,'trades.csv'));
    const csv=await fs.readFile(path.join(artifacts,'trades.csv'),'utf8');
    assert.equal(csv.split('\r\n').length,sells.length+1);
  }
  await page.locator('[data-action="tickets"]').click();
  assert.match(await page.locator('#dialog').innerText(),/调仓计划/);
  await close();
  checks.push(sells.length?'成交筛选、已实现盈亏、调仓计划与 CSV 导出':'真实空成交状态与调仓单入口；成交明细和导出由隔离账户用例覆盖');
  await nav('logs');
  assert.equal(await page.locator('#page-content tbody tr').count(),expected.runs.length);
  assert.doesNotMatch(await page.locator('#page-content').innerText(),/paper status:|gate_ready=/);
  await screenshot('logs');
  for(const status of ['failed','success']) {
    await page.locator('[data-log-filter="'+status+'"]').click();
    const run=expected.runs.find(r=>r.status===status);
    if(run) {
      await page.locator('[data-run="'+run.id+'"]').first().click();
      await page.getByRole('heading',{name:'真实运行步骤',exact:true}).waitFor();
      const response=await context.request.get(base+'/api/runs/'+run.id);
      const detail=await response.json();
      assert.equal(await page.locator('#dialog details').count(),detail.steps.length);
      if(detail.steps.length) {
        await page.locator('#dialog details').first().evaluate(el=>el.open=true);
        assert.ok((await page.locator('#dialog pre').first().innerText()).length);
      }
      assert.notEqual(await page.evaluate(()=>window.__log_xss),true);
      await screenshot('run-'+status);
      await close();
    }
  }
  checks.push('真实成功/失败日志、步骤数量与输出，HTML 文本安全展示');
  await nav('reports');
  for (const report of expected.reports.slice(0,2)) {
    await page.locator('[data-report="'+report.id+'"]').click();
    await page.locator('#dialog .dialog-body').waitFor();
    assert.ok((await page.locator('#dialog .dialog-body').innerText()).length>20);
    assert.notEqual(await page.evaluate(()=>window.__report_xss),true);
    await screenshot(report.kind+'-report');
    await close();
  }
  if(!expected.reports.length)assert.match(await page.locator('#page-content').innerText(),/尚无策略报告/);
  checks.push('已有报告正文或尚未生成状态');
  await page.locator('#strategy-select').selectOption('C3');
  await page.waitForFunction(()=>document.querySelector('#cost-select'));
  assert.match(await page.locator('.strategy-bar').innerText(),/模型成本|前向/);
  await page.locator('#cost-select').selectOption('25');
  await page.waitForFunction(()=>document.querySelector('.strategy-bar').textContent.includes('单边 25 bps'));
  const candidateResponse=await context.request.get(base+'/api/dashboard?strategy_id=C3&cost_bps=25');
  const candidate=await candidateResponse.json();
  await nav('overview');
  assert.equal(await page.locator('.metric-value').first().innerText(),money(candidate.account.total));
  if(candidate.strategy.performance_verdict==='NOT_STARTED'){
    assert.equal(candidate.trades.length,0);
    assert.equal(candidate.account.total,null);
    assert.match(await page.locator('body').innerText(),/尚未启动|尚未建立/);
  }
  assert.match(await page.locator('.historical-panel').innerText(),/历史筛选/);
  await screenshot('v03-strategy');
  await page.locator('#strategy-select').selectOption('S500-C3');
  await page.locator('.universe-panel').waitFor();
  const sourceResponse=await context.request.get(base+'/api/dashboard?strategy_id=S500-C3&cost_bps=25');
  const sourceDashboard=await sourceResponse.json();
  if(sourceDashboard.strategy.account_mode==='observation'){
    assert.match(await page.locator('.strategy-bar').innerText(),/观察模拟 · 未经历史验收/);
    assert.equal(sourceDashboard.account.total,100000);
    assert.equal(sourceDashboard.strategy.historical_screen.winner,null);
    checks.push('观察账户显示真实初始资金，明确未经历史验收且不伪造胜者');
  }
  assert.match(await page.locator('.universe-panel').innerText(),/来源日期|核验交易日|证券|家公司/);
  assert.ok((await page.locator('.universe-panel').innerText()).includes(String(sourceDashboard.universe.security_count)));
  assert.equal(await page.locator('.source-links a').count(),sourceDashboard.universe.source_urls.length);
  assert.equal(await page.locator('.metric-value').first().innerText(),money(sourceDashboard.account.total));
  const historical=sourceDashboard.strategy.historical_screen;
  if(historical?.metrics_valid===false){
    assert.match(await page.locator('.historical-panel').innerText(),/数据未通过|不可用/);
    const cells=await page.locator('.history-table tbody .num').allTextContents();
    assert.ok(cells.every(value=>value==='— / —'),'invalid historical and benchmark returns must be hidden');
  }
  for(const width of [390,320]){
    await page.setViewportSize({width,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width,'S&P 500 source panel overflow');
  }
  await page.setViewportSize({width:1440,height:1000});
  await screenshot('sp500-source');
  checks.push('S&P 500来源日期、核验、证券数、来源链接及风险闸门；无效历史收益和基准指标隐藏');
  await page.locator('#strategy-select').selectOption('V04');
  await page.waitForFunction(()=>!document.querySelector('#cost-select'));
  assert.equal(await page.locator('.metric-value').first().innerText(),money(expected.account.total));
  await nav('reports');
  checks.push('策略版本与10/25bps模型账本切换，前向与历史筛选分开，V04原账目保持');
  if(!process.env.SHM_BROWSER_URL||process.env.SHM_TEST_SETTINGS==='1') {
    restoreSettings=true;
    const changed=originalTime==='05:31'?'05:32':'05:31';
    await page.locator('.page-actions [data-action="schedule"]').click();
    await page.locator('#check-time').fill(changed);
    await page.locator('#schedule-form [type="submit"]').click();
    await page.locator('#overlay').waitFor({state:'hidden'});
    await page.reload();
    await page.locator('.page-actions [data-action="schedule"]').waitFor();
    await page.locator('.page-actions [data-action="schedule"]').click();
    assert.equal(await page.locator('#check-time').inputValue(),changed);
    await page.locator('#check-time').fill(originalTime);
    await page.locator('#schedule-form [type="submit"]').click();
    await page.locator('#overlay').waitFor({state:'hidden'});
    assert.equal((await readDashboard()).schedule.time,originalTime);
    restoreSettings=false;
    checks.push('设置保存、刷新后持久化及恢复原时间 '+originalTime);
  }
  for(const width of [390,320]) {
    await page.setViewportSize({width,height:844});
    for(const route of ['overview','holdings','trades','logs','reports']) {
      await nav(route);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width,route+' overflow');
    }
  }
  await page.setViewportSize({width:390,height:844});await nav('overview');
  await screenshot('mobile');
  assert.deepEqual(errors,[]);
  checks.push('390/320 像素全部页面无横向溢出，无浏览器异常');
  const result={status:'PASS',url:base,completed_at:new Date().toISOString(),checks,account:expected.account,
    holdings:expected.holdings.length,trades:expected.trades.length,runs:expected.runs.length,reports:expected.reports.length};
  await fs.writeFile(path.join(artifacts,'acceptance.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify(result,null,2));
})().catch(async error => {
  console.error(error);
  if(page)await screenshot('failure').catch(()=>{});
  process.exitCode=1;
}).finally(async()=>{
  if(restoreSettings&&context) {
    const response=await context.request.post(base+'/api/settings',{data:{daily_time:originalTime}});
    if(!response.ok()){console.error('Could not restore original schedule');process.exitCode=1}
  }
  if(browser)await browser.close();
  if(fixture) {
    const cleanup=await stopFixture(fixture);
    await fs.writeFile(path.join(artifacts,'cleanup.json'),JSON.stringify(cleanup,null,2));
    console.log('Legacy fixture database and temporary files removed');
  }
}).catch(error=>{console.error(error);process.exitCode=1});
