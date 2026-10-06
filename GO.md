# GO.md

## StockWaveScanner V3 - Development Handoff

Last Updated: 2026-10-06

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

Current working principle:

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

---

# 6. Financial Holding Parser Status

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

# 7. Turso DEV Coverage

## 2880 華南金

```text
2024-01 ~ 2024-12 ✅
2025-01 ~ 2025-12 ✅
2026-01 ~ 2026-08 ✅ existing
```

Historical script:

```text
scripts/backfill_v3_financial_holding_huanan.py
```

Result:

```text
HUA NAN HISTORICAL BACKFILL OK
```

2025 YoY against 2024: ✅

2026-01 ~ 2026-08 YoY against 2025: ✅

Important implementation note:

```text
December earnings
→ usually announced in January next year
```

Therefore historical MOPS backfill must separate target data year from announcement query year.

---

## 2881 富邦金

```text
2025-01 ~ 2025-12 ✅
```

Historical script:

```text
scripts/backfill_v3_financial_holding_fubon.py
```

Result:

```text
FUBON HISTORICAL BACKFILL OK
```

2026 existing rows:

```text
2026-03
2026-05
2026-06
2026-07
2026-08
```

These rows now have PrevYTD / YoY.

Known current-year gaps:

```text
2026-01
2026-02
2026-04
```

Important 2025-12 special case:

```text
2025-12 Monthly = 140.0
2025-12 YTD     = 120850.0
2025-12 EPS     = 8.36
```

Backfill must prioritize single-December profit instead of full-year profit.

---

## 2882 國泰金

Current database coverage:

```text
2012-01 ~ 2026-08
```

Historical coverage strong: ✅

YoY coverage strong: ✅

No immediate historical backfill priority.

---

## 2883 凱基金

```text
2025-01 ~ 2025-12 ✅
2026-01 ~ 2026-08 ✅ existing
```

Historical script:

```text
scripts/backfill_v3_financial_holding_kgi.py
```

Result:

```text
KGI HISTORICAL BACKFILL OK
```

2026-01 ~ 2026-08 now have PrevYTD / YoY.

Important findings:

```text
2025 list URL uses category=all
```

2025 titles often do not contain `2025年`.

Historical discovery must scan both 2025 and 2026 news centers because 2025-12 was announced in 2026-01.

Prefer the Financial Holding summary figures in the official article title. Do not use broad article-body regex first because article bodies also contain subsidiary figures.

2025-09 official fallback:

```text
Monthly = 4528.0
YTD     = 19050.0
EPS     = 1.09
```

---

## 2884 玉山金

Current known DEV coverage:

```text
2025-07 only
```

Known characteristic:

```text
monthly_net_profit = NULL
```

This NULL is intentional based on current source availability.

Historical coverage remains incomplete.

Priority: High

---

## 2885 元大金

Current database coverage:

```text
2002-02 ~ 2026-08
```

Historical coverage strong: ✅

YoY coverage strong: ✅

No immediate historical backfill priority.

---

## 2886 兆豐金

Current database coverage:

```text
2024-01 ~ 2025-12
```

Existing historical backfill:

```text
scripts/backfill_v3_financial_holding_mega.py
```

Historical state:

```text
2024 ✅
2025 ✅
```

Known gap:

```text
2026 current-year data missing
```

This is not a historical backfill problem.

---

## 2887 台新新光金

Current known DEV coverage:

```text
2026-01 ~ 2026-08 ✅
```

Historical 2025:

```text
Not yet backfilled
```

Next planned historical script:

```text
scripts/backfill_v3_financial_holding_taishin.py
```

Recommended next task:

```text
Backfill 2025-01 ~ 2025-12
↓
Validate 12/12
↓
Update 2026-01 ~ 2026-08 YoY
```

---

## 2889 國票金

```text
2025-01 ~ 2025-12 ✅
2026-01 ~ 2026-08 ✅ existing
```

Historical script:

```text
scripts/backfill_v3_financial_holding_ibf.py
```

Result:

```text
IBF HISTORICAL BACKFILL OK
```

2026-01 ~ 2026-08 now have PrevYTD / YoY.

Official source:

```text
https://www.ibf.com.tw/performance_reports
```

Only parse the `本公司` section and avoid subsidiary figures from 國際票券、國票證券、國票創投.

---

## 2890 永豐金

Current known DEV coverage:

```text
2026-08 only
```

Historical coverage incomplete.

Priority: High

---

## 2891 中信金

Current known DEV coverage:

```text
2025-12
2026-03
2026-05
```

Coverage remains sparse.

Current parser uses hardcoded official PDF sources.

Priority: High

---

## 2892 第一金

Current known DEV coverage:

```text
2026-08 only
```

Current parser source is MoneyDJ, which is secondary.

Historical coverage incomplete.

Priority: High

Prefer an official stable source when available.

---

## 5880 合庫金

```text
2025-01 ~ 2025-12 ✅
2026-01 ~ 2026-08 ✅ existing
```

Historical script:

```text
scripts/backfill_v3_financial_holding_tcf.py
```

Result:

```text
TCF HISTORICAL BACKFILL OK
```

2026-01 ~ 2026-08 now have PrevYTD / YoY.

Historical backfill queries:

```text
ROC 114 announcements
+
ROC 115 announcements
```

because 2025-12 was announced in 2026-01.

Parser must always use:

```text
合庫金控(合併)
```

and must not use subsidiary rows.

---

# 8. Historical Backfill Progress

Completed as of 2026-10-06:

```text
2880 華南金      ✅ 2024 + 2025
2881 富邦金      ✅ 2025
2883 凱基金      ✅ 2025
2889 國票金      ✅ 2025
5880 合庫金      ✅ 2025
```

Already historically strong before this round:

```text
2882 國泰金      ✅ long history
2885 元大金      ✅ long history
2886 兆豐金      ✅ 2024 + 2025
```

Still requiring historical/current completeness work:

```text
2884 玉山金
2887 台新新光金
2890 永豐金
2891 中信金
2892 第一金
```

Additional current-year gaps:

```text
2881 富邦金: 2026-01 / 2026-02 / 2026-04
2886 兆豐金: 2026 current-year coverage missing
```

---

# 9. Recommended Next Order

Next session:

```text
1. 2887 台新新光金
   └─ backfill 2025-01 ~ 2025-12

2. 2884 玉山金
   └─ investigate stable official historical source

3. 2890 永豐金
   └─ expand beyond single latest official page

4. 2891 中信金
   └─ replace sparse hardcoded PDF coverage with historical discovery/backfill

5. 2892 第一金
   └─ investigate official source and reduce dependency on secondary source
```

After historical baseline is stable:

```text
Historical Backfill
↓
YoY completeness
↓
EPS / ROE
↓
Dividend / Yield
↓
Main Profit Type
↓
Financial Environment
↓
UI
```

Do not design Financial Holding scoring before the data foundation is stable.

---

# 10. Historical Baseline Strategy

Recommended baseline:

```text
2024-01 ~ 2025-12
```

Reason:

```text
2025 YoY requires 2024
2026 YoY requires 2025
```

Current implementation has prioritized 2025 first for stocks with complete 2026 current-year data because this immediately unlocks 2026 YoY.

Once all 13 companies have comparable 2025 data, continue filling 2024 where sources allow.

---

# 11. Data Quality Rules Learned

## 11.1 Announcement Year != Data Year

```text
December earnings
→ usually announced in January next year
```

Historical backfill must support target data year + next announcement year.

Confirmed for:

```text
2880 華南金
2883 凱基金
5880 合庫金
```

## 11.2 Prefer Holding Company Numbers

Financial Holding articles often contain subsidiary figures.

Always prefer explicit holding-company summary values.

Examples:

```text
凱基金控
合庫金控(合併)
本公司
```

## 11.3 YTD Reconciliation

Whenever monthly and cumulative data are both available:

```text
Previous YTD
+
Current Monthly
≈
Current YTD
```

must be validated before database write.

Tolerance should match source precision.

## 11.4 Historical Backfill Must Be Atomic

Preferred workflow:

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

# 12. Current Audit

Existing audit:

```powershell
.\.venv\Scripts\python.exe .\scripts\audit_v3_financial_holding_monthly.py
```

Previous result:

```text
AUDIT OK
```

Important:

Current audit validates structure/query/basic formatting. It does not by itself prove complete historical coverage.

Historical completeness must additionally check:

```text
expected months
actual months
YTD reconciliation
YoY availability
```

---

# 13. Working Commands

```powershell
.\.venv\Scripts\python.exe .\scripts\audit_v3_financial_holding_monthly.py

.\.venv\Scripts\python.exe .\scripts\backfill_v3_financial_holding_huanan.py

.\.venv\Scripts\python.exe .\scripts\backfill_v3_financial_holding_fubon.py

.\.venv\Scripts\python.exe .\scripts\backfill_v3_financial_holding_kgi.py

.\.venv\Scripts\python.exe .\scripts\backfill_v3_financial_holding_ibf.py

.\.venv\Scripts\python.exe .\scripts\backfill_v3_financial_holding_tcf.py

.\.venv\Scripts\python.exe .\scripts\backfill_v3_financial_holding_mega.py
```

---

# 14. Immediate Next Task

Create:

```text
scripts/backfill_v3_financial_holding_taishin.py
```

Goal:

```text
2887 台新新光金
2025-01 ~ 2025-12
```

Requirements:

```text
Existing Parser unchanged
DEV only
Official source preferred
12/12 required
YTD reconciliation required
Do not write partial rows
After write, update all YoY
Verify 2026-01 ~ 2026-08 PrevYTD / YoY
```

After success:

```text
2887 2025 ✅
2887 2026 YoY ✅
```

Then continue to:

```text
2884 玉山金
```

---

# 15. Session Summary - 2026-10-06

Completed today:

```text
2880 華南金
- Historical backfill 2024 + 2025
- 2025 YoY generated
- 2026 YoY generated
- MOPS cross-year announcement handling confirmed

2881 富邦金
- Historical backfill 2025
- Fixed December full-year vs single-month parsing
- Existing 2026 rows received YoY

2883 凱基金
- Historical backfill 2025
- Fixed 2025 news-list discovery
- Fixed Chinese month parsing
- Prevented subsidiary-data contamination
- Added official 2025-09 fallback
- 2026-01 ~ 08 YoY generated

2889 國票金
- Historical backfill 2025
- 12/12 complete
- YTD reconciliation passed
- 2026-01 ~ 08 YoY generated

5880 合庫金
- Historical backfill 2025
- Cross-year MOPS handling confirmed
- 12/12 complete
- 2026-01 ~ 08 YoY generated
```

Current Historical Backfill completion count:

```text
5 companies completed in this round
+
3 companies already historically strong
```

Next:

```text
2887 台新新光金
```
