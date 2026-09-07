# FL 股息和 2021 Q2 股份主证据补充

**所请求的两组主证据均已取得。** 本轮仅使用 3 次新查询/获取，未访问既有 SEC 403 路径或已超时的 2021 年报 URL。全部文件在本目录；没有修改 root 的 FL 工作文件、行情、manifest 或代码。

## 2017 年 11 月声明的 $0.31 股息

发行人原始发布路径：<https://www.footlocker-inc.com/ns/pdfs/2017/4Q17-Dividend-Release.pdf>。本轮取得其搜索索引全文，保存为 `2017Q4-issuer-dividend-indexed.txt`；没有下载该 PDF。索引的标题错误显示“May 11, 1998”，但正文明确如下：

> NEW YORK, NY, November 15, 2017 ... declared a quarterly cash dividend ... of $0.31 per share, which will be payable on February 2, 2018 to shareholders of record on January 19, 2018.

同日发行人通过 PRNewswire 发布的原文与之完全一致：<https://www.prnewswire.com/news-releases/foot-locker-inc-declares-quarterly-dividend-of-031-per-share-300557094.html>，署名 `News provided by Foot Locker, Inc.`，时间 **2017-11-15 15:30 ET**；全文索引保存为 `2017Q4-company-release-prnewswire-indexed.txt`。

因此这笔股息可直接使用 **$0.31 / 声明 2017-11-15 / record 2018-01-19 / payable 2018-02-02**。金额来自单笔主文，不需要从全年 $1.24 总额反推。主文没有明确写 ex-date，也没有在本次声明中证明实际到账日；这两项不应伪装成已由该声明直接证明。

## 2021 Q2 原始 10-Q

发行人原始文件：<https://investors.footlocker-inc.com/static-files/a3da522c-cb46-4718-971a-df6b3f306d9e>。

匿名取得 HTTP 200，**实际格式为 RTF**，199,125 字节，SHA256 `a06ac2f937c9973c593ab91537e7feba6fbd4ce61c3060a90e00a81018785827`。保存为 `03-FL-2021Q2.body`，以 macOS `textutil` 离线转出 `03-FL-2021Q2.txt` 和空白归一文本。此 URL 与 root 已超时的 2021 年报 URL 不同；未重试后者。

报告截至 **2021-07-31**。第 4 页提供完整 Q2 和 H1 股份权益变动表，股份单位为千股：

|项目|Q2|H1|
|---|---:|---:|
|期初已发行普通股|104,286|103,693|
|Restricted stock issued|+11|+479|
|Issued under director and stock plans|+219|+344|
|期末已发行普通股|104,516|104,516|
|期初库存股|−887|−74|
|Tax withholding|−3|−195|
|Repurchases|−125|−746|
|ESPP reissued|+301|+301|
|期末库存股|−714|−714|

两组已发行股和库存股加减均精确对账；表中没有拆股或反向拆股项目。已发行股不能误称为流通在外股数：7 月 31 日两者相减约为 **103,802 千股**。

报告封面另给出 **2021-09-03 流通在外普通股 103,807,679 股**。这一后续日期的股数仍与 7 月末处于同一尺度，支持终点后的单位连续性；但封面余额不是完整的 8 月股份流水。严格证据范围是：完整表证明 2021 H1/Q2 的股数变化由普通发行、回购和税款交回解释；9 月初余额提供后续尺度佐证，不能被写成已取得 8 月每一笔股份变动。

该完整报告可与 root 已有的 2020 年报 2018—2020 股数表合并核验。这里只补主证据，不替 root 宣布价格尾段或研究门槛通过。

`facts.json` 包含字段、来源、哈希和加减核对；`2021Q2-equity-excerpt.txt` 保留完整权益表段落；`request-log.json` 记录 3 次操作。原始 RTF 及提取文本均保留，便于 root 复核。
