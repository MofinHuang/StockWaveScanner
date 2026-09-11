# StockWaveScanner - Current Handoff / V2 Direction

## 1. 重要：下次開始時不要重新研究目前進度

GPT 在下一次對話開始後，應優先閱讀本段。

不要重新詢問使用者「昨天做到哪裡」。

不要重新做已完成的檔案復原。

不要直接重新跑 TDCC historical backfill。

不要直接重新跑 Price historical backfill。

不要執行：

```powershell
git reset --hard
```

除非已先確認目前未 commit 的檔案全部有安全備份。

絕對不要使用：

```powershell
git push --force
```

---

# 2. 2026-09-11 Current Recovery Status

昨日開發的新功能曾因 Git main 與 origin/main divergence，在同步 GitHub 過程中暫時從 main 工作目錄消失。

已建立本機安全 branch：

```text
backup-before-sync-20260911
```

昨日程式並未遺失。

目前已從該 backup branch 恢復：

```text
scripts/backtest_trade_plan_v2.py
strategy/bullish_v2.py
strategy/trade_plan_v2.py
strategy/foreign_data.py
```

其中：

```text
strategy/scanner.py
```

原本就是空檔，已確認應刪除。

`scripts/debug_*.py` 為使用者刻意瘦身刪除的研究／debug 檔案，不要恢復。

目前以下檔案已通過 Python syntax / import 測試：

```text
strategy/foreign_data.py
strategy/bullish_v2.py
strategy/trade_plan_v2.py
scripts/backtest_trade_plan_v2.py
```

Import test：

```text
IMPORT OK
```

---

# 3. Bullish V2 Current Status

`strategy/bullish_v2.py` 已建立。

主要入口：

```python
evaluate_bullish_v2(...)
```

目前 research score：

```text
Trend       /25
Setup       /20
Momentum    /20
Foreign     /15
TDCC        /20
----------------
Total       /100
```

這是 research model。

不要直接修改既有 production：

```text
Sleep / Chip / Breakout v1
```

Bullish V2 的目的是取代「三關全部 PASS 才推薦」這種過度僵硬的思考方式，建立真正適合選股排名的 Opportunity Score。

---

# 4. Trade Plan V2 Current Status

`strategy/trade_plan_v2.py` 已建立。

主要入口：

```python
evaluate_trade_plan_v2(...)
```

目前可輸出：

```text
latest_close

buy_zone_low
buy_zone_high

risk_price

target_zone_low
target_zone_high

entry_status

action

candidate_eligible
```

設計原則：

* 不修改 DB
* 不使用 date.today()
* 使用 reference_date
* target zone 是 Risk / Reward 模型參考
* target zone 不是價格預測
* EXTENDED 股票即使很強，也不可直接視為適合追價

目前 Trade Plan Config 已包含：

```text
ATR period
recent low window
不同 stage 的 entry zone
risk ATR buffer
minimum risk %
maximum candidate risk %
1.5R target
2.5R target
```

---

# 5. Foreign V2 Research

`strategy/foreign_data.py` 已恢復昨日修改。

TPEx：

```text
STORED
ZERO_INFERRED
INSUFFICIENT_DATA
```

規則維持：

有 official institutional row：

```text
STORED
```

沒有 row，但股票當日有 daily_price，且 qfiiStat crawl SUCCESS：

```text
foreign_net = 0
ZERO_INFERRED
```

不能製造假的：

```text
foreign_buy = 0
foreign_sell = 0
```

TWSE Bullish V2 research 新增：

```python
allow_twse_zero_inferred=True
```

只有 Bullish V2 research 使用。

Production 預設仍：

```python
allow_twse_zero_inferred=False
```

TWSE research 已驗證：

```text
89 組 T86 missing stock/date
89 組在官方 TWT38U 同樣 absent

parser dropped = 0
normalized DB write missing = 0
```

因此 Bullish V2 research 可在：

```text
daily_price 存在
+
TWSE_T86_MARKET crawl SUCCESS
+
institutional row missing
```

時推論：

```text
foreign_net = 0
ZERO_INFERRED
```

但不能推論 buy / sell。

---

# 6. TDCC Historical Current Status

TDCC historical backfill 已完成。

最後結果：

```text
Units    : 23748
SUCCESS  : 15820
SKIP     : 7924
NO_DATA  : 4
ERROR    : 0
```

DB 現況：

```text
TDCC date range:
2026-06-12 ~ 2026-08-28

Distinct TDCC dates:
12

Rows:
23744
```

日期包括：

```text
2026-06-12
2026-06-18
2026-06-26
2026-07-03
2026-07-09
2026-07-17
2026-07-24
2026-07-31
2026-08-07
2026-08-14
2026-08-21
2026-08-28
```

不要重新抓已完成的 TDCC history。

應依：

```text
crawl_logs SUCCESS
```

自動 SKIP。

---

# 7. Price Historical Backtest Problem Found

Trade Plan V2 historical backtest 已建立：

```text
scripts/backtest_trade_plan_v2.py
```

功能包含：

```text
Historical snapshots
Bullish V2 evaluation
Trade Plan evaluation
T+1 entry simulation
Buy zone touch
Fill price
Risk
1.5R / 2R / 2.5R
5D / 10D / 20D return
MFE
MAE
Risk first
Target first
Score group
Stage group
EXTENDED chase research
```

回測避免 look-ahead：

```text
T 日收盤產生 signal
最早 T+1 才可成交
```

問題已確認不是 Git 資料遺失。

目前 daily_prices：

```text
first market date : 2025-07-01
latest market date: 2026-08-14
distinct dates    : 275
rows              : 79634
```

Active stocks：

```text
1979
```

目前：

```text
Price >=30 days:
1951
```

但多數股票最早 Price date：

```text
2026-06-18 : 1947 stocks
```

因此若 reference date 使用：

```text
2026-07-17
```

結果為：

```text
Price >=30 days : 5
TDCC >=4 dates  : 1979
```

所以 historical backtest 只找到：

```text
candidates       : 5
eligible signals : 0
errors           : 0
```

這不是 Bullish V2 bug。

真正原因：

```text
Price historical coverage 不足
```

---

# 8. New Historical Price Backfill

2026-09-11 已新增：

```text
scripts/backfill_market_prices.py
```

目的：

```text
TWSE + TPEx 全 active stocks
historical daily price backfill
```

不使用舊的：

```python
has_price_month()
```

作為完成判斷。

原因：

`has_price_month()` 目前只要該月有一筆 daily_price：

```python
return count > 0
```

就會誤判整個月份完成。

新的 backfill 改用：

```text
crawl_logs
```

判斷。

只有：

```text
status = SUCCESS
```

才 SKIP。

ERROR / RUNNING 可重新 retry。

---

# 9. Price Backfill Raw-first Validation

TWSE 測試：

```text
Stock : 1101
Month : 2026-05

daily_prices = 20
raw_responses = 1
crawl_log = SUCCESS / 20
```

TPEx 測試：

```text
Stock : 1240
Month : 2026-05

daily_prices = 20
raw_responses = 1
crawl_log = SUCCESS / 20
```

因此：

```text
TWSE Raw-first = PASS
TPEx Raw-first = PASS
```

Crawler 可直接重用。

---

# 10. Price Backfill Phase 1

目前第一階段：

2026-05
2026-06

Active stocks × 2 months：

Units = 3958

開始前：

Already SUCCESS = 4
Need download   = 3954

2026-09-11 早上曾開始 TWSE：

python scripts/backfill_market_prices.py `
  --start 2026-05 `
  --end 2026-06 `
  --market TWSE `
  --sleep 0.15

執行接近台股 09:00 開盤時間後開始大量 ERROR，因此使用者已手動 Ctrl+C。

停止時：

Units    : 2178
Processed: 325
SUCCESS  : 58
SKIP     : 1
NO_DATA  : 0
ERROR    : 265

目前工作判斷：

大量 ERROR 很可能與接近台股開盤時間、官方 TWSE 資料來源當時不穩定或限制有關。

目前不優先追查這 265 筆 ERROR，也不要因此修改 crawler。

若未來在收盤後或非盤前／盤中時段仍持續出現大量 ERROR，再重新調查 error_message。

已 SUCCESS 的 request_key 已保存在 crawl_logs，後續重新執行會自動 SKIP，不必重新抓。

# 11. NEXT SESSION — START HERE

下次 GPT 接手後：

不要重新做 Git recovery。

不要重新檢查 Bullish V2 檔案是否遺失。

不要重新跑已完成的 TDCC historical backfill。

不要優先調查 2026-09-11 早上產生的 265 個 TWSE Price ERROR。

第一個工作：

在適合抓資料的非盤前／盤中時段，繼續 TWSE historical Price backfill：

python scripts/backfill_market_prices.py `
  --start 2026-05 `
  --end 2026-06 `
  --market TWSE `
  --sleep 0.15

已 SUCCESS 的 request_key 會自動：

SKIP SUCCESS

所以可以安全續跑。

TWSE 完成後，再跑 TPEx：

python scripts/backfill_market_prices.py `
  --start 2026-05 `
  --end 2026-06 `
  --market TPEx `
  --sleep 0.15

Price historical backfill 完成後，再檢查：

2026-07-17
Price >= 30 days

目前舊結果：

Price >=30 days : 5
TDCC >=4 dates  : 1979

完成 Price backfill 後，Price >=30 days 應明顯增加。

確認 historical coverage 足夠後，才重新執行：

scripts/backtest_trade_plan_v2.py

---

# 12. Project Strategy Direction Has Changed

第一版策略：

```text
Sleep /30
Chip /40
Breakout /30
Total /100
```

並要求：

```text
Sleep PASS
+
Chip PASS
+
Breakout PASS
=
Final PASS
```

研究已證明：

```text
Sleep 與 Breakout 同日高度互斥
```

因此第一版雖然可以算 100 分，但不是使用者真正想要的選股模型。

新版不要再以：

```text
「三關全部 PASS」
```

作為主要推薦邏輯。

使用者真正需要的是：

> 從全市場中找出「近期最值得等待或考慮進場」的股票，而不是找所有條件同一天同時成立的股票。

---

# 13. V2 Investment Philosophy

GPT 應扮演資深台股分析研究夥伴。

可以參考公開可查的台股分析師方法論精神，例如：

```text
鐘崑禎
王倚隆
以及其他成熟的基本面 / 籌碼 / 技術 / 趨勢分析方法
```

但：

不要宣稱完整複製任何分析師私人模型。

不要因為某分析師推薦某股票，就直接加入 TOP10。

系統應自己依資料與回測驗證。

可以借鏡的核心精神：

```text
1. 先選對方向
2. 找強勢或可能轉強的股票
3. 不只看單一技術指標
4. 籌碼必須協助驗證
5. 好股票也要等合理買點
6. 不追已過度延伸的股票
7. 買進前先決定風險價
8. 買進前先有完整交易劇本
9. 賣點與停損的重要性不低於買點
10. 所有規則最後必須用歷史資料回測
```

---

# 14. New TOP10 Definition

新版最重要的輸出不是：

```text
PASS / FAIL
```

而是：

```text
TOP 10 BUY OPPORTUNITIES
```

每天使用最新「已完成交易日」資料掃描：

```text
TWSE + TPEx
```

產生全市場 ranking。

TOP10 代表：

> 目前在趨勢、位置、動能、籌碼與風險報酬綜合考量下，最值得優先觀察的 10 檔。

不是保證上漲。

不是無條件立即買進。

---

# 15. Proposed Opportunity Score V2 /100

目前建議研究以下新版權重：

## A. Trend /20

判斷股票的大方向是否有利。

例如：

```text
價格相對 MA20 / MA60
MA20 slope
中短期趨勢排列
近期高低點結構
```

重點：

```text
不要逆著明顯下降趨勢硬找買點
```

---

## B. Setup / Entry Timing /20

判斷現在是不是「值得準備進場的位置」。

例如：

```text
整理
量縮
回測支撐
靠近 MA10 / MA20
波動收斂
突破前整理
突破後第一次健康拉回
```

這一項取代舊版：

```text
Sleep 必須 30/30
```

Sleep Strong 仍可保留，但不是所有強勢股必經條件。

---

## C. Momentum / Volume /15

判斷價格是否真的開始轉強。

例如：

```text
近高突破
5D / 10D / 20D momentum
成交量放大
收盤靠近高點
突破後是否站穩
```

不要只因單日爆量就給高分。

---

## D. Foreign /15

判斷外資是否支持目前走勢。

研究：

```text
近期淨買超
連續性
由賣轉買
買超加速
價格與外資是否同步
```

必須使用 effective foreign semantic。

ZERO_INFERRED：

```text
foreign_net = 0
```

不可製造 fake buy / sell。

---

## E. TDCC /10

判斷持股結構是否往有利方向改變。

主要觀察：

```text
large_holder_pct
retail_holder_pct
```

偏多方向：

```text
large holders 增加
retail holders 減少
```

最好使用市場橫向 percentile / ranking，而不是單一死門檻。

---

## F. Relative Strength /10

TOP10 必須考慮：

> 這檔股票是否比市場其他股票更強。

可比較：

```text
5D return percentile
10D return percentile
20D return percentile
```

避免只因股票自己上漲，就不知道它其實落後大盤或其他股票。

---

## G. Trade Quality /10

這一項非常重要。

不是「股票很強」就適合今天買。

評估：

```text
目前價格距離 buy zone
risk %
Risk / Reward
是否過度延伸
是否已錯過合理進場位置
```

即使 Bullish Score 很高：

如果：

```text
EXTENDED
```

或：

```text
risk 太大
```

就不能進 TOP10 Buy List。

---

# 16. TOP10 Hard Filters

進入 TOP10 前至少要求：

```text
data_status = READY

candidate_eligible = True

Bullish Score >= research minimum
```

Stage 優先：

```text
SETUP
READY
BREAKOUT
MOMENTUM
```

若：

```text
EXTENDED
```

不可列為「建議追價 TOP10」。

可以列：

```text
強勢觀察
等待拉回
```

若：

```text
WEAK
```

不進 TOP10。

若：

```text
risk_pct > 10%
```

預設不進 candidate。

如果買進區已明顯低於／遠離現價：

```text
WAIT
```

而不是硬給 BUY。

---

# 17. Chinese Stock State Display

網站不要只顯示英文 Stage。

使用者看到的主要狀態：

```text
打底
蓄勢
待發動
突破
動能延續
漲幅延伸
偏弱
```

Bullish V2 internal stage 可保留英文。

UI 顯示使用中文。

其中：

```text
漲幅延伸
```

可能代表非常強，

但：

```text
強 ≠ 現在適合追價
```

因此操作提示通常為：

```text
等待拉回
```

---

# 18. Buy / Risk / Target Model

每一檔 TOP10 必須提供：

```text
模型買進參考區
風險參考價
模型獲利參考區
操作提示
```

## Buy Zone

不要只給單一價格。

使用：

```text
buy_zone_low ~ buy_zone_high
```

可綜合：

```text
ATR
MA10 / MA20
近期支撐
突破位
近期低點
stage
```

---

## Risk Price

買進前必須先知道：

```text
分析錯了要在哪裡離場
```

Risk Price 可依：

```text
近期 swing low
重要支撐
ATR buffer
```

計算。

Risk 不能過大。

---

## Target Zone

使用 Risk / Reward：

```text
1.5R ~ 2.5R
```

作為模型獲利參考區。

這是：

```text
trade planning reference
```

不是：

```text
股價預測
```

---

# 19. Suggested Action Labels

網站操作提示盡量簡單：

```text
可分批布局
等待回測買進區
等待突破確認
突破後可觀察
持有／動能續強
漲幅延伸－不要追價
跌破風險價－退出觀察
偏弱－暫不考慮
資料不足
```

避免輸出太多專業術語。

---

# 20. TOP10 Card Required Fields

第二頁每檔 TOP10 建議至少顯示：

```text
Rank

股票代號
股票名稱

Bullish Score /100

目前狀態
例如：
待發動

最新收盤價

買進參考區

風險參考價

獲利參考區

操作提示

詳細分析按鈕
```

不要在 TOP10 首頁塞所有技術數據。

---

# 21. Detailed Analysis Page / Modal

使用者點：

```text
詳細分析
```

才顯示：

```text
Trend score
Setup score
Momentum score
Foreign score
TDCC score
Relative Strength
Trade Quality

目前狀態判斷原因

近期價格結構

外資變化

TDCC 變化

買進區計算概念

風險價

Risk %

1.5R
2R
2.5R

模型操作劇本
```

並用白話解釋。

不要只顯示：

```text
MA20=xxx
ATR=xxx
```

必須翻譯成：

```text
股價仍維持短期多頭結構
目前接近合理買進區
外資近期由賣轉買
大戶比例增加
目前尚未過度延伸
```

---

# 22. Future Fundamental / Industry Layer

因公開投資方法常包含：

```text
產業趨勢
營收
EPS
成長
低基期
未來展望
```

StockWaveScanner 未來可以增加：

```text
Fundamental / Industry Overlay
```

但目前若 DB 尚無可靠資料：

不要虛構基本面分數。

不要自行從未知資料猜 EPS 或目標價。

應先建立正式資料來源與 backtest，再考慮納入 /100。

目前 Bullish V2 先以：

```text
Price
Trend
Setup
Momentum
Foreign
TDCC
Relative Strength
Trade Quality
```

完成第一階段。

---

# 23. Mobile UI V2

新版網站必須 Mobile First。

不要像第一版把全部資料塞在同一頁。

建議使用手機底部 Navigation：

```text
狀態
TOP10
查股票
```

---

# 24. Page 1 — 系統狀態

第一頁只回答：

> 今天資料有沒有更新成功？

顯示：

```text
StockWaveScanner

資料日期：
YYYY-MM-DD

最後更新：
YYYY-MM-DD HH:MM

Active stocks：
1979

Price ready：
xxxx / 1979

Foreign ready：
xxxx / 1979

TDCC ready：
xxxx / 1979

Ranking ready：
xxxx / 1979

系統狀態：
資料正常
```

如果某資料源失敗：

清楚顯示：

```text
部分資料尚未更新
```

不要假裝正常。

---

# 25. Page 2 — 今日 TOP10

第二頁：

```text
今日 TOP10
```

採手機卡片式列表。

例如：

```text
#1  2330 台積電

看漲強度：82 /100
狀態：待發動

最新：xxx

買進參考：
xxx ~ xxx

風險：
xxx

獲利參考：
xxx ~ xxx

操作：
等待回測後分批布局

[詳細分析]
```

依排名顯示 10 檔。

不要一次展開所有細節。

---

# 26. Page 3 — 股票查詢

第三頁：

```text
股票查詢
```

輸入：

```text
股票代號
```

例如：

```text
2330
```

或股票名稱：

```text
台積電
```

搜尋結果使用與 TOP10 詳細頁相同資料格式。

即使股票不在 TOP10：

仍然顯示：

```text
Bullish Score
狀態
買進區
風險價
獲利區
操作提示
排名
```

若不適合買：

必須直接說：

```text
目前不建議進場
```

並說明原因。

---

# 27. Ranking Output Philosophy

不要讓 TOP10 變成單純：

```text
Score 最大的前 10 名
```

真正排序應考慮：

```text
Score
+
Timing
+
Trade Quality
+
Risk
+
是否已過度延伸
```

例如：

```text
股票 A Score 90
但已 EXTENDED
```

不一定比：

```text
股票 B Score 80
且正進入 READY buy zone
```

更值得買。

所以要區分：

```text
Strongest Stocks
```

與：

```text
Best Current Buy Opportunities
```

使用者主要要的是第二種。

---

# 28. Backtest Requirements Before Production

任何 TOP10 規則修改前都應回測。

至少比較：

```text
5D
10D
20D return

Win rate

MFE
MAE

1.5R target first
2R target first
2.5R target first

Risk first
```

並依：

```text
Score band
Stage
State
Market
```

拆分結果。

尤其比較：

```text
SETUP
READY
BREAKOUT
MOMENTUM
EXTENDED
```

哪一種真正有較好的：

```text
未來報酬
風險報酬
成功率
```

不能只憑感覺修改 production。

---

# 29. Current Priority Order

目前不要先做 UI。

後續順序：

1. 收盤後／非盤前盤中時段續跑 TWSE Price historical backfill

2. 完成 TPEx Price historical backfill

3. 確認 historical Price coverage

4. 跑 Bullish V2 + Trade Plan V2 historical backtest

5. 分析哪種 Stage / Score 真正有效

6. 調整 TOP10 ranking

7. 驗證 Buy Zone / Risk / Target 模型

8. 最後製作 GitHub Pages Mobile V2 UI

不要跳過 historical backtest 直接修改 production ranking。

---

# 30. Communication Rules For Next GPT

使用者不是 Python 專業開發者。

每次只做一個明確步驟。

回答優先格式：

```text
現在做什麼
↓
PowerShell 指令
↓
正常會看到什麼
```

不要一次提供 10 個後續指令。

如果使用者貼出 ERROR：

```text
停止
→ 分析 ERROR
→ 再提供下一個指令
```

不要叫使用者自己猜。

如果已有 AGENTS.md 紀錄：

不要重新詢問前一天做過什麼。

直接從：

```text
NEXT SESSION — START HERE
```

開始。

---

# 31. Investment Output Disclaimer / Semantic

StockWaveScanner 提供的是：

```text
模型研究結果
看漲機會排序
模型買進參考區
風險參考價
Risk / Reward 參考
```

不是保證獲利。

「建議買入價」在系統語意上應稱：

```text
模型買進參考區
```

「賣出價」應區分：

```text
風險退出價
模型獲利參考區
```

避免把單一模型價格描述成確定會發生的市場價格。

---

# 32. Most Important Next Action

下一次回來詢問 GPT 時，不需要再復原昨日程式，也不需要先查 2026-09-11 早上的 Price ERROR。

若目前時間適合進行歷史資料抓取，直接續跑：

python scripts/backfill_market_prices.py `
  --start 2026-05 `
  --end 2026-06 `
  --market TWSE `
  --sleep 0.15

目的：

完成全市場歷史股價 coverage，
讓 Bullish V2 / Trade Plan V2
可以進行有效 historical backtest。

已 SUCCESS 的股票／月份會自動 SKIP。

若再次於非盤前／盤中時段大量出現 ERROR：

停止 backfill，

再檢查 crawl_logs error_message，

不要讓使用者自行猜錯誤原因。

目前不要：

重新抓 TDCC historical
重新做 Git recovery
恢復 scripts/debug_*.py
直接修改 production Sleep / Chip / Breakout
直接製作新版 UI
