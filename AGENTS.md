# AGENTS.md

## Project
StockWaveScanner

## Purpose
台股全市場掃描器。

目前策略主體：

- Sleep /30
- Chip /40
  - Foreign /20
  - TDCC /20
- Breakout /30
- Total /100

目前最終 PASS 邏輯仍是：

- Sleep PASS
- Chip PASS
- Breakout PASS

三關全部 PASS 才為最終 PASS。

但目前研究結果顯示：
Sleep 與 Breakout 在「同一交易日」高度互斥，
未來可能改成時序型策略，不要直接在未驗證前修改 production 規則。

---

# Current Data Coverage

目前 active stocks：

- Total: 1979
- TWSE: 1089
- TPEx: 890

2026-08-14 coverage：

- Price >= 30 days: 1951 / 1979
- Foreign ready: 1977 / 1979
- TDCC >= 4 dates: 1979 / 1979
- Ranking ready: 1950 / 1979

TDCC coverage 已完成：

- 1974 stocks 有 4 dates
- 5 stocks 有 5 dates
- TDCC < 4 = 0

---

# TPEx Foreign

## Official source

TPEx qfiiStat。

欄位：

- row[1] stock_id
- row[2] stock_name
- row[3] foreign_buy
- row[4] foreign_sell
- row[5] foreign_net

官方單位為「張」。

DB normalization：

- foreign_buy = lot * 1000
- foreign_sell = lot * 1000
- foreign_net = official net lot * 1000

注意：

foreign_net 必須使用官方欄位，
不要自行用 foreign_buy - foreign_sell 重算。

---

## qfiiStat buy/sell semantics

2026-08-14 已驗證：

searchType=buy：

- positive net
- 包含少量 zero net

searchType=sell：

- negative net
- 包含少量 zero net

buy ∪ sell 可完整涵蓋 positive / negative net 股票。

若 active stock 有 daily price，
但當日 qfiiStat crawl 已 SUCCESS 且股票沒有 institutional row：

可推論：

foreign_net = 0

但不能推論：

- foreign_buy
- foreign_sell

因此 effective Foreign 狀態：

- STORED
- ZERO_INFERRED
- INSUFFICIENT_DATA

ZERO_INFERRED 只能補 foreign_net=0，
buy/sell 必須保持 unknown。

---

# TPEx Effective Foreign Weekly Logic

strategy/foreign.py 目前有 effective builder。

重要規則：

使用「該股票自己的 daily_prices 日期」
作為需要 Foreign coverage 的交易日集合。

不要使用整個市場 calendar 強迫每檔股票
每個市場交易日都有 Foreign row。

原因：

個股可能有：

- 停牌
- 暫停交易
- 個別無行情日

因此：

股票有 daily_price
+ qfiiStat SUCCESS
+ institutional row missing
→ ZERO_INFERRED

股票有 daily_price
+ qfiiStat 沒有 SUCCESS 證據
→ INSUFFICIENT_DATA

股票本身沒有 daily_price
→ 不視為 Foreign 缺資料日

最近修正後：

Foreign INSUFFICIENT_DATA 已從 99 檔降到 0
（在 Ranking prefilter 後）。

---

# TDCC

## Latest market data

官方 Open Data：

https://openapi.tdcc.com.tw/v1/opendata/1-5

最新資料一次可抓全市場。

2026-08-14 實測：

- rows = 68476
- securities = 4028
- 4-digit ids = 2961
- levels = 1 ~ 17
- single data_date = 20260814

正式寫入前：

只與 stocks active TWSE/TPEx 主檔做 intersection。

不要只靠「4 碼數字」判定普通股。

---

## TDCC strategy fields

使用：

- level 1
- level 2
- level 15

定義：

retail_holder_pct
= level 1 + level 2

large_holder_pct
= level 15

---

## TDCC historical query

歷史頁：

https://www.tdcc.com.tw/portal/zh/smWeb/qryStock

現行查詢流程已驗證：

1. GET /portal/zh/
   - 建立 JSESSIONID

2. GET /portal/zh/smWeb/qryStock
   - 取得：
     - SYNCHRONIZER_TOKEN
     - SYNCHRONIZER_URI
     - firDate
     - scaDate options

3. POST /portal/zh/smWeb/qryStock
   - method=submit
   - firDate
   - scaDate
   - sqlMethod=StockNo
   - stockNo
   - stockName=""

重要：

SYNCHRONIZER_TOKEN 不能安全重複使用。

已實測：

- 第一次 POST 成功
- 同 token 第二、第三次查詢失敗

因此正式 crawler 必須：

每次 POST 前重新 GET qryStock 取得新 token。

---

## TDCC CDN behavior

直接 requests GET qryStock
可能得到：

HTTP status = 200

但 body 其實：

HTTP 403 Forbidden

Server:

HiNetCDN

因此不能只依賴 response.raise_for_status()。

需要 body-level embedded 403 detection。

成功方式：

- 先 GET homepage
- 建立 JSESSIONID
- 使用 browser-like headers
- Accept-Encoding 只使用：
  - gzip
  - deflate

不要送 br，
除非環境已有 Brotli decoder。

---

# Raw-first principle

所有 crawler 正式寫 normalized DB 前，
都應先保存 Raw。

若 Raw 保存失敗：

停止該同步。

不要在 Raw-first 原則下跳過 Raw
直接寫 normalized DB。

crawl log 應支援：

- RUNNING
- SUCCESS
- ERROR

歷史回補應細粒度 request_key，
例如：

TDCC_HISTORY:<stock_id>:<scaDate>

方便：

- SUCCESS skip
- 中斷續跑
- 單筆 retry
- 單筆 ERROR 不阻斷其他資料

---

# Ranking Current Status

build_ranking() 目前：

ranking rows = 1950

market：

- TWSE = 1080
- TPEx = 870

資料完整性：

INSUFFICIENT_DATA AFTER PREFILTER = 0

目前 status：

- FAIL = 1950
- PASS = 0

這不是資料 coverage bug。

目前為策略交集問題。

---

# Current Strategy Pass Distribution

Full market：

Sleep PASS:
661

Foreign PASS:
24

TDCC PASS:
87

Chip PASS:
2

Breakout PASS:
30

Final PASS:
0

Chip PASS stocks：

1. 6423 億而得
   - Foreign 20
   - TDCC 20
   - Chip 40
   - Sleep FAIL
   - Breakout FAIL

2. 2371 大同
   - Foreign 20
   - TDCC 20
   - Chip 40
   - Sleep FAIL
   - Breakout FAIL

Important intersection result：

- Sleep PASS ∩ Chip PASS = 0
- Chip PASS ∩ Breakout PASS = 0
- Sleep PASS ∩ Breakout PASS = 0
- 2-of-3 main gates PASS = 0

因此不要直接因為 Final PASS=0 就降低分數門檻。

---

# Sleep Analyzer v1

Score:

A. Price near MA20 = 10
B. Volatility contraction = 10
C. Volume contraction = 10

PASS = 30/30

Default rules：

Price:

abs(close - MA20) / MA20 <= 0.05

Volatility:

recent 10-day mean range
/
previous 20-day mean range
<= 0.80

Volume:

recent 10-day mean volume
/
previous 20-day mean volume
<= 0.80

---

# Breakout Analyzer v1

Score:

A. Latest close > previous 20-day high = 10
B. Latest volume / previous 20-day avg >= 1.50 = 10
C. Close near daily high = 10

PASS = 30/30

Close position rule：

(high - close) / (high - low) <= 0.25

---

# Sleep vs Breakout Research

Full market:

Sleep PASS = 661
Breakout PASS = 30
Both PASS = 0

Breakout PASS stocks at current day：

Sleep condition counts：

- price near MA20 = 0 / 30
- volatility contraction = 12 / 30
- volume contraction = 7 / 30

因此「同日 Sleep + Breakout」高度不合理。

主要原因：

Breakout 發生後價格通常已離開 MA20 ±5% 區域。

但 volume 並不是數學上互斥：

Sleep volume condition PASS = 1092
Breakout volume condition PASS = 319
Both volume conditions PASS = 113

---

# Historical Sleep Before Breakout

Breakout PASS = 30

曾在 breakout 前 Sleep PASS：

- within 10 trading days = 10 / 30
- within 20 trading days = 10 / 30
- within 30 trading days = 10 / 30
- within 40 trading days = 10 / 30

因此不是 lookback window 長度問題。

10 檔曾 Sleep PASS：

- 9 stocks: last Sleep PASS = T-1
- 1 stock: T-6

20 / 30 Breakout stocks
在現有歷史資料中沒有 Sleep PASS。

因此不要直接採：

「最近 30 日曾 Sleep PASS」

作為 Breakout 的硬前置條件。

---

# Sleep Condition Snapshots Before Breakout

Breakout PASS 30 stocks：

T-1:

- price = 14 / 30
- volatility = 15 / 30
- volume = 16 / 30
- Sleep PASS = 9 / 30

T-3:

- price = 22 / 30
- volatility = 4 / 30
- volume = 12 / 30
- Sleep PASS = 2 / 30

T-5:

- price = 24 / 30
- volatility = 3 / 30
- volume = 15 / 30
- Sleep PASS = 2 / 30

T-10:

- price = 12 / 30
- volatility = 1 / 30
- volume = 16 / 30
- Sleep PASS = 0 / 30

重要發現：

T-3 / T-5 的主要 blocker 是 volatility contraction。

---

# Sleep Volatility Threshold Sensitivity

Tested:

- 0.80
- 0.85
- 0.90
- 0.95
- 1.00
- 1.10

Sleep PASS among Breakout stocks：

T-1:

- 0.80 = 9/30
- 0.85 = 10/30
- 0.90 = 10/30
- 0.95 = 11/30
- 1.00 = 11/30
- 1.10 = 11/30

T-5:

- 0.80 = 2/30
- 0.85 = 4/30
- 0.90 = 5/30
- 0.95 = 8/30
- 1.00 = 8/30
- 1.10 = 10/30

結論：

0.80 對較早期 setup 確實偏嚴，
但單純放寬 volatility threshold
無法讓大部分 Breakout 股票變成 Sleep setup。

不要直接修改 production：

volatility_ratio_max = 0.80

目前比較合理的研究方向：

保留 Sleep PASS 的嚴格語意，
另外研究較寬鬆的 Sleep Setup。

---

# Candidate Future Direction

不要立即實作。

下一階段候選：

Sleep Strong:

- original Sleep PASS = 30/30

Sleep Setup:

- 最近 N 日曾 Sleep score >= 20
- 或其他 setup score 定義

可能的策略模型：

Setup A:
Sleep / Compression
→ Chip
→ Breakout

Setup B:
Momentum / Continuation
→ Breakout

不要假設所有 Breakout 都必須由 Sleep setup 產生。

---

# Next Recommended Research

下一支 debug：

scripts/debug_sleep_setup_score_before_breakout.py

建議比較：

- previous 1 / 3 / 5 / 10 days
- ever Sleep score >= 20
- ever Sleep score = 30
- Sleep score >= 20 + price near MA20
- Sleep score >= 20 + volume contraction

目的：

判斷 Sleep 應維持硬 PASS，
還是新增獨立的 setup semantic。

---

# Important Rules For Future Agents

1. 不要重新抓已完成的 6000 筆 TDCC history。
2. 不要把 TPEx missing institutional row 直接視為資料不足。
3. TPEx ZERO_INFERRED 只能推論 foreign_net=0。
4. 不要為 ZERO_INFERRED 製造假的 foreign_buy / foreign_sell。
5. TDCC history token 每次 POST 前必須重新 GET。
6. TDCC latest 與 history 使用不同資料來源。
7. 不要因 Final PASS=0 就直接降低策略門檻。
8. 不要直接把 Sleep volatility 0.80 改成 0.95/1.00。
9. 目前策略研究重點是「setup semantic / timing」，不是 data coverage。
10. 所有回測與 snapshot logic 應逐步移除 date.today() dependency，統一使用 as_of_date / reference_date。