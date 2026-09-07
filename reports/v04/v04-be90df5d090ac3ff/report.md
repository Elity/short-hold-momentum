# SHM v0.4 历史时点标普500研究

状态：**INCONCLUSIVE**；胜者：**无**。

共同评价区间：2005-01-04 → 2026-09-04。
使用历史时点股票池，修复数据与公司行动记账；C0–C4规则与10/25bps模型成本保持。全部属于已知历史，不是新样本外。

历史成分来源覆盖至 2026-09-04；所需截止 2026-09-04；成分覆盖检查：PASS；已知成分日价格覆盖：89.8%。
当前503证券名单未用于回填历史。成分未知区间仍保留原评价日期，暂停新增排名买入；这些区间的结果不能作为有效策略成绩。

| 候选 | 10bps年化/回撤 | 25bps年化/回撤 | 晋级 |
|---|---:|---:|---|
| S500-C0 | 数据检查未通过，指标无效 | 数据检查未通过，指标无效 | 否 |
| S500-C1 | 数据检查未通过，指标无效 | 数据检查未通过，指标无效 | 否 |
| S500-C2 | 数据检查未通过，指标无效 | 数据检查未通过，指标无效 | 否 |
| S500-C3 | 数据检查未通过，指标无效 | 数据检查未通过，指标无效 | 否 |
| S500-C4 | 数据检查未通过，指标无效 | 数据检查未通过，指标无效 | 否 |

原始数字及逐日路径只保留作数据审计，不以异常CAGR宣称扩池有效。
10%为预警目标，不是本轮淘汰线。历史行情中的开盘价与模型成本不构成券商执行证据。

当时报价与成交额的资格数据覆盖：86.5%。5美元门槛使用当时实际报价，ADV60使用当时成交额；动量和收益仍用含分红复权价。

补入 152 只归档价格序列（不代表已通过质量验收），隔离 4 只；隔离证券仍保留在历史成分和覆盖率分母中。
- 未解决：NYSE Titanium Metals缓存混入其他证券；免费候选仍有2个整行缺口、6个季度报价冲突及早期成交量口径疑点，未应用。
- 未解决：历史成员是 Millipore，但 WIKI 的 MIL 元数据为 MFC Industrial，2010年报价约7至16美元，与Millipore每股107美元收购事件不符。
- 未解决：2018年停止更新的归档不能补齐之后的退市公司行情、换股和现金收购结算；新增序列仍需逐项核验身份与终止事件，不能作为合格收益证据。
- 未解决：原Allergan Inc与Watson/Actavis为独立发行人；WIKI AGN为后者的历史，原Allergan价格尚未取得可信完整替代。
- 未解决：WIKI LSI不对应历史LSI Corporation：2012/13八季报价与SEC均不符，不能作为原半导体公司的行情。

已登记 10 项有来源的公司行动。换股和现金权益单独记账，不伪装为市场成交、不重复计入复权收益。
现金权益先记应收，本轮按预先固定的有效日后第5个XNYS交易日释放；这是模拟假设，不是实测券商到账。未配置结算规则的未知应收仍阻止晋级。

## S500-C0

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "PASS", "PIT_PRICE_COVERAGE": "PASS", "PIT_ELIGIBILITY_BASIS": "PASS", "PRICE_REPAIR_EVIDENCE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "PASS", "SIGNAL_DATA_10": "PASS", "HOLDING_PRICE_JUMPS_10": "PASS", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "PASS", "SIGNAL_DATA_25": "PASS", "HOLDING_PRICE_JUMPS_25": "PASS", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_UNRESOLVED_HISTORICAL_PRICE_EVIDENCE, VERIFIED_LARGE_MARKET_MOVE, WARN_ONE_YEAR_DEPENDENCY

持仓超过50%的原始价格跳变全部保留。仅精确匹配核验记录的真实市场波动不作为坏数据；其余仍待核验，亏损不删除。

| 日期 | 股票 | 缓存单日涨跌 | 前一日持仓权重 |
|---|---|---:|---:|
| 2020-03-09 | APA | -53.86% | 3.40% |

VERIFIED_LARGE_MARKET_MOVE：APA 2020-03-09 close_to_close -53.864734%；证据 `data/reference/v04-remediation/price-evidence/APA-2020-03-09/review.md`。

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 8.00%、回撤 -18.95%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.39977847683484125, "Unknown": 0.6165836616105917, "Information Technology": 0.6837368146572403, "Consumer Discretionary": 0.4044644629801914, "Financials": 0.35709123587622765, "Consumer Staples": 0.3393240118176622, "Industrials": 0.2803370205922164, "Utilities": 0.34233848894566554, "Materials": 0.20639787994104014, "Real Estate": 0.2805703342747208, "Energy": 0.40961214948950503, "Communication Services": 0.14135586029779867}

## S500-C1

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "PASS", "PIT_PRICE_COVERAGE": "PASS", "PIT_ELIGIBILITY_BASIS": "PASS", "PRICE_REPAIR_EVIDENCE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "PASS", "SIGNAL_DATA_10": "PASS", "HOLDING_PRICE_JUMPS_10": "PASS", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "PASS", "SIGNAL_DATA_25": "PASS", "HOLDING_PRICE_JUMPS_25": "PASS", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_UNRESOLVED_HISTORICAL_PRICE_EVIDENCE, WARN_ONE_YEAR_DEPENDENCY

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 6.75%、回撤 -22.68%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.39977847683484125, "Unknown": 0.6165836616105919, "Information Technology": 0.6837368146572406, "Consumer Discretionary": 0.40446446298019145, "Financials": 0.35709123587622765, "Consumer Staples": 0.33932401181766214, "Industrials": 0.28033702059221643, "Utilities": 0.34233848894566565, "Materials": 0.20639787994104006, "Real Estate": 0.28057033427472095, "Energy": 0.40961214948950525, "Communication Services": 0.14135586029779873}

## S500-C2

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "PASS", "PIT_PRICE_COVERAGE": "PASS", "PIT_ELIGIBILITY_BASIS": "PASS", "PRICE_REPAIR_EVIDENCE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "PASS", "SIGNAL_DATA_10": "PASS", "HOLDING_PRICE_JUMPS_10": "PASS", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "PASS", "SIGNAL_DATA_25": "PASS", "HOLDING_PRICE_JUMPS_25": "PASS", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_UNRESOLVED_HISTORICAL_PRICE_EVIDENCE, WARN_ONE_YEAR_DEPENDENCY

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 6.75%、回撤 -22.68%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.40033175849733266, "Unknown": 0.5394297858795428, "Information Technology": 0.4807549528383851, "Consumer Discretionary": 0.40505155603973786, "Financials": 0.3579545610187728, "Consumer Staples": 0.3341998156384781, "Industrials": 0.2794143692750005, "Utilities": 0.20735600573781088, "Materials": 0.19904091215870037, "Real Estate": 0.27762067340626645, "Energy": 0.28081653641885246, "Communication Services": 0.1406574646331345}

## S500-C3

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "PASS", "PIT_PRICE_COVERAGE": "PASS", "PIT_ELIGIBILITY_BASIS": "PASS", "PRICE_REPAIR_EVIDENCE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "PASS", "SIGNAL_DATA_10": "INCONCLUSIVE", "HOLDING_PRICE_JUMPS_10": "PASS", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "PASS", "SIGNAL_DATA_25": "INCONCLUSIVE", "HOLDING_PRICE_JUMPS_25": "PASS", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_UNRESOLVED_HISTORICAL_PRICE_EVIDENCE, WARN_ONE_YEAR_DEPENDENCY

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 6.75%、回撤 -22.68%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.39977847683500944, "Unknown": 0.6045092297018045, "Information Technology": 0.6648346340241642, "Consumer Discretionary": 0.404632932035559, "Financials": 0.35801978412252405, "Consumer Staples": 0.33520279153921123, "Industrials": 0.2774374298234836, "Utilities": 0.34234317172283285, "Materials": 0.20704810218593664, "Real Estate": 0.2805703342749158, "Energy": 0.4015741178335682, "Communication Services": 0.14324449272789985}

## S500-C4

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "PASS", "PIT_PRICE_COVERAGE": "PASS", "PIT_ELIGIBILITY_BASIS": "PASS", "PRICE_REPAIR_EVIDENCE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "PASS", "SIGNAL_DATA_10": "PASS", "HOLDING_PRICE_JUMPS_10": "PASS", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "PASS", "SIGNAL_DATA_25": "PASS", "HOLDING_PRICE_JUMPS_25": "PASS", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_UNRESOLVED_HISTORICAL_PRICE_EVIDENCE, WARN_ONE_YEAR_DEPENDENCY

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 7.26%、回撤 -25.27%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.4885894276280701, "Unknown": 0.6706045209434326, "Information Technology": 0.6837368146575689, "Consumer Discretionary": 0.41197308542805117, "Financials": 0.45837707292258933, "Consumer Staples": 0.33932401181770616, "Industrials": 0.28033702059221643, "Utilities": 0.34233848894566554, "Materials": 0.20639787994104006, "Real Estate": 0.3395267910819994, "Energy": 0.4096121494897328, "Communication Services": 0.18767742594956116}

原v0.3结果：[v03-e74f9b21da5093f1](../../v03/v03-e74f9b21da5093f1/report.md)；旧快照 5f9b4715f73d7c3ef5bf19dc88d3df4ad05348544ed4f2419513bc6f81f5e4fd，本轮未重新运行owner股票池，不混作同快照比较。

run_id: `v04-be90df5d090ac3ff`；snapshot: `e14083ce3aec3f088fb4681f3497e12111dc84126cc663db1789c6a59d68195a`。
复现：`uv run --no-sync shm research-v04 --repo-root .`。
