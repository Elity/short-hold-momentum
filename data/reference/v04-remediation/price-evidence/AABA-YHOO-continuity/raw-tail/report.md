# AABA 2017 年更名后原始报价候选

结论：线索中的单文件确实存在，已取得并固定版本；**2017-06-19 至 2017-12-29 的 136 个交易日全部有完整、有效 OHLCV**。本轮只交付原始候选和审计，没有复权拼接、修改仓库或部署。

## 实际来源和版本

取得的是作者 **szrlee** 的公开 GitHub 项目，而非未经核实的 Kaggle 版本：

- 仓库：[szrlee/Stock-Time-Series-Analysis](https://github.com/szrlee/Stock-Time-Series-Analysis)
- 文件：`data/AABA_2006-01-01_to_2018-01-01.csv`
- GitHub 文件最近修改提交：`55639c5cfa7556c4372ff361c026acb792bfdcf4`，2018-01-11 06:14:03 UTC。
- [固定提交的原始 CSV](https://raw.githubusercontent.com/szrlee/Stock-Time-Series-Analysis/55639c5cfa7556c4372ff361c026acb792bfdcf4/data/AABA_2006-01-01_to_2018-01-01.csv)
- 原始文件 SHA256：`219a6434d20f717ed921a8335ff9b3c9ca9d04b0c0b0e266db010cb922c040eb`，145,792 字节。

同一提交下的 `data_collection.ipynb` 已下载并只读解析，没有运行。采集代码明确：

```python
data = pdr.DataReader(ticker, 'google', start, end)
data['Name'] = ticker
```

日期参数为 2006-01-01 至 2018-01-01，作者注明的上游是 **Google Finance，经 pandas_datareader 采集**。`Name=AABA` 是采集脚本添加的标签，也用于更名前历史；历史证券身份依照前一份 SEC 专项确认，不把该标签当作当年实际交易代码。

搜索结果及其他公开 notebook 将该数据和用户提示的 Kaggle slug 关联，但本轮没有取得 Kaggle 元数据或版本号。因此版本事实是 **GitHub 固定提交和内容哈希**，不声称已验证某个 Kaggle v1/v2。没有执行 Yahoo 刷新。

## 实际内容与请求区间

原始文件实际为 **3,019 行，2006-01-03 至 2017-12-29**，列为 `Date, Open, High, Low, Close, Volume, Name`。没有 `Adj Close`、分红或拆股列。

请求尾段已原样切出：

| 日期 | Open | High | Low | Close | Volume |
|---|---:|---:|---:|---:|---:|
| 2017-06-19 | 54.00 | 55.03 | 53.80 | 54.46 | 39,430,343 |
| 2017-12-29 | 69.79 | 70.13 | 69.43 | 69.85 | 6,613,070 |

这 136 行覆盖全部相应 XNYS 交易日，无重复、缺口、非正价格、无效高低关系或无效成交量。2017 年最后一个交易日为 12 月 29 日；文件名中的 2018-01-01 是查询结束参数，不是实际报价日。

原始候选：

- `AABA-2017-06-19-to-2017-12-29.raw-candidate.csv`
- `AABA-2017-06-19-to-2017-12-29.raw-candidate.parquet`
- 尾段 Parquet SHA256：`1bbe90f4d5467505946ea8e6fb2bc77884ada785cbdd3db698c9d7f604c93ee1`。

2017-12-29 是此数据集的采集终点，不是 AABA 的证券终止日；69.85 不能自动成为强制退出或清算价。

## 原文件的旧缺陷与 WIKI 重叠

完整原 CSV 在请求范围之前存在两处结构问题：**2010-04-01 缺行**；**2011-08-02 Open 12.96 高于 High 12.94**。已保留并单独记录，不使用这些记录替换既有 WIKI 前缀，也不将全文件标为无缺陷。

与已有 WIKI YHOO 共 2,883 个交易日重叠。最近 2017 年重叠 115 行，名义价位整体一致，但并非逐字段相同：Open 最大差 .22，Close 最大差 .0092；成交量存在较大供应商差异。详细统计和全部原始对应行均已保存。

更名边界：WIKI 的 2017-06-16 Close 为 **52.5892**，此 Google 源同日 Close 为 **52.58**，差约 **1.75 bps**。新源 6 月 19 日 Open 为 **54.00**。这支持接续价格处于相同名义尺度，但不能为了消除小差异而任意缩放历史或替换某日成交价。

## 本轮没有证明的事项

- 文件没有公司行动列，**尚未完成 2017 年下半年完整分红/拆股主证审计**，也没有确定最终复权接续实现。
- 采集 notebook 明确注明 Google 上游，但本轮没有再用另一份独立报价逐行核对新增尾段。
- 136 行覆盖真实年内交易日，仍需现行策略排程确认每笔实际出场所需日期；没有因指数移除创建现金事件或下单。

因此本轮状态为 `RAW_TAIL_CANDIDATE_VERIFIED_NOT_CANONICALIZED_NOT_APPLIED`。前一份身份审计中“更名后无本地报价”的状态现在已有这条新候选补充，尚未升级为已部署价格。

复现与审计入口为 `audit_raw_candidate.py`、`audit.json`、`collection-notebook-provenance.json`、`overlap-statistics.json` 和 `2017-06-rename-boundary-observations.csv`。原始 CSV 与 notebook 完整保留。

定向公开请求 **4/4**：文件搜索、GitHub 提交元数据、固定提交单 CSV、同提交采集 notebook。后三次均 HTTP 200、未跟随重定向；无注册、付费、访问绕过或新的行情供应商查询。审计脚本不联网，主仓库/manifest 未修改，未运行回测。
