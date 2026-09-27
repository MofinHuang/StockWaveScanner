# StockWaveScanner — AGENTS.md

## 0. IMPORTANT — NEXT GPT MUST READ THIS FIRST

本文件是 StockWaveScanner 目前最新的專案方向與交接文件。

下次 GPT 接手後：

- 不要重新從頭規劃整個 StockWaveScanner。
- 不要重新詢問使用者目前做到哪裡。
- 不要重新進行 Historical Backfill。
- 不要重新追查舊的 Crawler 問題。
- 不要重新討論資料是否補齊。
- 不要重新從 UI 基礎架構開始。
- 不要操作 Turso PROD。
- 不要把缺資料當成 0 分。
- 不要一次處理很多問題。
- 如果發生錯誤，只處理第一個 ERROR。

目前專案：

> StockWaveScanner 核心系統、UI、資料來源、Historical Data、Score Engine、GitHub Actions 已完成。

歷史資料與模型所需主要資料目前也已補齊。

目前已經不是「把系統做完」階段。

正式進入：

```text
模型校正
↓
Stage 數字化
↓
進出場規則
↓
風險管理
↓
Backtest 驗證
↓
UI 解釋能力提升
```

目前最新工作重點：

> 將 Stage 從單純文字分類，改成有實際價格、百分比與風險數字支撐的交易狀態模型。

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

真正目標：

> 每天從 TWSE + TPEx 全市場中，找出值得研究、目前位置合理、風險可控制的股票，並以一般投資人能理解的方式說明原因。

系統必須回答：

```text
1. 現在市場環境如何？

2. 這是不是值得研究的強勢股票？

3. 現在是不是合理進場位置？

4. 如果進場：
   買在哪裡？
   風險多少？
   哪裡代表判斷錯誤？
   哪裡可以保護獲利？
   合理上方空間在哪裡？
```

核心理念：

> 先找值得研究的股票，再判斷現在值不值得進場。

---

# 2. Current Investment Model

核心流程：

```text
Market Regime
      ↓
Strength Score
      ↓
Timing Score
      ↓
Stage
      ↓
Buy Priority
      ↓
Trade Plan
```

但新版要再加入：

```text
Price Structure
      ↓
Buy Zone
      ↓
Breakout Price
      ↓
Risk Price
      ↓
Target Zone
      ↓
Stage 數字化
```

未來 Stage 不能只由 Score 直接決定。

---

# 3. Strength Score

Strength 回答：

> 這是不是值得優先研究的股票？

目前模型概念：

```text
Trend
Relative Strength
Momentum / Volume
Chip
Fundamental / Industry
```

Strength 不回答：

> 現在能不能買。

即使：

```text
Strength = 92
```

也有可能：

```text
Timing = 30
Stage = EXTENDED
```

代表：

> 股票很強，但價格已經偏離合理進場位置。

---

# 4. Timing Score

Timing 回答：

> 這檔股票現在的位置是否適合進場？

Timing 可包含：

```text
Price Position
Support
Volume
Gap
Setup Quality
Risk
Reward
```

但：

> Timing Score 不能成為唯一進場條件。

未來真正進場判斷必須加入：

```text
Buy Zone
Breakout Price
Risk %
Price Distance
Stage
```

---

# 5. Stage — New Direction

目前 Stage 名稱易懂：

```text
BASE
SETUP
READY
BREAKOUT
MOMENTUM
EXTENDED
WEAK
WAITING_DATA
```

中文：

```text
打底
蓄勢
進場訊號
突破
動能延續
漲幅延伸
偏弱
資料不足
```

但目前最大的問題：

> 有文字，沒有數字邊界。

例如：

```text
漲幅延伸
```

使用者知道意思，但不知道：

```text
究竟高出多少算延伸？
距離合理進場區多少？
追進去風險多少？
跌到哪裡需要退出？
```

因此新版 Stage 必須數字化。

---

# 6. Stage V2.1 — Numeric Stage Model

目前先採 Research Threshold。

所有門檻未來必須透過 Historical Backtest 驗證。

## BASE — 打底

概念：

> 結構仍在形成，尚未到合理進場位置。

初始規則：

```text
Price 尚未進 Buy Zone

且

距 Buy Zone 上緣 > 約 3%

且

尚未突破 Breakout Price
```

UI：

```text
打底
距買進區 -5.2%
尚未進入布局區
```

---

## SETUP — 蓄勢

概念：

> 價格逐漸靠近合理布局區。

初始規則：

```text
距 Buy Zone 約 0% ~ 3%

且

價格結構改善

且

尚未明顯 EXTENDED
```

UI：

```text
蓄勢
距買進區 1.8%
接近合理布局區
```

---

## READY — 進場訊號

概念：

> 價格正式進入模型認定的合理買進區。

初始規則：

```text
Price >= Buy Zone Low

AND

Price <= Buy Zone High

AND

Risk % <= 8%

AND

Strength 達最低門檻

AND

Stage != EXTENDED
```

UI：

```text
進場訊號

最新價
66.5

買進參考
65.0 ~ 67.0

目前風險
5.6%
```

重要：

> READY 不代表保證上漲。

代表：

> 目前價格位於模型認定的合理風險報酬區。

---

# 7. BREAKOUT — 突破

概念：

> 價格剛突破重要關鍵價。

初始 Research Threshold：

```text
Close > Breakout Price

且

突破幅度約 0% ~ 3%

且

Volume Ratio >= 1.3
```

其中：

```text
Breakout %
=
(Current Price - Breakout Price)
/
Breakout Price
× 100
```

UI：

```text
突破

突破價
67.5

最新價
68.5

突破幅度
+1.48%

量能
1.42x
```

文字：

> 剛突破關鍵價格，目前偏離幅度仍小。

---

# 8. MOMENTUM — 動能延續

概念：

> 已突破，趨勢仍強，但已不是最早的進場位置。

初始 Research Threshold：

```text
高於 Breakout Price 約 3% ~ 8%

且

趨勢仍維持

且

未過度偏離 MA20 / ATR
```

UI：

```text
動能延續

突破幅度
+5.7%

距 MA20
+4.2%
```

未持有：

> 已離開最佳早期進場區，需注意追價風險。

已持有：

> 趨勢仍強，可續抱並提高風險保護。

---

# 9. EXTENDED — 漲幅延伸

概念：

> 股票仍可能很強，但價格已經離合理進場位置太遠。

Research Trigger：

符合其中一項即可列入 EXTENDED 候選：

```text
Price > Breakout Price + 8%

OR

Price > MA20 + 10%

OR

Distance from MA20 > 2 ATR
```

未來可透過 Backtest 調整。

UI：

```text
漲幅延伸

距突破價
+11.4%

距 MA20
+10.8%

目前不適合追價
```

重要：

> EXTENDED 不等於股票不好。

代表：

> 現在的新進場 Risk / Reward 已經變差。

---

# 10. WEAK — 偏弱

概念：

> 原本價格結構開始失效。

初始條件可包含：

```text
Close < Risk Price
```

或：

```text
Close < MA20
且
Trend Structure 明顯轉弱
```

若正式跌破 Risk Price：

```text
EXIT_SIGNAL = TRUE
```

UI：

```text
偏弱

風險價
62.8

最新價
62.2

已跌破模型風險價
```

---

# 11. WAITING_DATA

必要資料不足：

```text
Strength = NULL
Timing = NULL
Buy Priority = NULL
Stage = WAITING_DATA
```

不可：

```text
缺資料
→ 0 分
```

也不可：

```text
WAITING_DATA
→ TOP10
```

---

# 12. Five Core Numbers

新版每一檔股票至少必須有以下五個價格：

```text
Latest Price

Buy Zone

Breakout Price

Risk Price

Target Zone
```

Example：

```text
最新價
68.50

買進參考區
65.00 ~ 67.00

突破價
67.50

風險價
62.80

目標區
74.00 ~ 78.00
```

---

# 13. Buy Zone

Buy Zone 不是單一價格。

使用：

```text
buy_zone_low

buy_zone_high
```

可能來源：

```text
MA10

MA20

Swing Low

Breakout Level

High Volume Zone

Gap Support

ATR

Recent Price Structure
```

語意：

> 模型合理布局區。

不是：

> 保證上漲區。

---

# 14. Buy Zone Distance

需要新增：

```text
distance_to_buy_zone_pct
```

若價格高於 Buy Zone High：

```text
(Current Price - Buy Zone High)
/
Buy Zone High
× 100
```

例如：

```text
Latest = 68.5
Buy Zone High = 67

Distance
=
+2.24%
```

UI：

```text
距買進區
+2.24%
```

如果價格位於 Buy Zone：

```text
0%
或
IN_ZONE
```

---

# 15. Breakout Price

新增正式欄位：

```text
breakout_price
```

來源可考慮：

```text
Recent High

Platform High

Swing High

Resistance

High Volume Resistance
```

Breakout Price 必須代表：

> 價格突破後，原本盤整或壓力結構正式改變的位置。

---

# 16. Breakout Distance

新增：

```text
breakout_distance_pct
```

公式：

```text
(Current Price - Breakout Price)
/
Breakout Price
× 100
```

例如：

```text
Breakout = 67.5
Current = 68.5

Breakout Distance
=
+1.48%
```

Stage 可依此判斷：

```text
0 ~ 3%
→ BREAKOUT

3 ~ 8%
→ MOMENTUM

> 8%
→ EXTENDED Candidate
```

---

# 17. Risk Price

Risk Price 回答：

> 如果原本交易假設錯了，哪個價位代表劇本失效？

可依：

```text
Swing Low

Support

Breakout Level

High Volume Support

Gap Support

MA20

ATR Buffer
```

Risk Price 不是固定：

```text
-5%
```

而是：

> 結構失效位置。

---

# 18. Risk %

新增：

```text
risk_pct
```

公式：

```text
(Current Price - Risk Price)
/
Current Price
× 100
```

Example：

```text
Current = 68.5
Risk = 62.8

Risk %
=
8.32%
```

初始 Entry Research Threshold：

```text
Risk <= 8%
```

未來用 Backtest 校正。

---

# 19. Entry Signal

未來不再使用：

```text
Timing >= XX
```

直接等於進場。

Entry 應至少：

```text
ENTRY_READY =

Price >= Buy Zone Low

AND

Price <= Buy Zone High

AND

Risk % <= Entry Risk Threshold

AND

Strength >= Minimum Strength

AND

Stage != EXTENDED

AND

Readiness = READY
```

Breakout Entry 則可另外定義：

```text
BREAKOUT_ENTRY =

Breakout Distance >= 0%

AND

Breakout Distance <= 3%

AND

Volume Ratio >= 1.3

AND

Risk % acceptable
```

---

# 20. Exit Signal

Exit 必須拆成：

```text
Defensive Exit

Profit Protection
```

---

# 21. Defensive Exit

最重要條件：

```text
Close < Risk Price
```

代表：

> 原本交易假設失效。

此時：

```text
exit_signal = DEFENSIVE_EXIT
```

UI：

```text
跌破風險價

風險價
62.8

最新價
62.2
```

---

# 22. Profit Protection

如果股票已經上漲：

> 不應該永遠使用最初的 Risk Price。

新增：

```text
trailing_risk_price
```

初步可考慮：

```text
MAX(
    MA20,
    Recent Swing Low,
    Breakout Price
)
```

再視需要加入：

```text
ATR Buffer
```

Example：

```text
Entry
66

Current
82

Original Risk
62.8

Trailing Risk
75.5
```

此時已持有者應看：

```text
75.5
```

而不是：

```text
62.8
```

---

# 23. Entry Advice vs Position Advice

同一檔股票：

```text
未持有
```

與：

```text
已持有
```

必須顯示不同建議。

Example：

```text
Strength = 92
Stage = EXTENDED
```

未持有：

> 漲幅延伸，目前高於合理進場區，不宜追價。

已持有：

> 趨勢仍強，可續抱；提高風險保護並觀察 Trailing Risk Price。

核心：

```text
未持有
→ Entry Advice

已持有
→ Position Advice
```

---

# 24. Target Zone

Target 不只是：

```text
固定漲幅 %
```

初步仍可使用：

```text
1.5R
~
2.5R
```

但必須同時檢查：

```text
Previous High

Heavy Volume Resistance

Overhead Supply

Structure Resistance
```

Target：

> Trade Planning Reference。

不是：

> 股價預測。

---

# 25. Reward / Risk

未來新增：

```text
reward_risk_ratio
```

概念：

```text
Potential Reward
/
Potential Risk
```

例如：

```text
Entry
66

Risk
62

Target
74

Risk
4

Reward
8

R/R
2.0
```

可以顯示：

```text
預估風險報酬
2.0R
```

---

# 26. Stage Priority Logic

未來 Stage 不應只做：

```text
if timing > 80
→ READY
```

而應依價格結構優先。

概念順序：

```text
if Data Not Ready
    WAITING_DATA

else if Price < Risk Price
    WEAK

else if Extended Condition
    EXTENDED

else if Breakout Distance > 3% and <= 8%
    MOMENTUM

else if Breakout Distance >= 0% and <= 3%
    BREAKOUT

else if Price inside Buy Zone
    READY

else if Distance to Buy Zone <= 3%
    SETUP

else
    BASE
```

注意：

> 這只是目前的 Research Logic。

正式寫入 Production 前必須先確認現有程式欄位與計算方式。

---

# 27. Proposed Stage Numeric Thresholds

目前 Research Starting Point：

| Stage | 初始數字 |
|---|---|
| BASE | 距 Buy Zone > 3% |
| SETUP | 距 Buy Zone 約 0~3% |
| READY | Price inside Buy Zone + Risk ≤ 8% |
| BREAKOUT | Breakout +0~3% |
| MOMENTUM | Breakout +3~8% |
| EXTENDED | Breakout >8% 或 MA20 >10% 或 >2 ATR |
| WEAK | Close < Risk Price |
| WAITING_DATA | Required Data Missing |

所有門檻：

> 都不是最終 Production 真理。

需 Backtest。

---

# 28. UI New Direction

未來 Stage 顯示不可只顯示：

```text
漲幅延伸
```

應顯示：

```text
漲幅延伸

距突破價
+11.4%

距 MA20
+10.8%

買進區
65 ~ 67

最新
74.6
```

READY：

```text
進場訊號

最新
66.5

買進區
65 ~ 67

風險價
62.8

目前風險
5.6%
```

BREAKOUT：

```text
突破

突破價
67.5

最新
68.5

突破幅度
+1.48%

量能
1.42x
```

---

# 29. Stock Detail — Required Fields

個股明細未來至少顯示：

```text
Strength

Timing

Buy Priority

Stage

Latest Price

Buy Zone Low

Buy Zone High

Distance to Buy Zone %

Breakout Price

Breakout Distance %

Risk Price

Risk %

Trailing Risk Price

Target Zone

Reward / Risk

Entry Advice

Position Advice
```

---

# 30. TOP10 UI

TOP10 列表仍保持簡潔。

不要全部顯示技術資料。

建議：

```text
#1 2330 台積電

強度
86

時機
82

狀態
突破 +1.4%

最新
1285

買進區
1245 ~ 1270

風險
5.3%
```

點擊才看完整 Trade Plan。

---

# 31. Watchlist / Holdings

Watchlist 必須區分：

```text
純觀察
```

與：

```text
已持有
```

持有者額外顯示：

```text
Average Cost

Shares

Current Return

Original Risk

Trailing Risk

Position Advice
```

---

# 32. Score vs Price Structure

正式原則：

```text
Score
=
判斷股票品質

Price Structure
=
判斷進場位置

Risk
=
判斷錯了在哪裡退出

Stage
=
把 Price Structure 翻譯成簡單狀態
```

所以：

> Stage 不能只是 Score 的另一種名稱。

---

# 33. Strength != Entry

例如：

```text
Strength = 94

Current Price = 120

Buy Zone = 100 ~ 105

Breakout = 106
```

即使非常強：

```text
Breakout Distance
=
+13.2%
```

Stage：

```text
EXTENDED
```

未持有：

> 不追。

這是新版 Stage 最重要的價值。

---

# 34. Future Backtest

資料目前已補齊。

所以未來可以利用現有 Historical Data 驗證：

```text
Buy Zone Accuracy

Breakout Threshold

3% Breakout Range

8% Extended Threshold

Risk <= 8%

MA20 Distance

ATR Distance

Trailing Risk
```

測試結果：

```text
5D Return

10D Return

20D Return

Win Rate

MFE

MAE

Risk First

1.5R First

2R First

2.5R First
```

並拆分：

```text
Stage

Strength Band

Timing Band

Market Regime

TWSE / TPEx
```

---

# 35. Model Version

Stage 新規則必須建立版本。

例如：

```text
stage_model_version
=
v2.1
```

避免未來：

```text
Stage 定義改了
```

但 Historical Result 無法追溯。

---

# 36. Current Development Strategy

目前專案已完成。

後續開發原則：

```text
不要大改整套架構

↓

先調整 Stage / Trade Plan

↓

建立數字化邏輯

↓

再 Backtest

↓

最後才校正門檻
```

不先重寫 Strength Score。

不重新補 Historical Data。

不重做 Crawler。

---

# 37. Git / Environment Safety

Repo：

```text
https://github.com/MofinHuang/StockWaveScanner
```

Local：

```text
D:\002.Programs\002.Others\Python\StockWaveScanner
```

Branch：

```text
main
```

Python：

```text
.\.venv\Scripts\python.exe
```

不要使用：

```text
python

py -3.13
```

---

# 38. Turso

資料庫：

```text
Turso DEV
=
stockwave-dev
```

```text
Turso PROD
=
stockwave-prod
```

所有開發、測試：

> 只能操作 DEV。

禁止：

> 操作 PROD。

除非使用者日後明確要求正式發布。

---

# 39. Git Safety

禁止：

```text
git push --force
```

除非使用者明確要求且理解風險。

禁止：

```text
git reset --hard
```

除非非常明確安全。

不可 Commit：

```text
.env

GO.md

AGENTS.md
```

除非使用者日後明確改變規則。

---

# 40. Development Communication Rule

使用繁體中文。

使用者不是 Python 專職工程師。

每次：

```text
一次只做一個清楚步驟
```

回答格式優先：

```text
現在做什麼

↓

要改什麼

↓

完整程式 / 完整函式

↓

PowerShell 指令

↓

正常結果
```

如果 ERROR：

```text
停止

↓

只分析第一個 ERROR

↓

修正

↓

再繼續
```

不要一次猜十個問題。

---

# 41. Commit Rule

不要為每個小修改一直 Commit。

應：

```text
完成一個完整功能區塊

↓

確認執行正常

↓

Commit

↓

Push
```

---

# 42. Current Next Action

下次繼續時：

> 不要重新討論 Stage 為什麼需要數字化。

已經確定。

第一個正式工作：

```text
檢查目前 Stage / Trade Plan 實際程式
```

找出目前：

```text
Stage 在哪裡計算

Buy Zone 在哪裡計算

Risk Price 在哪裡計算

Target 在哪裡計算

Breakout 是否已有欄位

ATR 是否已有欄位
```

然後：

> 在不破壞現有 Score Engine 的前提下，設計 Stage V2.1。

優先新增：

```text
breakout_price

distance_to_buy_zone_pct

breakout_distance_pct

risk_pct

trailing_risk_price

reward_risk_ratio
```

再調整：

```text
BASE
SETUP
READY
BREAKOUT
MOMENTUM
EXTENDED
WEAK
```

---

# 43. Important — Do Not Immediately Hardcode Everything

下一次不要直接看到：

```text
3%

8%

10%

2 ATR
```

就立刻全部寫死進 Production。

正確流程：

```text
先確認現有資料欄位

↓

先建立 Derived Metrics

↓

確認目前股票可以正確算出

↓

Stage 使用 Research Threshold

↓

Historical Backtest

↓

再決定正式 Threshold
```

---

# 44. Final Stage Principle

新版 Stage 的核心：

> Stage 不只告訴使用者股票現在「叫什麼狀態」。

而要告訴使用者：

```text
現在多少錢

合理買在哪裡

距離合理位置多少 %

突破了多少 %

目前承擔多少風險 %

哪裡代表判斷錯誤

如果已持有，哪裡應開始保護獲利
```

最後呈現：

```text
Stage
+
Price
+
Distance %
+
Risk %
+
Invalidation Price
+
Trade Plan
```

---

# 45. Final Project Principle

StockWaveScanner 最終共同遵循：

> 用基本面與產業判斷值不值得研究，用趨勢與相對強勢確認市場是否認同，用籌碼確認資金方向，最後用價格結構與風險報酬決定現在能不能進場。

新版再補一句：

> 分數用來找股票，價格結構用來決定行動。

系統最終追求：

```text
正確資料

↓

可解釋模型

↓

有數字依據的 Stage

↓

明確進場區

↓

明確風險價

↓

明確獲利保護

↓

Historical Backtest

↓

簡單易懂的 UI
```

Stage 最終不應只是：

```text
漲幅延伸
```

而應是：

```text
漲幅延伸

距突破價 +11.4%

距合理買進區 +9.8%

目前風險 12.1%

未持有：不追價

已持有：續抱，保護價 72.5
```

這就是下一階段 StockWaveScanner 最重要的方向。

# StockWaveScanner V3 — 新邏輯與頁面規劃

## 46. IMPORTANT — V3 新方向

目前先不要立即調整 Production 程式。

下一階段先完成：

```text
模型規則確認
↓
頁面資訊架構確認
↓
資料來源盤點
↓
公式與權重確認
↓
Derived Metrics
↓
Backtest
↓
最後才進行 Production 調整
```

本次 V3 重點不是推翻現有 StockWaveScanner。

既有：

```text
Historical Data
Score Engine
Stage
Trade Plan
UI
GitHub Actions
```

全部保留。

V3 主要強化：

```text
個股可解釋評分
+
族群資金觀察
+
分析師觀點
+
ETF 持股異動
+
金控股專屬觀察
+
全面繁體中文 UI
```

---

# 47. V3 個股核心評分原則

個股評分只保留三大面向：

```text
基本面
籌碼面
技術面
```

不得加入：

```text
族群分數
ETF 持股異動
分析師推薦
熱門程度
新聞聲量
```

直接影響個股評分。

正式概念：

```text
基本面
+
籌碼面
+
技術面
↓
綜合評分
↓
進場時機
↓
價格結構
↓
Stage
↓
Trade Plan
```

核心原則：

> 個股本身好不好，與目前市場正在偏好什麼族群，必須分開判斷。

---

# 48. 基本面

基本面回答：

> 公司本身是否值得持續研究？

預計包含：

```text
營收成長
獲利能力
EPS 成長
毛利率
營業利益率
ROE
產業成長性
財務穩定性
```

未來每個項目都應：

```text
有原始數據
+
有計算公式
+
有分數
+
有繁體中文說明
```

Example：

```text
基本面
82 分

營收趨勢
良好

EPS
持續成長

毛利率
穩定

產業趨勢
正向
```

不可：

```text
資料缺少
→ 0 分
```

資料不足必須：

```text
NULL
或
資料不足
```

---

# 49. 籌碼面

籌碼面回答：

> 市場資金是否正在支持這支股票？

預計包含：

```text
外資
投信
自營商
三大法人
融資
融券
大戶持股
持股集中度
籌碼連續性
```

Example：

```text
籌碼面
78 分

外資
近 5 日偏多

投信
連續買超

融資
小幅增加

大戶
持股增加
```

---

# 50. 技術面

技術面回答：

> 股價趨勢與價格結構是否健康？

預計包含：

```text
Trend
Relative Strength
Momentum
Volume
MA20
MA60
ATR
5D Return
10D Return
20D Return
Price Structure
Breakout Structure
```

UI 全部改繁體中文。

Example：

```text
技術面
88 分

趨勢
多頭

相對強勢
強

量能
放大

價格結構
正向
```

重要：

```text
技術面高
≠
現在適合進場
```

進場仍由：

```text
Buy Zone
Breakout
Risk
Stage
Trade Plan
```

判斷。

---

# 51. 綜合評分

未來個股可以顯示：

```text
綜合評分
基本面
籌碼面
技術面
```

初步 Research Weight 可考慮：

```text
基本面 30%
籌碼面 30%
技術面 40%
```

但：

> 目前不得直接寫死為 Production Final Weight。

未來必須透過 Historical Backtest 驗證。

---

# 52. 進場時機

進場時機與三大個股評分分開。

概念：

```text
基本面
籌碼面
技術面
↓
判斷股票品質
```

而：

```text
Buy Zone
Breakout
Risk
Volume
Price Position
↓
判斷進場時機
```

Example：

```text
綜合評分
88

基本面
85

籌碼面
82

技術面
94

進場時機
52

Stage
漲幅延伸
```

代表：

> 股票本身很強，但目前價格位置已不理想。

---

# 53. V3 全面繁體中文

前端 UI 未來以繁體中文呈現。

程式內部欄位仍可保留英文。

例如：

```text
Strength
→ 綜合評分

Fundamental
→ 基本面

Chip
→ 籌碼面

Technical
→ 技術面

Timing
→ 進場時機

Stage
→ 交易階段

Buy Zone
→ 買進參考區

Breakout Price
→ 突破價

Risk Price
→ 風險價

Target Zone
→ 目標參考區

Reward / Risk
→ 風險報酬比

Trailing Risk
→ 獲利保護價
```

Stage UI：

```text
BASE
→ 打底

SETUP
→ 蓄勢

READY
→ 進場訊號

BREAKOUT
→ 突破

MOMENTUM
→ 動能延續

EXTENDED
→ 漲幅延伸

WEAK
→ 偏弱

WAITING_DATA
→ 資料不足
```

---

# 54. 族群資金頁

新增獨立頁面：

```text
族群資金
```

目的：

> 判斷目前市場資金偏好哪些產業與次產業。

族群不得納入個股評分。

個股最多：

```text
顯示所屬族群
+
以顏色顯示目前族群偏好狀態
```

Example：

```text
主要族群
記憶體

狀態
強勢偏多
```

---

# 55. 族群分類架構

底層建議至少分：

```text
大產業
次產業
題材
```

Example：

```text
大產業
半導體

次產業
記憶體

題材
DRAM
HBM
AI 記憶體
```

另一例：

```text
大產業
電子零組件

次產業
散熱

題材
AI 伺服器
液冷
資料中心
```

重要：

```text
官方產業分類
與
市場題材分類
```

必須分開維護。

---

# 56. 族群資金觀察內容

族群頁至少分析：

```text
法人
大戶
主力動向
成交金額
成交量
漲跌家數
族群廣度
技術強度
資金延續性
```

時間：

```text
當日
當週
當月
```

畫面狀態：

```text
強勢偏多
偏多
中性
偏弱
強勢偏弱
```

可搭配：

```text
↑↑
↑
→
↓
↓↓
```

---

# 57. 族群範例

預計可包含：

```text
半導體
晶圓代工
IC 設計
記憶體
封裝測試
半導體設備
面板
散熱
PCB
被動元件
AI 伺服器
網通
電池
儲能
電動車
機器人
低軌衛星
矽光子
```

族群未來可持續擴充。

---

# 58. 族群廣度

族群頁應避免只看少數大型權值股。

新增：

```text
族群廣度
```

Example：

```text
記憶體 12 檔

10 檔站上 MA20
8 檔上漲
7 檔量能增加
6 檔創 20 日新高
```

可判斷：

```text
族群廣度
強
```

若只有 1～2 檔股票上漲：

```text
族群廣度
弱
```

---

# 59. 族群頁資訊架構

第一層：

```text
族群總覽
```

顯示：

```text
族群
當日
當週
當月
法人
大戶
主力
技術狀態
```

第二層：

```text
族群明細
```

顯示：

```text
族群成員
族群趨勢
法人
大戶
主力
成交量
族群廣度
```

第三層：

```text
點擊股票
→ 個股明細
```

---

# 60. 分析師觀點頁

新增獨立頁面：

```text
分析師觀點
```

第一階段指定：

```text
鐘崑禎
王倚隆
黎志建
陳於晨
```

目的：

> 整理分析師近期在研究什麼，以及他們主要從什麼面向判斷。

不得將：

```text
分析師提及
分析師看多
分析師推薦
```

直接加進個股分數。

---

# 61. 分析師評論時間範圍

提供：

```text
當日
近 3 日
近 7 日
近 30 日
```

每則評論至少整理：

```text
分析師
日期
來源
標題
涉及族群
涉及股票
主要分析面向
關鍵因素
摘要
```

---

# 62. 分析師分析面向

每一則評論可以歸類：

```text
基本面
籌碼面
技術面
產業面
總體面
事件面
```

Example：

```text
分析師
陳於晨

主要面向
基本面
產業面

關注因素
營收
毛利率
產業成長
市占率
產品組合
```

---

# 63. 分析師觀察面向統計

未來可以統計：

```text
近 30 日
```

某分析師評論偏好：

```text
基本面 45%
產業面 35%
籌碼面 10%
技術面 10%
```

這不是分析師評分。

目的：

> 了解每位分析師習慣從什麼角度研究市場。

---

# 64. 分析師共同關注

新增：

```text
近期共同關注族群
近期共同關注股票
```

Example：

```text
PCB
3 / 4 位分析師近期提及

半導體
2 / 4

AI 伺服器
2 / 4
```

此資訊：

```text
只能作為市場觀察
不得直接轉換為個股加分
```

---

# 65. ETF 持股異動頁

新增獨立頁面：

```text
ETF 持股異動
```

指定 ETF：

```text
0050
0056
00981A
00878
00919
009816
```

重要：

> 此頁不是 ETF 資金流入／流出。

真正目的：

> 追蹤指定 ETF 最近買進、增加、減少、賣出哪些股票。

---

# 66. ETF 持股異動時間

統計：

```text
當日
近 5 日
近 20 日
```

概念：

```text
當日
今日持股 - 前一交易日持股

近 5 日
今日持股 - 5 個交易日前持股

近 20 日
今日持股 - 20 個交易日前持股
```

若資料來源只有權重：

```text
改用權重變化
```

並清楚標示：

```text
持股變化
或
權重變化
```

不可假裝是實際成交買賣資料。

---

# 67. ETF 持股狀態

ETF 持股可以分：

```text
新進
持續加碼
持平
持續減碼
剔除
```

Example：

```text
00981A

新進
A 股

持續加碼
B 股
C 股

持續減碼
D 股

剔除
E 股
```

---

# 68. ETF 共識持股

新增：

```text
ETF 共識持股
```

目的：

> 找出多檔 ETF 同時增加或減少的股票。

Example：

```text
近 5 日共同加碼

台積電
0050 ↑
00981A ↑
009816 ↑
```

可統計：

```text
加碼 ETF 數
減碼 ETF 數
持股趨勢
```

Example：

```text
股票
台積電

加碼 ETF
4

減碼 ETF
0

狀態
明顯加碼
```

---

# 69. ETF 配息與價格資訊

ETF 頁仍需保留：

```text
ETF 名稱
最新價格
近 5 日漲跌
近 20 日漲跌
配息頻率
最近配息
下一次配息
除息日
最後買進日
發放日
```

配息頻率：

```text
月配
季配
半年配
年配
尚無資料
```

未有正式資料不得自行推定。

---

# 70. ETF 個股反查

個股頁可顯示：

```text
近期 ETF 持股動向
```

Example：

```text
00981A
近 5 日加碼

00878
近 20 日加碼

00919
持平
```

此資訊：

> 只作輔助，不影響基本面、籌碼面、技術面分數。

---

# 71. 金控股觀察頁

新增獨立頁面：

```text
金控股觀察
```

原因：

> 金控股的評估方式與一般電子股不同。

需另外建立專屬 KPI。

---

# 72. 金控股主要觀察欄位

總覽至少顯示：

```text
最新價格
近 5 日漲跌
近 20 日漲跌
單月 EPS
累計 EPS
ROE
現金股利
股票股利
殖利率
法人動向
主要獲利類型
```

---

# 73. 金控類型

金控可依主要獲利來源分類：

```text
銀行型
壽險型
證券型
綜合型
```

目的：

> 不同類型不得完全使用同一套解讀方式。

銀行型可重點觀察：

```text
淨利差
放款
手續費收入
呆帳
ROE
```

壽險型可重點觀察：

```text
匯率
避險成本
債券
股市
資本適足
```

證券型可重點觀察：

```text
台股成交量
證券手續費
ETF
資本市場
承銷
```

---

# 74. 金控股息觀察

金控頁新增：

```text
現金股利
股票股利
現金殖利率
近 5 年配息
配息率
除息日
最後買進日
填息狀態
```

用於長期收益型觀察。

---

# 75. 金控法人觀察

時間：

```text
當日
近 5 日
近 20 日
```

包含：

```text
外資
投信
自營商
三大法人
大戶持股變化
```

顯示：

```text
強勢偏多
偏多
中性
偏弱
強勢偏弱
```

---

# 76. 金控景氣環境

新增金融環境提示：

```text
利率環境
匯率環境
台股成交量
債券環境
```

此項是：

```text
環境資訊
```

不是：

```text
個股直接加分項目
```

未來需再研究哪些指標適合量化。

---

# 77. 個股頁族群提示

個股頁可以顯示：

```text
主要族群
+
族群目前偏好狀態
```

Example：

```text
主要族群
記憶體

狀態
強勢偏多
```

以顏色顯示即可。

建議：

```text
強勢偏多
紅 / 深色

偏多
橘

中性
灰

偏弱
藍
```

實際 UI 色彩日後再確認。

族群狀態：

```text
不得影響個股分數
```

---

# 78. 個股頁分析師提示

個股頁可以顯示：

```text
近期分析師關注
```

Example：

```text
近期分析師關注
2 人
```

點擊後查看：

```text
分析師
日期
評論
分析面向
```

同樣：

```text
不影響個股分數
```

---

# 79. V3 頁面總覽

目前預計主要頁面：

```text
1. 個股排行
2. 個股明細
3. 族群資金
4. 分析師觀點
5. ETF 持股異動
6. 金控股觀察
7. Watchlist
8. Holdings
```

---

# 80. 個股排行

個股排行維持簡潔。

Example：

```text
#1 2330 台積電

綜合評分
86

基本面
82

籌碼面
79

技術面
91

Stage
突破

族群
半導體 ●

最新價
1285

買進參考區
1245 ~ 1270

目前風險
5.3%
```

不可在 TOP10 塞入所有指標。

詳細資料：

```text
點擊後進個股明細
```

---

# 81. 個股明細

個股明細預計：

```text
綜合評分

基本面
籌碼面
技術面

進場時機

Stage

Latest Price
Buy Zone
Breakout Price
Distance
Risk Price
Risk %
Trailing Risk
Target Zone
Reward / Risk

族群提示

ETF 持股提示

分析師提示

Entry Advice
Position Advice
```

UI 最終全部繁體中文。

---

# 82. V3 三套外部觀察模型

重要：

個股評分之外，目前有三套獨立觀察系統：

```text
族群資金模型
分析師觀點模型
ETF 持股異動模型
```

另外：

```text
金控股
```

使用專屬觀察頁。

這些系統：

```text
可以互相參照
```

但：

```text
不可直接污染個股基本面
籌碼面
技術面評分
```

---

# 83. V3 最重要的模型邊界

正式原則：

```text
個股模型
→ 判斷股票本身

族群頁
→ 判斷市場資金偏好

分析師頁
→ 判斷市場專業人士近期觀察方向

ETF 頁
→ 判斷大型 ETF 最近調整哪些持股

金控頁
→ 針對金融股使用專屬 KPI
```

不要把所有東西揉成一個「超級總分」。

---

# 84. V3 Final Principle

StockWaveScanner 下一階段不是只回答：

```text
哪一支股票分數最高？
```

而是逐步回答：

```text
這支股票本身好不好？
↓
基本面 / 籌碼面 / 技術面

市場現在偏好什麼？
↓
族群資金

專業分析師最近在研究什麼？
↓
分析師觀點

大型 ETF 最近在調整什麼股票？
↓
ETF 持股異動

如果是金融股：
目前獲利、股息、法人與金融環境如何？
↓
金控股觀察

最後：
現在價格是不是合理？
↓
Stage / Trade Plan
```

核心維持：

> 分數用來找股票，價格結構用來決定行動。

V3 新增：

> 族群告訴我們市場資金偏好，分析師告訴我們市場正在研究什麼，ETF 告訴我們大型資金組合正在調整什麼。

但最終：

> 個股交易判斷仍須回到自身基本面、籌碼面、技術面、價格結構與風險。

我本身不懂PYTHON，在本機使用PYTHON環境，將你提供我的程式碼完整複製貼上，或新增檔案，再執行，最後將該專案上傳至個人公開的GITHUB，運用ACTION排程自動執行，更新資料。現在我們可以開始V3版了，請告訴我該如何做? 如果你需要我先提供什麼，也請告知