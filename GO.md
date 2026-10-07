# GO.md

## StockWaveScanner V3 - Development Handoff

Last Updated: 2026-10-07

---

## 1. Project

Repository:

```text
https://github.com/MofinHuang/StockWaveScanner
```

Local:

```text
D:\002.Programs\002.Others\Python\StockWaveScanner
```

Branch:

```text
main
```

Local Python must always use:

```powershell
.\.venv\Scripts\python.exe
```

Do not use:

```text
python
py -3.13
```

Development database:

```text
stockwave-dev
```

Production database:

```text
stockwave-prod
```

Current development work must remain DEV only unless explicitly requested otherwise.

---

## 2. Required Reading Order

Before continuing development:

```text
AGENTS.md
↓
METHOD.md
↓
GO.md
```

Priority:

```text
AGENTS.md > METHOD.md > GO.md
```

---

## 3. Development Rules

### 3.1 Existing Working Code

Existing working Parser / Sync should remain unchanged unless there is a confirmed defect in the existing incremental workflow.

Historical data completion should use separate files:

```text
backfill_*.py
```

Working principle:

```text
Existing Parser
    ↓
Keep unchanged

Historical data missing
    ↓
Create separate backfill_*.py

Backfill completed
    ↓
Update YoY

Then
    ↓
Audit Turso DEV
```

Do not modify a working daily Parser merely to support historical backfill.

### 3.2 Error Handling

When execution returns ERROR:

```text
STOP
↓
Handle only the first ERROR
↓
Fix
↓
Rerun
```

Do not simultaneously redesign unrelated parts.

### 3.3 Git

Do not use:

```text
git add .
git reset --hard
git push --force
```

Use explicit files.

### 3.4 Missing Data

Missing data must remain:

```text
NULL
```

or appropriate status such as:

```text
WAITING_DATA
```

Never convert missing data to zero.

### 3.5 Financial Holding Historical Backfill

Historical backfill workflow:

```text
Collect all target months
↓
Validate all target months
↓
Validate YTD continuity
↓
Only then connect to Turso
↓
Upsert
↓
Update YoY
↓
Verify
```

If source validation fails:

```text
Do not write partial historical data
```

---

## 4. V3 Scoring Architecture

Overall score remains:

```text
Fundamental 30
+
Chip 30
+
Technical 40
=
Overall 100
```

The following domains do not directly enter Overall:

```text
Sector
ETF
Analyst
News
Popularity
Financial Holding
```

Financial Holding remains a separate observation domain.

Do not design a Financial Holding score yet.

---

# 5. Financial Holding Domain

## 5.1 Stocks

| Stock ID | Name | Type |
|---|---|---|
| 2880 | 華南金 | BANK |
| 2881 | 富邦金 | INSURANCE |
| 2882 | 國泰金 | INSURANCE |
| 2883 | 凱基金 | MIXED |
| 2884 | 玉山金 | BANK |
| 2885 | 元大金 | SECURITIES |
| 2886 | 兆豐金 | BANK |
| 2887 | 台新新光金 | MIXED |
| 2889 | 國票金 | SECURITIES |
| 2890 | 永豐金 | BANK |
| 2891 | 中信金 | BANK |
| 2892 | 第一金 | BANK |
| 5880 | 合庫金 | BANK |

Business Type UI labels:

```text
BANK       → 銀行型
INSURANCE  → 壽險型
SECURITIES → 證券型
MIXED      → 綜合型
```

---

## 5.2 Tables

### financial_holding_master

Master data for financial holding companies.

### financial_holding_monthly

Fields:

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

Units:

```text
monthly_net_profit = 百萬元
ytd_net_profit     = 百萬元
ytd_eps            = 元
ytd_profit_yoy_pct = %
```

YoY:

```text
(current_ytd / previous_year_same_month_ytd - 1) * 100
```

Rules:

```text
Previous-year YTD missing
→ previous_year_ytd_net_profit = NULL
→ ytd_profit_yoy_pct = NULL

Previous-year YTD = 0
→ ytd_profit_yoy_pct = NULL
```

---

# 6. Financial Holding Implementation Status

## 6.1 Current Parser

Current Monthly Parser coverage:

```text
13 / 13
```

All 13 Financial Holding stocks have a working current parser path.

Shared incremental sync:

```text
scripts/sync_v3_financial_holding_monthly.py
```

Current-year backfill:

```text
scripts/backfill_v3_financial_holding_current_year.py
```

---

## 6.2 Historical Scripts

Historical backfill scripts already used include:

```text
scripts/backfill_v3_financial_holding_huanan.py
scripts/backfill_v3_financial_holding_fubon.py
scripts/backfill_v3_financial_holding_kgi.py
scripts/backfill_v3_financial_holding_ibf.py
scripts/backfill_v3_financial_holding_tcf.py
scripts/backfill_v3_financial_holding_mega.py
scripts/backfill_v3_financial_holding_taishin.py
scripts/backfill_v3_financial_holding_esun.py
scripts/backfill_v3_financial_holding_sinopac.py
scripts/backfill_v3_financial_holding_ctbc.py
scripts/backfill_v3_financial_holding_first.py
```

Do not reopen completed historical scripts unless a confirmed source/data defect is found.

---

## 6.3 Financial Holding UI Export

Exporter:

```text
scripts/export_v3_financial_holdings.py
```

Output:

```text
docs/data/latest/financial_holdings.json
```

Exporter rules:

```text
DEV database only
13 Financial Holding companies only
Missing values remain null
Do not convert null to 0
History keeps latest 24 rows per company
Financial Holding remains independent Domain JSON
```

JSON top-level structure:

```text
generated_at
history_months
summary
holdings
```

Each Holding contains:

```text
stock_id
stock_name
business_type
business_type_label
latest
coverage
history
```

Current summary semantics:

```text
holding_count

latest_data_month

latest_period_holding_count
latest_period_monthly_count
latest_period_ytd_count
latest_period_eps_count
latest_period_yoy_count

latest_period_positive_yoy_count
latest_period_negative_yoy_count
latest_period_flat_yoy_count

type_distribution
```

Important:

```text
latest_period_*
```

must only count companies whose:

```text
latest.data_month == summary.latest_data_month
```

Do not mix older company latest rows into the latest-period summary.

---

# 7. Turso DEV Coverage

Latest audit:

```text
==========================================================================================
FINANCIAL HOLDING MONTHLY COVERAGE SUMMARY
==========================================================================================
Stock         Rows                 Range   Monthly     YTD     EPS     YoY
------------------------------------------------------------------------------------------
2880 華南金        32       2024-01~2026-08        32      32      32      20
2881 富邦金        17       2025-01~2026-08        17      17      17       5
2882 國泰金       176       2012-01~2026-08       176     176     176     164
2883 凱基金        20       2025-01~2026-08        20      20      20       8
2884 玉山金        11       2025-02~2025-12         7      11      11       0
2885 元大金       295       2002-02~2026-08       295     295     295     283
2886 兆豐金        24       2024-01~2025-12        24      24      24      12
2887 台新新光金      20       2025-01~2026-08        20      20      20       8
2889 國票金        20       2025-01~2026-08        20      20      20       8
2890 永豐金        13       2025-01~2026-08        13      13      13       1
2891 中信金        14       2025-01~2026-05        14      14      14       2
2892 第一金        13       2025-01~2026-08        13      13      13       1
5880 合庫金        20       2025-01~2026-08        20      20      20       8
==========================================================================================

AUDIT OK
```

---

## 7.1 Current-Year Coverage Notes

Latest domain month currently available:

```text
2026-08
```

At latest export:

```text
Latest Financial Holding companies: 10 / 13
```

Companies not yet at 2026-08:

```text
2884 玉山金
Latest = 2025-12

2886 兆豐金
Latest = 2025-12

2891 中信金
Latest = 2026-05
```

Additional known sparse current-year coverage:

```text
2881 富邦金
2026-01 / 2026-02 / 2026-04 missing

2891 中信金
2026 currently contains partial months
```

Do not interpret missing current-year rows as zero earnings.

---

# 8. Historical Backfill Status

Historical Financial Holding backfill phase is complete enough for the first Financial Holding Domain UI.

2025 baseline:

```text
2880 華南金       ✅
2881 富邦金       ✅
2882 國泰金       ✅ historical coverage already strong
2883 凱基金       ✅
2884 玉山金       ✅ 2025-02 ~ 2025-12
2885 元大金       ✅ historical coverage already strong
2886 兆豐金       ✅
2887 台新新光金   ✅
2889 國票金       ✅
2890 永豐金       ✅
2891 中信金       ✅
2892 第一金       ✅
5880 合庫金       ✅
```

Important 2884 rule:

```text
2884 2025-01
→ intentionally not backfilled / unavailable
```

Do not claim that a physical `WAITING_DATA` row exists unless one actually exists in DB.

Correct wording:

```text
2025-01 intentionally not backfilled / unavailable
```

or:

```text
維持缺資料 / WAITING_DATA 語意
```

---

# 9. Important Financial Holding Data Notes

## 9.1 2884 玉山金

2025 historical values:

```text
2025-02 Monthly 2724 / YTD 5749 / EPS 0.36
2025-03 Monthly NULL / YTD 8792 / EPS 0.55
2025-04 Monthly NULL / YTD 11300 / EPS 0.71
2025-05 Monthly 2850 / YTD 14152 / EPS 0.88
2025-06 Monthly NULL / YTD 16753 / EPS 1.05
2025-07 Monthly NULL / YTD 20210 / EPS 1.25
2025-08 Monthly 3094 / YTD 23305 / EPS 1.44
2025-09 Monthly 2897 / YTD 26202 / EPS 1.62
2025-10 Monthly 3130 / YTD 29333 / EPS 1.81
2025-11 Monthly 2944 / YTD 32277 / EPS 2.00
2025-12 Monthly 2010 / YTD 34287 / EPS 2.12
```

Use monthly self-report:

```text
2025-12 YTD = 34287
```

Do not replace with later formal annual:

```text
34342
```

because the Domain dataset is monthly self-report data.

---

## 9.2 2887 台新新光金

2025 historical backfill completed.

2026 existing rows received previous-year YTD and YoY.

---

## 9.3 2890 永豐金

2025 historical backfill completed.

Existing:

```text
2026-08 YTD = 33344
Previous-year YTD = 18073
YoY = 84.50%
```

---

## 9.4 2891 中信金

2025 historical backfill completed.

Known existing 2026 rows include:

```text
2026-03
YTD = 23104
YoY = 16.05%

2026-05
YTD = 34790
YoY = 40.99%
```

Current-year coverage remains sparse.

---

## 9.5 2892 第一金

2025 historical backfill completed.

Existing:

```text
2026-08 YTD = 23850
Previous-year YTD = 19655
YoY = 21.34%
```

---

# 10. Data Quality Rules Learned

## 10.1 Announcement Year != Data Year

```text
December earnings
→ usually announced in January next year
```

Historical backfill must support:

```text
target data year
+
next announcement year
```

---

## 10.2 Prefer Holding Company Numbers

Financial Holding articles often contain subsidiary figures.

Always prefer explicit holding-company summary values.

Examples:

```text
凱基金控
合庫金控(合併)
本公司
```

Do not broadly parse subsidiary figures into holding-company data.

---

## 10.3 YTD Reconciliation

Whenever monthly and cumulative data are both available:

```text
Previous YTD
+
Current Monthly
≈
Current YTD
```

must be validated before historical database write.

Tolerance should match source precision.

---

## 10.4 December Special Cases

Some official sources contain both:

```text
December single-month profit
```

and:

```text
full-year cumulative profit
```

Parser/backfill must distinguish these.

Example:

```text
2881 富邦金
2025-12 Monthly = 140
2025-12 YTD     = 120850
2025-12 EPS     = 8.36
```

Never use full-year YTD as December Monthly.

---

# 11. Financial Holding UI Status

Current exporter completed:

```text
scripts/export_v3_financial_holdings.py
```

Current JSON successfully generated:

```text
docs/data/latest/financial_holdings.json
```

Latest verified summary:

```text
holding_count                     = 13
latest_data_month                 = 2026-08
latest_period_holding_count       = 10
latest_period_monthly_count       = 10
latest_period_ytd_count           = 10
latest_period_eps_count           = 10
latest_period_yoy_count           = 10
latest_period_positive_yoy_count  = 10
latest_period_negative_yoy_count  = 0
latest_period_flat_yoy_count      = 0
```

Business type distribution:

```text
BANK       = 7
INSURANCE  = 2
SECURITIES = 2
MIXED      = 2
```

UI location:

```text
市場
↓
其他市場觀察
↓
金控股觀察
```

Do not add a new bottom navigation item.

Existing bottom navigation remains:

```text
首頁
排行
市場
我的
```

Recommended UI flow:

```text
市場
↓
金控股觀察
↓
同頁展開 Financial Holding Domain
↓
Summary
↓
Type Filter
↓
13 Financial Holding companies
↓
Later: click company → Detail Overlay
```

V1 should display:

```text
Company
Stock ID
Business Type
Latest Data Month
YTD Net Profit
YTD EPS
YTD Profit YoY
```

Missing values:

```text
NULL → —
```

Never:

```text
NULL → 0
```

If a company's latest month is older than:

```text
summary.latest_data_month
```

UI should clearly identify it as older-period data.

---

# 12. GitHub Actions

## 12.1 Daily Incremental DEV

Workflow:

```text
.github/workflows/daily-incremental-dev.yml
```

Schedule:

```text
Taiwan Monday-Friday 20:15
UTC Monday-Friday 12:15
```

Current intended sequence:

```text
Daily Incremental Pipeline
↓
V3 Sector Sync
↓
V3 Sector Snapshot
↓
V3 ETF Holdings Sync
↓
V3 Financial Holding Monthly Sync
```

Financial Holding step:

```text
python scripts/sync_v3_financial_holding_monthly.py
```

Status:

```text
Workflow definition updated locally
GitHub Actions execution pending verification
```

Do not mark automation fully verified until GitHub Actions passes.

---

## 12.2 V3 UI DEV

Workflow:

```text
.github/workflows/publish-v2-ui-dev.yml
```

Schedule:

```text
Taiwan every day 21:20
UTC every day 13:20
```

Current intended sequence:

```text
Export V2 Base Snapshot
↓
Build V2 Score
↓
Export V3 Sector
↓
Export V3 ETF
↓
Export V3 Financial Holding
↓
Build V3 UI Snapshot
↓
Validate generated JSON
↓
Upload artifact
↓
GitHub Pages
```

Financial Holding export:

```text
python scripts/export_v3_financial_holdings.py
```

Required output validation:

```text
docs/data/latest/financial_holdings.json
```

Status:

```text
Workflow definition updated locally
GitHub Actions execution pending verification
```

---

# 13. Working Commands

Financial Holding audit:

```powershell
.\.venv\Scripts\python.exe .\scripts\audit_v3_financial_holding_monthly.py
```

Financial Holding incremental sync:

```powershell
.\.venv\Scripts\python.exe .\scripts\sync_v3_financial_holding_monthly.py
```

Financial Holding UI export:

```powershell
.\.venv\Scripts\python.exe .\scripts\export_v3_financial_holdings.py
```

Expected exporter end:

```text
[PASS] Exported:
D:\002.Programs\002.Others\Python\StockWaveScanner\docs\data\latest\financial_holdings.json

FINANCIAL HOLDING EXPORT OK
```

---

# 14. Current Immediate Task

Current task:

```text
Financial Holding automation verification
```

Sequence:

```text
1. Commit Financial Holding exporter
2. Commit workflow updates
3. Push main
4. Manually run Daily Incremental DEV
5. Verify Financial Holding Monthly Sync
6. Manually run V3 UI DEV
7. Verify financial_holdings.json export
8. Verify GitHub Pages artifact
9. Then continue Financial Holding UI implementation
```

If GitHub Actions returns ERROR:

```text
STOP
↓
Handle only first ERROR
↓
Fix
↓
Rerun
```

Do not continue UI changes until the automation path is confirmed.

---

# 15. Session Summary - 2026-10-07

Completed:

```text
Financial Holding historical baseline
- Historical backfill phase completed
- 13-company audit passed
- Missing data remains NULL
- YoY generated where previous-year YTD exists

Financial Holding Export
- Created scripts/export_v3_financial_holdings.py
- DEV-only protection
- 13 companies exported
- Latest 24 history rows per company
- Independent financial_holdings.json
- Correct latest-period summary semantics
- Missing values remain null

Financial Holding Automation
- Added sync_v3_financial_holding_monthly.py to Daily Incremental DEV
- Added export_v3_financial_holdings.py to V3 UI DEV
- Added financial_holdings.json validation
- Pending GitHub Actions runtime verification
```

Next:

```text
Git Sync
↓
GitHub Actions Daily Incremental DEV test
↓
GitHub Actions V3 UI DEV test
↓
Financial Holding UI
```