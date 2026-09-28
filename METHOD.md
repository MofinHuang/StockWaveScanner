# 2. METHOD.md

這份以後專門當：

> **StockWaveScanner 技術設計書 / 方法論**

把目前已確認的模型與 Domain 設計留下，不放「明天做什麼」。

你目前 METHOD 本身方向其實是對的，例如已把 Turso 定義成歷史真相、JSON 定義成 UI Snapshot，而且明確規定族群 / ETF / 分析師不得直接污染個股評分。:chatgpt-content-reference{index="5"}

我建議直接整理成下面新版：

```markdown
# StockWaveScanner V3 — METHOD.md

## 1. 文件用途

本文件記錄 StockWaveScanner 長期有效的：

- 系統架構
- 資料設計
- 模型方法
- Domain 邊界
- 已確認研究結論

不記錄：

- 今日進度
- 下一步工作
- DEBUG 紀錄

目前進度請看：

```text
GO.md

2. Project Mission
StockWaveScanner 的目的不是：
預測哪一檔一定會漲

而是：
找出值得研究的股票，並判斷目前價格結構是否適合行動。

核心原則：
分數用來找股票，價格結構用來決定行動。

3. Overall Model
正式個股 Overall 只包含：
Fundamental
Chip
Technical

目前 Research Weight：
Fundamental 30%
Chip        30%
Technical   40%

以下資料只做外部觀察：
Sector
ETF
Analyst
News
Popularity

不得直接進 Overall。
4. Technical V2
Technical V1 經目前 Backtest 後淘汰。
Technical V2 保留。
Technical V2：
Trend Structure    35%
Price Position     40%
Momentum Quality   25%

主要概念：
Trend Structure
MA20 / MA60
Close / MA20

Price Position
Close / MA20
Close / MA20 ATR Position

Momentum Quality
5D Return
20D Return
Volume Ratio

Technical 高：
不代表現在適合進場

進場仍由價格結構與 Stage 判斷。
5. Overall V2 / Stage V2
目前保留：
Technical V2
Overall V2
Stage V2

仍屬：
RESEARCH

不是最終 Production Model。
Stage V2：
AVOID
WATCH
SETUP
READY
BREAKOUT
EXTENDED
WAITING_DATA

Stage 必須和：
Overall
Buy Zone
Breakout
Risk
Price Position

共同解讀。
6. Trade Plan
目前主要欄位：
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

目前 Research 計算：
Buy Zone
Low  = MA20 - 0.25 ATR
High = MA20 + 0.50 ATR

Risk Price
= Buy Low - 1.50 ATR

Breakout：
前 20 個交易日 High 最大值
不包含當日

Target：
Buy High + 2 ATR
~
Buy High + 3 ATR

R/R 必須：
Risk > 0
Reward > 0

才計算。
目前 R/R 不控制 Stage。
7. Ranking
Research Priority：
Overall DESC

回答：
哪些股票值得優先研究？

Action Priority：
BREAKOUT
→ READY
→ SETUP

同一 Stage：
Overall DESC

回答：
哪些股票目前較接近可行動位置？

兩者不可混在一起。
8. Data Architecture
正式資料流：
External Sources
↓
GitHub Actions / Scripts
↓
Normalize
↓
Turso
↓
Derived Metrics / Score
↓
UI Snapshot
↓
JSON
↓
GitHub Pages

前端：
不得直接連 Turso

9. Turso vs JSON
Turso：
原始資料
歷史資料
跨日比較資料
Snapshot
可追溯資料

JSON：
最新畫面資料
Derived Result
模型結果
UI 顯示資料

原則：
Turso = 歷史真相

JSON = 畫面快照

10. Current Main Pipeline
目前：
Turso DEV
↓
scripts/export_v2_ui_snapshot.py
↓
stocks.json
↓
scripts/build_v2_scores.py
↓
top10.json
action_priority.json
↓
scripts/build_v3_ui_snapshot.py
↓
v3_ui.json
↓
GitHub Pages

前端主要個股資料：
docs/data/latest/v3_ui.json

11. Sector Domain
資料表：
sector_master
stock_sector_rel
sector_snapshot_daily

Script：
scripts/sync_v3_industry_sector.py
scripts/build_v3_sector_snapshot.py
scripts/export_v3_sectors.py

JSON：
docs/data/latest/sectors.json

族群用途：
判斷目前市場資金偏好哪些產業方向。

主要指標：
1D / 5D / 20D Return
Technical Strength
Breadth
Foreign
Trust
Dealer
Large Holder Change
Above MA20 Ratio
New High Count

族群：
不得直接加入 Overall

12. Analyst Domain
12.1 Purpose
分析師頁用途：
整理公開來源中，市場專業人士近期發布了哪些研究內容。

不得：
分析師提及
→ 個股加分

12.2 Tables
目前：
analyst_master
analyst_source
analyst_comment
analyst_comment_stock
analyst_comment_sector
analyst_comment_factor

關係：
analyst_master
↓
analyst_source
↓
analyst_comment
├─ analyst_comment_stock
├─ analyst_comment_sector
└─ analyst_comment_factor

12.3 Current Analysts
目前：
A001 鐘崑禎
A002 王倚隆
A003 黎志建
A004 陳於晨
A005 林睿閎

12.4 Source Rule
第一階段來源：
YOUTUBE
PODCAST
WEBSITE
OTHER

目前已實作：
YOUTUBE

內容治理原則：
SUMMARY_ONLY

不永久保存：
Full Transcript
完整字幕
完整文章
完整 Caption

保留：
來源
標題
發布日期
來源 URL
Structured Result

12.5 Analyst V1
目前 V1 正式只做：
分析師
日期
YouTube 標題
來源
原始影片連結

時間篩選：
今日
3 日
7 日
30 日
全部

不根據標題自動判斷：
推薦
買進
賣出
看多
看空

12.6 Transcript Research
已驗證：
youtube-transcript-api
faster-whisper
yt-dlp

技術上可取得影片內容。
YouTube Transcript API 存在：
IpBlocked
TranscriptsDisabled

問題。
Whisper small：
CPU 可執行
但長影片耗時高

因此：
Transcript / Whisper / 內容分析延後至後期。

目前不納入：
GitHub Actions Production Pipeline

目前也不使用：
OpenAI
外部 LLM
本機 LLM

13. ETF Domain
ETF 頁目的：
追蹤指定 ETF 最近增加、減少、新進、剔除哪些股票。

不是：
ETF 資金流入流出頁。

預計資料表：
etf_master
etf_holding_daily

至少保存：
trade_date
etf_id
stock_id
shares
weight_pct
market_value

觀察期間：
當日
5D
20D

狀態：
新進
加碼
減碼
剔除

若只有權重：
必須明確標示為權重變化，不可假裝成實際交易。

ETF Domain 不直接影響 Overall。
14. Financial Holding Domain
金控股需使用金融業專屬觀察方式。
一般資料沿用：
Price
Institutional
TDCC
Financial Report

未來可建立：
financial_holding_monthly

觀察：
Monthly Profit
Monthly EPS
YTD Profit
YTD EPS
ROE
Dividend
Yield
Institutional
Interest Rate Environment
FX Environment
Bond Environment
Market Turnover

不得直接硬套一般電子股解讀方式。
15. Domain JSON
原則上依 Domain 分離：
docs/data/latest/

v3_ui.json
sectors.json
analysts.json
etfs.json
financial_holdings.json

避免建立單一無限制增長的大型 JSON。
16. UI Architecture
主要頁面：
首頁
排行
市場
我的

市場：
族群資金
分析師觀點
ETF 持股異動
金控股觀察

我的：
Watchlist
Holdings

17. Analyst Content Governance
公開來源可以整理：
Metadata
自有摘要
結構化標籤
來源連結

不要永久保存：
完整文章
完整逐字稿
完整字幕
完整影片內容

若未來進行 Transcript：
取得
↓
記憶體處理
↓
產生 Structured Result
↓
丟棄原始 Transcript

18. Final Model Boundary
個股
→ Fundamental / Chip / Technical

族群
→ 市場偏好

分析師
→ 市場研究方向

ETF
→ 大型組合調整

金控
→ 金融業專屬資訊

Stage / Trade Plan
→ 價格與風險

不得建立：
所有東西加在一起的超級總分

最終原則：
分數用來找股票，價格結構用來決定行動。