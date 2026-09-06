# RSHCQ研究键与旧RadioShack普通股：有限身份核验

**结论：有足够的发行人、交易所及当时交易方证据，把研究键RSHCQ识别为旧RadioShack Corporation普通股这一历史身份，并以WIKI RSH继续审阅2003-12-19—2011-07-11的有限候选。不能把后来使用RadioShack品牌的General Wireless新公司当作这只旧股。** 本次没有应用价格、修改成员表或建立Live全局alias；七笔源股息也没有被全部升级为主证已核实。

新公开请求 **4/4**，均为有记录的Search API调用，无额外浏览、重试或行情查询。已到上限，后续只整理返回的本地材料。文件和原始返回保存于本目录，来源URL、文本hash及等级见 `source-index.json`；这是索引返回的来源文本，不声称另下载了完整SEC原始HTML或PDF。

## 旧普通股身份和ticker沿革

| 事实 | 已取得证据 | 范围/等级 |
|---|---|---|
| 旧发行人为 **RadioShack Corporation，CIK 0000096289** | [2010 SEC10-K](https://www.sec.gov/Archives/edgar/data/96289/000009628911000010/form10k123110.htm)封面：Delaware，注册文件1-5571，NYSE普通股，**每股面值$1**；Item5明确ticker **RSH** | 发行人SEC申报内容，经搜索索引取得 |
| RSH在NYSE的最后会话为2015-02-02 | [SEC 2015-02-06 8-K](https://www.sec.gov/Archives/edgar/data/96289/000009628915000007/form8k020615.htm)明确“Trading was suspended immediately after the close on February 2, 2015”；[NYSE自身公告](https://ir.theice.com/press/news-details/2015/NYSE-to-Suspend-Trading-Immediately-in-RadioShack-Corporation-and-Commence-Delisting-Proceedings/default.aspx)明确旧RadioShack common stock、RSH | SEC与交易所主文 |
| **RSH→RSHC** 的underlying生效日为 **2015-02-03** | [OCC #36153，MIAX托管](https://www.miaxglobal.com/sites/default/files/alert-files/RSH_Symbol_Change_36153.pdf)：因转到OTC改代码；交付仍为100股RadioShack common shares，**CUSIP750438103**，其他条款不变 | 交易所托管OCC文件。这里只用普通股身份信息，不用期权结算价模拟普通股现金 |
| RSHC的期权根代码改名日为2015-02-04 | 同一OCC文件明确区分underlying 2月3日与option 2月4日 | 不能把期权生效日误写成股票代码生效日 |
| **RSHCQ确实用于旧RadioShack Corporation卖方** | [2015-06-23 Hilco通稿](https://www.marketscreener.com/news/latest/RadioShack-Intellectual-Property-Sells-For-Over-26MM-20582529/)明确“RadioShack Corporation (OTCMKTS: RSHCQ)”并说明处置该公司的无形资产；另[MarketBeat历史资料](https://www.marketbeat.com/stocks/OTCMKTS/RSHCQ/)列出Previous Symbol NYSE:RSH、CIK96289 | 当时处置顾问的GlobeNewswire通稿转载＋二级代码/CIK交叉核对；不把二级资料升级为SEC主文 |

**本轮未取得RSHC→RSHCQ的精确生效日或对应原始代码变更通知，因此该日期保持空缺。** 只能确认RSHCQ至迟已见于2015-06-23的当时交易方通稿；不猜2015年某个具体交易日。

这不要求把2015年代码名称倒写成2004年的实际挂牌代码：`RSHCQ`在这里是研究稳定键，有限窗口内实际使用的历史上市代码是 **RSH**。`identity-findings.json`明确保存此区别，仅供有限研究身份引用，不是可执行的全局alias配置。

## 旧股和后来品牌/资产买方必须分开

Hilco通稿将旧 **RadioShack Corporation (RSHCQ)** 列为资产处置对象，将 **General Wireless Operations Inc.** 列为品牌/无形资产买方，成交价$26.2m、品牌资产出售于2015-06-19完成。

[买方2015-07-01公告](https://www.prnewswire.com/news-releases/general-wireless-acquires-the-radioshack-brand-300107296.html)直接说：

> “General Wireless Operations Inc., doing business as RadioShack … closed on a $26.2 million purchase of the RadioShack brand … a new and reinvigorated company.”

已取得的[资产购买协议镜像](https://contracts.justia.com/companies/radioshack-corp-28376/contract/455134/)也把 **General Wireless Inc.**列作Buyer，把 **RadioShack Corporation及子公司**列作Sellers。协议与品牌成交公告出现的是不同层面的买方法人名称，本报告不把这些买方实体自行合并；它们均不能仅因购买旧品牌而成为原RSH普通股的连续行情。

上述是资产/品牌出售证据，**不是旧普通股换入新公司股份的证据，也不是每股旧股应收$26.2m的股东分配**。本轮没有取得或推定旧股取消日期、股东回收金额、新股交换比例。有限价格窗口早在2011年结束，无需先研究2015年的破产现金结算；以后任何新公司/新股都保持在本映射之外。

## 有限年报对现金和名义单位的支持

取得的2010 SEC10-K索引文本约130,000字符，包含封面、Item5及Item6等，但不是完整原始年报下载；不会声称已经读完未返回的全部财务附注。

**现金：** Item6的Selected Financial Data（原文标为UNAUDITED）列示2006、2007、2008、2009、2010各年 **Dividends declared per share均为$0.25**。这是发行人报告的年度声明总额，不能单凭它推定每个具体ex-date或每年只有一笔付款。Item5进一步列出2009、2010的季度声明总额均集中在第四季度$0.25，其余三个季度为0。

2010年的单笔有更明确的主文及[发行人公告](https://www.prnewswire.com/news-releases/radioshack-corporation-declares-dividend-106915723.html)：董事会 **2010-11-04** 声明年度现金股息 **$0.25/普通股**，record **2010-11-26**，并在 **2010-12-16**支付。11月8日是该新闻稿的发布日期，不另算一笔股息，也不替代11月4日董事会声明日。

| WIKI已观察ex-date | 原现金字段 | 本轮独立主文支持到的程度 |
|---|---:|---|
| 2004-11-29 | 0.25 | **2004金额主文尚未取得**；不从后年费率回推 |
| 2005-11-29 | 0.25 | **2005金额主文尚未取得** |
| 2006-11-29 | 0.25 | 2006年度声明每股总额0.25；具体event/record/pay/ex未独立证明 |
| 2007-11-27 | 0.25 | 2007年度声明每股总额0.25；同上 |
| 2008-11-25 | 0.25 | 2008年度声明每股总额0.25；同上 |
| 2009-11-24 | 0.25 | 2009年度及第四季度声明总额0.25；具体日期仍未独立证明 |
| 2010-11-23 | 0.25 | 单笔年度$0.25及声明/record/pay由主文支持；**exact ex-date仍只按WIKI观察记录** |

未从因子反推任何现金；未从record日期或交易日历填造ex-date。逐笔等级保存在 `dividend-evidence.csv`。2007年报目录页虽出现在返回中，但没有返回其现金财务表，不能拿目录当作2004/2005金额证据。

**单位及源身份：** 新取得的2010年报Item5发布2009—2010八季NYSE综合交易最高/最低价。本轮把这16个端点与旧WIKI RSH的相应季度比较，**8/8季度的High和Low均逐值完全相等，所有差为0**。这增强了有限窗口末段是同一旧普通股、原始美元名义尺度的证据，不是只依靠ticker字符串。

详见 `2010-SEC-quarter-price-table.excerpt.txt` 和 `SEC-2009-2010-quarter-price-check.csv`。audit agent已另核对的SPY2004/2005持仓价值/股数锚点仍由其预检保存，本轮没有重复计算。2010年报明确回购等股本变化，不把回购导致股数下降当作拆股；本轮也**没有取得一条穷尽2003—2011所有拆股/股本事件的发行人证明**。

## 有限候选边界与待证项

继续审阅的对象应严格是：

```text
research_key: RSHCQ
source_ticker: RSH
issuer: RadioShack Corporation
CIK: 0000096289
security: old common stock, $1 par
window: 2003-12-19 through 2011-07-11
actual listing ticker in this window: RSH
```

该窗口与1902行日期/内部因子检查由 `work/v04-rsh-identity-preflight/`负责。本轮只补身份、新的发行人季度价与有限现金证据，没有复做预检或创建价格候选。

尚不能宣称：七笔exact ex-date全有主证；2004/2005金额已独立确认；RSHC→RSHCQ精确日期已证实；2015买方股票与旧股连续；完整日线/公司行动已获最终应用许可。年度声明总额、单笔实际支付、原源除息日和证券代码沿革分别记录，保持这些边界后可继续有限候选评审。

检索还返回了一份CIK **1011006**、YHOO的2010年报及其拆股文字，已明确排除，**没有把Yahoo的股息或拆股用于RadioShack**。

状态：`HISTORICAL_ISSUER_IDENTITY_SUPPORTED_FOR_BOUNDED_RESEARCH_REVIEW`；0主仓修改、0应用、0 Live全局alias。源证据和剩余限制均在 `identity-findings.json`，4次请求在 `request-log.json`。
