# StockWaveScanner V2.1 - Data Source Verification

> Version: V2.1
>
> Verification Date: 2026-09-12
>
> Purpose: 驗證 StockWaveScanner V2 所需官方資料來源是否可取得、可解析，並判斷是否適合作為 Production Data Pipeline 的主要來源。
>
> Requirement Reference: `DATA_REQUIREMENT_MATRIX.md`

---

# 1. Verification Principle

資料來源只有在實際測試成功後，才能標記為 VERIFIED。

驗證至少包含：

1. Official Source
2. Connection
3. Parse
4. Record Count
5. Required Fields
6. Whole-market / Batch Capability
7. Historical Capability
8. Production Suitability

正式資料流程原則：

```text
Official
↓
Whole-market / Batch
↓
Structured JSON / CSV
↓
Validate
↓
Normalize
↓
Turso Historical Core

避免將：

Per-stock × 2000 requests
HTML scraping
Browser automation

作為 Production Daily Pipeline 的主要架構。

2. Verification Result

本次建立：

scripts/verify_data_sources.py

一次驗證主要官方資料來源。

2026-09-12 實測結果：

PASS : 15
WARN : 0
FAIL : 0
3. Verification Summary
Dataset	Market	Source	Result
Stock Master	TWSE	TWSE OpenAPI	VERIFIED
Stock Master	TPEx	MOPS Open Data CSV	VERIFIED
Market Index Current	TWSE	TWSE OpenAPI	VERIFIED
Market Index Historical	TWSE	TWSE Monthly Query	VERIFIED
Market Index Current	TPEx	TPEx OpenAPI	VERIFIED
Market Index Historical	TPEx	TPEx Monthly Query	VERIFIED
Daily Price	TWSE	TWSE OpenAPI	VERIFIED
Daily Price	TPEx	TPEx OpenAPI	VERIFIED
Institutional	TWSE	TWSE T86	VERIFIED
Institutional	TPEx	TPEx OpenAPI	VERIFIED
TDCC	All	TDCC OpenAPI	VERIFIED
Monthly Revenue	TWSE	TWSE OpenAPI	VERIFIED
Monthly Revenue	TPEx	MOPS Open Data CSV	VERIFIED
Quarterly Financial - General	TWSE	TWSE OpenAPI	VERIFIED
Quarterly Financial - General	TPEx	MOPS Open Data CSV	VERIFIED
4. Stock Master - TWSE

Status:

VERIFIED

Source:

TWSE OpenAPI

Endpoint:

https://openapi.twse.com.tw/v1/opendata/t187ap03_L

Format:

JSON

2026-09-12 Result:

records = 1094
first = 1101 台泥

Required fields confirmed:

公司代號
公司名稱
公司簡稱
產業別
上市日期
已發行普通股數或TDR原股發行股數

Production Decision:

PRIMARY
5. Stock Master - TPEx

Status:

VERIFIED

Preferred Source:

MOPS Open Data

Endpoint:

https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv

Format:

CSV

2026-09-12 Result:

records = 891
first = 1240 茂生農經

Required fields confirmed:

公司代號
公司名稱
公司簡稱
產業別
上櫃日期
已發行普通股數或TDR原股發行股數

Production Decision:

PRIMARY
6. TPEx Stock Master OpenAPI Note

Alternative Endpoint:

https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O

此 API 為官方來源，但 Windows 環境實測曾發生：

Connection Reset
Incomplete Payload
TLS close_notify issue

Server 曾回：

HTTP 200
Content-Length = 1072022

但實際只下載：

15992 bytes

因此：

HTTP 200
≠
Payload Complete

Production Decision:

NOT PRIMARY

TPEx Stock Master 正式優先使用：

MOPS CSV
7. Market Index - TWSE Current

Status:

VERIFIED

Endpoint:

https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST

Format:

JSON

2026-09-12 Result:

records = 9
range = 1150901 .. 1150911

Fields:

Date
OpeningIndex
HighestIndex
LowestIndex
ClosingIndex

用途：

Daily Incremental
Current Month
Market Regime
8. Market Index - TWSE Historical

Status:

VERIFIED

Endpoint Pattern:

https://www.twse.com.tw/indicesReport/MI_5MINS_HIST
    ?response=json
    &date=YYYYMM01

2026-07 Test:

stat = OK
records = 22
first = 115/07/01
last = 115/07/31

用途：

Historical Backfill
2–5 Year Backtest
9. Market Index - TPEx Current

Status:

VERIFIED

Endpoint:

https://www.tpex.org.tw/openapi/v1/tpex_index

Format:

JSON

2026-09-12 Result:

records = 9
range = 20260901 .. 20260911

Fields:

Date
Open
High
Low
Close
Change

用途：

Daily Incremental
Current Month
Market Regime
10. Market Index - TPEx Historical

Status:

VERIFIED

Endpoint:

https://www.tpex.org.tw/www/zh-tw/indexInfo/inx

Method:

POST

Parameters:

date = yyyy/mm/01
response = json

Example:

date = 2026/07/01

2026-07 Result:

stat = ok
month = 115/07
records = 22
first = 2026/07/01
last = 2026/07/31

Fields:

日期
開市
最高
最低
收市
漲/跌

Historical page indicates data available from:

1999-09

用途：

Historical Backfill
2–5 Year Backtest
11. Daily Price - TWSE

Status:

VERIFIED

Endpoint:

https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL

Format:

JSON

2026-09-12 Result:

records = 1379

Confirmed sample fields:

Date
Code
Name
TradeVolume
TradeValue
OpeningPrice

Expected V2 Normalize fields:

stock_id
trade_date
open
high
low
close
volume
turnover
trade_count

Production Use:

Daily Batch Price Update

Important:

Historical backfill strategy仍需與歷史官方查詢來源一起設計。

不使用：

2000 stocks × per-stock request

作為 Production Daily Pipeline。

12. Daily Price - TPEx

Status:

VERIFIED

Endpoint:

https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes

Format:

JSON

2026-09-12 Result:

records = 11193

Sample fields:

Date
SecuritiesCompanyCode
CompanyName
Close
Change
Open

重要：

11193 records

明顯不只是單一交易日股票數。

因此在正式 Historical Migration 前，需要由程式進一步 Audit：

Distinct Trade Dates
Date Range
Records Per Date
Duplicate Key

Status:

SOURCE VERIFIED
SEMANTIC RANGE AUDIT PENDING

這不是阻擋 Turso Schema 設計的問題，但在正式 Backfill 前必須確認。

13. Institutional - TWSE

Status:

VERIFIED

Historical Query:

https://www.twse.com.tw/rwd/zh/fund/T86

Test Date:

2026-09-11

Result:

records = 1330
fields = 19

用途：

Foreign
Investment Trust
Dealer

V2 必須 Normalize：

foreign_buy
foreign_sell
foreign_net

trust_buy
trust_sell
trust_net

dealer_buy
dealer_sell
dealer_net

並保留：

STORED
ZERO_INFERRED
INSUFFICIENT_DATA

資料語意。

14. Institutional - TPEx

Status:

VERIFIED

Endpoint:

https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading

2026-09-12 Result:

records = 894

Confirmed fields include:

Date
SecuritiesCompanyCode
CompanyName

Foreign Investors Buy
Foreign Investors Sell
Foreign Investors Difference

Foreign Dealers Buy
Foreign Dealers Sell
...

後續 Normalize 必須將 TPEx 英文欄位映射成 V2 統一欄位。

Historical backfill method仍需在 Migration Phase 驗證。

15. TDCC Shareholding Distribution

Status:

VERIFIED

Endpoint:

https://openapi.tdcc.com.tw/v1/opendata/1-5

Dataset:

集保戶股權分散表

2026-09-12 Result:

records = 68867

Confirmed fields:

證券代號
占集保庫存數比例%
人數
資料日期
股數
持股分級

V2 Normalize:

stock_id
data_date
holder_level
holder_count
shares
percentage

Derived Features:

Large Holder %
Retail Holder %

Large Holder WoW Change
Retail Holder WoW Change

Important:

V1 已有 TDCC Historical Backfill。

因此：

DO NOT REDOWNLOAD HISTORICAL TDCC

直到 V1 DB Audit 完成。

16. Monthly Revenue - TWSE

Status:

VERIFIED

Endpoint:

https://openapi.twse.com.tw/v1/opendata/t187ap05_L

2026-09-12 Result:

records = 1070
month = 11508

Confirmed fields:

資料年月
公司代號
營業收入-當月營收
營業收入-去年同月增減(%)

V2 needs at least:

24 months

Derived:

Revenue YoY
Revenue MoM
3M Revenue YoY
Cumulative YoY
Growth Acceleration
17. Monthly Revenue - TPEx

Status:

VERIFIED

Endpoint:

https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv

Format:

CSV

2026-09-12 Result:

records = 891
month = 11508

Required fields verified.

Production Decision:

PRIMARY
18. Quarterly Financial - TWSE General Industry

Status:

VERIFIED

Endpoint:

https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci

2026-09-12 Result:

records = 1048

Sample fields:

出表日期
年度
季別
公司代號
公司名稱
營業收入
營業成本
原始認列生物資產及農產品之利益（損失）
19. Quarterly Financial - TPEx General Industry

Status:

VERIFIED

Endpoint:

https://mopsfin.twse.com.tw/opendata/t187ap06_O_ci.csv

2026-09-12 Result:

records = 883

Sample fields:

出表日期
年度
季別
公司代號
公司名稱
營業收入
營業成本
原始認列生物資產及農產品之利益（損失）
20. Financial Data Limitation

目前只完成：

General Industry

財報不能直接假設所有公司使用完全相同 Schema。

後續仍需處理：

Financial Holding
Banking
Insurance
Securities / Futures
Other Special Financial Reporting Types

因此目前：

Financial Source = VERIFIED
Full Financial Normalization = PENDING

在完整 Mapping 完成前：

Fundamental Score

不得假裝已涵蓋全部公司。

21. Industry Data

Stock Master 已確認包含：

industry_code

但正式：

industry_code
→
industry_name

Mapping 尚未完成。

Status:

PENDING

後續 Industry Feature 候選：

Industry Relative Strength
Industry Breadth
Industry Momentum
Peer Comparison
22. Analyst Digest

Research Channels:

老王股票
鐘崑禎 / WE178

Status:

PENDING

原則：

Public Information Only
No Full Video Storage
No Audio Storage
No Full Transcript Storage

Analyst Mention:

DOES NOT DIRECTLY INCREASE STOCK SCORE

只作：

Analyst Attention = TRUE

與 StockWaveScanner 模型交叉研究。

23. HTTP Data Quality Rules

V2 Collector 不可只判斷：

HTTP 200

所有資料抓取至少必須驗證：

HTTP / Connection Success
Payload Not Empty
Parse Success
Expected Schema
Expected Minimum Rows
Required Fields

必要時再驗證：

Date Range
Expected Payload Size
Duplicate Keys

TPEx Stock Master OpenAPI 已證明：

HTTP 200

仍可能伴隨：

Incomplete Payload
24. Missing Data Rules

不得：

Missing
→
0

必須區分：

Valid Zero
Missing
Empty Source
Parse Error
Network Error
Insufficient History

尤其 Institutional 必須維持：

STORED
ZERO_INFERRED
INSUFFICIENT_DATA
25. Incremental Update Plan

Trading Day:

Stock Master Snapshot Check
Market Index
Daily Price
Institutional

Weekly:

TDCC

Monthly:

Revenue

Quarterly:

Financial
26. Historical Requirement

Feature Warm-up:

Minimum = 120 Trading Days

Backtest:

Minimum = 2 Years
Preferred = 3–5 Years

Historical Backfill 不應每天重新下載。

流程：

Initial Historical Backfill
↓
Turso Historical Core
↓
Daily Incremental Delta
27. V1 Historical Data

Archive:

StockWaveScanner_V1_Data_Archive_20260912

Includes:

stocks.db
stocks_before_tdcc_backfill_20260910.db
stocks-db.zip

V1 資料需先 Audit，再決定 Migration。

優先評估：

Price
Institutional
TDCC

Current Stock Master 可直接從新的官方 V2 Source 重建。

28. Automated Verification Tool

File:

scripts/verify_data_sources.py

Execution:

.\.venv\Scripts\python.exe .\scripts\verify_data_sources.py

2026-09-12 Result:

PASS : 15
WARN : 0
FAIL : 0

此工具保留於 V2 repository。

用途：

Development Environment Verification
API Change Verification
New Server Verification
GitHub Actions Troubleshooting
Data Source Health Check
29. Phase 2 Result

Verified:

Stock Master
Market Index
Daily Price
Institutional
TDCC
Monthly Revenue
Quarterly Financial - General

Still Pending:

TPEx Daily Price Semantic Range Audit
Full Financial Type Mapping
Industry Code Mapping
Analyst Digest Source Design
Historical Migration Audit

這些項目不阻止進入 Turso Schema Design。

30. Next Phase

下一階段：

Phase 3
Turso V2 Schema Design

Initial Core Tables:

stock_master
market_index_daily
stock_price_daily
institutional_daily
tdcc_distribution
monthly_revenue
quarterly_financial
sync_state

設計原則：

Normalized
Idempotent
Incremental Friendly
Historical Backtest Friendly
DEV First
Production Later

所有 Schema 先建立於：

stockwave-dev

DEV 驗證成功後，才套用至：

stockwave-prod

存檔後，**這一步只執行**：

```powershell
git status

我預期仍然是：

Untracked files:
    DATA_SOURCE_VERIFICATION.md
    scripts/

只是這時候兩個檔案內容都正式定稿了。