# StockWaveScanner V2.1 - Data Requirement Matrix

> Version: V2.1 Draft 1
>
> Purpose: 定義 StockWaveScanner V2 評分、交易時機、風險規劃與研究摘要所需的原始資料、歷史長度、更新頻率與缺值規則。

核心原則：

**用基本面與產業判斷值不值得研究，用趨勢與相對強勢確認市場是否認同，用籌碼確認資金方向，最後用價格結構與風險報酬決定現在能不能買。**

---

# 1. V2 評分架構

StockWaveScanner V2 不再只使用單一 Bullish Score。

整體架構：

1. Market Regime
2. Strength Score / 100
3. Timing Score / 100
4. Buy Priority
5. Trade Plan

---

## 1.1 Market Regime

Market Regime 不直接計入個股 100 分。

用途：

- 判斷目前整體市場風險
- 調整選股門檻
- 調整可接受的進場積極程度
- 協助判斷是否應降低持股曝險

初始狀態：

- BULLISH：偏多
- NEUTRAL：中性震盪
- HIGH_RISK：高風險

---

## 1.2 Strength Score

研究階段初始權重：

| 模組 | 權重 |
|---|---:|
| Trend | 25 |
| Relative Strength | 20 |
| Momentum / Volume | 15 |
| Chip | 20 |
| Fundamental / Industry | 20 |
| Total | 100 |

以上權重為研究起始值，最終必須透過歷史回測驗證，不視為正式固定權重。

---

## 1.3 Timing Score

研究階段初始權重：

| 模組 | 權重 |
|---|---:|
| Price Position | 25 |
| Support / Volume / Gap | 20 |
| Setup Quality | 20 |
| Risk | 20 |
| Reward / Upside | 15 |
| Total | 100 |

---

## 1.4 Buy Priority

研究階段初始公式：

```text
Buy Priority =
Strength Score × 65%
+
Timing Score × 35%

Strength 與 Timing 必須分開。

例如：

Strength = 92
Timing = 32
Stage = EXTENDED

代表：

股票很強
但目前不是理想的新進場點

另一檔：

Strength = 79
Timing = 84
Stage = READY

反而可能是目前較好的買進候選。

2. Data Requirement Summary
類別	資料	最低歷史需求	更新頻率	主要用途
Stock Master	股票基本資料	Current	視異動	股票識別
Market Index	大盤 OHLCV	120 Trading Days	Daily	Market Regime
Price	個股 OHLCV	120 Trading Days	Daily	Trend / RS / Timing
Institutional	三大法人	20+ Trading Days	Daily	Chip
TDCC	股權分散	Multiple Weeks	Weekly	Chip
Revenue	月營收	24 Months	Monthly	Fundamental
Financial	財報	8 Quarters	Quarterly	Fundamental
Industry	產業分類	Current	Low Frequency	Industry
Analyst Digest	YouTube 公開資訊	Recent	Daily	Research Digest

正式歷史回測資料：

Minimum: 2 years
Preferred: 3–5 years
3. Stock Master
3.1 Purpose

建立全市場股票基本識別資料。

3.2 Required Fields
Field	Type	Required	說明
stock_id	TEXT	YES	股票代號
stock_name	TEXT	YES	股票名稱
market	TEXT	YES	TWSE / TPEx
security_type	TEXT	YES	Stock / ETF / Other
industry_code	TEXT	NO	產業代碼
industry_name	TEXT	NO	產業名稱
listed_date	DATE	NO	上市櫃日期
is_active	BOOLEAN	YES	是否仍上市櫃
updated_at	DATETIME	YES	更新時間
3.3 Scoring Rule

Stock Master 本身不計分。

用途：

全市場 universe
股票搜尋
產業分類
排除非目標商品

V2 初期主要研究：

台灣上市普通股
台灣上櫃普通股

ETF、權證、特別股等商品應與普通股區隔。

4. Market Index Data
4.1 Purpose

用於 Market Regime。

4.2 Required Fields
Field	Type	Required
trade_date	DATE	YES
market	TEXT	YES
index_code	TEXT	YES
open	REAL	YES
high	REAL	YES
low	REAL	YES
close	REAL	YES
volume	REAL	NO
turnover	REAL	NO
4.3 Historical Requirement
Minimum = 120 trading days
Backtest = 2–5 years
4.4 Candidate Features

研究候選：

Close vs MA20
Close vs MA60
MA20 slope
MA60 slope
MA20 vs MA60
20D return
60D return
market breadth
recent drawdown
volatility

Market Breadth 若需要，可能由全市場個股自行計算，例如：

% stocks above MA20
% stocks above MA60
new highs
new lows
5. Daily Price Data

Price 是 V2 最核心資料。

5.1 Required Fields
Field	Type	Required
stock_id	TEXT	YES
trade_date	DATE	YES
open	REAL	YES
high	REAL	YES
low	REAL	YES
close	REAL	YES
volume	REAL	YES
turnover	REAL	Prefer
trade_count	INTEGER	Optional

Primary Key 概念：

stock_id + trade_date
5.2 Historical Requirement

正式 feature warm-up：

Minimum = 120 trading days

不可再使用 V1：

>= 30 days

作為正式 readiness 判斷。

原因：

V2 需要：

MA60
MA slope
RS 20D
ATR
volume average
swing high / low
breakout structure
support
price position
6. Trend / 25
6.1 Required Raw Data

只需要：

OHLCV
6.2 Candidate Features
Moving Average
MA10
MA20
MA60
Price Position
Close > MA20
Close > MA60
MA Structure
MA20 > MA60
MA Slope
MA20 slope
MA60 slope
Price Structure

研究：

Higher High
Higher Low
recent swing high
recent swing low
breakout structure
consolidation structure
6.3 Important Principle

Trend 不應只看：

今日漲跌幅

Trend 要回答：

股價目前是否處於有持續性的上升結構？

7. Relative Strength / 20

Relative Strength 是 V2 重要新增核心。

這裡的 RS 是：

個股與全市場其他股票比較。

不是 RSI。

7.1 Required Raw Data

全市場：

Daily Close
7.2 Required Returns

至少計算：

5D Return
10D Return
20D Return

可保留研究：

60D Return
7.3 Cross-sectional Percentile

每天對全市場股票排名。

例如：

5D Return Percentile
10D Return Percentile
20D Return Percentile

範圍：

0–100

100 代表市場中相對最強。

7.4 Initial Research Formula
RS Score =
5D Percentile × 20%
+
10D Percentile × 30%
+
20D Percentile × 50%

此公式為研究起點，必須回測。

8. Momentum / Volume / 15
8.1 Required Raw Data
OHLCV
8.2 Candidate Features
Momentum
5D Return
10D Return
20D Return
recent high distance
breakout
breakout continuation
Volume
Volume MA5
Volume MA20
Volume Ratio

例如：

Volume Ratio =
Today Volume / MA20 Volume
8.3 Close Position

研究：

Close Position =
(Close - Low) / (High - Low)

用途：

判斷當天是否收在相對高位。

8.4 Important Principle

成交量放大：

不等於
一定偏多

必須搭配：

Price direction
breakout
close position
support / resistance

判斷。

9. Institutional Data

包含：

Foreign
Investment Trust
Dealer
9.1 Required Fields
Field	Required
stock_id	YES
trade_date	YES
foreign_buy	Prefer
foreign_sell	Prefer
foreign_net	YES
trust_buy	Prefer
trust_sell	Prefer
trust_net	YES
dealer_buy	Prefer
dealer_sell	Prefer
dealer_net	YES
data_status	YES
10. Foreign Investor

Foreign 不應只看：

今天買超多少張

必須考慮：

股票成交量
買賣強度
連續性
加速度
股價是否確認
10.1 Candidate Features
Foreign Net 1D
Foreign Net 5D
Foreign Net 20D
Foreign Intensity

例如：

Foreign Intensity 5D =
Foreign Net 5D / Total Volume 5D
Foreign Intensity 20D =
Foreign Net 20D / Total Volume 20D
10.2 Transition

研究：

持續賣超
→
賣超縮小
→
轉買

這種狀態可能比單日大量買超更有研究價值。

11. Institutional Data Status

必須保留 V1 已驗證有效的資料語意。

允許：

STORED
ZERO_INFERRED
INSUFFICIENT_DATA
11.1 STORED

來源有完整資料：

foreign_buy
foreign_sell
foreign_net

可正常使用。

11.2 ZERO_INFERRED

可以合理確認：

foreign_net = 0

但來源沒有提供完整：

foreign_buy
foreign_sell

禁止偽造：

foreign_buy = 0
foreign_sell = 0
11.3 INSUFFICIENT_DATA

無法可靠判定。

不得：

自動當成 0

也不得因缺資料直接讓股票受到負分。

12. Investment Trust

至少需要：

Trust Net 1D
Trust Net 5D
Trust Net 20D

研究：

連續買超天數
由賣轉買
買超增加
與價格同步
買超強度
13. Dealer

至少需要：

Dealer Net 1D
Dealer Net 5D
Dealer Net 20D

Dealer 權重是否應低於 Foreign / Trust，後續由回測決定。

14. TDCC

TDCC 定位：

中期籌碼結構確認。

不是短線進場訊號。

14.1 Required Raw Data
Field	Required
stock_id	YES
data_date	YES
holder_level	YES
holder_count	YES
shares	YES
percentage	YES
14.2 Derived Features

需將級距轉換為研究用分類。

例如：

Large Holder %
Retail Holder %

再計算：

Large Holder WoW Change
Retail Holder WoW Change
14.3 Positive Structure Example
Large Holder ↑
Retail Holder ↓

可能為偏正向籌碼結構。

但 TDCC：

不能單獨決定買進

且因更新頻率較低：

不應壓過每日價格趨勢
15. Chip / 20

Chip Score 初期候選來源：

Foreign
Investment Trust
Dealer
TDCC

研究時應評估：

absolute amount
intensity
continuity
acceleration
price confirmation

原則：

籌碼確認價格，而不是籌碼凌駕價格。

16. Monthly Revenue

Fundamental V2 正式啟用前，必須先建立可靠資料來源。

不得：

資料不存在
→
Fundamental Score = 0
16.1 Required Fields
Field	Required
stock_id	YES
revenue_month	YES
revenue	YES
revenue_yoy	Prefer Derived
revenue_mom	Prefer Derived
cumulative_revenue	Prefer
cumulative_yoy	Prefer
16.2 Historical Requirement
Minimum = 24 months
16.3 Candidate Features
Revenue YoY
Revenue MoM
3M Revenue YoY
Cumulative Revenue YoY
Growth Acceleration
17. Quarterly Financial Data
17.1 Required Fields

候選：

Field
stock_id
fiscal_year
fiscal_quarter
revenue
gross_profit
operating_income
net_income
eps
gross_margin
operating_margin
net_margin
17.2 Historical Requirement
Minimum = 8 quarters
Preferred = 12+ quarters
17.3 Candidate Features
EPS YoY
Revenue YoY
Gross Margin Trend
Operating Margin Trend
EPS Acceleration
Profitability Improvement
18. Fundamental / Industry / 20

Fundamental / Industry 目前屬：

V2 planned

在正式資料源與回測完成前：

不得假裝已有完整 Fundamental Score。

建議模型版本明確區隔，例如：

V2.1-TECH-CHIP
V2.2-FUNDAMENTAL

避免使用者誤以為目前排名已包含完整基本面。

19. Industry Data
19.1 Required Data

至少：

stock_id
industry_code
industry_name

後續研究可能加入：

industry relative strength
industry breadth
industry momentum
industry cycle
peer comparison

產業題材、循環與未來展望若沒有正式可量化資料：

不得自行生成分數
20. Timing Score

Timing 的目的不是：

這是不是好公司？

而是：

現在是不是適合進場？

21. Price Position / 25

候選資料：

Close
MA10
MA20
MA60
ATR
Recent High
Recent Low

研究：

是否離 MA20 過遠
是否接近支撐
是否突破後過度延伸
是否位於合理風險位置
22. Support / Volume / Gap / 20

研究：

Support
MA10
MA20
swing low
breakout price
consolidation upper edge
high-volume price area
Gap

記錄：

gap up
gap down
unfilled gap

是否有效需回測。

23. Setup Quality / 20

候選結構：

tight consolidation
breakout setup
pullback setup
breakout retest
volume contraction
volatility contraction
higher low
base structure

目的：

區分「已經很強」和「正在形成適合進場的結構」。

24. Risk / 20

需要：

ATR
Swing Low
Support
Breakout Level
Current Price
24.1 Risk Price

Risk Price 定義：

當價格跌破此處時，原本的交易邏輯已明顯失效。

不是單純：

固定 -5%
固定 -10%
24.2 Candidate Logic

Risk Price 可參考：

recent swing low
key support
breakout level
MA structure
ATR buffer
24.3 Risk Percentage
Risk % =
(Current Price - Risk Price)
/
Current Price

研究初期 Buy Priority Hard Filter：

Risk <= 10%

最終門檻必須回測。

25. Reward / Upside / 15

需要：

Current Price
Buy Zone
Risk Price
Resistance
Previous High
High-volume Supply Area
26. Target Zone

Target 不是預測股價。

定義：

交易計畫中的風險報酬參考區。

研究起點：

1.5R
2.0R
2.5R

但不能只依 R 倍數。

還必須考慮：

previous high
resistance
overhead supply
high-volume area

因此：

Target Zone =
Risk / Reward
+
Price Structure
27. Buy Zone

Buy Zone 必須是：

Range

而不是單一：

Recommended Buy Price

候選來源：

MA10
MA20
ATR
swing low
support
breakout level
volume zone
gap structure
28. Stage

每檔股票需有 Stage。

Internal：

BASE
SETUP
READY
BREAKOUT
MOMENTUM
EXTENDED
WEAK

Mobile Chinese：

BASE      = 打底
SETUP     = 蓄勢
READY     = 待發動
BREAKOUT  = 突破
MOMENTUM  = 動能延續
EXTENDED  = 漲幅延伸
WEAK      = 偏弱
28.1 Important Principle
強
≠
現在適合追價

例如：

Strength 92
Stage EXTENDED

未持有：

漲幅延伸，不宜追價

已持有：

趨勢仍強，可續抱，但應提高風險保護
29. Initial Buy Candidate Filter

研究階段初始條件：

data_status = READY
Strength >= 65
Timing >= 60
Risk <= 10%
Stage != WEAK
Stage != EXTENDED

用途：

New-entry TOP10

此門檻不是最終正式值，必須經 Backtest Calibration。

30. Data Readiness

每檔股票都應有資料完整性狀態。

候選：

READY
WARMING_UP
PARTIAL
INSUFFICIENT_DATA
30.1 READY

核心資料完整：

Price history >= required warm-up
required market data available
required score inputs available
30.2 WARMING_UP

例如：

新上市股票
歷史不足 120 trading days

可顯示，但不應正常參與完整排名。

30.3 PARTIAL

部分非核心資料缺失。

例如：

TDCC 尚未更新

但核心 Price / Trend 可計算。

是否可排名依缺失模組決定。

30.4 INSUFFICIENT_DATA

核心資料不足。

不得正常參與 TOP10。

31. Missing Data Principle

禁止：

缺資料 = 0 分

因為這會把：

資料品質問題

誤認為：

股票品質差

應區分：

Negative Signal

與：

Missing Signal
32. Analyst Digest

研究來源：

老王股票
鐘崑禎 / WE178

用途：

補充研究觀點，不直接影響股票評分。

32.1 Required Data

候選欄位：

Field
channel
video_id
published_at
title
source_url
available_public_text
summary_status
mentioned_stock_ids
mentioned_industries
32.2 Daily Derived Digest

每天產生：

今日市場觀點
老王重點
鐘崑禎重點
共同關注產業
提及股票
與 StockWaveScanner TOP10 重疊股票
分析師看好但模型不同意的股票
模型不同意原因
32.3 Important Rule
Analyst Mention
≠
Score Bonus

只設定：

Analyst Attention = TRUE

除非未來 Backtest 證明：

Analyst Attention + READY

有顯著統計優勢，才研究是否加入模型。

33. Watchlist / Holdings

V2 自選股票與持股資料先使用 Browser LocalStorage。

LocalStorage 只保存個人資料：

stock_id
added_at
avg_cost
shares
first_buy_date

不要保存：

stock_name
latest_price
Strength
Timing
Stage
Risk

這些每日由最新 stocks.json 提供。

33.1 Holding Rule
shares > 0

視為已持有。

shares = 0
或空白

視為純觀察。

33.2 Position Derived Data

可由前端即時計算：

Cost = avg_cost × shares

Market Value = latest_price × shares

Unrealized P/L =
Market Value - Cost

Return % =
Unrealized P/L / Cost

V2 暫不處理：

多批交易
手續費
證交稅
完整交易流水帳

未來 V3 可演進成 Trade Journal。

34. Entry Advice vs Position Advice

同一檔股票必須區分：

未持有

與：

已持有

例如：

Stage = EXTENDED

未持有：

漲幅延伸，不建議追價

已持有：

趨勢仍強，可續抱，但應提高風險保護

因此：

Entry Advice

與：

Position Advice

不可完全共用相同文字。

35. Data Storage Principle

V2 正式資料架構：

Official Data Source
        ↓
Incremental Daily Update
        ↓
Turso Historical Core
        ↓
Feature Engine
        ↓
Scoring Engine
        ↓
Ranking
        ↓
Latest JSON
        ↓
GitHub Pages
36. Git Storage Policy

Git：

不是歷史資料倉庫

Git 主要存：

source code
configuration
model definitions
tests
latest published JSON
frontend
36.1 Production Latest JSON

預計：

docs/data/latest/status.json
docs/data/latest/market.json
docs/data/latest/top10.json
docs/data/latest/stocks.json
docs/data/latest/analyst_digest.json

不建立：

docs/data/2026-09-12/
docs/data/2026-09-13/
docs/data/2026-09-14/
...

避免 Git repository 無限膨脹。

37. Turso Historical Core

Turso 用於：

Normalized Historical Data

主要保存：

stock master
daily market data
daily stock price
institutional
TDCC
monthly revenue
quarterly financial
update status

Derived Score 原則上：

可重新計算

不一定需要永久保存每日全部 feature。

Backtest 所需資料則另行評估。

38. Raw Data Retention

Raw response 不建議永久保存。

研究原則：

Raw
↓
Validate
↓
Normalize
↓
Historical Core

Raw 可：

discard after normalization

或只保留：

7–30 days

供 debug 使用。

39. Incremental Update Frequency
39.1 Trading Day

更新：

Price
Market Index
Institutional
39.2 Weekly

只在 TDCC 有新一期時：

TDCC
39.3 Monthly

只在新月份資料發布時：

Revenue
39.4 Quarterly

只在新財報資料發布時：

Financial
40. Production Collection Principle

V2 Production 不再採用 V1：

約 2000 檔股票
×
逐股票 API request

作為主要每日架構。

優先尋找：

Whole-market
Batch
Official
Daily Dataset

目標：

一天抓一次市場資料
而不是一檔股票打一次 API
41. Historical Requirement

Feature Engine 正式 warm-up：

至少 120 trading days

正式模型回測：

Minimum = 2 years
Preferred = 3–5 years

需要盡可能涵蓋不同市場：

多頭
空頭
震盪
高波動
低波動
42. Backtest Target

不能只看：

Score 越高，當天漲幅越高

應測：

Forward Return
5D
10D
20D
40D
Risk
Maximum Adverse Excursion
Maximum Drawdown after signal
Opportunity
Maximum Favorable Excursion
Trade Quality
Win Rate
Average Return
Median Return
Risk-adjusted Return
Hit Target Before Stop
43. Data Source Verification Requirement

Data Requirement Matrix 確認後，下一階段不是立刻寫 crawler。

必須先對每一類資料完成 Data Source Verification。

每個資料源至少確認：

Official Source
Endpoint / Download Method
Whole-market or Per-stock
JSON / CSV / HTML / API
Historical Coverage
Daily Availability
Publish Time
Rate Limitation
Required Fields
Missing Data Behavior
Required Transformation
Incremental Update Method
Historical Backfill Method
Whether V1 Data Can Be Reused
44. V1 Historical Data Reuse

V1 source code 已封存於 Git branch：

archive-v1-20260912

V1 本機歷史資料庫已移出專案：

StockWaveScanner_V1_Data_Archive_20260912

目前包含：

stocks.db
stocks_before_tdcc_backfill_20260910.db
stocks-db.zip

V2 不應立即重新下載所有歷史資料。

必須先評估舊資料是否可利用。

可能可 reuse：

Stock Master
Price
Institutional
TDCC

評估項目：

Coverage
Completeness
Data Quality
Duplicate Status
Schema Mapping
Source Reliability

確認可用後，再考慮 Migration 到 Turso。

45. Current V2 Environment

Local Python：

Python 3.13

Virtual Environment：

.venv

Database：

Turso DEV
Turso PROD

DEV / PROD 均已通過：

Connection OK
SELECT 1 = 1

Secrets 只存放於：

.env

.env 不得 commit 到 Git。

Production GitHub Actions 未來改用：

GitHub Secrets

Frontend Browser：

不得直接連接 Turso
不得取得 Turso Auth Token

手機端只讀取 GitHub Pages 發布的 latest JSON。

46. Target Production Architecture

最終每日流程：

Taiwan Official Data Sources
        ↓
Fetch Delta
        ↓
Validate
        ↓
Normalize
        ↓
Turso Historical Core
        ↓
Feature Engine
        ↓
Market Regime
        ↓
Strength Score
        ↓
Timing Score
        ↓
Stage
        ↓
Trade Plan
        ↓
Buy Priority
        ↓
TOP10
        ↓
Latest JSON
        ↓
GitHub Pages

研究摘要流程：

YouTube Public Information
        ↓
Analyst Digest
        ↓
Mentioned Stocks / Industries
        ↓
Cross-check StockWaveScanner Results
        ↓
analyst_digest.json
47. Mobile Product Structure

V2 Mobile navigation：

首頁
TOP10
研究摘要
自選股票

核心 UI 原則：

列表只回答「今天要不要注意它」，明細頁才回答「為什麼」。

48. Homepage Data Requirement

首頁主要顯示：

Data Date
Last Update Status
Market Regime
TOP10 Readiness
Watchlist Important Changes

需要：

status.json
market.json
top10.json
stocks.json
49. TOP10 Data Requirement

TOP10 每列主要顯示：

rank
stock_id
stock_name
Strength
Timing
Stage
latest_price
Buy Zone
short Action

點擊後進入 Individual Stock Detail。

50. Individual Stock Detail

股票明細至少顯示：

Strength
Timing
Buy Priority
Stage
Latest Price
Buy Zone
Risk Price
Risk %
Target Zone
Action

並提供 Score Breakdown：

Trend
Relative Strength
Momentum / Volume
Chip
Fundamental

進階資料預設可收合：

MA20
MA60
ATR
5D Return
10D Return
20D Return
RS Percentile
Foreign 5D
Foreign 20D
Large Holder %
Retail Holder %
51. Analyst Digest Storage

Git 不保存：

Video
Audio
Full Transcript

只保存小型結構化結果：

analyst_digest.json

主要用途：

讓使用者每天用約 1–3 分鐘了解兩個頻道的重要觀點。

若公開文字不足：

summary_status = LIMITED

不得自行捏造影片內容。

52. Model Versioning

每次模型公式、權重或資料範圍重大變更時，應建立 model version。

例如：

V2.1-TECH-CHIP
V2.2-FUNDAMENTAL
V2.3-CALIBRATED

發布 JSON 建議包含：

model_version
data_date
generated_at

避免不同時期分數無法辨識模型差異。

53. Data Quality Principle

資料流程中必須明確區分：

Source Missing
Source Empty
Valid Zero
Parse Error
Network Error
Insufficient History

不得全部轉成：

0

尤其：

0

必須代表真正有意義的零值，而不是抓取失敗。

54. Update Idempotency

每日同步必須能重複執行。

同一筆：

stock_id + trade_date

重跑時不得產生 Duplicate。

TDCC：

stock_id + data_date + holder_level

也必須具備唯一性。

目的：

GitHub Actions Retry
Manual Retry
Network Retry

皆不應破壞資料庫。

55. DEV / PROD Principle

Turso：

stockwave-dev
stockwave-prod

用途必須分開。

DEV：

schema test
crawler test
feature test
migration test
backtest experiment

PROD：

validated schema
validated pipeline
production daily data

原則：

所有重大資料庫異動先在 DEV 驗證，再進 PROD。

56. V2 Development Order

目前開發順序：

1. Data Requirement Matrix
2. Data Source Verification
3. Turso Schema
4. V1 Historical Data Audit
5. Historical Migration / Backfill
6. Daily Incremental Pipeline
7. Feature Engine
8. Market Regime
9. Strength Score
10. Timing Score
11. Stage
12. Trade Plan
13. Historical Backtest
14. Calibration
15. TOP10
16. Analyst Digest
17. Watchlist / Holdings
18. Mobile UI
19. GitHub Actions Production

不應提前跳到 UI 或 Daily Crawler，而跳過資料定義與回測。

57. Current Project Status

已完成：

V1 source archive
V1 historical DB archive
V2 clean rebuild
Python 3.13 environment
Turso DEV connection
Turso PROD connection
V2 architecture definition

目前階段：

Phase 1
Data Requirement Matrix

下一階段：

Phase 2
Data Source Verification
58. Next Action

本文件確認後，下一步建立：

DATA_SOURCE_VERIFICATION.md

逐項確認：

Stock Master
Market Index
Daily Price
Institutional
TDCC
Monthly Revenue
Quarterly Financial
Industry
Analyst Digest

每項確認：

來源
網址 / API
官方與否
資料格式
全市場或逐股票
歷史長度
更新時間
Rate Limit
欄位完整度
缺值行為
是否可增量更新
是否可做歷史 Backfill
V1 資料是否值得 reuse

在 Data Source Verification 完成之前：

先不要正式建立 Turso Schema
先不要正式開發 Daily Crawler

避免再次發生資料抓完後才發現：

歷史不足
粒度錯誤
欄位不足
來源不穩定
API 不適合 Production

貼完、存檔後，現在只執行：

```powershell
git status