# StockWaveScanner V3

StockWaveScanner 是一套針對台灣股票市場建立的研究型股票掃描系統。

系統目標不是預測「哪一檔股票明天一定會漲」，而是每天從 TWSE 與 TPEx 股票中找出：

- 值得優先研究的股票
- 基本面、籌碼面、技術面較佳的股票
- 目前價格結構較接近可行動位置的股票
- 可量化 Buy Zone、Breakout、Risk 與 Target 的股票

核心理念：

> **分數用來找股票，價格結構用來決定行動。**

---

## 1. V3 核心架構

```text
External Sources
↓
GitHub Actions / Scripts
↓
Normalize
↓
Turso DEV
↓
Derived Metrics / Score
↓
UI Snapshot
↓
JSON
↓
GitHub Pages
```

前端不直接連接 Turso。

---

## 2. 個股模型

目前個股 Overall Score 只包含：

```text
Fundamental 30%
Chip        30%
Technical   40%
```

目前使用：

```text
Technical V2
Overall V2
Stage V2
```

目前仍屬：

```text
RESEARCH
```

不是最終 Production Model。

---

## 3. Stage V2

目前 Stage：

```text
AVOID
WATCH
SETUP
READY
BREAKOUT
EXTENDED
WAITING_DATA
```

高分股票不代表現在適合進場。

是否適合行動仍需搭配：

```text
Buy Zone
Breakout Price
Risk Price
Target Zone
Stage
Trade Plan
```

---

## 4. Ranking

### Research Priority

回答：

```text
哪些股票值得優先研究？
```

排序：

```text
Overall DESC
```

### Action Priority

回答：

```text
哪些股票目前較接近可行動位置？
```

排序：

```text
BREAKOUT
→ READY
→ SETUP
→ Overall DESC
```

---

## 5. Market Domains

目前 V3 Market Domain：

```text
族群資金           ✅ V1
分析師觀點         ✅ V1 Metadata
ETF 持股異動       ✅ V1
金控股觀察         ⏳ NEXT
```

這些 Market Domain：

```text
不直接加入個股 Overall Score
```

---

## 6. Sector Domain

目前已完成：

```text
sector_master
stock_sector_rel
sector_snapshot_daily
```

主要觀察：

```text
1D / 5D / 20D
法人
大戶變化
族群廣度
MA20 以上比例
創新高家數
成分股
```

輸出：

```text
docs/data/latest/sectors.json
```

---

## 7. Analyst Domain

目前 V1 追蹤：

```text
鐘崑禎
王倚隆
黎志建
陳於晨
林睿閎
```

正式 V1：

```text
Metadata + YouTube Link
```

Transcript / Whisper / 深度內容分析延後至後期。

輸出：

```text
docs/data/latest/analysts.json
```

---

## 8. ETF Domain

目前 V1 追蹤七檔：

```text
0050
0056
00878
00919
00929
00981A
009816
```

資料來源使用各投信官方公開資料。

ETF V1 比較：

```text
Holdings Snapshot 差異
```

正式狀態：

```text
NEW       = 新進
INCREASE  = 持股增加
DECREASE  = 持股減少
REMOVED   = 剔除
UNCHANGED = 無變化
```

ETF Snapshot 差異不等同已確認的實際買進 / 賣出交易。

比較期間：

```text
1D
5D
20D
```

歷史資料不足時：

```text
available = false
```

不人工製造歷史 Snapshot。

輸出：

```text
docs/data/latest/etfs.json
```

---

## 9. V3 UI

GitHub Pages：

```text
https://mofinhuang.github.io/StockWaveScanner/
```

主要導航：

```text
首頁
排行
市場
我的
```

市場：

```text
族群資金
分析師觀點
ETF 持股異動
金控股觀察
```

我的：

```text
Watchlist
Holdings
```

主要前端：

```text
docs/index.html
docs/app.js
docs/styles.css
```

主要資料入口：

```text
docs/data/latest/v3_ui.json
```

---

## 10. Main Scripts

### 個股

```text
scripts/export_v2_ui_snapshot.py
scripts/build_v2_scores.py
scripts/build_v3_ui_snapshot.py
```

### Sector

```text
scripts/sync_v3_industry_sector.py
scripts/build_v3_sector_snapshot.py
scripts/export_v3_sectors.py
```

### Analyst

```text
scripts/seed_v3_analyst_master.py
scripts/sync_v3_analyst_youtube.py
scripts/export_v3_analysts.py
```

### ETF

```text
scripts/init_v3_etf_schema.py
scripts/seed_v3_etf_master.py
scripts/sync_v3_etf_holdings.py
scripts/export_v3_etfs.py
```

### Research / Backtest

```text
scripts/backtest_v3_model.py
scripts/backtest_technical_v2_candidate.py
scripts/backtest_stage_v2_candidate.py
scripts/analyze_v3_v2_robustness.py
```

Research Script 不等於 Production Pipeline。

---

## 11. GitHub Actions

### Daily Incremental DEV

```text
Daily Incremental
↓
Sector Sync
↓
Sector Snapshot
↓
ETF Holdings Sync
```

### V3 UI DEV

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

目前開發與驗證只使用：

```text
stockwave-dev
```

---

## 12. Local Development

Project：

```text
D:\002.Programs\002.Others\Python\StockWaveScanner
```

Branch：

```text
main
```

本機 Python：

```text
.\.venv\Scripts\python.exe
```

不要直接使用：

```text
python
py -3.13
```

GitHub Actions 則由 `actions/setup-python` 建立 Python 環境後使用 `python`。

---

## 13. Documentation

專案固定維護四份 Markdown：

```text
AGENTS.md
→ 開發規則 / 安全規則 / 設計邊界

METHOD.md
→ 目前版本架構 / 模型 / Domain / 資料規格

GO.md
→ 目前進度 / 下一步 / 專案交接點

README.md
→ GitHub 專案系統說明
```

維護原則：

```text
一般功能完成
→ 主要更新 GO.md

版本架構或核心規則大幅調整
→ 更新 METHOD.md

開發安全規則或設計邊界改變
→ 更新 AGENTS.md

對外專案說明需要調整
→ 更新 README.md
```

不再另外維護：

```text
DATA_REQUIREMENT_MATRIX.md
DATA_SOURCE_VERIFICATION.md
```

其必要內容已整合至 `METHOD.md`。

---

## 14. Current Roadmap

```text
個股模型                  ✅
Trade Plan                ✅
Research Priority         ✅
Action Priority           ✅
V3 UI                      ✅

族群資金 V1              ✅
分析師觀點 V1 Metadata   ✅
ETF 持股異動 V1          ✅

金控股觀察                ⏳ NEXT
ETF 5D / 20D              ⏳ 等 Snapshot 累積
更多 Historical Backtest ⏳
分析師 Transcript         ⏸ 後期
跨 Domain 綜合研究        ⏳ 後期
```

---

## 15. Final Principle

StockWaveScanner V3 依序回答：

```text
這支股票本身是否值得研究？
→ Fundamental / Chip / Technical

現在市場偏好什麼？
→ Sector

大型 ETF 組合最近調整什麼？
→ ETF Holdings Snapshot

市場專業人士近期研究什麼？
→ Analyst

現在價格位置合理嗎？
→ Stage / Trade Plan
```

最後維持：

> **分數用來找股票，價格結構用來決定行動。**
