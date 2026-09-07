# S&P 500 历史成分补丁：2026-07-01 至 2026-09-04

这是候选数据修复包，尚未覆盖仓库 `data/reference/sp500_history.csv`。没有运行新回测，没有修改策略、参数或行情。

## 原文件来源及语义

- 来源：<https://github.com/fja05680/sp500>，项目原审查文档为 `/Users/fighting/code/short-hold-momentum/docs/reference_spotcheck.md`。
- 原项目锁定上游 commit：`c31ac3cc56f28cf9a02b4e694eff7ceab596a0ff`。
- 上游文件：`S&P 500 Historical Components & Changes (Updated).csv`。
- 原文件 SHA-256：`39a9202c9ef69a74c0ff07e2113ad41fb6da7c8c5b6cd9541f0185fb4391e717`。
- 本轮直接核对 GitHub Contents API：仓库本地文件的 Git blob SHA 与上游当前对象都为 `dd4fd53569ce3a107dae4fe61cfee0a37ee4d52b`。这不是本地意外截断；上游也只更新到 2026-06-30。
- 原文件两列为 `date,tickers`，2718 个严格递增、不重复的日期，1996-01-02 至 2026-06-30。后期是稀疏的成分事件/快照行，读取规则是取不晚于决策日的最近已生效快照，不要求原文件每天都有一行。
- 原作者 README 明确说明：旧历史来自 Trading Evolved 配套数据，之后人工汇总 Wikipedia 及相关新闻；Wikipedia 的 Selected Changes 并不完整。此补丁不把 1996–2026 年旧历史重新包装成已完整独立审计的数据。

## 追加事件与生效边界

| 生效交易日 | 加入 | 移除 | 根据 |
|---|---|---|---|
| 2026-07-01 | MBGL | — | SPGI 分拆完成公告 + 2026 年 3 月指数公司 spin-off 方法论，临时进入母公司指数 |
| 2026-07-02 | — | MBGL | 首个 regular-way 交易日后移出，且 S&P 明确安排该日开盘加入 SmallCap 600 |
| 2026-08-05 | FERG | EA | S&P 2026-07-31 公告，明确开盘前生效 |
| 2026-08-18 | RDDT | AVB | S&P 2026-08-13 公告，明确开盘前生效 |
| 2026-08-18 | VMRK | EQR | S&P 指数续存说明 + SEC 2026-08-17 合并完成公告，明确新代码在 8 月 18 日开盘交易 |

**MBGL 的临时指数行属于公开方法论与特定公司事件相结合的重建，并非逐字载明于一份独立的 S&P 500 当日全量名单。** 已保留该判断的完整依据；不能把它描述为下载到了 7 月 1 日官方成分文件。暂时加入 7 月 1 日使证券数为 504，7 月 2 日恢复 503。源方法论容许指数委员会对特殊情况另作处理；本轮未查到适用于 MBGL 的例外通知。

按项目实际日历函数，该扩展区间的选股日为 **2026-07-22、2026-08-19**，并不与 MBGL 的临时日期重合。新上市 MBGL 也不具备 260 日历史资格。本包没有因此省略该临时事件，而是明确记录重建方法与边界。

### 已真实读取并保存的主要来源

1. [FERG 替换 EA，8 月 5 日生效](https://press.spglobal.com/2026-07-31-Ferguson-Enterprises-Set-to-Join-S-P-500-and-ADI-Global-Distribution-to-Join-S-P-SmallCap-600?asPDF=1) — `ferg-effective-20260805.tool.json`。
2. [RDDT 替换 AVB，以及 EQR/VMRK 指数续存](https://press.spglobal.com/2026-08-13-Reddit-Set-to-Join-S-P-500-and-Sun-Communities-to-Join-S-P-MidCap-400) — `reddit-effective-20260818.tool.json`。
3. [SEC：合并完成与 VMRK 的 8 月 18 日交易日期](https://www.sec.gov/Archives/edgar/data/915912/000110465926097833/tm2623381d1_ex99-1.htm) — `vivmark-effective-20260818.tool.json`。
4. [SPGI 于 7 月 1 日完成 MBGL 分拆](https://press.spglobal.com/2026-07-01-S-P-GLOBAL-INC-COMPLETES-SEPARATION-OF-MOBILITY-GLOBAL-INC) — `mbgl-spin-effective-20260701.tool.json`。
5. [MBGL 于 7 月 2 日加入 SmallCap 600](https://press.spglobal.com/2026-06-26-Gulfport-Energy-and-Mobility-Global-Set-to-Join-S-P-SmallCap-600) — `mbgl-smallcap-effective-20260702.tool.json`。
6. [S&P 2026 年 3 月 Equity Indices Policies & Practices，Spin-Offs 部分](https://www.spglobal.com/spdji/pt/documents/methodologies/methodology-sp-equity-indices-policies-practices.pdf) — `spinoff-methodology-202603.tool.json`。
7. [9 月 4 日发布、9 月 21 日才生效的季度调整](https://press.spglobal.com/2026-09-04-Bloom-Energy,-Illumina,-and-Everpure-Set-to-Join-S-P-500-Others-to-Join-S-P-100,-S-P-MidCap-400,-and-S-P-SmallCap-600) — `future-changes-20260921.tool.json`。BE、P、ILMN **未**提前写入；TAP、TTD、BLDR 保留至本补丁截止日。

`*.tool.json` 保存 Browse 工具返回原文、源 URL、缓存抓取日期及 trace ID；不是声称本轮逐一直接下载了原始 HTML/PDF。公告目录另有本轮直接 HTTP 200 下载的 `official-archive-live.html` 和真实取证时间 `official-archive-live.meta.json`，覆盖到 2026-09-04。

## 完整性检查方法

不是仅把现有 503 名单与旧名单求差后向前填充。本轮先查看真实官方公告目录，再读取区间内 S&P 500 调整及全部 7 条其他 Set-to-Join 公告，检查有无母公司位于 S&P 500 的临时分拆。7 月 2 日的 Midera 分拆母公司 MIDD 属 MidCap 400；其他所审公告属于 400/600 间调整或并购方继续留在 500，没有产生额外 500 成分变化。对应原文保存在 `archive-review-*.tool.json`。

由已知 6 月 30 日名单逐事件构造后，9 月 4 日终态恰好与此前双源核验的 9 月 3 日 SPY 股票/Wikipedia 503 名单一致。这只作为独立终态核对，不作为每个历史日期的唯一依据。

## 证券身份及后续行情处理

- FERG：Ferguson Enterprises，CIK `0002011641`，CUSIP `31488V107`。
- RDDT：Reddit，CIK `0001713445`，CUSIP `75734B100`。
- AVB：AvalonBay，SEC 披露主体 CIK `0000915912`。
- EQR → VMRK：S&P 明确说明原 EQR 续存；当前 VMRK 的 CIK `0000906107`、CUSIP `29476L107` 对应续存主体。
- MBGL 的名称与 ticker 有公司和指数公告依据；本包没有另外核验其 CIK，故清单中保持空值，不填写猜测值。

**成分重建不等于完成行情连续性修复。** EQR/VMRK 的同主体映射、AVB 股份换股、EA 收购现金兑付，以及当时账户若持有上述股票的公司行为，仍应由行情/执行审计明确处理。不得直接把 VMRK 行情当作 AVB 的同股数行情，也不得用前收盘价伪造成交。

## 输出与验证

- `sp500_history.through-20260904.csv`：候选完整文件，原文件全部字节原样作为前缀，追加 47 个 XNYS 交易日，截止 2026-09-04。
- `membership-events.csv`：事件差分。
- `extension-date-checks.csv`：每个追加日期的证券数与应用事件。
- `membership-patch-manifest.json`：原文件/候选文件哈希、来源索引、身份信息、事件与验证结果。
- `build_membership_patch.py`：可重跑的离线生成及边界断言脚本；不会覆盖仓库 CSV。

运行：

```sh
cd /Users/fighting/code/short-hold-momentum
PYTHONPATH=src .venv/bin/python /Users/fighting/Documents/Codex/2026-09-06/co-2/work/v04-remediation-membership/build_membership_patch.py
```

通过的断言包括：旧文件字节保持不变、日期严格递增且不重复、追加日期全部为 XNYS 交易日、事件前后边界正确、9 月 21 日调整未提前生效、终态与独立当前快照一致。应用前必须核对 manifest 的原文件哈希仍匹配，并由主任务归档旧文件及证据。
