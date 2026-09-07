# SHM 历史价格补救调查

本次只调查数据来源与证券身份，没有修改 SHM 源码或行情缓存，也没有放宽质量门槛。

274 个缺失历史 ticker 中，列出 35 个映射假设，23 个有本地候选缓存。15 个改名映射已有发行人、SEC 或交易所材料支持；CTL→LUMN 目前仅取得二手材料。

15 个身份已有一手材料支持的映射，按旧审计日历估计最多增加 1.7073 个覆盖率百分点；把全部 23 个本地候选都假设可用，也只有 2.5027 个百分点。这个估计没有完成行情连续性、复权、预热期验证，也不能与 WIKI 贡献直接相加。

证券改名证据只证明身份关系，不证明当前缓存的历史行情正确。尤其不能将合并后的新公司历史图表直接赋给旧证券。

| 旧 ticker | 本地候选 | 改名生效日 | 估计覆盖率增量（百分点） | 证据 |
|---|---|---|---:|---|
| BK | BNY | 2026-05-21 | 0.1982 | [来源](https://www.nasdaq.com/press-release/bny-announces-planned-change-stock-ticker-symbol-bny-2026-05-11) |
| MMC | MRSH | 2026-01-14 | 0.1952 | [来源](https://www.marsh.com/en/corp/about/news/marsh-mclennan-to-change-nyse-symbol-to-mrsh.html) |
| ABC | COR | 2023-08-30 | 0.1732 | [来源](https://investor.amerisourcebergen.com/news/news-details/2023/AmerisourceBergen-becomes-Cencora-in-alignment-with-the-companys-growing-global-footprint-and-central-role-in-pharmaceutical-access-and-care/default.aspx?code=c10cSuWwd&aff_unique2=c10cSuWwd) |
| PKI | RVTY | 2023-05-16 | 0.1710 | [来源](https://ir.revvity.com/news/investor-news/news-details/2023/Launching-Revvity-A-Scientific-Solutions-Company-Powering-Innovation-from-Discovery-to-Cure/default.aspx) |
| ANTM | ELV | 2022-06-28 | 0.1630 | [来源](https://www.sec.gov/Archives/edgar/data/1156039/000119312522183957/d359422d8k.htm) |
| BLL | BALL | 2022-05-10 | 0.1615 | [来源](https://investors.ball.com/news-presentations/press-releases/detail/82/ball-board-declares-quarterly-dividend-stock-ticker-symbol-changing-to-ball) |
| SYMC | GEN | 2019-11-05 | 0.1381 | [来源](https://investor.gendigital.com/news/news-details/2022/Introducing-Gen-The-Company-to-Power-Digital-Freedom/default.aspx) |
| TMK | GL | 2019-08-09 | 0.1359 | [来源](https://investors.globelifeinsurance.com/news-releases/2019/august/torchmark-corporation-has-officially-been-renamed-globe-life-inc?accessibility=true) |
| JEC | J | 2019-12-10 | 0.1121 | [来源](https://www.sec.gov/Archives/edgar/data/52988/000005298819000066/tickerchangeandcnbcrel.htm) |
| RE | EG | 2023-07-10 | 0.0556 | [来源](https://www.everestglobal.com/gb-en/news-media/press-releases/2023/everest-to-rebrand-company-name-and-nyse-ticker) |
| WLTW | WTW | 2022-01-10 | 0.0555 | [来源](https://investors.wtwco.com/news-releases/news-release-details/willis-towers-watson-announces-nasdaq-ticker-symbol-change-wltw) |
| FLT | CPAY | 2024-03-25 | 0.0527 | [来源](https://www.corpay.com/corporate-newsroom/17651/fleetcor-announces-rebranding-to-corpay) |
| KORS | CPRI | 2019-01-02 | 0.0448 | [来源](https://www.sec.gov/Archives/edgar/data/1530721/000119312518362322/d653406dex991.htm) |
| NLOK | GEN | 2022-11-08 | 0.0278 | [来源](https://investor.gendigital.com/news/news-details/2022/Introducing-Gen-The-Company-to-Power-Digital-Freedom/default.aspx) |
| FI | FISV | 2025-11-11 | 0.0227 | [来源](https://investors.fiserv.com/news-releases/news-release-details/fiserv-announces-transfer-stock-exchange-listing-nasdaq) |

SYMC→NLOK→GEN 需要特别核查资产出售、特别股息与 Avast 合并；WLTW、J、FISV 等也不能因为后来的改名得到确认，就默认更早的并购或分拆历史正确。

MYL→VTRS、UTX→RTX、DISCA→WBD、HCP/PEAK→DOC、HRS→LHX、RX→IQV 保留为身份或公司行动尚未解决的假设；RX→IQV 对当前缺失观察日没有可用覆盖贡献。

## TIE：污染已证实，完整替代数据仍未取得

NYSE:TIE 是 Titanium Metals Corporation（CIK 1011657）。原缓存 2010-02-19 收盘 $12.06，下一交易日 2010-02-22 跳至 $22,900；同期 Investing 可见收盘为 $12.21。不能据此断言污染片段属于哪一家海外公司。

[SEC 2010 年报](https://www.sec.gov/Archives/edgar/data/1011657/000119312511049208/d10k.htm)给出的 2010 四季度高低价分别为 17.39/10.54、21.29/13.80、22.93/16.87、21.10/16.60，2011-02-18 收盘为 $20.14。年报还说明 2008 年每股普通股股息 $0.30、2009 年 2 月暂停季度普通股股息；这些材料不足以重建完整日线与复权因子。

[SEC 收购公告](https://www.sec.gov/Archives/edgar/data/79958/000119312513006827/d464033dex992.htm)确认 2013-01-07 完成现金合并，剩余每股普通股换取 $16.50，随后不再在 NYSE 交易。原缓存延续至 2018，以及某些网站把 $16.50 零量记录重复到 2026 的做法，都不能作为正常日线使用。

通过 Investing 正常日期筛选，申请 2003-10-01 至 2013-01-07，仅得到 2009-07-23 至 2013-01-07 的 867 条可见记录：194 条缺量、4 个交易日缺失、21 条 OHLC 关系矛盾，2010 季度极值与 SEC 不一致，复权/总回报口径不明。该表只能作交叉核验证据，不能作为完整替代数据。

不可把缺量填零、人工造高低价、删掉缺日，或把收购后的静态价格当作交易数据来过门槛。

## 后续接入要求

1. 优先处理 WIKI 中可核实身份的原 ticker 历史，保留原始 OHLC、股息、拆股及来源截止日。WIKI 的下载、覆盖与重叠检查由主任务处理，本调查不重复下载。
2. 对这 15 个改名候选，核查重叠期收益序列、拆股和分红调整，按有效日期建立证券身份映射；保留缓存哈希，不直接改写 ticker 含义。
3. TIE 保持缺失/污染状态，直到取得足够日线和公司行动材料。若研究采用更窄历史区间或剔除证券，应作为另一个明确的研究样本，披露其偏差。
4. 在接入后重新计算 PIT 覆盖率、价量资格及异常跳变门槛；本报告的覆盖增量只是调查优先级，不代表回测已通过。

## 文件

- remediation-manifest.json：所有映射的身份状态、证据链接、缓存哈希、TIE 审计。
- rename-evidence-priority.csv：按覆盖贡献排列的映射调查状态。
- missing-priority.csv：原 274 个缺失证券及覆盖贡献。
- TIE-investing-visible.tsv / TIE-investing-visible-parsed.csv：原始可见表及解析表。
- TIE-investing-coverage.json：缺失与一致性检查。
- TIE-2010-10k-source.txt：SEC 年报提取文本（截取长度已披露）。
- search-evidence-initial.json / search-evidence-targeted.json：搜索所得材料与 URL。
