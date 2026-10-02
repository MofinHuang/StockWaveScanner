StockWaveScanner V3 — GO.md
Last Updated：
```text
2026-10-02
```
本文件是專案唯一的「進度交接點」。
本文件只記錄：
```text
目前做到哪裡
最新決策
目前未完成項目
下一步工作
```
開發規範：
```text
AGENTS.md
```
版本架構與方法：
```text
METHOD.md
```
---
1. Current Status
目前 StockWaveScanner V3 已完成主要核心：
```text
Historical Data
V3 Score Engine
Technical V2
Overall V2
Stage V2
Trade Plan
Research Priority
Action Priority
V3 UI Snapshot
GitHub Pages
Watchlist
Holdings
```
目前 Market Domain：
```text
族群資金           ✅ V1
分析師觀點         ✅ V1 Metadata
ETF 持股異動       ✅ V1
金控股觀察         🚧 IN PROGRESS
```
目前正式進行：
```text
Financial Holding Domain / 金控股觀察
```
目前金控第一階段已完成：
```text
13 家上市金控研究母體
financial_holding_master
financial_holding_monthly
10 家月獲利 Parser
共同 Incremental Sync
兆豐金 Historical Backfill / YoY 驗證
```
尚未完成：
```text
2883 凱基金
2889 國票金
5880 合庫金

13 家來源完整性整理
歷史 Backfill 策略統一
EPS / ROE
股利 / 殖利率
主要獲利類型
金融環境
Financial Holding UI
```
---
2. Current Model
Overall：
```text
Fundamental 30%
Chip        30%
Technical   40%
```
目前：
```text
Technical V2 → 保留
Overall V2   → 保留
Stage V2     → 保留
```
仍屬：
```text
RESEARCH
```
不要因單日 Snapshot 修改模型。
Financial Holding Domain：
```text
目前不設計 Financial Holding Score
目前不調整一般個股 Overall Score
```
---
3. Current Stage
目前正式 Stage：
```text
AVOID
WATCH
SETUP
READY
BREAKOUT
EXTENDED
WAITING_DATA
```
Ranking：
```text
Research Priority
→ Overall DESC
```
```text
Action Priority
→ BREAKOUT
→ READY
→ SETUP
→ Overall DESC
```
最近一次既有 V3 UI Snapshot：
```text
Total Stocks      : 1,988
Research Priority : 10
Action Priority   : 222

BREAKOUT     : 4
READY        : 207
SETUP        : 11
WATCH        : 1,380
EXTENDED     : 52
AVOID        : 43
WAITING_DATA : 291
```
---
4. Current Production Data Flow
個股：
```text
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
```
Market Domain：
```text
Sector
→ sectors.json

Analyst
→ analysts.json

ETF
→ etfs.json

↓
scripts/build_v3_ui_snapshot.py
↓
v3_ui.json
```
Financial Holding Domain 目前仍在資料層：
```text
各金控官方 / 可驗證公開來源
↓
各公司 Parser
↓
scripts/sync_v3_financial_holding_monthly.py
↓
Turso DEV
financial_holding_monthly
```
尚未進入：
```text
JSON Export
V3 UI
General Overall
```
---
5. V3 UI
主要前端：
```text
docs/index.html
docs/app.js
docs/styles.css
```
目前：
```text
首頁      ✅
排行      ✅
市場      ✅
我的      ✅
Watchlist ✅
Holdings  ✅
```
市場頁：
```text
市場
├─ 族群資金       ✅ V1
├─ 分析師觀點     ✅ V1 Metadata
├─ ETF 持股異動   ✅ V1
└─ 金控股觀察     🚧 DATA LAYER
```
---
6. Sector Domain — COMPLETED V1
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
UI 已完成：
```text
綜合強度
1D
5D
20D
外資
投信
自營商
大戶變化
族群廣度
MA20 以上比例
創新高家數
成分股展開
點擊進個股明細
```
目前：
```text
不調整族群 Threshold
```
Sector Domain 不直接影響 Overall。
---
7. Analyst Domain — COMPLETED V1 METADATA
目前分析師：
```text
A001 鐘崑禎
A002 王倚隆
A003 黎志建
A004 陳於晨
A005 林睿閎
```
資料表：
```text
analyst_master
analyst_source
analyst_comment
analyst_comment_stock
analyst_comment_sector
analyst_comment_factor
```
`analyst_source`：
```text
UNIQUE (analyst_id, source_url)
```
正式 Script：
```text
scripts/seed_v3_analyst_master.py
scripts/sync_v3_analyst_youtube.py
scripts/export_v3_analysts.py
```
目前 Metadata：
```text
5 位分析師
每位 15 支
總計 75 支
```
正式 Analyst V1：
```text
Metadata + YouTube Link
```
目前篩選：
```text
今日
3 日
7 日
30 日
全部
```
不保存：
```text
完整 Transcript
完整字幕
完整影片內容
```
Analyst Domain 不直接影響 Overall。
---
8. Analyst Deep Content — DEFERRED
已研究：
```text
youtube-transcript-api
yt-dlp
faster-whisper
```
目前已知：
```text
部分影片可直接取得 Transcript
部分影片遇到 IpBlocked / TranscriptsDisabled
Whisper small 可在本機 CPU 執行
長影片處理時間較高
```
目前決策：
```text
分析師深度內容分析延後到最後階段
```
暫時不做：
```text
Transcript Production
Whisper Production
內容摘要 Production
股票辨識
族群辨識
Factor 辨識
GitHub Actions Whisper
```
目前也不使用：
```text
OpenAI
相關外部 LLM
```
進行 Analyst Transcript 分析。
---
9. ETF Domain — COMPLETED V1
目前 ETF：
```text
0050
0056
00878
00919
00929
00981A
009816
```
資料來源：
```text
各投信官方公開來源
```
資料表：
```text
etf_master
etf_holding_daily
```
正式 Script：
```text
scripts/init_v3_etf_schema.py
scripts/seed_v3_etf_master.py
scripts/sync_v3_etf_holdings.py
scripts/export_v3_etfs.py
```
JSON：
```text
docs/data/latest/etfs.json
```
已整合：
```text
scripts/build_v3_ui_snapshot.py
docs/app.js
docs/styles.css
docs/data/latest/v3_ui.json
```
ETF V1 正式狀態：
```text
NEW
INCREASE
DECREASE
REMOVED
UNCHANGED
```
UI 使用：
```text
新進
持股增加
持股減少
剔除
無變化
```
重要：
```text
ETF V1 比較 Holdings Snapshot 差異
不是已確認的實際買進 / 賣出交易
```
比較期間：
```text
1D
5D
20D
```
目前歷史資料採 Daily Workflow 自然累積。
Snapshot 不足：
```text
available = false
```
不得人工製造歷史比較結果。
ETF Domain 不直接影響 Overall。
---
10. Financial Holding Domain — IN PROGRESS
10.1 研究母體
目前上市金控研究母體共 13 家：
```text
2880 華南金
2881 富邦金
2882 國泰金
2883 凱基金
2884 玉山金
2885 元大金
2886 兆豐金
2887 台新新光金
2889 國票金
2890 永豐金
2891 中信金
2892 第一金
5880 合庫金
```
目前研究分類：
```text
2880 BANK
2881 INSURANCE
2882 INSURANCE
2883 MIXED
2884 BANK
2885 SECURITIES
2886 BANK
2887 MIXED
2889 SECURITIES
2890 BANK
2891 BANK
2892 BANK
5880 BANK
```
`holding_type` 目前是研究分類：
```text
不是官方法定分類
```
10.2 Schema
已建立：
```text
financial_holding_master
financial_holding_monthly
```
Schema Script：
```text
scripts/init_v3_financial_holding_schema.py
scripts/seed_v3_financial_holding_master.py
```
`financial_holding_monthly` 目前主要欄位：
```text
stock_id
data_month
monthly_net_profit
ytd_net_profit
ytd_eps
previous_year_ytd_net_profit
ytd_profit_yoy_pct
source_date
source_url
data_status
```
資料庫：
```text
Turso DEV
stockwave-dev
```
10.3 Monthly Earnings Parser
目前已成功：
```text
2880 華南金       ✅
2881 富邦金       ✅
2882 國泰金       ✅
2884 玉山金       ✅
2885 元大金       ✅
2886 兆豐金       ✅
2887 台新新光金   ✅
2890 永豐金       ✅
2891 中信金       ✅
2892 第一金       ✅
```
尚未建立：
```text
2883 凱基金       ⏳ NEXT
2889 國票金       ⏳
5880 合庫金       ⏳
```
目前 Parser：
```text
scripts/parse_v3_financial_holding_huanan.py
scripts/parse_v3_financial_holding_fubon.py
scripts/parse_v3_financial_holding_cathay.py
scripts/parse_v3_financial_holding_esun.py
scripts/parse_v3_financial_holding_yuanta.py
scripts/parse_v3_financial_holding_mega.py
scripts/parse_v3_financial_holding_taishin.py
scripts/parse_v3_financial_holding_sinopac.py
scripts/parse_v3_financial_holding_ctbc.py
scripts/parse_v3_financial_holding_first.py
```
共同 Incremental Sync：
```text
scripts/sync_v3_financial_holding_monthly.py
```
目前策略：
```text
LATEST_MONTHS = 3

各 Parser 取得可用資料
↓
共同 Sync 僅 UPSERT 最近 3 個月
↓
只重算受影響月份 YoY
```
10.4 Current Source Coverage
目前各家公司來源完整度不同。
```text
2885 元大金       歷史資料完整度高，最新 2026-08
2882 國泰金       歷史資料可解析，最新 2026-08
2881 富邦金       多筆 2026 官方公告，歷史仍待補
2887 台新新光金   2026-01 ～ 2026-08
2880 華南金       目前先驗證 2024-12 / 11 / 03，最新資料待補
2884 玉山金       目前 2025-07，Monthly=NULL，不人工反推
2886 兆豐金       2024 + 2025 共 24 筆，已完成 Backfill / YoY
2890 永豐金       目前 2026-08
2891 中信金       目前 8 筆、不連續
2892 第一金       目前 2026-08
```
10.5 Historical Backfill Strategy
今日確立：
```text
第一次建立公司 Collector
→ 可取得歷史時，另外做 Historical Backfill

日常執行
→ Incremental Sync
→ 最近 1～3 個月
```
目的：
```text
保留歷史資料
可計算去年同期 YoY
避免 Daily Sync 每天重寫全部歷史
```
目前已正式驗證：
```text
2886 兆豐金
```
已建立：
```text
scripts/backfill_v3_financial_holding_mega.py
```
Backfill 後 YoY 已驗證：
```text
2025-12  0.95%
2025-11 -0.22%
2025-10 -2.42%
2025-09 -3.53%
2025-08 -5.39%
```
13 家 Collector 完成後：
```text
再統一整理各公司 Historical Backfill
```
10.6 Financial Holding Rules
來源優先順序：
```text
官方 Structured API / CSV
↓
官方可解析頁面 / PDF
↓
公開資訊觀測站內容
↓
可驗證的公告轉載來源
```
目前：
```text
先建立可靠 Collector
再統一整理來源完整性
```
禁止：
```text
為了補資料自行猜數值
為了補單月數字人工反推
把 Missing Data 當成 0
```
金控 Domain：
```text
不直接影響一般 Overall Score
```
目前仍不要設計：
```text
Financial Holding Score
```
---
11. GitHub Actions
Daily Incremental DEV
目前既有 Pipeline：
```text
Daily Incremental Pipeline
↓
Official Industry Sector Sync
↓
Sector Snapshot
↓
ETF Holdings Sync
```
Workflow：
```text
.github/workflows/daily-incremental-dev.yml
```

2026-10-02 已重新檢討每日排程，統一以台灣時間規劃：
```text
每日 02:17        Historical Backfill
週一～週五 20:15  Daily Incremental
週一～週五 20:35  Monthly Revenue
週一～週五 20:50  Quarterly Financial
每日 21:20        V3 UI Build / GitHub Pages
每週日 09:17      TDCC Weekly
```

對應 GitHub Actions UTC cron：
```text
Historical Backfill  17 18 * * *
Daily Incremental     15 12 * * 1-5
Monthly Revenue       35 12 * * 1-5
Quarterly Financial   50 12 * * 1-5
V3 UI                 20 13 * * *
TDCC Weekly            17 1 * * 0
```

排程原則：
```text
當日正式資料先同步
↓
低頻 Fundamental 資料檢查
↓
最後才重建 Score / Domain JSON / V3 UI
```
Historical Backfill 與每日正式資料 Pipeline 分離，避免互相競爭執行資源。

Financial Holding：
```text
目前先完成 Local + Turso DEV 資料層
尚未加入 GitHub Actions
```
等 13 家來源完成並穩定後再決定是否加入 Daily Workflow。
V3 UI DEV
目前包含：
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
Workflow：
```text
.github/workflows/publish-v2-ui-dev.yml
```
目前正式開發 / 測試：
```text
Turso DEV
stockwave-dev
```
未經明確要求不得操作 PROD。
---
12. Current Roadmap
```text
族群資金
✅ V1

分析師觀點
✅ V1 Metadata

ETF 持股異動
✅ V1

金控股觀察
🚧 IN PROGRESS

├─ 13 家 Master          ✅
├─ Monthly Schema        ✅
├─ Monthly Parser        10 / 13
├─ Historical Backfill   🚧 部分完成
├─ EPS / ROE             ⏳
├─ 股利 / 殖利率          ⏳
├─ 主要獲利類型           ⏳
├─ 金融環境               ⏳
└─ UI                    ⏳

ETF 5D / 20D
⏳ 等 Snapshot 自然累積

Technical / Overall 更多驗證
⏳ 後續

分析師 Transcript / Whisper
⏸ 最後階段

跨 Domain 綜合研究
⏳ 後期
```
---
13. NEXT ACTION
下一次直接繼續：
```text
Financial Holding Domain
```
下一家公司：
```text
2883 凱基金
```
流程：
```text
研究官方月獲利來源
↓
建立
scripts/parse_v3_financial_holding_kgi.py
↓
Local Parser 驗證
↓
接入
scripts/sync_v3_financial_holding_monthly.py
↓
Turso DEV 驗證
```
完成 2883 後：
```text
2889 國票金
↓
5880 合庫金
```
13 家 Monthly Collector 全部完成後：
```text
來源完整性盤點
↓
Historical Backfill 統一
↓
YoY 完整性
↓
EPS / ROE
↓
股利 / 殖利率
↓
主要獲利類型
↓
金融環境
↓
再決定 Schema 擴充與 UI
```
目前不要先設計 Score。
---
14. Do Not Restart
下一次不要：
重做 V3 Score Engine
重做 Technical V2
重做 Overall V2
重做 Stage V2
重新 Historical Price Backfill
重做 V3 首頁
重做族群 Schema
重做 sectors.json
重做族群 UI
重做 Analyst Schema
重做 5 位 Analyst Seed
重抓已存在的 75 支 YouTube Metadata
重做 ETF Schema
重新研究已成功的七檔 ETF Parser
重做 Financial Holding Schema
重做 13 家 Financial Holding Master
重做已成功的 10 家 Financial Holding Parser
每天重新 Backfill 金控所有歷史
現在設計 Financial Holding Score
現在把 Financial Holding 加進 Overall
現在繼續做 Whisper / Transcript
操作 Turso PROD
---
15. Development Instruction
下一次開始時：
```text
讀 AGENTS.md
↓
讀 METHOD.md
↓
讀 GO.md
```
然後直接：
```text
2883 凱基金
```
開發規則：
使用者目前偏好直接取得「整份程式碼」，不要拆成多個貼上位置。
一次一個步驟。
發生 ERROR 只處理第一個。
DEV only。
Python 一律使用：
```text
.\.venv\Scripts\python.exe
```
完成功能區塊後再 Commit。
Git 不使用 `git add .`。
完整 Markdown 更新提供實體 `.md` 檔下載。
Financial Holding 日常同步使用 Incremental，不重跑完整歷史。
Historical Backfill 與 Daily Incremental 分開。
---
16. 最近完成
2026-10-02：
```text
修正 Market Index 跨月份 Incremental 重複資料問題。
原因為月份交界時 Current API 仍可能回傳上一交易日，
與上一月份 Historical API 形成相同 market / index / trade_date。

修正 fetch_market_range：
每次月份抓取只接受 row_date 與 month_start 同年月的資料。

本機 DEV 驗證成功：
TWSE 2026-09-30 ～ 2026-10-01 新增 2 筆
TPEx 2026-09-30 ～ 2026-10-01 新增 2 筆
兩邊 Last Data Date 均推進至 2026-10-01
Market Index Pipeline OK

重新檢討並調整 GitHub Actions 排程：
02:17 Historical Backfill
20:15 Daily Incremental
20:35 Monthly Revenue
20:50 Quarterly Financial
21:20 V3 UI Build / GitHub Pages
週日 09:17 TDCC Weekly
```

2026-09-29 Financial Holding Domain：
```text
建立 financial_holding_master
建立 financial_holding_monthly
建立 13 家上市金控 Master

完成並驗證：
2885 元大金
2882 國泰金
2881 富邦金
2887 台新新光金
2880 華南金
2884 玉山金
2886 兆豐金
2890 永豐金
2891 中信金
2892 第一金

建立：
scripts/sync_v3_financial_holding_monthly.py

共同同步策略：
LATEST_MONTHS = 3

完成兆豐金：
2024 / 2025 Historical Backfill
YoY 計算驗證
```
目前完成度：
```text
Financial Holding Monthly Collector
10 / 13
```
下一次：
```text
2883 凱基金
```
---
17. 文件維護規則
專案固定只維護四份 Markdown：
```text
AGENTS.md
→ 開發規則 / 安全規則 / 設計邊界
→ 原則上固定，不隨一般功能開發修改

METHOD.md
→ 目前版本的架構 / 模型 / Domain / 資料規格
→ V3 定版後原則上固定
→ 只有版本升級或大幅規則 / 架構 / UI 異動才修改

GO.md
→ 唯一進度交接點
→ 每次一個完整專案 / Domain / 階段結束前更新

README.md
→ GitHub 專案系統說明
→ 不要求每次功能完成都更新
```
不要再另外維護：
```text
DATA_REQUIREMENT_MATRIX.md
DATA_SOURCE_VERIFICATION.md
```
其必要內容已整合至：
```text
METHOD.md
```