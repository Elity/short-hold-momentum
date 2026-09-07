# ATVI 2016-11-25 whole-row repair proposal

The selected complete IEX row is O37.45 / H37.58 / L37.20 / C37.22 / V3,206,319. JacksonCrow and SheepB both report the same OHLC to float precision and V3,206,300. They are two Yahoo/yfinance archive captures, not two independent vendors.

Across the 10 XNYS sessions before and after the date (2016-11-10 to 2016-12-09), both Yahoo captures agree with IEX on all OHLC within $0.011 on 20/20 neighboring sessions. Their largest relative volume difference from IEX is about 0.00917%. The target volume differs by only 19 shares; the entire IEX row is used without mixing fields.

Old WIKI is the outlier: nominal open36.52 is below low37.20. The bad value was already in the preserved old prefix. Current adjusted open=36.301142628845, low=36.977067518977. Using the existing constant canonical factor 0.994007191370356, the replacement adjusted open is 37.225569316820. Close, volume, as_traded_close and dollar_volume remain exactly unchanged. Newer Yahoo Adj Close fields are not imported.

The 2016-11-30 WIKI open also differs by $0.05 from IEX/Yahoo but is internally valid. That supplier difference is retained as evidence and is not part of this proposed repair.

Files: repair-proposal.json, audit.json, original-row.json, ATVI-2016-11-25.patch.csv, provider-target-and-20-neighbors.csv, and current-canonical-factor-window.csv. Root should verify that the final 2021 candidate still contains the original row/factor, then replace only this complete row and refresh hashes. No main manifest or candidate was modified, and no network requests were made.
