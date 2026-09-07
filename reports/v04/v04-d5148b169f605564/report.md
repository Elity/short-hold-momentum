# SHM v0.4 历史时点标普500研究

状态：**INCONCLUSIVE**；胜者：**无**。

共同评价区间：2005-01-04 → 2026-09-04。
本轮只更换股票池，C0–C4规则与10/25bps模型成本保持。全部属于已知历史，不是新样本外。

历史成分来源覆盖至 2026-06-30；所需截止 2026-09-04；成分覆盖检查：INCONCLUSIVE；已知成分日价格覆盖：77.2%。
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

## S500-C0

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "INCONCLUSIVE", "PIT_PRICE_COVERAGE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "PASS", "SIGNAL_DATA_10": "PASS", "HOLDING_PRICE_JUMPS_10": "INCONCLUSIVE", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "PASS", "SIGNAL_DATA_25": "PASS", "HOLDING_PRICE_JUMPS_25": "INCONCLUSIVE", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_MEMBERSHIP_HISTORY_INCOMPLETE, WARN_PIT_PRICE_COVERAGE_BELOW_80_PERCENT, WARN_HOLDING_PRICE_JUMPS_RAW_METRICS_INVALID, WARN_ONE_YEAR_DEPENDENCY

持仓发生超过50%的缓存价格跳变，需要核实证券身份、单位及公司行为；不删除该证券来改善结果。

| 日期 | 股票 | 缓存单日涨跌 | 前一日持仓权重 |
|---|---|---:|---:|
| 2010-02-22 | TIE | 189783.91% | 3.11% |
| 2010-04-30 | TIE | -99.95% | 7.07% |
| 2010-04-26 | TIE | 170952.64% | 0.00% |

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 8.00%、回撤 -18.95%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.46726975129037185, "Unknown": 0.9860237051782265, "Information Technology": 0.559477281112122, "Consumer Discretionary": 0.40446445539817427, "Financials": 0.38443167488264846, "Consumer Staples": 0.4042998641741948, "Industrials": 0.28033703954635114, "Utilities": 0.34636819290986254, "Materials": 0.2709907701405617, "Real Estate": 0.27498941163122215, "Energy": 0.4096121795625073, "Communication Services": 0.14135559453082241}

## S500-C1

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "INCONCLUSIVE", "PIT_PRICE_COVERAGE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "PASS", "SIGNAL_DATA_10": "PASS", "HOLDING_PRICE_JUMPS_10": "INCONCLUSIVE", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "PASS", "SIGNAL_DATA_25": "PASS", "HOLDING_PRICE_JUMPS_25": "INCONCLUSIVE", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_MEMBERSHIP_HISTORY_INCOMPLETE, WARN_PIT_PRICE_COVERAGE_BELOW_80_PERCENT, WARN_HOLDING_PRICE_JUMPS_RAW_METRICS_INVALID, WARN_ONE_YEAR_DEPENDENCY

持仓发生超过50%的缓存价格跳变，需要核实证券身份、单位及公司行为；不删除该证券来改善结果。

| 日期 | 股票 | 缓存单日涨跌 | 前一日持仓权重 |
|---|---|---:|---:|
| 2010-02-22 | TIE | 189783.91% | 3.11% |
| 2010-04-30 | TIE | -99.95% | 7.07% |
| 2010-04-26 | TIE | 170952.64% | 0.00% |

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 6.75%、回撤 -22.68%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.4672697512903722, "Unknown": 0.9860237051782265, "Information Technology": 0.559477281112122, "Consumer Discretionary": 0.40446445539817416, "Financials": 0.3844316748826485, "Consumer Staples": 0.4042998641741946, "Industrials": 0.28033703954635114, "Utilities": 0.34636819290986237, "Materials": 0.2709907701405619, "Real Estate": 0.274989411631222, "Energy": 0.4096121795625075, "Communication Services": 0.14135559453082241}

## S500-C2

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "INCONCLUSIVE", "PIT_PRICE_COVERAGE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "PASS", "SIGNAL_DATA_10": "PASS", "HOLDING_PRICE_JUMPS_10": "INCONCLUSIVE", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "PASS", "SIGNAL_DATA_25": "PASS", "HOLDING_PRICE_JUMPS_25": "INCONCLUSIVE", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_MEMBERSHIP_HISTORY_INCOMPLETE, WARN_PIT_PRICE_COVERAGE_BELOW_80_PERCENT, WARN_HOLDING_PRICE_JUMPS_RAW_METRICS_INVALID, WARN_ONE_YEAR_DEPENDENCY

持仓发生超过50%的缓存价格跳变，需要核实证券身份、单位及公司行为；不删除该证券来改善结果。

| 日期 | 股票 | 缓存单日涨跌 | 前一日持仓权重 |
|---|---|---:|---:|
| 2010-04-26 | TIE | 170952.64% | 0.00% |
| 2010-04-23 | TIE | -99.94% | 6.61% |

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 6.75%、回撤 -22.68%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.466288419147584, "Unknown": 0.4639329816899824, "Information Technology": 0.4807549249890692, "Consumer Discretionary": 0.40505155326219994, "Financials": 0.37267671782222045, "Consumer Staples": 0.4009322783254784, "Industrials": 0.27941437413040515, "Utilities": 0.20868794748916267, "Materials": 0.1987946598600576, "Real Estate": 0.2758368622603738, "Energy": 0.28081642128160456, "Communication Services": 0.1411887427333127}

## S500-C3

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "INCONCLUSIVE", "PIT_PRICE_COVERAGE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "PASS", "SIGNAL_DATA_10": "PASS", "HOLDING_PRICE_JUMPS_10": "INCONCLUSIVE", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "PASS", "SIGNAL_DATA_25": "PASS", "HOLDING_PRICE_JUMPS_25": "INCONCLUSIVE", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_MEMBERSHIP_HISTORY_INCOMPLETE, WARN_PIT_PRICE_COVERAGE_BELOW_80_PERCENT, WARN_HOLDING_PRICE_JUMPS_RAW_METRICS_INVALID, WARN_ONE_YEAR_DEPENDENCY

持仓发生超过50%的缓存价格跳变，需要核实证券身份、单位及公司行为；不删除该证券来改善结果。

| 日期 | 股票 | 缓存单日涨跌 | 前一日持仓权重 |
|---|---|---:|---:|
| 2010-02-22 | TIE | 189783.91% | 3.11% |
| 2010-04-26 | TIE | 170952.64% | 0.00% |
| 2010-04-23 | TIE | -99.94% | 6.61% |

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 6.75%、回撤 -22.68%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.4662884191475527, "Unknown": 0.9860237051782194, "Information Technology": 0.5391136677088664, "Consumer Discretionary": 0.40463294298065483, "Financials": 0.3862376650241688, "Consumer Staples": 0.400869597384215, "Industrials": 0.27743743365774504, "Utilities": 0.3465947272855732, "Materials": 0.26911809435024947, "Real Estate": 0.27498941163122215, "Energy": 0.4015741178337361, "Communication Services": 0.14324421498718615}

## S500-C4

检查：{"MEMBERSHIP_HISTORY_COVERAGE": "INCONCLUSIVE", "PIT_PRICE_COVERAGE": "INCONCLUSIVE", "NEXT_SESSION_10": "PASS", "FUNDED_LONG_ONLY_10": "PASS", "EXECUTION_DATA_10": "PASS", "SIGNAL_DATA_10": "PASS", "HOLDING_PRICE_JUMPS_10": "INCONCLUSIVE", "BENCHMARK_PRICE_JUMPS_10": "PASS", "EVALUATION_COVERAGE_10": "PASS", "NEXT_SESSION_25": "PASS", "FUNDED_LONG_ONLY_25": "PASS", "EXECUTION_DATA_25": "PASS", "SIGNAL_DATA_25": "PASS", "HOLDING_PRICE_JUMPS_25": "INCONCLUSIVE", "BENCHMARK_PRICE_JUMPS_25": "PASS", "EVALUATION_COVERAGE_25": "PASS"}
警告：WARN_MEMBERSHIP_HISTORY_INCOMPLETE, WARN_PIT_PRICE_COVERAGE_BELOW_80_PERCENT, WARN_HOLDING_PRICE_JUMPS_RAW_METRICS_INVALID, WARN_ONE_YEAR_DEPENDENCY

持仓发生超过50%的缓存价格跳变，需要核实证券身份、单位及公司行为；不删除该证券来改善结果。

| 日期 | 股票 | 缓存单日涨跌 | 前一日持仓权重 |
|---|---|---:|---:|
| 2010-02-22 | TIE | 189783.91% | 4.12% |
| 2010-04-30 | TIE | -99.95% | 7.07% |
| 2010-04-26 | TIE | 170952.64% | 0.00% |

逐年、2019年后、剔除最佳年数值及同风控SPY辅助对照保存在JSON，均标记为未验证诊断。

同大盘趋势与波动预算SPY辅助对照：年化 7.26%、回撤 -25.27%；不含个股退出。

行业权重仅按当前来源标签描述，不充当历史行业时点数据；旧证券无法识别的部分保留Unknown。
行业峰值权重：{"Health Care": 0.4705824313236819, "Unknown": 0.9901078270384247, "Information Technology": 0.6162129997365589, "Consumer Discretionary": 0.4167895842423073, "Financials": 0.506041238143738, "Consumer Staples": 0.4042998641741282, "Industrials": 0.2803370395463508, "Utilities": 0.34636819290986237, "Materials": 0.27099077014056194, "Real Estate": 0.33730185713283134, "Energy": 0.4096121795623481, "Communication Services": 0.18767741984147404}

原v0.3结果：[v03-e74f9b21da5093f1](../../v03/v03-e74f9b21da5093f1/report.md)；旧快照 5f9b4715f73d7c3ef5bf19dc88d3df4ad05348544ed4f2419513bc6f81f5e4fd，本轮未重新运行owner股票池，不混作同快照比较。

run_id: `v04-d5148b169f605564`；snapshot: `40748daff46ca3c6be4e130035f19c754437184e1024df12dfe568610aa613f4`。
复现：`uv run --no-sync shm research-v04 --repo-root .`。
