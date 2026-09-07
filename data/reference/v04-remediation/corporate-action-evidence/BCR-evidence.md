# BCR：C. R. Bard终止权益、缺失日线与末笔普通分红

核查日：2026-09-07。仅在work目录生成候选数据和登记提案，未修改仓库或冻结源码。

## 身份、并购与交易日

WIKI代码BCR名称为Bard；原发行人SEC文件确认C. R. Bard, Inc.，CIK 9892，NYSE:BCR。不是BDX自身，也不与同名基金拼接。

原Bard 2017-12-29 Form 8-K的Introductory Note及Item 3.01/3.03确认，每股旧Bard普通股消灭并转换为222.93美元现金和0.5077股BD普通股；BD的自身8-K独立给出同一条款。NYSE递交SEC的退市通知明确合并于2017-12-29生效，证券于2017-12-29停止交易。其2018-01-09登记摘牌日期不应误作最后交易日。

WIKI实际最后一行2017-12-28：O333.49/H334.03/L331.24/C331.24；原始与复权相同。其后没有污染尾部需要删除。建议last_trading_session=2017-12-28，effective_session=2017-12-29。4月23日协议、4月24日SEC披露均见原Bard最终8-K交叉引用，登记announced_date采用可核验的4月24日披露日。

主要来源：

- 原Bard 8-K：https://www.sec.gov/Archives/edgar/data/9892/000119312517383532/0001193125-17-383532.txt （BCR-sec-closing.txt）
- NYSE退市通知：https://www.sec.gov/Archives/edgar/data/9892/000087666117000815/ruleprovisionnotice.htm （BCR-nyse-removal.txt）
- BD 8-K：https://investors.bd.com/sec-filings/all-sec-filings/content/0001193125-17-383523/d517273d8k.htm （BCR-bd-closing.txt）

现金按已确定的ADR-014于有效交易日之后第5个XNYS交易日2018-01-08释放；这是模型，不是实测券商到账。换股小数在研究中保留；没有取得普通股适用的零股出售价格，因此cash_in_lieu_price不填造数值。

## 2017-11-08日线补充

通过Investing.com的正常网页日期筛选读取2017-11-01至11-15表格，NYSE美元报价显示11月8日O334.05/H334.21/L333.08/C334.08、成交量635.56K。原始记录和邻日保存于BCR-investing-visible-prices.csv，步骤与精度保存于BCR-investing-provenance.json。

按照已确认的使用范围，volume登记635560，明确它是来源舍入值，显示分辨率10股，绝非已核验的精确逐股成交量。邻日OHLC在显示精度内吻合WIKI；不同供应商的成交量仍有差异，因此不覆盖任何已有WIKI成交量，仅补缺失日。as_traded_close=334.08；dollar_volume=334.08×635560，保留同样的量值精度限制。

已有Cam Nugent/IEX归档没有BCR；既有GitHub stock-data来源也没有bcr.csv，未调用Yahoo、未绕过共享下载预算。

## 最后0.26美元普通分红没有被WIKI计入

当时Nasdaq刊载的BNK Invest/DividendChannel报道明确Bard季度分红0.26美元，record date为2017-12-08、pay date为2017-12-29。StreetInsider、DividendHistory和Investing AU一致给出ex-date=2017-12-07；StreetInsider列宣告日2017-10-11。Investing美国/英国文本曾显示前一日，但其AU本地版、另两份资料和T+2后的日期规则一致；不采用这一日期偏移。

- 当时报导：https://www.nasdaq.com/articles/daily-dividend-report-bcr-xyl-eqt-mms-tex-itt-2017-10-12 （BCR-contemporary-dividend-report.txt）
- 日期交叉检查：https://dividendhistory.org/payout/BCR/ （BCR-dividend-history-secondary.txt）
- https://www.streetinsider.com/dividend_history.php?q=BCR
- https://au.investing.com/equities/c-r-bard-dividends

证据边界：有界搜索未恢复发行人原始10月11日分红公告；以上分红条款来自当时报导和一致的后续日期表。已直接取得原Bard2017Q3 SEC原文，但其只确认前九个月0.78美元，不包含这一笔，故不把该季报冒充末笔分红来源。

归档2017-12-07的ex-dividend=0，7月20日之后adj_close/raw_close始终为1。因此12月分红并未通过复权变化计入。BCR已记录的4月27日、7月20日分红分别验证WIKI公式为P_ex/(P_ex+D)，误差小于1e-12，不能使用1-D/P_prev近似。

12月7日原价332.07、D=0.26，修复乘子为332.07/332.33=0.9992176451117865。对12月7日以前的adjusted OHLC整体再乘此值，保留原始close、volume、dollar_volume不变；12月7日及之后不再乘。该方法使ex-day的复权日收益精确等于(P_ex+D)/P_prev-1，也正确区分分红前持有者与后来买入者。新补11月8日同样位于修复区间。

这笔0.26美元一旦修入总回报日线，合并现金仍为222.93，不可改成223.19，否则会重复记收益并把普通股息错误发给除息后买入的人。

audit_and_propose_bcr.py可复现并固定输入/输出SHA256、邻日核对和除息收益恒等式。输出BCR.repaired-candidate.parquet、BCR-price-audit.json、BCR-manifest-proposal.json供root核准登记。其证据范围不等于对全部WIKI历史行情的全面认证。
