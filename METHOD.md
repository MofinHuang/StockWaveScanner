# StockWaveScanner V3 — METHOD.md

## 1. 文件用途

本文件是 StockWaveScanner V3 的技術設計書 / 方法論。

本文件只記錄版本層級且長期有效的：

- 系統架構
- 資料架構
- 模型方法
- Domain 邊界
- 正式資料需求
- 正式資料來源
- 資料品質規則
- 已確認研究結論

本文件不記錄：

- 今日進度
- 下一步工作
- 單次 DEBUG 紀錄
- 單次 API 測試筆數
- 暫時性研究過程
- 某次專案工作的完成清單

目前進度與下一步請看：

```text
GO.md
```

除非發生下列情況，否則本文件不應頻繁修改：

```text
V3 → V4 等版本升級
核心模型規則大幅調整
Domain 架構大幅調整
資料架構大幅調整
主要 UI / Pipeline 架構改版
正式資料來源策略改變
```

---

## 2. Project Mission

StockWaveScanner 的目的不是：

```text
預測哪一檔股票一定會漲
```

而是：

```text
找出值得研究的股票，
並判斷目前價格結構是否適合行動。
```

核心原則：

> 分數用來找股票，價格結構用來決定行動。

---

## 3. Overall Model

正式個股 Overall 只包含：

```text
Fundamental
Chip
Technical
```

目前 Research Weight：

```text
Fundamental  30%
Chip         30%
Technical    40%
```

以下資料只做外部觀察：

```text
Sector
ETF
Analyst
News
Popularity
Financial Holding Domain
```

不得直接進 Overall。

---

## 4. Technical V2

Technical V1 經目前 Backtest 後淘汰。

目前保留：

```text
Technical V2
```

Technical V2：

```text
Trend Structure    35%
Price Position     40%
Momentum Quality   25%
```

主要概念：

### Trend Structure

```text
MA20 / MA60
Close / MA20
```

### Price Position

```text
Close / MA20
Close / MA20 ATR Position
```

### Momentum Quality

```text
5D Return
20D Return
Volume Ratio
```

Technical 高：

```text
不代表現在適合進場
```

進場仍由價格結構與 Stage 判斷。

---

## 5. Overall V2 / Stage V2

目前保留：

```text
Technical V2
Overall V2
Stage V2
```

仍屬：

```text
RESEARCH
```

不是最終 Production Model。

Stage V2：

```text
AVOID
WATCH
SETUP
READY
BREAKOUT
EXTENDED
WAITING_DATA
```

Stage 必須和：

```text
Overall
Buy Zone
Breakout
Risk
Price Position
```

共同解讀。

---

## 6. Trade Plan

主要欄位：

```text
buy_zone_low
buy_zone_high
distance_to_buy_zone_pct

breakout_price
breakout_distance_pct

risk_price
current_risk_pct

target_low
target_high

reward_risk_ratio
```

目前 Research 計算：

### Buy Zone

```text
Low  = MA20 - 0.25 ATR
High = MA20 + 0.50 ATR
```

### Risk Price

```text
Buy Low - 1.50 ATR
```

### Breakout

```text
前 20 個交易日 High 最大值
不包含當日
```

### Target

```text
Buy High + 2 ATR
~
Buy High + 3 ATR
```

Reward / Risk 必須：

```text
Risk > 0
Reward > 0
```

才計算。

目前：

```text
R/R 不控制 Stage
```

---

## 7. Ranking

### Research Priority

排序：

```text
Overall DESC
```

回答：

```text
哪些股票值得優先研究？
```

### Action Priority

排序：

```text
BREAKOUT
→ READY
→ SETUP
```

同一 Stage：

```text
Overall DESC
```

回答：

```text
哪些股票目前較接近可行動位置？
```

Research Priority 與 Action Priority 不可混在一起。

---

## 8. Data Architecture

正式資料流：

```text
External Sources
↓
GitHub Actions / Scripts
↓
Validate
↓
Normalize
↓
Turso
↓
Derived Metrics / Score
↓
Domain Export / UI Snapshot
↓
JSON
↓
GitHub Pages
```

前端：

```text
不得直接連 Turso
```

---

## 9. Turso vs JSON

### Turso

負責：

```text
原始標準化資料
歷史資料
跨日比較資料
Snapshot
可追溯資料
```

### JSON

負責：

```text
最新畫面資料
Derived Result
模型結果
Domain 結果
UI 顯示資料
```

核心原則：

```text
Turso = 歷史真相
JSON  = 畫面快照
```

---

## 10. Core Data Requirements

| Domain | 主要資料 | 最低歷史需求 | 更新頻率 | 主要用途 | Overall |
|---|---|---:|---|---|---|
| Stock Master | 股票基本資料 | Current | 低頻 / 每日檢查 | 股票識別 | 否 |
| Market Index | 大盤 OHLCV | 120 Trading Days | Daily | Market Context | 否 |
| Daily Price | 個股 OHLCV | 120 Trading Days | Daily | Technical / Trade Plan | 是 |
| Institutional | 三大法人 | 20+ Trading Days | Daily | Chip | 是 |
| TDCC | 股權分散 | Multiple Weeks | Weekly | Chip | 是 |
| Monthly Revenue | 月營收 | 24 Months | Monthly | Fundamental | 是 |
| Quarterly Financial | 季財報 | 8 Quarters | Quarterly | Fundamental | 是 |
| Sector | 產業 / 族群 Snapshot | 20+ Trading Days | Daily | 市場偏好 | 否 |
| Analyst | 公開 Metadata | Recent | Daily | 市場研究方向 | 否 |
| ETF Holdings | ETF 持股 Snapshot | 持續累積 | Daily | 大型組合調整 | 否 |
| Financial Holding | 金控專屬 KPI | 待正式定義 | Monthly / Quarterly | 金融業觀察 | 否 |

正式模型 Historical Backtest：

```text
Minimum   = 2 years
Preferred = 3–5 years
```

---

## 11. Core Data Fields

### 11.1 Stock Master

```text
stock_id
stock_name
market
security_type
industry_code
industry_name
listed_date
is_active
updated_at
```

用途：

```text
全市場 Universe
股票搜尋
產業分類
排除非目標商品
```

Stock Master 本身不計分。

### 11.2 Market Index

```text
trade_date
market
index_code
open
high
low
close
volume
turnover
```

用途：

```text
市場環境
市場風險背景
市場報酬比較
後續 Market Regime 研究
```

### 11.3 Daily Price

```text
stock_id
trade_date
open
high
low
close
volume
turnover
trade_count
```

Primary Key：

```text
(stock_id, trade_date)
```

由價格歷史計算：

```text
MA20
MA60
ATR
5D Return
20D Return
Volume Ratio
Price Position
Breakout
Buy Zone
Risk Price
Target Zone
Stage
```

### 11.4 Institutional

```text
stock_id
trade_date

foreign_buy
foreign_sell
foreign_net

trust_buy
trust_sell
trust_net

dealer_buy
dealer_sell
dealer_net

data_status
```

資料狀態必須保留：

```text
STORED
ZERO_INFERRED
INSUFFICIENT_DATA
```

### 11.5 TDCC

```text
stock_id
data_date
holder_level
holder_count
shares
percentage
```

Derived：

```text
Large Holder %
Retail Holder %
Large Holder WoW Change
Retail Holder WoW Change
```

TDCC 定位：

```text
中期籌碼結構確認
```

不是短線進場訊號。

### 11.6 Monthly Revenue

```text
stock_id
revenue_month
revenue
revenue_yoy
revenue_mom
cumulative_revenue
cumulative_yoy
source_date
```

最低歷史需求：

```text
24 Months
```

### 11.7 Quarterly Financial

```text
stock_id
fiscal_year
fiscal_quarter
source_date

revenue
gross_profit
operating_income
net_income
eps

gross_margin
operating_margin
net_margin
roe
```

最低歷史需求：

```text
8 Quarters
```

金融業財報 Schema 與一般產業不同，不得假設：

```text
Financial Holding
Banking
Insurance
Securities
```

可完全套用一般產業欄位。

---

## 12. Official Data Source Policy

正式資料來源優先順序：

```text
官方結構化 API / CSV
↓
官方頁面可解析資料
↓
其他經明確驗證來源
```

避免：

```text
未驗證第三方資料
以搜尋結果取代正式來源
把抓取失敗當成 0
以程式執行日期覆蓋官方資料日期
```

### 12.1 Core Market Sources

目前已驗證並使用的主要來源：

| Dataset | Market | 正式來源 |
|---|---|---|
| Stock Master | TWSE | TWSE OpenAPI |
| Stock Master | TPEx | MOPS Open Data CSV |
| Market Index | TWSE | TWSE OpenAPI / Monthly Query |
| Market Index | TPEx | TPEx OpenAPI / Monthly Query |
| Daily Price | TWSE | TWSE OpenAPI |
| Daily Price | TPEx | TPEx OpenAPI |
| Institutional | TWSE | TWSE T86 |
| Institutional | TPEx | TPEx OpenAPI |
| TDCC | All | TDCC OpenAPI |
| Monthly Revenue | TWSE | TWSE OpenAPI |
| Monthly Revenue | TPEx | MOPS Open Data CSV |
| Quarterly Financial - General | TWSE | TWSE OpenAPI |
| Quarterly Financial - General | TPEx | MOPS Open Data CSV |

主要 Endpoint：

```text
TWSE Stock Master
https://openapi.twse.com.tw/v1/opendata/t187ap03_L

TPEx Stock Master
https://mopsfin.twse.com.tw/opendata/t187ap03_O.csv

TWSE Current Index
https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST

TPEx Current Index
https://www.tpex.org.tw/openapi/v1/tpex_index

TWSE Daily Price
https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL

TPEx Daily Price
https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes

TWSE Institutional
https://www.twse.com.tw/rwd/zh/fund/T86

TPEx Institutional
https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading

TDCC
https://openapi.tdcc.com.tw/v1/opendata/1-5

TWSE Monthly Revenue
https://openapi.twse.com.tw/v1/opendata/t187ap05_L

TPEx Monthly Revenue
https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv

TWSE Quarterly Financial - General
https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci

TPEx Quarterly Financial - General
https://mopsfin.twse.com.tw/opendata/t187ap06_O_ci.csv
```

### 12.2 Data Source Validation

Collector 不可只判斷：

```text
HTTP 200
```

至少驗證：

```text
Connection Success
Payload Not Empty
Parse Success
Expected Schema
Expected Minimum Rows
Required Fields
```

必要時再驗證：

```text
Official Date
Date Range
Payload Size
Duplicate Keys
Business Semantics
```

---

## 13. Missing Data / Data Quality

不得：

```text
Missing → 0
```

必須區分：

```text
Valid Zero
Source Missing
Source Empty
Parse Error
Network Error
Insufficient History
WAITING_DATA
```

資料品質問題不得被誤認為股票品質差。

所有同步程序必須可安全重跑。

例如：

```text
stock_price_daily
→ (stock_id, trade_date)

institutional_daily
→ (stock_id, trade_date)

tdcc_distribution
→ (stock_id, data_date, holder_level)

etf_holding_daily
→ (trade_date, etf_id, stock_id)
```

GitHub Actions Retry / Manual Retry 不得產生 Duplicate。

---

## 14. Sector Domain

資料表：

```text
sector_master
stock_sector_rel
sector_snapshot_daily
```

正式 Script：

```text
scripts/sync_v3_industry_sector.py
scripts/build_v3_sector_snapshot.py
scripts/export_v3_sectors.py
```

JSON：

```text
docs/data/latest/sectors.json
```

族群用途：

```text
判斷目前市場資金偏好哪些產業方向
```

主要指標：

```text
1D Return
5D Return
20D Return
Technical Strength
Breadth
Foreign
Trust
Dealer
Large Holder Change
Above MA20 Ratio
New High Count
```

Sector Domain 不得直接加入 Overall。

---

## 15. Analyst Domain

### 15.1 Purpose

分析師頁用途：

```text
整理公開來源中，市場專業人士近期發布了哪些研究內容。
```

分析師提及不得直接轉成個股加分。

### 15.2 Tables

```text
analyst_master
analyst_source
analyst_comment
analyst_comment_stock
analyst_comment_sector
analyst_comment_factor
```

關係：

```text
analyst_master
↓
analyst_source
↓
analyst_comment
├─ analyst_comment_stock
├─ analyst_comment_sector
└─ analyst_comment_factor
```

`analyst_source` 唯一性：

```text
UNIQUE (analyst_id, source_url)
```

### 15.3 Current Analysts

```text
A001 鐘崑禎
A002 王倚隆
A003 黎志建
A004 陳於晨
A005 林睿閎
```

### 15.4 Source Rule

允許來源類型：

```text
YOUTUBE
PODCAST
WEBSITE
OTHER
```

目前 V1 已實作：

```text
YOUTUBE
```

來源必須公開、可追溯並保留原始 URL。

### 15.5 Content Governance

內容治理原則：

```text
SUMMARY_ONLY
```

可以保存：

```text
來源
標題
發布日期
來源 URL
作者
Metadata
Structured Result
StockWaveScanner 自有摘要
```

不永久保存：

```text
完整文章
Full Transcript
完整字幕
完整 Caption
完整影片內容
```

若未來進行 Transcript：

```text
取得內容
↓
暫時處理
↓
產生 Structured Result
↓
丟棄原始 Transcript
```

### 15.6 Analyst V1

目前 V1 主要呈現：

```text
分析師
日期
YouTube 標題
來源
原始影片連結
```

時間篩選：

```text
今日
3 日
7 日
30 日
全部
```

不得只依影片標題自動判斷：

```text
推薦
買進
賣出
看多
看空
```

僅被提及不代表推薦。

Transcript / Whisper / 深度內容分析延後至後期。

目前不使用 OpenAI 或相關外部 LLM 進行 Analyst Transcript 分析。

Analyst Domain 不直接影響 Overall。

---

## 16. ETF Domain

### 16.1 Purpose

ETF Domain 用途：

```text
追蹤指定 ETF 的持股 Snapshot 變化
```

觀察：

```text
目前持股
新進
持股增加
持股減少
剔除
多檔 ETF 的共同持股變化
```

不是：

```text
ETF 資金流入流出頁
```

也不能把 Snapshot 差異直接解讀成：

```text
ETF 已確認的實際買進 / 賣出交易
```

### 16.2 Current ETF Scope

V1 固定追蹤：

```text
0050
0056
00878
00919
00929
00981A
009816
```

目前不主動擴充其他 ETF。

### 16.3 Official Source Rule

ETF Holdings 僅使用各投信官方公開來源：

```text
0050   → 元大投信
0056   → 元大投信
00878  → 國泰投信
00919  → 群益投信
00929  → 復華投信
00981A → 統一投信
009816 → 凱基投信
```

不得以第三方網站取代正式持股來源，除非未來另有明確決策。

### 16.4 Tables

```text
etf_master
etf_holding_daily
```

`etf_master`：

```text
etf_id
etf_name
issuer_name
source_type
source_url
active
sort_order
created_at
updated_at
```

`etf_holding_daily`：

```text
trade_date
etf_id
stock_id
stock_name
shares
weight_pct
market_value
source_url
created_at
```

Primary Key：

```text
(trade_date, etf_id, stock_id)
```

Indexes：

```text
(etf_id, trade_date)
(stock_id, trade_date)
```

### 16.5 Snapshot Date Rule

`trade_date` 代表：

```text
官方 PCF / 持股基準日 / Snapshot Date
```

不是：

```text
程式執行日期
```

官方日期可能為下一交易日生效日期，因此不得強制改成「今天」。

### 16.6 Snapshot Completeness

若官方來源回傳明顯不完整資料：

```text
Reject Snapshot
```

不得讓不完整 Snapshot 覆蓋正常歷史資料。

每檔 ETF 應具有合理最低持股筆數檢查。

### 16.7 Change Semantics

正式狀態：

```text
NEW
INCREASE
DECREASE
REMOVED
UNCHANGED
```

UI：

```text
NEW       = 新進
INCREASE  = 持股增加
DECREASE  = 持股減少
REMOVED   = 剔除
UNCHANGED = 無變化
```

不得使用：

```text
買進
賣出
```

來描述 Snapshot 差異。

### 16.8 Comparison Metric

若前後 Snapshot 都有：

```text
shares
```

優先使用：

```text
SHARES
```

若官方來源只提供：

```text
weight_pct
```

則使用：

```text
WEIGHT
```

UI 必須明確區分持股數變化與權重變化。

### 16.9 Comparison Period

V1 提供：

```text
1D
5D
20D
```

目前 Export 使用不同 Snapshot 日期：

```text
1D  → 至少 2 個不同日期 Snapshot
5D  → 至少 6 個不同日期 Snapshot
20D → 至少 21 個不同日期 Snapshot
```

歷史資料不足時：

```text
available = false
```

仍可顯示：

```text
目前持股
```

但不能標示為：

```text
當日異動
```

ETF 歷史資料採 Daily Workflow 自然累積，不人工製造歷史 Snapshot。

### 16.10 ETF Production Flow

Schema / Seed：

```text
scripts/init_v3_etf_schema.py
scripts/seed_v3_etf_master.py
```

Daily Sync：

```text
scripts/sync_v3_etf_holdings.py
```

Export：

```text
scripts/export_v3_etfs.py
```

正式流程：

```text
Official ETF Sources
↓
scripts/sync_v3_etf_holdings.py
↓
Turso DEV
↓
etf_holding_daily
↓
scripts/export_v3_etfs.py
↓
docs/data/latest/etfs.json
↓
scripts/build_v3_ui_snapshot.py
↓
docs/data/latest/v3_ui.json
↓
GitHub Pages
```

ETF Domain 不直接影響 Overall。

---

## 17. Financial Holding Domain

金控股與一般電子股的解讀方式不同。

一般資料可沿用：

```text
Price
Institutional
TDCC
Financial Report
```

未來可建立：

```text
financial_holding_monthly
```

候選觀察：

```text
Monthly Profit
Monthly EPS
YTD Profit
YTD EPS
ROE
Dividend
Yield
Institutional
Business Type
Interest Rate Environment
FX Environment
Bond Environment
Market Turnover
```

可能類型：

```text
銀行型
壽險型
證券型
綜合型
```

不同類型未來可使用不同觀察重點。

金控股 Domain：

```text
不得直接硬套一般電子股的解讀方式
```

目前尚未正式定稿 Schema 與 Score。

金融業專屬資料來源也需在此 Domain 建置時再正式驗證。

---

## 18. Domain JSON

目前 Domain JSON：

```text
docs/data/latest/v3_ui.json
docs/data/latest/sectors.json
docs/data/latest/analysts.json
docs/data/latest/etfs.json
```

未來：

```text
docs/data/latest/financial_holdings.json
```

原則：

```text
Domain JSON 保持可獨立檢查
前端目前統一以 v3_ui.json 為主要入口
```

避免建立無限制增長的大型單一 JSON。

---

## 19. UI Architecture

主要導航：

```text
首頁
排行
市場
我的
```

市場：

```text
族群資金
分析師觀點
ETF 持股異動
金控股觀察
```

我的：

```text
Watchlist
Holdings
```

個股明細不是主導航頁，而是所有股票入口共用的 Detail View。

---

## 20. GitHub Actions Architecture

### Daily Incremental DEV

```text
Daily Incremental
↓
Official Industry Sector Sync
↓
Sector Snapshot
↓
ETF Holdings Sync
```

### V3 UI DEV

```text
Export V2 Base Snapshot
↓
Build V2 Score
↓
Export V3 Sector
↓
Export V3 ETF
↓
Build V3 UI Snapshot
↓
GitHub Pages
```

所有開發與目前正式驗證均使用：

```text
stockwave-dev
```

未經明確要求不得操作：

```text
stockwave-prod
```

---

## 21. Backtest Boundary

目前：

```text
Technical V2
Overall V2
Stage V2
```

已通過目前可用歷史資料的初步比較，但仍不是最終 Production Model。

目前已知限制：

- 有效歷史期間仍短
- Forward Window 有重疊
- 月營收存在可用日期 Proxy
- 部分季財報使用 Research Proxy
- 尚未完整加入市場相對報酬
- 尚未加入交易成本
- 尚需更多歷史資料驗證

因此不得因單日 Snapshot 分布直接修改：

```text
Technical Score
Overall Weight
Stage Threshold
```

任何模型調整應遵循：

```text
建立 Candidate
↓
Historical Backtest
↓
Robustness Check
↓
確認後再更新 Research Model
```

---

## 22. Final Model Boundary

```text
個股
→ Fundamental / Chip / Technical

族群
→ 市場偏好

分析師
→ 市場研究方向

ETF
→ 大型組合持股 Snapshot 變化

金控
→ 金融業專屬資訊

Stage / Trade Plan
→ 價格結構與風險
```

不得建立：

```text
所有東西加在一起的超級總分
```

最終維持：

> 分數用來找股票，價格結構用來決定行動。

並補充：

> 族群看市場資金偏好，ETF 看大型組合持股變化，分析師看市場研究方向，金控股使用金融業專屬觀察方式；這些資訊提供研究背景，不直接改變個股 Overall Score。
