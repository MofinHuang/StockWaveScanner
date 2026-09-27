# StockWaveScanner V3

StockWaveScanner 是一套針對台灣股票市場建立的研究型股票掃描系統。

系統目標不是預測「哪一檔股票明天一定會漲」，而是每天從 TWSE 與 TPEx 股票中，找出：

- 值得優先研究的股票
- 基本面、籌碼面、技術面表現較佳的股票
- 目前價格位置較合理的股票
- 接近可行動區域的股票
- 風險可被量化與管理的股票

核心理念：

> **分數用來找股票，價格結構用來決定行動。**

---

# V3 核心架構

StockWaveScanner V3 將股票研究拆成兩個主要層次。

## 1. 個股模型

個股正式評分只包含：

```text
基本面
+
籌碼面
+
技術面
↓
綜合評分

目前 Research Weight：
基本面 Fundamental   30%
籌碼面 Chip          30%
技術面 Technical     40%

權重目前仍屬 Research Model，未視為最終 Production 定值。
2. 價格結構與交易階段
高分股票不代表目前適合進場。
StockWaveScanner 會再利用價格結構判斷：
Buy Zone
Breakout Price
Risk Price
Target Zone
Stage
Trade Plan

目前核心流程：
Market Regime
↓
Fundamental / Chip / Technical
↓
Overall Score
↓
Price Structure
↓
Stage
↓
Trade Plan
↓
UI

V3 個股評分
基本面 Fundamental
用來回答：
公司本身是否值得持續研究？

主要觀察：
- 月營收
- YoY
- MoM
- EPS
- 毛利率
- 營業利益率
- ROE
- 獲利能力
- 財務狀況
主要資料來源：
- MOPS
- TWSE
- TPEx
籌碼面 Chip
用來回答：
市場資金是否正在支持這支股票？

主要觀察：
- 外資
- 投信
- 自營商
- 三大法人
- TDCC 集保
- 大戶持股
- 持股集中度
- 融資
- 融券
- 籌碼連續性
技術面 Technical V2
Technical V2 不再單純追求「漲得越強分數越高」，而是更重視：
- 趨勢結構
- 價格位置
- 動能品質
主要指標：
MA20
MA60
ATR
5D Return
10D Return
20D Return
Volume Ratio
Breakout Structure
Price Position

Technical V2 Research Weight：
Trend Structure      35%
Price Position       40%
Momentum Quality     25%

Technical V1 已經過 Backtest 後淘汰，目前 V3 使用 Technical V2。
Overall Score
目前 Overall V2：
Fundamental 30%
+
Chip 30%
+
Technical V2 40%

Overall Score 回答的是：
哪些股票值得優先研究？

它不直接代表：
現在適合買進。

是否適合行動，仍需看 Stage 與 Trade Plan。
Stage V2
目前 Stage 包含：
AVOID
WATCH
SETUP
READY
BREAKOUT
EXTENDED
WAITING_DATA

中文概念：
Stage	說明
AVOID	暫不關注
WATCH	持續觀察
SETUP	型態準備 / 蓄勢
READY	接近合理進場位置
BREAKOUT	突破確認
EXTENDED	漲幅延伸
WAITING_DATA	資料不足


Stage 的目的不是替股票貼標籤，而是把價格結構轉換成較容易理解的交易狀態。
Trade Plan
目前 Trade Plan 主要欄位：
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

目前 Research 計算方式：
Buy Zone
Low
=
MA20 - 0.25 ATR

High
=
MA20 + 0.50 ATR

Risk Price
Risk Price
=
Buy Zone Low - 1.50 ATR

Target Zone
Target Low
=
Buy Zone High + 2 ATR

Target High
=
Buy Zone High + 3 ATR

Breakout Price
使用：
前 20 個交易日最高價

不包含當日。
目前 Trade Plan 仍屬 Research Model，後續會持續透過 Historical Backtest 驗證。
Research Priority 與 Action Priority
V3 將股票排序拆成兩種不同目的。
Research Priority
回答：
哪些股票值得優先研究？

排序：
Overall Score DESC

輸出：
top10.json

Action Priority
回答：
哪些股票目前價格位置比較接近可以行動？

Stage 優先順序：
BREAKOUT
↓
READY
↓
SETUP

同一 Stage：
Overall Score DESC

輸出：
action_priority.json

V3 市場觀察模型
除了個股模型以外，V3 規劃加入三套外部觀察系統：
族群資金
分析師觀點
ETF 持股異動

另外建立：
金控股觀察

重要原則：
族群、ETF、分析師不直接影響個股 Fundamental / Chip / Technical Score。

它們屬於額外市場觀察資訊。
族群資金
族群頁主要回答：
市場資金目前偏好哪些產業與題材？

預計觀察：
當日
當週
當月

法人
大戶
主力
成交量
族群廣度
技術強度

族群分類預計至少包含：
INDUSTRY
SUB_INDUSTRY
THEME

例如：
半導體
↓
記憶體
↓
DRAM / HBM / AI 記憶體

族群功能目前屬 V3 下一階段建置項目。
分析師觀點
分析師頁的目的不是建立「分析師推薦分數」。
主要整理：
分析師
日期
來源
標題
摘要
涉及股票
涉及族群
主要分析面向
關鍵因素

預計觀察期間：
當日
近 3 日
近 7 日
近 30 日

分析面向包含：
基本面
籌碼面
技術面
產業面
總體面
事件面

目前指定研究對象：
鐘崑禎
王倚隆
黎志建
陳於晨

分析師功能目前屬 V3 下一階段建置項目。
ETF 持股異動
ETF 頁主要不是看 ETF 資金流入流出。
真正要回答：
ETF 最近增加、減少、新進或剔除了哪些股票？

目前規劃追蹤：
0050
0056
00981A
00878
00919
009816

統計期間：
當日
近 5 日
近 20 日

狀態：
新進
持續加碼
持平
持續減碼
剔除

未來也會整理：
ETF 共識加碼
ETF 共識減碼

ETF 功能目前屬 V3 下一階段建置項目。
金控股觀察
金融股與一般電子股的評估邏輯不同，因此 V3 規劃建立獨立觀察頁。
主要觀察：
最新價
5D Return
20D Return

單月 EPS
累計 EPS
ROE

現金股利
殖利率

法人動向
主要獲利類型
金融環境

金控類型：
銀行型
壽險型
證券型
綜合型

不同類型未來會使用不同的觀察重點。
金控股功能目前屬 V3 下一階段建置項目。
V3 UI
目前 V3 GitHub Pages 已完成第一版。
主要導航：
首頁
排行
市場
我的

首頁
目前顯示：
- 今日市場環境
- TAIEX
- TPEX
- V3 評分概況
- Stage 分布
- 今日優先觀察
- 個股研究排行
排行
目前主要提供：
- 個股研究排行
- Overall Score
- Fundamental
- Chip
- Technical
- Stage
- 最新價格
- 漲跌幅
- 個股搜尋
- Stage 篩選
市場
目前已建立 V3 導覽骨架：
族群資金
分析師觀點
ETF 持股異動
金控股觀察

各 Domain 資料與模型將逐步建置。
我的
分為：
Watchlist
Holdings

Watchlist
用來管理：
- 正在觀察的股票
- Overall
- Fundamental
- Chip
- Technical
- Stage
Holdings
目前可記錄：
- 平均成本
- 股數
- 最新價格
- 未實現損益
- 報酬率
- Stage
未來將加入：
Original Risk
Trailing Risk
Position Advice

個股明細
個股明細不是主導航頁，而是所有股票入口共用的 Detail View。
可由：
首頁
排行
搜尋
Watchlist
Holdings

點擊股票進入。
目前主要內容：
最新價格

交易階段 Stage

綜合評分
基本面
籌碼面
技術面

Technical V2

Trade Plan

買進參考區
突破價
風險價
目標參考區
風險報酬比

Watchlist / Holdings

資料架構
V3 維持：
外部資料來源
↓
GitHub Actions
↓
資料清洗 / 標準化
↓
Turso DEV
↓
Derived Metrics / Score Engine
↓
UI Snapshot Export
↓
JSON
↓
GitHub Pages

前端不直接連接 Turso。
Turso
Turso 主要負責：
原始資料
歷史資料
跨日比較資料
需要回溯的 Snapshot
未來正式模型歷史結果

目前環境：
DEV
stockwave-dev

PROD
stockwave-prod

所有開發、測試與 Research：
只操作 DEV。

除非正式發布，否則不得操作 PROD。
JSON
JSON 負責：
最新畫面快照
模型結果
繁體中文 UI 資料
頁面摘要

概念：
Turso
=
歷史真相

JSON
=
最新畫面快照

目前正式前端：
docs/data/latest/v3_ui.json

V3 Data Domain 規劃
未來預計逐步拆分：
docs/data/latest/

market.json
stocks.json
stock_scores.json
sectors.json
analysts.json
etfs.json
financial_holdings.json
meta.json

完整個股資料未來也可拆分：
docs/data/latest/stocks/2330.json
docs/data/latest/stocks/2454.json

避免首頁一次載入所有個股完整明細。
目前主要程式
正式流程：
scripts/export_v2_ui_snapshot.py
scripts/build_v2_scores.py
scripts/build_v3_ui_snapshot.py

研究 / Backtest：
scripts/backtest_v3_model.py
scripts/backtest_technical_v2_candidate.py
scripts/backtest_stage_v2_candidate.py
scripts/analyze_v3_v2_robustness.py

Research Script 不應在未確認前直接視為 Production Pipeline。
V3 前端
主要檔案：
docs/index.html
docs/app.js
docs/styles.css

資料來源：
docs/data/latest/v3_ui.json

GitHub Pages：
https://mofinhuang.github.io/StockWaveScanner/

Local Development
專案位置：
D:\002.Programs\002.Others\Python\StockWaveScanner

Branch：
main

Python：
.\.venv\Scripts\python.exe

請不要使用：
python

或：
py -3.13

Git 開發規則
禁止：
git push --force

除非明確了解風險。
不要任意使用：
git reset --hard

不要使用：
git add .

請明確指定要提交的檔案。
以下檔案原則上不 Commit：
.env
AGENTS.md
GO.md

Research / Local 文件也應先確認後再提交。
GitHub Pages 發布
完成一個完整功能區塊後：
git status

檢查修改。
例如：
git add docs/index.html docs/app.js docs/styles.css

確認：
git status

Commit：
git commit -m "feat: update V3 UI"

Push：
git push origin main

Backtest
目前 V3 仍屬：
RESEARCH

Technical V2、Overall V2、Stage V2 已通過目前可使用歷史資料的初步比較，但仍不是最終 Production Model。
目前限制包括：
- 有效歷史期間仍短
- Forward Window 有重疊
- 月營收存在可用日期 Proxy
- 部分季財報使用 Research Proxy
- 尚未完整加入市場相對報酬
- 尚未加入交易成本
- 尚需更多歷史資料驗證
因此目前不應因為單日 Snapshot 分布不好，就直接修改：
Technical Score
Overall Weight
Stage Threshold

任何模型調整都應：
建立 Candidate
↓
Historical Backtest
↓
Robustness Check
↓
確認後再更新 Research Model

後續 V3 Roadmap
目前 V3 已完成：
Historical Data
Score Engine

Technical V2
Overall V2
Stage V2

Trade Plan

Research Priority
Action Priority

V3 UI Snapshot

V3 GitHub Pages 第一版

首頁
排行
市場導航
我的股票導航
Watchlist
Holdings 基礎

下一階段預計逐步建置：
族群資金
↓
ETF 持股異動
↓
分析師觀點
↓
金控股觀察
↓
個股頁外部觀察提示
↓
Trailing Risk
↓
Position Advice
↓
更多 Historical Backtest
↓
模型校正

實際順序仍以資料來源可行性與模型研究結果為準。
Final Principle
StockWaveScanner V3 的核心不是只回答：
哪一支股票分數最高？

而是依序回答：
這支股票本身好不好？
↓
基本面 / 籌碼面 / 技術面


現在市場偏好什麼？
↓
族群資金


大型 ETF 最近調整什麼？
↓
ETF 持股異動


市場專業人士近期研究什麼？
↓
分析師觀點


現在價格位置合理嗎？
↓
Stage / Trade Plan


如果已經持有：
↓
如何管理風險與保護獲利？

最終維持兩個核心原則：
分數用來找股票，價格結構用來決定行動。

以及：
族群看資金偏好，ETF 看大型組合調整，分析師看市場研究方向；所有資訊最後仍回到個股本身的基本面、籌碼面、技術面、價格結構與風險。