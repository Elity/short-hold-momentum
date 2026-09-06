# Trading Evolved / Norgate 历史行情来源调查

调查日期：2026-09-06。范围严格限制为 **10 次搜索、页面读取或 GitHub 目录/小文件请求**；没有下载压缩包、批量行情、注册账户、购买服务或绕过权限。本文只记录本次可核对的结果，不声称已穷尽互联网。

**结论：本次没有找到可直接、免费、获明确许可使用的完整退市美股 OHLCV＋拆股/股息历史包。** Trading Evolved 作者公开的 `data.zip` 被作者明确标为随机测试数据；公开配套仓库提供代码、指数成分和示例数据，并未附带所需完整真实行情。Norgate 的公开免费试用要求注册，只有最近两年历史，不能补 TIE 2010 年等旧缺口；完整退市历史属于付费订阅。

| 来源与直接链接 | 本次确认的内容 | 对本项目的用途与限制 |
|---|---|---|
| [作者 Andreas F. Clenow 的 Trading Evolved 页面](https://www.followingthetrend.com/trading-evolved/) | Downloads 明确区分 source code 与 **“random data generated for testing”**。 | 不能把配套 `data.zip` 当真实退市股票行情，更不能拿随机数据补缺口。 |
| [作者列出的源码 ZIP](https://www.dropbox.com/s/tj85sufbsi820ya/Trading%20Evolved.zip?dl=0) | 作者页面给出的代码下载链接。 | 可用于研究代码；本次未下载 ZIP，也未检验 Dropbox 链接是否仍可成功下载。 |
| [作者列出的 Random Test Data ZIP](https://www.dropbox.com/s/etocgt9zgeedo22/data.zip?dl=0) | 作者将其标为随机测试数据。 | 仅测试用途；排除为行情补全来源。未下载。 |
| [ahmedengu/trading_evolved](https://github.com/ahmedengu/trading_evolved) | README 说明是获作者许可的书籍代码镜像。递归目录快照 `b6a2c8a8facaaecdc13dd64284c9e6d5c28c9f3b`，`truncated=false`；数据路径主要为 `data/index_members/sp500.csv`、少量指数/ETF示例 CSV、Backtests CSV、`random_stock_data.py`。 | `sp500.csv` 是约 7.8 MB 的历史成分文件，不是逐证券行情。未见完整退市 OHLCV、拆股、股息包；代码获许可不等于市场数据再分发获许可。 |
| [hsm207/trading_evolved](https://github.com/hsm207/trading_evolved) | README 要求使用自己的 `QUANDL_API_KEY` 并 ingest Quandl bundle。目录快照 `90dd50c1e608f8dc9841ac29b4b5c6c1d72b0380`，`truncated=false`；`data/` 只有 ETF/油价示例 CSV。 | 是环境与书籍示例代码，不是额外的完整行情包；不能补已经取得的 WIKI 归档之外的旧缺口。 |
| [cs224/andreas_clenow_trading_evolved](https://github.com/cs224/andreas_clenow_trading_evolved) | 仓库代码标 MIT。目录快照 `8762626d11d8ff8c004ffdf20d737a35e07e1fd2`，`truncated=false`；`norgate_stock_data/data` 仅一个 35 字节条目，没有包含逐证券 CSV 的数据树。 | 不是公开的 Norgate 数据镜像。不能从代码 MIT 许可推断外部 Norgate 行情也可公开使用。 |
| [上述仓库的 Norgate 导入代码](https://github.com/cs224/andreas_clenow_trading_evolved/blob/8762626d11d8ff8c004ffdf20d737a35e07e1fd2/norgate_stock_data/norgate_stock_data.py) | 代码从外部本地 `data_path` 读取 `{symbol}_{norgate_assetid}.csv`；注释列出 Open/High/Low/Close/Volume/Turnover/Unadjusted Close/Dividend/Capital Event/S&P 500 等字段。无目录时直接报错。 | 若日后取得合规 Norgate 数据，这是字段映射参考；仓库本身没有提供这些 CSV。脚本还会 forward-fill，不能直接将其缺数处理照搬进 SHM。 |
| [Norgate 官方免费试用](https://norgatedata.com/freetrial.php) | 3 周试用；股票包按 Platinum 功能级别提供，但历史仅 **2 年**。新用户须注册，已有用户须登录。 | 不是免注册公开历史包；不足以检查 2005–2018 的旧退市数据。未注册或申请。 |
| [Norgate 官方股票包](https://norgatedata.com/stockmarketpackages.php) | Platinum 包含退市证券、历史指数成分及回溯 1990 年的数据；Diamond 回溯 1950 年。网页列出的 US Platinum 价格为 6 个月 USD 346.50、12 个月 USD 630。 | 属付费订阅，超出本次授权；价格只作本次页面记录，未购买。所需具体旧证券（包括 TIE）是否覆盖仍需向供应商逐项核实。 |
| [Norgate 数据内容表](https://norgatedata.com/data-content-tables.php) | 明确说明退市证券属于 Platinum/Diamond，并以最后交易年月后缀区分证券；文档也明确不保证早期退市库绝对完整。 | 有助于解决 ticker 复用，但不能仅凭产品介绍声称本项目所有缺口均可补齐。 |

Norgate 的官方介绍/申请页面还说明：数据库保存在 Windows 或 Windows VM，通过支持的平台/插件访问；Python 支持为 Windows。服务按订阅提供，历史数据不是独立一次性公开下载商品；ASCII 导出只覆盖历史价格而非所有数据功能。试用须接受其许可条件。这些限制意味着它不是目前 macOS/NAS 流程可直接匿名拉取的免费完整包。

本次发现可以直接使用的公开链接是**作者说明、代码、成分和数据服务文档**，不是可以直接导入为真实完整退市行情的文件。已有 WIKI 原始/复权归档仍是实际可用补充，但本文没有重新下载，也不扩大其 2018 年停更后的覆盖。针对 TIE、证券身份复用及 2018 年后缺口，本次调查没有找到满足完整性与公开使用条件的新免费包。

请求清单（共 10 次）：

1. 搜索 `Trading Evolved Andreas Clenow source code data download stocks historical`。
2. 搜索 `Norgate Data free sample historical delisted stocks data download`。
3. 读取作者 Trading Evolved 页面。
4. 搜索 Norgate 官网免费试用、样例和退市数据。
5. GitHub API：ahmedengu 仓库递归目录。
6. GitHub API：hsm207 仓库递归目录。
7. GitHub API：cs224 仓库递归目录。
8. 搜索 Norgate 官网 US Stocks Platinum/Diamond 历史范围和订阅条件。
9. GitHub API：读取 cs224 的约 5 KB Norgate 导入脚本。
10. 读取 Norgate 官方免费试用页面，确认注册、3 周与 2 年限制。
