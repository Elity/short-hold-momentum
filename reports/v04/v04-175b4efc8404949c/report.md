# SHM v0.4 历史时点标普500研究

状态：**INCONCLUSIVE**；胜者：**无**。

共同评价区间：2005-01-04 → 2026-09-04。
使用历史时点股票池，修复数据与公司行动记账；C0–C4规则与10/25bps模型成本保持。全部属于已知历史，不是新样本外。

历史成分来源覆盖至 2026-09-04；所需截止 2026-09-04；成分覆盖检查：PASS；已知成分日价格覆盖：89.5%。
当前503证券名单未用于回填历史。成分未知区间仍保留原评价日期，暂停新增排名买入；这些区间的结果不能作为有效策略成绩。

| 候选 | 10bps年化/回撤 | 25bps年化/回撤 | 晋级 |
|---|---:|---:|---|
| S500-C0 | 数据检查未通过，指标无效 | 数据检查未通过，指标无效 | 否 |
| S500-C1 | 数据检查未通过，指标无效 | 数据检查未通过，指标无效 | 否 |
| S500-C2 | 数据检查未通过，指标无效 | 数据检查未通过，指标无效 | 否 |
| S500-C3 | 数据检查未通过，指标无效 | 数据检查未通过，指标无效 | 否 |
| S500-C4 | 数据检查未通过，指标无效 | 数据检查未通过，指标无效 | 否 |

原始数字及逐日路径只保留作数据审计，不以异常CAGR宣称扩池有效。
10%为预警目标，不是本轮淘汰线。官方开盘价与模型成本不构成券商执行证据。

当时报价与成交额的资格数据覆盖：86.1%。5美元门槛使用当时实际报价，ADV60使用当时成交额；动量和收益仍用含分红复权价。

补入 150 只归档价格序列（不代表已通过质量验收），隔离 4 只；隔离证券仍保留在历史成分和覆盖率分母中。
- 未解决：NYSE Titanium Metals 的缓存混入其他证券价格；免费替代日线缺日、缺量且复权未验证，尚无可信完整替代。
- 未解决：历史成员是 Millipore，但 WIKI 的 MIL 元数据为 MFC Industrial，2010年报价约7至16美元，与Millipore每股107美元收购事件不符。
- 未解决：2018年停止更新的归档不能补齐之后的退市公司行情、换股和现金收购结算；新增序列仍需逐项核验身份与终止事件，不能作为合格收益证据。
- 未解决：原Allergan Inc与Watson/Actavis为独立发行人；WIKI AGN为后者的历史，原Allergan价格尚未取得可信完整替代。
- 未解决：WIKI LSI不对应历史LSI Corporation：2012/13八季报价与SEC均不符，不能作为原半导体公司的行情。

已登记 4 项有来源的公司行动。换股和现金权益单独记账，不伪装为市场成交、不重复计入复权收益。
现金权益先记应收，本轮按预先固定的有效日后第5个XNYS交易日释放；这是模拟假设，不是实测券商到账。未配置结算规则的未知应收仍阻止晋级。

## S500-C0

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "PASS", "PIT_PRICE_COVERAGE": "PASS", "PIT_ELIGIBILITY_BASIS": "PASS", "PRICE_REPAIR_EVIDENCE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "INCONCLUSIVE", "SIGNAL_DATA_10": "INCONCLUSIVE", "HOLDING_PRICE_JUMPS_10": "PASS", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "INCONCLUSIVE", "SIGNAL_DATA_25": "INCONCLUSIVE", "HOLDING_PRICE_JUMPS_25": "PASS", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_UNRESOLVED_HISTORICAL_PRICE_EVIDENCE, WARN_ONE_YEAR_DEPENDENCY

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 8.00%、回撤 -18.95%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.40055060336316545, "Unknown": 0.5574957603464141, "Information Technology": 0.34168462516248166, "Consumer Discretionary": 0.3516979374203796, "Financials": 0.24961107331651053, "Consumer Staples": 0.36236014613102807, "Industrials": 0.18818436542170186, "Utilities": 0.34233848894566565, "Materials": 0.15684500094962325, "Real Estate": 0.11216531282557404, "Energy": 0.27105371243555537, "Communication Services": 0.13928190240957916}

## S500-C1

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "PASS", "PIT_PRICE_COVERAGE": "PASS", "PIT_ELIGIBILITY_BASIS": "PASS", "PRICE_REPAIR_EVIDENCE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "INCONCLUSIVE", "SIGNAL_DATA_10": "INCONCLUSIVE", "HOLDING_PRICE_JUMPS_10": "PASS", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "INCONCLUSIVE", "SIGNAL_DATA_25": "INCONCLUSIVE", "HOLDING_PRICE_JUMPS_25": "PASS", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_UNRESOLVED_HISTORICAL_PRICE_EVIDENCE, WARN_ONE_YEAR_DEPENDENCY

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 6.75%、回撤 -22.68%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.40055060336316506, "Unknown": 0.5574957603464142, "Information Technology": 0.3416846251624816, "Consumer Discretionary": 0.3516979374203796, "Financials": 0.2496110733165104, "Consumer Staples": 0.36236014613102796, "Industrials": 0.1881843654217019, "Utilities": 0.34233848894566543, "Materials": 0.15684500094962323, "Real Estate": 0.11216531282557397, "Energy": 0.2710537124355552, "Communication Services": 0.1392819024095791}

## S500-C2

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "PASS", "PIT_PRICE_COVERAGE": "PASS", "PIT_ELIGIBILITY_BASIS": "PASS", "PRICE_REPAIR_EVIDENCE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "INCONCLUSIVE", "SIGNAL_DATA_10": "INCONCLUSIVE", "HOLDING_PRICE_JUMPS_10": "PASS", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "INCONCLUSIVE", "SIGNAL_DATA_25": "INCONCLUSIVE", "HOLDING_PRICE_JUMPS_25": "PASS", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_UNRESOLVED_HISTORICAL_PRICE_EVIDENCE, WARN_ONE_YEAR_DEPENDENCY

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 6.75%、回撤 -22.68%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.401106025775015, "Unknown": 0.47268899987995533, "Information Technology": 0.333220764131376, "Consumer Discretionary": 0.3242658327908191, "Financials": 0.2468405925262861, "Consumer Staples": 0.3341998156383434, "Industrials": 0.1802497977958467, "Utilities": 0.20735600573781088, "Materials": 0.19904091215870048, "Real Estate": 0.1338594762308345, "Energy": 0.27504011562699915, "Communication Services": 0.1404246369914895}

## S500-C3

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "PASS", "PIT_PRICE_COVERAGE": "PASS", "PIT_ELIGIBILITY_BASIS": "PASS", "PRICE_REPAIR_EVIDENCE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "INCONCLUSIVE", "SIGNAL_DATA_10": "INCONCLUSIVE", "HOLDING_PRICE_JUMPS_10": "PASS", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "INCONCLUSIVE", "SIGNAL_DATA_25": "INCONCLUSIVE", "HOLDING_PRICE_JUMPS_25": "PASS", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_UNRESOLVED_HISTORICAL_PRICE_EVIDENCE, WARN_ONE_YEAR_DEPENDENCY

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 6.75%、回撤 -22.68%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.40055060336333426, "Unknown": 0.5574957603460584, "Information Technology": 0.3369965215519109, "Consumer Discretionary": 0.34581025906962404, "Financials": 0.24684059252615353, "Consumer Staples": 0.33520279153914145, "Industrials": 0.18885616400209265, "Utilities": 0.34234317172283285, "Materials": 0.2079590123572965, "Real Estate": 0.10933989377955072, "Energy": 0.27089892275790617, "Communication Services": 0.13944817721701608}

## S500-C4

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "PASS", "PIT_PRICE_COVERAGE": "PASS", "PIT_ELIGIBILITY_BASIS": "PASS", "PRICE_REPAIR_EVIDENCE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "INCONCLUSIVE", "SIGNAL_DATA_10": "INCONCLUSIVE", "HOLDING_PRICE_JUMPS_10": "PASS", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "INCONCLUSIVE", "SIGNAL_DATA_25": "INCONCLUSIVE", "HOLDING_PRICE_JUMPS_25": "PASS", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_UNRESOLVED_HISTORICAL_PRICE_EVIDENCE, WARN_ONE_YEAR_DEPENDENCY

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 7.26%、回撤 -25.27%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.40055060336331244, "Unknown": 0.6031500796787883, "Information Technology": 0.3947853774518837, "Consumer Discretionary": 0.41197308542805117, "Financials": 0.27105794570090586, "Consumer Staples": 0.3623601461309823, "Industrials": 0.21033564365521645, "Utilities": 0.34233848894566554, "Materials": 0.20616595557645614, "Real Estate": 0.13580680777841747, "Energy": 0.2710537124355553, "Communication Services": 0.13928190240957922}

原v0.3结果：[v03-e74f9b21da5093f1](../../v03/v03-e74f9b21da5093f1/report.md)；旧快照 5f9b4715f73d7c3ef5bf19dc88d3df4ad05348544ed4f2419513bc6f81f5e4fd，本轮未重新运行owner股票池，不混作同快照比较。

run_id: `v04-175b4efc8404949c`；snapshot: `8785fc331410c15b23c18c1df6e6a12ec9306525a15d1afb77983381758c5046`。
复现：`uv run --no-sync shm research-v04 --repo-root .`。
