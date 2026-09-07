# FISV 2025-11-12 缺口：本轮已取得的报价证据

本文件只保存先前已返回的检索正文摘录，没有发起新的行情或网页请求，没有修改价格缓存。以下价格、成交量均明确列在来源表格中，没有用插值、相邻日或计算推算。为便于核对，仅将工具返回的连续表格文本按行分开。

## 取证方式和时间

- 工具：`mcp__Search_MCP__web`。
- 查询：`FISV "Nov 12, 2025" historical data open high low volume`。
- 参数：`contentFormat="text"`，`maxResults=3`，`maxLength=4000`。
- 实际检索日期：2026-09-06，UTC。本次响应的跳转链接包含 Unix 时间标记 `1788705400`，对应 **2026-09-06 14:36:40 UTC**；工具没有单独提供 `retrieved_at` 字段，因此该时间标记不应解释为来源网页的更新日期。
- 响应 trace ID：`6a9d7a7725ce4f2fb193df64ae71dbb8`。
- 此前唯一的 Stooq 查询在 2026-09-06 14:35:45.455760 UTC 发起，SSL EOF 失败，未获得报价；没有把其当成价格证据。该请求已晚于 FISV 的 14:35 UTC 冷却截止时间。
- 下列内容是检索工具返回的网页正文，不是本轮另行下载的 HTML，也不是交易所原始行情文件。两页可能采用不同供应商或不同成交量统计口径；其相互独立性未做供应链层面的认证。

## 来源 1：FinancialContent / CloudQuote

URL：<https://markets.financialcontent.com/siliconvalley.com/quote/historical?Symbol=537%3A930831>

工具返回标题：`Fiserv (Nasdaq:FISV) Historical Data | Historical Stock Price Data for Fiserv (Nasdaq:FISV) | SiliconValley.com - Silicon Valley technology news, business news and commentary`

工具返回的缓存抓取时间：`crawledAt="2025-11-20T03:35:00.0000000Z"`。该结果没有提供独立的 `lastUpdatedAt` 字段。

正文相关原文：

```text
Fiserv (NQ: FISV) 61.17 -0.17 (-0.28%) Streaming Delayed PriceUpdated: 4:00 PM EST, Nov 19, 2025

Historical Prices
Date Open High Low Close Volume Change (%)
Nov 19, 2025 61.52 61.98 60.38 61.17 5,078,181 -0.17 (-0.28%)
Nov 18, 2025 62.16 62.69 61.13 61.34 7,236,149 -1.36 (-2.17%)
Nov 17, 2025 63.56 64.20 62.41 62.70 5,465,847 -0.72 (-1.14%)
Nov 14, 2025 64.00 64.15 63.02 63.42 5,596,504 -1.11 (-1.72%)
Nov 13, 2025 64.85 66.95 64.37 64.53 9,261,325 +0.15 (+0.23%)
Nov 12, 2025 64.20 64.87 63.11 64.38 6,241,184 +0.12 (+0.19%)

Stock Quote API & Stock News API supplied by www.cloudquote.io
Quotes delayed at least 20 minutes.
```

该表明确提供 2025-11-12 的完整 OHLCV。其成交量是精确列示的 **6,241,184**，不是把其他来源的 `6.24M` 展开得到的数值。

## 来源 2：Stoculator，旧 FI 页面

URL：<https://stoculator.com/stock/FI/historical>

工具返回标题：`Fiserv, Inc. - FI - Stock Historical Data & Price | Stoculator`

工具返回元数据：

- `crawledAt="2026-07-31T02:01:00.0000000Z"`
- `lastUpdatedAt="2025-11-10T16:00:00.0000000"`

页面沿用旧 FI 名称；下列历史表实际包含转为 FISV 后的日期。不能把页面旧代码标签当成该股在这些日期仍以 FI 交易的证明。

正文相关原文：

```text
Fiserv, Inc. (FI) NYSE 63.80 + 0.1 (+ 0.16 %) Updated at November 10, 2025 04:00PM Currency In USD

FI Historical Data
Date Range: Apply
Date Open Close Adj Close High Low Volume
November 19, 2025 61.52 61.17 61.17 61.98 60.38 5.09M
November 18, 2025 62.16 61.34 61.34 62.69 61.13 7.24M
November 17, 2025 63.56 62.7 62.7 64.2 62.41 5.47M
November 14, 2025 64 63.42 63.42 64.15 63.02 5.6M
November 13, 2025 64.85 64.53 64.53 66.95 64.37 9.27M
November 12, 2025 64.2 64.38 64.38 64.87 63.11 6.24M
November 11, 2025 63.6 64.26 64.26 64.47 62.84 5.51M
November 10, 2025 63.91 63.8 63.8 64.18 62.67 8.43M
November 07, 2025 60.95 63.7 63.7 63.84 60.95 14.16M
```

注意此表的列顺序是 `Open, Close, Adj Close, High, Low, Volume`，与来源 1 不同。2025-11-12 的 `Close` 和 `Adj Close` 均明确列为 **64.38**；它的完整 OHLC 与来源 1 一致。成交量只有缩略值，不能作为精确股数的独立确认。

## 修复可采用的直接表列值

```text
date        open   high   low    close  volume
2025-11-12  64.20  64.87  63.11  64.38  6241184
```

此行的完整 OHLCV 来自来源 1，来源 2 用于核对 OHLC 及其列示的复权收盘价。两个来源在相邻日的成交量存在差异，例如 11 月 13 日分别为 `9,261,325` 与 `9.27M`，因此保存时必须注明来源，不能伪标为 Yahoo/yfinance 原始数据。
