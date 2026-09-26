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