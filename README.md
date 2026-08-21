# StockWaveScanner — GitHub Daily MVP

這一版的目標只有三件事：

1. **GitHub Actions 每個交易日晚間自動更新資料**
2. **SQLite 資料庫跨次執行保留**
3. **手機直接用 GitHub Pages 看 Coverage、策略 PASS 與 Ranking**

既有 `Sleep / Chip / Foreign / TDCC / Breakout` 策略規則不在這個 MVP 中改動；`AGENTS.md` 仍是策略與資料語意的約束來源。

## 架構

```text
GitHub Actions (Asia/Taipei)
  18:37 weekday primary run
  20:37 weekday retry
        |
        v
GitHub Release: data-latest / stocks-db.zip
        |
        v
Price -> Foreign -> TDCC latest -> Ranking snapshot
        |
        +--> 更新 stocks-db.zip
        +--> GitHub Pages 手機 Dashboard
        +--> ops/latest-run.json
```

第二次排程會沿用 crawler 現有 `crawl_logs`；已經 `SUCCESS` 的單日資料會 skip，因此可作為 retry。

## 第一次啟用（不需要會 Python）

### 1. 準備既有資料庫

在原本可正常使用的 StockWaveScanner 電腦找到：

```text
data\stocks.db
```

Windows 11：在 `stocks.db` 上按右鍵 → **壓縮成 ZIP 檔案**。

ZIP 檔名請改成：

```text
stocks-db.zip
```

ZIP 裡面應直接包含：

```text
stocks.db
```

> Public repository 的 Release asset 也是公開資料。請確認 SQLite 裡只有可公開的市場資料，不含密碼、token、私人資訊。

### 2. 建立 GitHub Release

在 GitHub repository：

**Releases → Draft a new release**

設定：

```text
Tag:   data-latest
Title: StockWaveScanner persistent database
```

上傳 `stocks-db.zip` 後 Publish release。

這個 Release 之後會由 GitHub Actions 自動覆蓋更新，不需要每天手動上傳。

### 3. 開啟 GitHub Pages

Repository：

**Settings → Pages → Build and deployment → Source → GitHub Actions**

### 4. 第一次手動測試

Repository：

**Actions → Daily StockWaveScanner → Run workflow**

`date` 留空，按 **Run workflow**。

成功後，GitHub Pages 會出現手機版網站。

## 每日自動時間

`.github/workflows/daily.yml`：

- 星期一～五 **18:37 Asia/Taipei**：primary
- 星期一～五 **20:37 Asia/Taipei**：retry

GitHub 排程不是即時交易系統，實際開始時間可能因 runner 負載稍有延遲。

## 每日執行順序

```text
validate_db
price_twse
price_tpex
foreign_twse
foreign_tpex
tdcc_latest
ranking_snapshot
```

任一步驟發生錯誤後，後續步驟會標記 `BLOCKED`。手機頁面會顯示本次 `SUCCESS / ERROR / BLOCKED` 狀態；GitHub Actions 本身也會顯示失敗。

## 日期安全

新的單日 entrypoint 都要求顯式日期，例如：

```bash
python scripts/sync_twse_market_daily_one_day.py --date 2026-08-21
python scripts/sync_tpex_market_daily_one_day.py --date 2026-08-21
python scripts/sync_twse_market_institutional_one_day.py --date 2026-08-21
python scripts/sync_tpex_market_institutional.py --date 2026-08-21
```

Ranking 新增 `as_of_date` 邊界，Price / Foreign / TDCC 只讀取 reference date 以前資料，不因 DB 內存在未來資料污染 snapshot。

TDCC `latest` 官方 endpoint 沒有歷史日期參數。`--run-date` 只用來記錄「本次排程日」；真正的 TDCC `data_date` 仍以官方 response 為準，沒有 zero inference 或歷史偽造。

## 手機頁面資料

GitHub Pages 會提供：

- `index.html` — responsive dashboard
- `summary.json` — coverage / PASS summary
- `status.json` — 每日流程狀態
- `ranking.json` — ranking rows

Repository 本身另外保留輕量：

- `ops/latest-run.json`
- `ops/latest-summary.json`

SQLite DB 不 commit 到 Git；它只存在 `data-latest` Release asset。

## 目前刻意不做

- 不改 Sleep / Chip / Foreign / TDCC / Breakout 門檻
- 不把 Final PASS=0 當成資料錯誤
- 不新增 TDCC history refetch
- 不為 TPEx ZERO_INFERRED 製造 `foreign_buy / foreign_sell`
- 不用 FastAPI / Uvicorn / VPS / systemd

詳細資料語意請以 `AGENTS.md` 為準。
