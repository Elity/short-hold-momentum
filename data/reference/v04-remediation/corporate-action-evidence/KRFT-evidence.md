# KRFT → KHC：终止权益与复权检查

核查日期：2026-09-07。此文件只提出数据与公司行动修复，不修改候选参数。

## 法律条款与交易日期

- SEC原Kraft 2015-07-02 Form 8-K，Item 2.01：每股KRFT转换为一股Kraft Heinz普通股；另有16.50美元特殊现金股息，权益人为合并前立即在册的Kraft股东。
- 同一8-K，Item 3.01：KRFT于2015-07-02营业结束时停止NASDAQ交易。
- 公司2015-07-02完成公告再次明确KRFT当日收盘停止，KHC于2015-07-06开始交易。7月3日为XNYS假期，因此执行器有效交易日为7月6日；法律完成日仍是7月2日，两者不混称。
- 原Kraft 2015-03-25 8-K披露合并协议与特殊现金股息；2015-06-22公司公告正式宣告16.50美元现金股息，附合并完成条件。建议action的announced_date=2015-03-25，known_date=2015-07-02。

主来源与本地快照：

1. https://www.sec.gov/Archives/edgar/data/1545158/000119312515244355/d36612d8k.htm （KRFT-sec-closing-8k.txt）
2. https://news.kraftheinzcompany.com/press-releases-details/2015/The-Kraft-Heinz-Company-Announces-Successful-Completion-of-the-Merger-between-Kraft-Foods-Group-and-HJ-Heinz-Holding-Corporation/default.aspx （KRFT-issuer-closing.txt）
3. https://news.kraftheinzcompany.com/press-releases-details/2015/Kraft-Foods-Group-Declares-Regular-Quarterly-Dividend-of-055-Per-Share-and-Conditional-Special-Cash-Dividend-of-1650-Per-Share/default.aspx （KRFT-special-dividend-declaration.txt）
4. https://www.sec.gov/Archives/edgar/data/1545158/000119312515105187/d895051d8k.htm （KRFT-sec-announcement-8k.txt）

## 16.50美元是否已经计入旧股回报

WIKI的KRFT共702行，2012-09-17至2015-07-02；终止日后没有报价，无须裁剪污染尾部。其最后普通分红为2015-04-08的0.55美元。在2015-04-08至2015-07-02整个区间，所有原始/复权OHLC逐值相同，adj_close/close恒为1；没有16.50美元特殊股息动作。此前因普通股息形成的复权折扣逐次解除，2014-12-23之后的系数为0.993815，4月8日后为1。故此处旧股不是已包含合并现金对价的总回报延续序列。

容易误判的一点：WIKI的KHC首行2015-07-06确实带有ex-dividend=16.50。但KHC归档没有该日以前的价格；这条事件没有为持有KRFT的账户生成跨证券回报，也没有把现金预先放入KRFT终值。继受股票以该日实际股价与对应复权因子转换后，必须再记录一次16.50美元现金应收，才能还原完整法律权益。不得把KHC首行股息再单独发现金，也不得构造含该现金的跨KRFT/KHC复权连续价格后又加公司行动现金。

数量检查：KRFT末日原始收盘88.19美元，KHC首日原始开盘71美元。每股旧股首日权益=71+16.50=87.50美元，较末日收盘约-0.7824%。当前Yahoo缓存KHC的首日复权开盘除以同日adjusted/nominal因子也恢复约71美元，因子中的后续普通分红不会让额外16.50美元被再计一次。

公司另宣布7月31日的0.55美元普通股息由KHC支付；这一项继续由继受行情总回报口径承担，不加入本次强制转换现金。

KRFT-price-audit.json保存数据SHA256、全部原KRFT分红日期、终止窗口系数检查、KHC首日数据和权益连续性检查。CSV窗口和audit_krft.py提供可复现明细。本检查只认证该终止事件不双算，不宣称WIKI所有历史普通股息已经完整核实。

## 建议登记

默认权益：1 KRFT → 1 KHC + 16.50美元现金应收。最后交易日2015-07-02；有效交易日2015-07-06；source_price_treatment=terminal_before_action。零股比率为1:1，没有因换股比率自身产生新零股，无需填造cash-in-lieu报价。

按已经固定的ADR-014，现金于有效交易日后的第5个XNYS交易日2015-07-13释放。这是统一模型，不能写为实际券商入账日。源报价不需要修剪，建议添加有证据的终止窗口上限2015-07-02，以便后续刷新也不能引入污染尾段。
