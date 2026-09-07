# TWTR 主源核对：身份、上市与收购边界

新增请求 **4/4**，均为搜索；已保存每次完整工具响应。使用的是搜索服务返回的原始 SEC 文件文本/索引，没有额外直接抓取，也没有重新下载 TWTR 行情样本。此包不改主仓库，不生成或修改候选 Parquet。

## 可用条款及证据范围

|字段|结论|证据与限制|
|---|---|---|
|原始发行人|Twitter, Inc.，Delaware，**CIK 0001418091**|2013 发行人 10-K、2021 10-K SEC headers、2022 closing 8-K 一致。|
|上市股类|**Common Stock**；每股面值 $0.000005；NYSE:TWTR；CUSIP **90184L102**|2013 10-K、2022 8-K 注册证券表；CUSIP 来自 Musk 的 SEC 13D/A。不要自行改名为 Class A。|
|实际首个交易日|**2013-11-07**|2013 10-K 明称 “which was the initial trading date on the New York Stock Exchange”；并非仅引用 IPO 预计日期或股票交割日期。|
|合并完成日期|**2022-10-27**|2022 closing 8-K Introductory Note / Item 2.01。|
|首个不可交易会话|**2022-10-28，NYSE 开盘前停牌**|发行人 8-K Item 3.01 与 Dorsey 的 SEC 13D 相互支持。发行人搜索提取文本在 “was ... prior” 之间缺失动词；已原样保存。Dorsey 13D 完整原句为 “was suspended prior to the opening of the NYSE on October 28, 2022”，并带有 “Reporting Person understands” 的限定。此次没有取得独立 NYSE 交易所公告。|
|最后实际交易日|**2022-10-27 为边界推定；需与本地当日真实报价共同确认**|已读主源没有直写 “last trading day October 27”。10/28 开盘前停牌支持其前一会话是末个可交易候选；不单凭合并完成日或成员退出日宣称实际交易发生。`last_trading_date_primary_explicit` 保留 null。|
|默认每旧股现金|**$54.20，现金，不计利息**|2022 closing 8-K。旧普通股取消并转换为此现金权利；默认无后继股票。公司/子公司、Musk/Parent/Acquisition Sub 持股及依法行使异议估价权等例外排除。内幕持股的单独 rollover 不适用于普通模型持有人。|
|实际现金到账日|未证实|本包不把法律完成日当券商到账日；既定研究现金时点应由主任务依 ADR014 处理。|
|2013-11-07 至 2022-10-27 无普通现金分红|**未证实**|此次取得的 2013 文本被截断，2021 10-K 只得到正文标题与索引/headers；没有读到足以支持全期间的 Dividend Policy 或行动表。|
|同期间无拆股|**未证实**|未取得主源完整拆股/资本行动序列；不能由缺少搜索命中、OHLC 一致或 adjusted close 等于 close 推断全期间无拆股。|

2018 后所需发行人身份可固定为 Twitter, Inc. / CIK 0001418091，但本包不证明任一二级供应商文件的逐日身份、价量单位、全市场成交量口径或复权计算。无股息/无拆股字段均保留 null，不能将本包用作全期间 factor=1 的依据。

## 请求账本

|编号|请求文件|实际结果|
|---|---|---|
|1|`01-closing-search.json`|原 SEC closing 8-K、对应索引、Musk/Dorsey 13D 等；用于身份、现金对价、完成和停牌边界。|
|2|`02-ipo-dividend-search.json`|2013 10-K 明确实际首个交易日，另有招股书等截断内容；未取得完整股息披露。|
|3|`03-dividend-latest-search.json`|返回其他发行人，尽管查询含 TWTR CIK 路径；全部排除，失败仍计一次请求。|
|4|`04-annual-dividend-search.json`|找到 2021 10-K 的正确索引、headers、文件 URL；正文摘要仅 “twtr-20211231...”，只能用 headers 核实 CIK，不能声称已读正文股息或拆股条款。|

完整精确引文、URL 与可机读字段在 `primary-excerpts-and-terms.json`。以下链接均来自上述四次结果，未另发请求：

- 2013 10-K：<https://www.sec.gov/Archives/edgar/data/1418091/000095012314003031/twtr-10k_20131231.htm>
- 2022 closing 8-K：<https://www.sec.gov/Archives/edgar/data/1418091/000119312522272772/d411753d8k.htm>
- Dorsey 13D：<https://www.sec.gov/Archives/edgar/data/1590945/000119312522274034/d393652dsc13d.htm>
- Musk 13D/A：<https://www.sec.gov/Archives/edgar/data/1418091/000110465922113051/tm2229215d1_sc13da.htm>
- 2021 10-K SEC headers：<https://www.sec.gov/Archives/edgar/data/1418091/000141809122000029/0001418091-22-000029-index-headers.html>
- 2021 10-K 正文（已发现，未读取完整内容）：<https://www.sec.gov/Archives/edgar/data/1418091/000141809122000029/twtr-20211231.htm>
