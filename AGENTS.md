# StockWaveScanner — AGENTS.md

## 0. IMPORTANT — NEXT GPT MUST READ THIS FIRST

本文件是 StockWaveScanner 目前最新的專案方向與交接文件。

下次 GPT 接手後：

**不要重新詢問使用者做到哪裡。**

**不要重新進行 Git Recovery。**

**不要重新執行 TDCC Historical Backfill。**

**不要繼續優先追查 TWSE `428 / 308 / TooManyRedirects` 問題。**

**不要直接繼續原本 2026-05～2026-06 的逐股票 Historical Price Backfill。**

原因：

專案方向已於 2026-09-12 正式重新檢討。

目前優先工作已從：

```text
先補資料
→
再做模型
```

改成：

```text
先定義投資模型
→
定義真正需要的資料
→
重新設計資料架構
→
再決定 Historical Backfill 方式
```

舊的 per-stock TWSE monthly crawler 可以保留作為 Research / fallback 工具，但目前不再視為未來 Production 每日資料更新主架構。

---

# 1. Project Mission

StockWaveScanner 的目的不是：

```text
預測明天一定會漲的股票
```

也不是：

```text
單純挑出今天漲最多的股票
```

真正的目標是：

> 每天從 TWSE + TPEx 全市場中，找出值得研究、目前位置合理、風險可控制的股票，並以一般投資人看得懂的方式說明原因。

系統必須回答四個問題：

```text
1. 現在市場環境適不適合積極做多？

2. 這是不是一檔值得研究的強勢股票？

3. 這檔股票現在是不是合理的進場時機？

4. 如果進場：
   買在哪裡？
   分析錯了哪裡退出？
   合理的獲利空間在哪裡？
```

核心理念：

> 先找值得買的股票，再判斷現在值不值得買。

---

# 2. Current Investment Philosophy

StockWaveScanner 未來融合三種研究思想。

## A. 技術結構與市場環境

參考老王股票等公開投資研究方法的精神：

```text
趨勢
均線
價格結構
大量位置
突破
缺口
市場環境
籌碼
```

核心：

> 技術分析不要堆疊過多指標。

不建立：

```text
RSI
MACD
KD
CCI
ADX
...
```

幾十個指標一起投票的黑盒模型。

---

## B. 產業、基本面與法人研究

參考鐘崑禎等公開投資研究方法的精神：

```text
產業趨勢
未來營運
營收
EPS
低基期
法人籌碼
安全邊際
資金使用效率
```

核心：

> 股票交易的是未來，不只是過去財報。

---

## C. StockWaveScanner 自己的量化紀律

加入：

```text
Relative Strength

Cross-sectional Percentile

ATR

Risk / Reward

Historical Backtest

Walk-forward Test

No Look-ahead

TOP10 Ranking
```

任何外部分析師的方法：

```text
只能作為 Research Hypothesis
```

不能：

```text
因分析師推薦某股票
→
直接加入 TOP10
```

---

# 3. Core Model Architecture

新版不再依賴單一：

```text
Bullish Score /100
```

正式概念改成：

```text
Market Regime
      ↓
Strength Score
      ↓
Timing Score
      ↓
Buy Priority
      ↓
Trade Plan
```

---

# 4. Market Regime

Market Regime 回答：

> 現在整體市場是否適合積極操作股票？

Market Regime 不直接算入個股 100 分。

未來可觀察：

```text
TAIEX 趨勢

OTC 趨勢

指數 vs MA20 / MA60

上漲 / 下跌家數

全市場站上 MA20 比例

全市場站上 MA60 比例

成交量

外資整體方向

必要時加入：
NASDAQ
SOX
USD
Rates
```

UI 最終只需要顯示：

```text
偏多

震盪 / 中性

高風險
```

Market Regime 用來：

```text
控制選股門檻

控制操作積極度

控制是否適合追價
```

而不是：

```text
大盤不好
→
所有股票直接扣 20 分
```

---

# 5. Strength Score /100

Strength Score 回答：

> 這是不是一檔值得優先研究的股票？

不是：

> 現在是不是可以直接買？

目前 Research Starting Point：

```text
Trend                    /25

Relative Strength        /20

Momentum / Volume        /15

Chip                     /20

Fundamental / Industry   /20

--------------------------------

Strength                /100
```

目前權重只是 Research Starting Point。

未來必須以 Backtest 驗證。

---

# 6. Trend /25

Trend 回答：

> 股票大方向是否健康？

主要觀察：

```text
Close vs MA20

Close vs MA60

MA20 vs MA60

MA20 slope

近期 Higher High

近期 Higher Low

價格結構
```

核心：

```text
Close > MA20 > MA60
```

通常優於：

```text
Close < MA20 < MA60
```

但不能只靠單一條件判斷。

重要原則：

> 價格是市場最終結果。

籌碼應該協助確認價格，而不是取代價格。

---

# 7. Relative Strength /20

Relative Strength 回答：

> 這檔股票跟全市場其他股票相比，到底強不強？

不是只看：

```text
股票自己漲多少
```

而是做：

```text
Cross-sectional Ranking
```

初步研究：

```text
5D Return Percentile

10D Return Percentile

20D Return Percentile
```

Research Formula：

```text
RS

=

5D percentile × 20%

+

10D percentile × 30%

+

20D percentile × 50%
```

例如：

```text
RS = 90
```

代表：

> 最近表現約位於全市場前 10%。

20D 權重較高，避免單日急漲股票直接衝上排名。

---

# 8. Momentum / Volume /15

Momentum 回答：

> 股票現在是不是正在開始發動？

觀察：

```text
接近近期高點

突破近期高點

Volume Ratio

突破是否帶量

收盤是否接近高點

突破後是否站穩

大量成交位置

缺口

突破平台
```

重要：

```text
爆量
```

本身不能直接加高分。

例如：

```text
爆量突破 + 收高
```

與：

```text
爆量 + 長上影 + 收回區間
```

意義完全不同。

因此：

> Volume 必須和價格位置一起判斷。

---

# 9. Chip /20

Chip 目標：

> 確認重要資金是否支持目前價格方向。

未來完整 Chip Layer：

```text
Foreign

Investment Trust

Dealer

TDCC Large Holder

TDCC Retail Holder

Continuity

Acceleration
```

---

# 10. Foreign

Foreign 不只看：

```text
今天買超幾張
```

需要考慮：

```text
Foreign Net / Volume

5D accumulation

20D accumulation

Buy days

Sell → Buy transition

Acceleration

Price confirmation
```

Research example：

```text
ForeignIntensity5D

=

Sum(ForeignNet5D)

/ Sum(Volume5D)
```

保留既有 effective foreign semantic：

```text
STORED

ZERO_INFERRED

INSUFFICIENT_DATA
```

ZERO_INFERRED：

```text
foreign_net = 0
```

不得製造：

```text
fake foreign_buy = 0

fake foreign_sell = 0
```

---

# 11. TDCC

TDCC 是：

> 中期持股結構確認訊號。

主要觀察：

```text
Large Holder %

Retail Holder %
```

偏多結構：

```text
Large holders ↑

Retail holders ↓
```

TDCC 更新頻率較低。

所以未來：

```text
TDCC 不應占過高權重
```

也不應當成即時發動訊號。

---

# 12. Fundamental / Industry /20

這是新版非常重要的資料層，目前尚未正式完成。

未來希望加入：

```text
Monthly Revenue YoY

3M Revenue YoY

EPS Growth

Gross Margin Trend

Operating Margin Trend

Growth Acceleration

Industry Cycle

Future Expectation

Estimate Revision
```

不能簡化成：

```text
PE < 15
→
高分
```

因為：

```text
Technology

Financial

Cyclical

Growth
```

不同產業不能套相同估值標準。

尚未建立正式 Fundamental / Industry Data Source 前：

```text
不得虛構 Fundamental Score
```

也不能：

```text
Fundamental = 0
```

而錯誤降低總分。

必須有 Model Version。

---

# 13. Timing Score /100

Timing 回答：

> 這檔好股票現在是不是好的進場位置？

目前 Research Starting Point：

```text
Price Position              /25

Support / Volume / Gap      /20

Setup Quality               /20

Risk                        /20

Reward / Upside             /15

--------------------------------

Timing                     /100
```

---

# 14. Strength != Timing

這是 StockWaveScanner 最重要的設計之一。

例如：

```text
Stock A

Strength = 92

Timing = 32

Stage = EXTENDED
```

意思：

> 股票很強，但現在已經太遠，不應追價。

另一檔：

```text
Stock B

Strength = 79

Timing = 84

Stage = READY
```

可能反而：

> 更適合列入今日 TOP10。

因此：

```text
Strongest Stock
```

不等於：

```text
Best Current Buy Opportunity
```

使用者主要需要第二種。

---

# 15. Buy Priority

Research Formula 起始版本：

```text
Buy Priority

=

Strength × 65%

+

Timing × 35%
```

這只是研究起點。

最終權重需要 Backtest。

Buy Priority 不是單純：

```text
Score 最大前 10 名
```

必須搭配 Hard Filter。

---

# 16. Hard Filters

目前 Research Starting Point：

```text
data_status = READY

Strength >= 65

Timing >= 60

Risk <= 10%

Stage != WEAK

Stage != EXTENDED
```

以上數字未來必須經過 Historical Backtest 驗證。

---

# 17. Stock Stage

Internal：

```text
BASE

SETUP

READY

BREAKOUT

MOMENTUM

EXTENDED

WEAK
```

手機中文：

```text
打底

蓄勢

待發動

突破

動能延續

漲幅延伸

偏弱
```

最重要：

> 強 ≠ 現在適合追價。

EXTENDED 可以是很強的股票。

但：

```text
未持有
→
通常不要追價
```

---

# 18. Buy Zone

使用：

```text
buy_zone_low
~
buy_zone_high
```

不要只給：

```text
買進價 = XX
```

Buy Zone 可考慮：

```text
MA10

MA20

ATR

Swing Low

Support

Breakout Level

High Volume Zone

Gap

Recent Structure
```

語意：

> 模型買進參考區。

不是：

> 保證上漲價格。

---

# 19. Risk Price

Risk Price 回答：

> 如果原交易假設錯了，哪裡代表劇本失效？

可依：

```text
Swing Low

Support

Volume Zone

Breakout Level

ATR Buffer
```

例如：

```text
Entry = 60

Risk Price = 56
```

則：

```text
Risk = 4

Risk% = 6.67%
```

Risk Price 的重要性：

> 不低於 Target。

---

# 20. Target Zone

目前：

```text
1.5R
~
2.5R
```

但不能只做數學計算。

必須額外檢查：

```text
Previous High

Heavy Volume Resistance

Overhead Supply

Structure Resistance
```

如果上方重大壓力不到 1R：

```text
Trade Quality 應降低
```

Target 是：

> Trade Planning Reference

不是：

> 股價預測。

---

# 21. Data Architecture — New Direction

目前已正式決定：

> Git 不應該當 Historical Data Warehouse。

Git 應保存：

```text
Source Code

Configuration

Model Version

Frontend

Published Result JSON
```

不要保存：

```text
大量 Historical Price

Raw HTML

大量 Raw API Response

完整 Backtest Dataset

巨大 SQLite DB
```

---

# 22. Production Data Pipeline

未來 Production Daily Pipeline 應以：

```text
Official Market Source
        ↓
Market-level Daily Dataset
        ↓
Incremental Update
        ↓
Historical Core
        ↓
Feature Engine
        ↓
Ranking Engine
        ↓
JSON Publisher
        ↓
GitHub Pages
```

Production 不應以：

```text
1979 stocks
×
每支股票打一個 API
```

為主要方式。

應優先使用：

```text
TWSE 全市場 Daily API

TPEx 全市場 Daily API
```

以及各資料源的批次資料。

---

# 23. Incremental Update

每日只更新新增資料。

例如：

```text
Last Price Date
=
2026-09-11
```

今天：

```text
2026-09-14
```

只抓：

```text
2026-09-14
```

而不是重新抓歷史。

資料更新頻率：

```text
Price
→ Trading Day

Institutional
→ Trading Day

TDCC
→ New TDCC Week Only

Revenue
→ New Month Only

Financial
→ New Quarter Only
```

---

# 24. Historical Store

不能完全不保存 Historical Core。

因為模型需要：

```text
MA20

MA60

ATR

Relative Strength

Momentum

Volume Baseline

Swing Structure

TDCC Change

Foreign Trend

Backtest
```

所以架構：

```text
Raw
→
短期保存 / 用完刪除

Historical Core
→
長期保存、不進 Git

Derived Scores
→
可重新計算

Publish JSON
→
Git
```

---

# 25. Raw Response Policy

Raw-first 研究模式可以保留。

但 Production 不永久保存全部 Raw。

建議：

```text
Raw retention:

7 ~ 30 days
```

之後自動 purge。

真正長期保存：

```text
Normalized Historical Core
```

---

# 26. Historical Data Requirement

不要再以：

```text
Price >= 30 days
```

作為完整模型條件。

因為模型包含：

```text
MA60

20D RS

ATR

Volume baseline

Swing structure
```

正式 Feature Warm-up 建議：

```text
至少 120 trading days
```

Historical Backtest：

```text
最低 2 years

理想 3 ~ 5 years
```

最終仍須依資料來源與成本決定。

---

# 27. Research DB vs Production Git

概念必須分離：

```text
Research Data Warehouse

!=

Production Git Repository
```

Research 未來可以使用：

```text
SQLite

Parquet

DuckDB
```

初期可繼續 SQLite。

資料規模增加後：

```text
Parquet + DuckDB
```

值得考慮。

---

# 28. Git Published Data

GitHub Pages 未來主要使用：

```text
docs/data/latest/status.json

docs/data/latest/market.json

docs/data/latest/top10.json

docs/data/latest/stocks.json

docs/data/latest/analyst_digest.json
```

只保存：

```text
latest
```

不要每天新增：

```text
2026-09-01

2026-09-02

2026-09-03
```

避免 Git History 無限膨脹。

---

# 29. Analyst Digest

使用者固定關注：

```text
老王股票
https://www.youtube.com/@oldwangstock

鐘崑禎 / WE178
https://www.youtube.com/@WE178
```

系統未來每天需要：

```text
檢查是否有新影片
```

如果有：

```text
整理今日市場觀點

關注產業

提及股票

主要理由

操作觀點

風險提醒
```

一天多支影片：

```text
合併成今日摘要
```

避免使用者仍需看多篇。

---

# 30. Analyst Digest Is NOT Score

分析師提到某股票：

```text
Analyst Attention = TRUE
```

但：

```text
不直接加 Strength

不直接加 Timing

不直接進 TOP10
```

即使：

```text
老王
+
鐘崑禎
```

同時提到：

也不能直接推薦。

未來可以累積資料後研究：

```text
Analyst Mention
+
StockWave READY
```

是否具有額外統計優勢。

有 Backtest 證據後才能考慮納入模型。

---

# 31. Analyst Digest UI

手機頁：

```text
研究摘要
```

內容：

```text
今日市場觀點

老王今日重點

鐘崑禎今日重點

共同關注產業

提及股票

與 StockWave TOP10 交集

模型不同意的股票
```

模型不同意非常重要。

例如：

```text
Analyst Bullish

Strength = 92

Timing = 25

Stage = EXTENDED
```

必須說：

> 分析師觀點偏多，但目前模型判斷漲幅延伸，不建議追價。

---

# 32. Mobile Navigation

目前正式規劃：

```text
首頁

TOP10

研究摘要

自選股票
```

評分藍圖說明：

```text
放在系統說明 / 評分說明
```

不一定占 Bottom Navigation。

---

# 33. Home Page

首頁只回答：

```text
今天資料更新成功嗎？

市場環境如何？

TOP10 是否完成？

我的自選有沒有重要變化？
```

Example：

```text
StockWaveScanner

資料日期：
2026-09-14

市場環境：
偏多

Ranking：
1952 / 1979

我的自選：

3 檔有重要變化

2330
蓄勢 → 待發動

2382
進入買進參考區

2454
漲幅延伸－不要追
```

---

# 34. TOP10 UI

TOP10 使用：

> 條列式。

不要使用大型卡片塞滿全部資料。

每列主要顯示：

```text
Rank

Stock ID

Stock Name

Strength

Timing

Stage

Latest Price

Buy Zone

Action
```

Example：

```text
#1 2330 台積電                 >

強度 86
時機 82
狀態：待發動

最新 1280

買進參考
1250 ~ 1280

接近合理布局區
```

點擊：

```text
>
```

進入 Individual Stock Detail。

---

# 35. Watchlist / 我的自選

「查股票」已重新定義為：

```text
我的自選
```

頁面頂端仍提供：

```text
搜尋股票代號 / 股票名稱
```

搜尋結果可：

```text
加入自選
```

加入後：

```text
下次進入網站仍顯示
```

可：

```text
移除自選
```

移除代表：

> 不再關注。

但股票仍然可以再次搜尋及重新加入。

---

# 36. Watchlist UI

自選股票也採：

> 條列式。

不要大型卡片。

Example：

```text
2330 台積電                     >

強度 86
時機 82
狀態：待發動

最新 1280

買進參考
1250 ~ 1280

↑ 今日條件改善
```

持股：

```text
2382 廣達                       >

強度 84
時機 79
狀態：動能延續

最新 286

持有 2000 股
成本 268.5

損益 +6.52%

續抱，留意風險價 257
```

---

# 37. Watchlist Storage V2

V2 初期使用：

```text
Browser LocalStorage
```

避免為少量個人資料先建立：

```text
Login

Account

Cloud DB
```

LocalStorage 只保存：

```text
stock_id

added_at

avg_cost

shares

first_buy_date
```

不要保存：

```text
Stock Name

Latest Price

Strength

Timing

Stage

Risk
```

這些每天從：

```text
stocks.json
```

取得。

---

# 38. Watchlist Limitation

LocalStorage 有限制：

```text
手機
```

與：

```text
電腦
```

不一定同步。

V2 接受此限制。

未來如果使用者明確需要：

```text
跨裝置同步
```

再做：

```text
Cloud Watchlist

Login
```

---

# 39. Holdings

自選股票可以維護：

```text
平均買進價

持有股數

首次買進日期
```

判斷：

```text
shares > 0
```

代表：

```text
已持有
```

否則：

```text
純觀察
```

---

# 40. Holdings Derived Data

系統自動計算：

```text
Investment Cost

Market Value

Unrealized P/L

Return %
```

公式：

```text
Cost
=
Average Price × Shares

Market Value
=
Latest Price × Shares

P/L
=
Market Value - Cost

Return %
=
(Latest - Average Cost)
/ Average Cost
× 100
```

V2 暫時不納入：

```text
Trading Fee

Transaction Tax

Multiple Transaction Ledger
```

未來 V3 可升級 Trade Journal。

---

# 41. Entry Advice vs Position Advice

這是重要規則。

同一檔股票：

```text
未持有
```

與：

```text
已持有
```

操作建議不同。

例如：

```text
Strength = 92

Timing = 30

Stage = EXTENDED
```

未持有：

> 漲幅延伸－不要追價。

已持有：

> 趨勢仍強，可續抱；目前進入延伸階段，提高風險價保護獲利。

所以：

```text
未持有
→
Entry Advice

已持有
→
Position Advice
```

---

# 42. Individual Stock Detail

TOP10 與自選股票共用同一個：

```text
Individual Stock Detail Page
```

明細頁顯示：

```text
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
```

---

# 43. Score Explanation

詳細頁才顯示：

```text
Trend Score

RS Score

Momentum Score

Chip Score

Fundamental Score
```

並一定附：

> 白話說明。

例如不要只顯示：

```text
Trend 22 / 25
```

還要：

> 股價維持 MA20、MA60 之上，中短期趨勢仍向上。

---

# 44. Advanced Technical Data

技術數據預設收合：

```text
[展開技術數據]
```

包含：

```text
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
```

列表頁不顯示這些。

---

# 45. UI Core Rule

正式 UI 設計原則：

> 列表只回答「今天要不要注意它」。

> 明細頁才回答「為什麼」。

因此：

```text
TOP10
```

與：

```text
我的自選
```

都必須保持精簡條列。

---

# 46. Current Completed Work

已完成：

```text
Git Recovery

backup-before-sync-20260911

Bullish V2 Research Implementation

Trade Plan V2 Research Implementation

Foreign ZERO_INFERRED Research

TDCC Historical Backfill

Raw-first validation

Historical Trade Plan Backtest Skeleton
```

TDCC Historical：

```text
2026-06-12
~
2026-08-28

12 dates

23744 rows
```

不要重新抓。

---

# 47. Previous Historical Price Problem

過去發現：

```text
2026-07-17

Price >= 30 days
=
5 stocks

TDCC >= 4 dates
=
1979 stocks
```

原因：

```text
Historical Price Coverage insufficient
```

不是 Bullish V2 Bug。

後續建立：

```text
scripts/backfill_market_prices.py
```

曾嘗試：

```text
TWSE 2026-05
TWSE 2026-06
```

遇到：

```text
428

308

TooManyRedirects
```

2026-09-12 已決定：

> 暫停優先追查此 crawler。

因為新的 Data Architecture 應先定義完成。

---

# 48. Git Safety

已存在安全 branch：

```text
backup-before-sync-20260911
```

禁止：

```text
git reset --hard
```

除非確認未 commit 檔案已有安全備份。

絕對禁止：

```text
git push --force
```

除非使用者明確理解並要求。

---

# 49. Development Communication Rule

使用者不是 Python 專業開發者。

每次開發溝通：

```text
一次只做一個明確步驟
```

回答優先格式：

```text
現在做什麼

↓

PowerShell / 修改內容

↓

正常會看到什麼
```

如果使用者貼 ERROR：

```text
停止

↓

分析 ERROR

↓

再給下一步
```

不要一次提供十幾個操作指令。

---

# 50. NEW PROJECT WORKSTREAM

目前從這裡開始。

## Phase 1 — Model Specification

正式定義：

```text
Strength Score Formula

Timing Score Formula

Buy Priority

Stage

Buy Zone

Risk Model

Target Model

Market Regime
```

目前已有 Concept Blueprint。

下一步要把 Concept 變成：

```text
可實作公式
```

---

## Phase 2 — Data Requirement Matrix

每一個 Score 都建立：

```text
需要什麼欄位

來源

更新頻率

需要多少歷史

資料缺失如何處理
```

Example：

```text
MA60

Source:
Daily Price

Frequency:
Trading Day

Warm-up:
>= 60 trading days
```

最後決定：

```text
Historical Price
到底需要抓幾年
```

不要先抓再決定。

---

## Phase 3 — Production Data Architecture

重新設計：

```text
TWSE Daily Market Data

TPEx Daily Market Data

Institutional

TDCC

Revenue

Financial

Industry
```

核心：

```text
Market-level API

Incremental

Minimal Requests
```

停止把：

```text
per-stock API
```

作為 Production 主架構。

---

## Phase 4 — Historical Store

決定：

```text
SQLite
```

或：

```text
Parquet + DuckDB
```

初期偏向：

```text
SQLite
```

先完成模型。

DB：

```text
不進 Git
```

---

## Phase 5 — Fundamental / Industry Layer

研究正式資料來源：

```text
Revenue

Financial Statements

EPS

Margin

Industry Classification

Growth
```

資料來源確定前：

```text
Fundamental Score 不啟用
```

---

## Phase 6 — Analyst Digest

建立：

```text
OldWang Channel Monitor

WE178 Channel Monitor

Daily Digest

Industry Extraction

Stock Mention Extraction

Model Cross-check
```

每日摘要：

```text
1 ~ 3 minutes
```

即可閱讀完。

---

## Phase 7 — Historical Backtest

Historical Coverage 完成後：

測試：

```text
5D

10D

20D

Win Rate

MFE

MAE

Risk First

1.5R First

2R First

2.5R First
```

並依：

```text
Strength Band

Timing Band

Stage

Market Regime

TWSE / TPEx
```

拆分。

---

## Phase 8 — Model Calibration

用 Backtest 決定：

```text
25 / 20 / 15 / 20 / 20
```

是否合理。

不要因為目前討論結果就視為 Production 真理。

Backtest 可以：

```text
增加權重

降低權重

移除指標

調整 Hard Filter
```

---

## Phase 9 — Ranking Engine

建立：

```text
Best Current Buy Opportunities
```

而不是：

```text
Strongest Stocks
```

輸出：

```text
TOP10
```

並排除：

```text
WEAK

EXTENDED

Risk Too High

Data Not Ready
```

---

## Phase 10 — Watchlist / Holdings

建立：

```text
Search

Add Watchlist

Remove Watchlist

Average Cost

Shares

Buy Date

P/L

Entry Advice

Position Advice
```

V2：

```text
LocalStorage
```

---

## Phase 11 — Mobile V2

最後才建立 UI。

Navigation：

```text
首頁

TOP10

研究摘要

自選股票
```

TOP10：

```text
條列
```

Watchlist：

```text
條列
```

Detail：

```text
完整分析
```

---

# 51. CURRENT NEXT ACTION

下次 GPT 開始工作時：

不要從 Crawler Error 開始。

不要從 UI 開始。

不要重新跑任何 Historical Backfill。

第一個正式工作應該是：

> 建立 StockWaveScanner V2.1 Data Requirement Matrix。

將：

```text
Market Regime

Trend

Relative Strength

Momentum / Volume

Foreign

TDCC

Fundamental / Industry

Timing

Buy Zone

Risk

Target
```

逐項列出：

```text
計算目的

正式公式

需要欄位

資料來源

更新頻率

Historical Warm-up

Missing Data Policy
```

完成這張 Matrix 後：

才能正式決定：

```text
Production Crawler Architecture

Historical Data Range

Database Schema
```

---

# 52. FINAL PROJECT PRINCIPLE

StockWaveScanner 最終共同遵循：

> 用基本面與產業判斷值不值得研究，用趨勢與相對強勢確認市場是否認同，用籌碼確認資金方向，最後用價格結構與風險報酬決定現在能不能買。

Production 不追求：

```text
更多資料
```

而追求：

```text
正確的資料

↓

可解釋的公式

↓

經歷史驗證的模型

↓

簡單清楚的使用者結果
```

資料、模型、UI 都必須服務這個目標。
