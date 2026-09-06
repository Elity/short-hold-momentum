# STR / LSI / ALTR 身份与终止事件核对

2026-09-07；有界查询与本地归档核对。未修改主代码、主manifest或原始价格。

| 代码 | 作为原历史成员可保留的身份区间 | 需排除的归档 | 已确认终止权益 |
|---|---|---|---|
| STR | 2003-10-01 → 2016-09-16，3264行；Questar Corporation | 无2016后行情；ETF名称错误 | 2016-09-16，$25现金 + $0.07018 contingent dividend |
| LSI | 无；现有整段不能代表旧LSI Corporation | 2003-10-01 → 2018-03-07，3420行 | 真正旧LSI于2014-05-06转为每股$11.15现金；不能用错误行情算出的股份量结算 |
| ALTR | 2003-10-01 → 2015-12-24，3081行；Altera Corporation | 2018-03-01 → 2018-03-07，5行 | 2015-12-28，旧股每股$54现金 |

以上“可保留”指发行人身份区间得到佐证，不是每个日线值和所有公司行动均已通过审计。

## STR

- SEC 2015年10-K明确注册人为Questar Corporation（CIK 751652）。归档2014/2015八个季度的原始日内高低价，与SEC表中16个极值全部在分位舍入误差内匹配；因此不能因为wiki-stocks.csv叫ETF就删除这条真实Questar序列。
- 2016-09-16 8-K确认完成合并、旧股每股转换为$25现金，并请求NYSE在该日收盘后暂停交易。归档同日终止，最后raw close和adj close都是25.06。
- 2016-09-14双方联合公告另载：每天$0.00242，从8月19日至closing；若9月16日完成则合计$0.07018，record date为closing收盘，随后尽快支付。9月16日完成已经8-K确认，所以条件成立。
- 这笔尾部dividend不在归档的ex-dividend中。应识别总名义权益$25.07018；付款具体日未取得证据，应保留应收/付款时点限制，不擅自创建券商现金到账记录。
- 归档还保留2010-07-01的30.221293272371特殊分配调整，原始价从45.49降至15.22，而复权价连续。它提示Questar/QEP分拆应作为独立公司行动核验，不应把原始价断点直接当错误。

## LSI

- 真正LSI Corporation（CIK 703360）2013年第一季股价范围是6.51–7.66美元；本地LSI归档是60.29–67.44。2012/2013全部八季均不符，且高低价比例不是固定缩放。因此无法通过乘除一个常数修复这条旧LSI行情。
- 旧LSI的8-K确认2014-05-06被Avago收购，每股$11.15现金。归档2014-05-05却收于76.05，仍说明它不能用于旧LSI的持仓路径和终止结算。
- 2016-08-15 SEC发行人公告确认Sovran Self Storage（SSS）改名Life Storage并以LSI交易。该公告证实后来的ticker复用背景，但本次未取得足够季度原件来独立认定整条归档每个阶段究竟来自Sovran；无需等这一步完成即可拒绝把它当旧LSI。

## ALTR

- 旧Altera（CIK 768251）2014年10-K列出2013/2014八季的最高/最低收盘价。本地pre-2015段16个原始收盘极值全部在分位舍入误差内吻合；这里必须比较close极值，不能误拿日内high/low去比SEC的closing sale prices。
- 2015-12-28旧Altera的8-K确认合并完成并把每股转为$54现金。归档最后旧股bar为2015-12-24，close53.96；下一段竟直接跳到2018-03-01，间隔798天。
- Altair Engineering（另一CIK 1701732）的2018年10-K确认2017-11-01才首次以ALTR公开交易，之前没有公开市场。故2018五行绝不能拼到旧Altera；本次不把股票代码相同视作连续证券。

## 核对文件

- identity-action-segments.json：逐段结论、名义对价、生效日、付款时点限制、原始文件哈希。
- quarter-price-comparison.csv：24个季度的SEC与归档极值对照。
- *.excerpt.txt：关键SEC段落及直接URL。
- *.source.json / *.search.json：工具取回的原始证据；无关搜索结果不作为结论依据。

## 主要来源

- str_merger: https://www.sec.gov/Archives/edgar/data/751652/000119312516712322/d258533d8k.htm
- str_dividend: https://www.sec.gov/Archives/edgar/data/751652/000075165216000424/exhibit99jointpressrelease.htm
- lsi_merger: https://www.sec.gov/Archives/edgar/data/703360/000119312514185188/d723241d8k.htm
- altr_merger: https://www.sec.gov/Archives/edgar/data/768251/000119312515414631/d102231d8k.htm
- life_storage_rename: https://www.sec.gov/Archives/edgar/data/1060224/000119312516681926/d243423dex991.htm
- str_quarters: https://www.sec.gov/Archives/edgar/data/68589/000075165216000260/str12311510k.htm
- lsi_quarters: https://www.sec.gov/Archives/edgar/data/703360/000119312514069522/d628854d10k.htm
- altr_quarters: https://www.sec.gov/Archives/edgar/data/768251/000076825115000008/altera10k12312014.htm
- altair_new_issuer: https://www.sec.gov/Archives/edgar/data/1701732/000156459019005799/altr-10k_20181231.htm
