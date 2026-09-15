# StockWaveScanner V2

台股研究與波段選股系統。

StockWaveScanner V2 以「資料先累積、UI 持續可用、評分依資料完整度自動啟用」為核心設計，整合每日行情、法人籌碼、TDCC 集保、月營收、季度財報與市場指數資料，並透過 GitHub Actions 自動更新資料與發布 GitHub Pages Research Dashboard。

> 目前專案仍處於 V2 DEV 階段。  
> 所有開發、資料回補與 UI Export 僅允許操作 Turso DEV。  
> 禁止操作 PROD。

---

## V2 架構

```text
Official Data Sources
        │
        ▼
GitHub Actions
        │
        ├─ Daily Incremental
        ├─ TDCC Weekly
        ├─ Monthly Revenue
        ├─ Quarterly Financial
        └─ Historical Backfill
        │
        ▼
Turso DEV
stockwave-dev
        │
        ▼
scripts/export_v2_ui_snapshot.py
        │
        ▼
docs/data/latest/*.json
        │
        ▼
scripts/build_v2_scores.py
        │
        ▼
GitHub Pages
StockWaveScanner V2 Research Dashboard

前端不直接連線 Turso。

GitHub Actions 會先由 Turso DEV 匯出靜態 JSON Snapshot，再計算 V2 Score，最後發布至 GitHub Pages。

V2 Dashboard

GitHub Pages：

https://mofinhuang.github.io/StockWaveScanner/

目前主要功能：

首頁市場狀態
TAIEX / TPEX 市場指數
資料完整度
Sync State
股票搜尋
股票列表
個股研究明細
技術資料
法人籌碼
TDCC 集保資料
月營收
季財報
Strength Score
Timing Score
Buy Priority
Stage
TOP10
自選股票
持股成本
未實現損益
資料來源與狀態
Stock Master

主要來源：

MOPS 官方資料

目前涵蓋：

TWSE
TPEx
COMMON_STOCK
Daily Price

每日 Incremental 已完成並由 GitHub Actions 執行。

Historical Price 已完成回補：

2024-09-02 ~ 2026-09-11

Historical Price 不需要重新完整 Backfill。

Institutional

每日法人資料 Incremental 已完成。

包含 TWSE / TPEx 法人買賣資料。

Market Index

TAIEX / TPEX Market Index Incremental 已完成。

市場歷史資料會持續累積。

歷史資料不足時：

WAITING_HISTORY

不會將缺少的歷史資料視為 0。

TDCC

TDCC Weekly Incremental 已完成。

TWSE + TPEx COMMON_STOCK 目前已可取得最新集保資料。

Workflow：

.github/workflows/tdcc-weekly-dev.yml
Monthly Revenue

月營收 Incremental 已完成。

Historical Backfill 已完成：

2024-09 ~ 2026-08

歷史月營收不需要重新完整 Backfill。

Quarterly Financial

季度財報 Incremental 已完成。

目前主要來源：

MOPS / MopsFin

財報語意為：

累計季報

不是單季數值。

Historical Backfill 採由近至遠方式逐步補齊。

目前目標：

2026-Q2
2026-Q1
2025-Q4
2025-Q3
2025-Q2
2025-Q1
2024-Q4
2024-Q3

由 GitHub Actions 每日分 Slice 執行，不再由本機長時間完整回補。

Quarterly Financial 特殊格式

MOPS 財報並非所有公司都使用相同 Accounting Label 結構。

一般產業可使用 GENERAL 財報結構，但銀行、保險、金控等公司可能採用不同格式。

系統目前以 MopsFin 實際 Accounting Label 判斷。

遇到非 GENERAL 財報：

[SKIP] non-GENERAL report

不會：

強行套用 GENERAL 格式
將不存在的財報欄位轉成 0
因缺少財報而給股票低分
Historical Backfill

季度歷史財報採 Slice Queue 架構。

主要程式：

scripts/backfill_quarterly_financial_slice.py
scripts/run_historical_backfill_queue.py

Workflow：

.github/workflows/historical-backfill-dev.yml

基本策略：

NEWEST -> OLDEST

預設：

lookback_quarters = 8
slice_size = 100
max_slices = 4

每個 Slice 約處理 100 家公司。

內部 Fetch Batch：

10 stocks

每完成一個 Batch 就直接寫入 Turso DEV，因此不需要等待整個市場完成才保存結果。

進度記錄於：

sync_state

例如：

qfin_hist_2026_q2_twse
qfin_hist_2026_q2_tpex
qfin_hist_2026_q1_twse

狀態可能包含：

PARTIAL
SUCCESS

records_processed 作為 Cursor，下一次排程會從尚未完成的位置繼續。

V2 Score Engine

Score Engine：

scripts/build_v2_scores.py

目前 V2 Provisional Score：

Strength
Trend                  30%
Relative Strength      20%
Momentum + Volume      15%
Chip                   20%
Fundamental            15%
Buy Priority
Strength               65%
Timing                 35%
Data Readiness

StockWaveScanner V2 的核心原則：

Missing Data != Zero Score

缺資料不能被當成低分。

當：

readiness.overall != READY

則：

Strength     = NULL
Timing       = NULL
Buy Priority = NULL
Stage        = WAITING_DATA

該股票：

不進入 TOP10

UI 顯示：

--
WAITING_DATA
資料補齊中

等資料完整後，Score Engine 才會自動開始評分。

UI Snapshot

Turso DEV 不直接暴露給 Browser。

UI 資料流程：

Turso DEV
    ↓
scripts/export_v2_ui_snapshot.py
    ↓
docs/data/latest/*.json
    ↓
scripts/build_v2_scores.py
    ↓
GitHub Pages

docs/data/latest/ 為 GitHub Actions 動態產生資料，不 Commit 至 Repository。

V2 UI Workflow

Workflow：

.github/workflows/publish-v2-ui-dev.yml

流程：

Checkout
    ↓
Python
    ↓
Install requirements-daily.txt
    ↓
Validate DEV Secrets
    ↓
Export V2 UI Snapshot
    ↓
Build V2 Scores
    ↓
Upload Artifact
    ↓
Deploy GitHub Pages
開發環境

Local Repository：

D:\002.Programs\002.Others\Python\StockWaveScanner

Branch：

main

Windows 本機 Python 一律使用：

.\.venv\Scripts\python.exe

不要使用：

python
py -3.13
Turso Environment
DEV
stockwave-dev

目前：

Daily
Backfill
V2 UI
Score Engine
GitHub Actions

全部僅允許操作 DEV。

PROD
stockwave-prod

目前禁止操作。

Secrets

GitHub Actions 使用：

TURSO_DEV_DATABASE_URL
TURSO_DEV_AUTH_TOKEN

Repository 不保存 Token。

以下檔案禁止 Commit：

.env
GO.md
requirements-daily.txt

目前主要 Runtime Dependency：

libsql==0.1.11
python-dotenv==1.2.3
tzdata==2025.2
開發策略

V2 現階段採 UI First：

UI 先上線
    ↓
目前已有資料先顯示
    ↓
缺資料顯示 WAITING_DATA
    ↓
GitHub Actions 每日補歷史資料
    ↓
UI 每次重新 Export
    ↓
資料完整後自動計算 Score
    ↓
TOP10 自動產生

不再等待所有 Historical Backfill 完成後才開發 UI。

開發原則
UI 優先
Incremental 優先
Backfill 由近而遠
長時間工作交給 GitHub Actions
缺資料不得轉成 0
不因缺資料給低分
不重跑已完成的 Historical Dataset
發生錯誤時只處理第一個 Error
完成功能區塊後才 Commit
禁止 git push --force
除非明確確認安全，禁止 git reset --hard
.env 不可 Commit
GO.md 不可 Commit
Turso PROD 不可操作
Current Stage

目前 V2 Dashboard 已成功部署。

已確認：

首頁                  PASS
市場資料              PASS
股票搜尋              PASS
個股明細              PASS
資料完整度            PASS
WAITING_DATA Logic    PASS

季度歷史財報仍透過 Historical Backfill DEV 持續補齊。

下一階段：

Quarterly Financial History
        ↓
Readiness READY
        ↓
Score Generation
        ↓
TOP10
        ↓
Score Model Calibration
        ↓
Backtest
Disclaimer

StockWaveScanner 為資料研究與程式開發專案。

系統產生之 Score、Ranking、TOP10 與其他研究資訊僅供研究參考，不構成任何投資建議。