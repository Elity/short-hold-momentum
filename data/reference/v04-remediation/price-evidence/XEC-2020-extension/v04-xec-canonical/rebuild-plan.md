# XEC：等待确定 ledger 的有限构建准备

**两条 IEX 整行可用于已识别的旧前缀修复；接续数学已确定，但尚不构建或批准行情。** 本阶段只读取 `work/v04-xec-extension-preflight/` 的审计和原行副本，零网络；没有读取主仓完整行情或修改主仓。根节点仍负责发行人、单位、尾段报价以及具体现金事件的主证裁定。

## 两条整行核对

|日期|IEX O / H / L / C / V|用途|
|---|---|---|
|2015-08-28|104.84 / 110.29 / 104.84 / 107.75 / 1,537,283|替换原 WIKI O104.64 < L104.84 的整行|
|2017-11-08|125.58 / 127.89 / 121.25 / 125.34 / 1,480,059|补原前缀唯一缺日|

IEX 原成员副本 SHA256 为 `925dd82d168b5db014e908d3a70bb6cfd05e93cb0a0b1565324707dd86d466bb`，与 preflight 记录相符。两行价格区间有效；SheepB 的对应价格在浮点精度内一致。

2015-08-28 的 IEX **Close 和 Volume 与原 WIKI 完全相同**，其美元成交额仍为 **165,642,243.25**。因此整行换源可以修复 Open，同时逐值保留旧名义 Close、Volume 和 dollar_volume。其余旧前缀名义字段也必须逐值不变。2017-11-08 是新增缺日，名义 Close/Volume/成交额全部来自同一 IEX 行。

调整后的两行使用旧前缀原有每股单位：已有日取 `旧 canonical Close / 旧 as_traded_close`；缺日仅在前后已观察日的旧因子相等时沿用该因子。随后和其他旧行一起接受已确认事件的前置修正，不单独重置单位。

## 旧事件修正：固定 March 27 锚点

每个待裁定旧事件 e，以该日保留的名义 Close C 为基准：

```text
q_old = 1 + WIKI 原记录 D_old / C
q_verified = 1 + ledger 已核 D / C
对所有 date < e 的调整 OHLC 同乘 q_old / q_verified
```

这一操作把事件处因子跳变从 q_old 改为 q_verified，同时保持事件日及其后单位。多笔事件依次应用，相当于乘数相乘；**2018-03-27 的原 canonical 行保持不变**。名义 Close、Volume 和 dollar_volume 不因现金事件调整。

该公式不预设 **2017-09-14 的 $0.16** 是真还是假。若根节点主证确认没有该笔付款，可显式填 D=0；若未知，必须保留 null，不能以 0 代替未知。同理，2017-11-14、2018-02-14 以及八个尾段日期的金额都由根节点提供，脚本不读取诊断反推现金列来决定金额。

除两条明确换源/补日以及 ledger 指定事件产生的必要 pre-ex OHLC 倍率外，其他 WIKI 前缀列值保留原样，不重新构造整段历史。

## 尾段和输出范围

仅追加 **2018-03-28—2020-03-10 的 491 个原始 SheepB 整行**，从保留的 2018-03-27 canonical 因子出发：

```text
f_today = f_previous × (原 Close_today + ledger D_today) / 原 Close_today
调整 OHLC_today = 当天同一原源 OHLC × f_today
名义 Close = 原 Close；Volume = 原 Volume；美元成交额 = 原 Close × 原 Volume
```

不使用 SheepB 的旧 `Adj Close` 尺度，不补仓式分配普通股息现金，不为 2020-03-10 或 2021-08-19 建立终止事件。预期输出 **4,138 行 = 3,646 旧行 + 1 缺日 + 491 尾日**。

2020-03-10 原开盘约 **16.55999947** 作为正常排程下退出开盘报价保留；该日期仍只是固定排程锚点，修复后是否还有路径需要更晚报价，由根节点的固定研究确定。本脚本不自动扩展到 2021 年。

## 脚本接口和当前状态

`build_xec.py` 只向自身所在 work 目录输出 parquet 和 `build-audit.json`，不写主仓，不调用行情接口或自动应用 manifest。

调用方式：

```bash
/Users/fighting/code/short-hold-momentum/.venv/bin/python \
  /Users/fighting/Documents/Codex/2026-09-06/co-2/work/v04-xec-canonical/build_xec.py \
  --ledger /absolute/path/to/verified-xec-ledger.json
```

`ledger.pending.json` 是**不可执行的空金额模板**。根节点提供的正式 ledger 必须显式包含：

- `status: VERIFIED_FOR_WORK_BUILD`、固定 `snapshot_time`、XEC 身份/单位和正常退出报价证据；
- 每个事件的 `ex_date`、`cash`、`status: confirmed` 和来源说明；
- preflight 列出的三个争议旧日期及八个尾段日期全部作出明确决定。确认为无派息的日期可以写 0，未核金额不能写 0。

脚本仅检查输入完整性和数学，不代替根节点的证据审核，也不会把已填 `confirmed` 自动提升为应用许可。额外发现并确认的窗口内事件可加入 ledger；更晚价格、拆股或非现金公司行动需另行审查，不由这份有限脚本处理。

未来构建时，脚本才读取 preflight 已登记且固定哈希的完整 canonical/SheepB 文件；当前准备阶段没有读取这些主仓/外部目录行情。它会核对原输入哈希、两条整行、旧名义字段、原锚点、4,138 个完整 XNYS 日期、价量关系、每日现金总回报恒等式和 parquet 读回，输出仍标为 `WORK_CANDIDATE_REQUIRES_ROOT_REVIEW`。

本轮只完成语法检查和“pending ledger 在读取完整行情之前被拒绝”的验证，**未运行任何带猜测金额的构建，未生成价格候选，未新增测试框架**。
