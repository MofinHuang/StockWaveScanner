# 3. GO.md

這一份最重要。

**以後每完成一個 Domain，我們就直接重寫 GO.md 的「目前完成 / 接續點」；不要一直往下 append。**

目前最新版我建議直接改成：

```markdown
# StockWaveScanner V3 — GO.md

Last Updated：

```text
2026-09-28

本文件只記錄：
目前做到哪裡
最新決策
目前未完成項目
下一步工作

開發規範：
AGENTS.md

系統與模型方法：
METHOD.md

1. Current Status
目前 StockWaveScanner V3 已完成主要核心：
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

目前正式進入：
V3 Market Domain 擴充

2. Current Model
Overall：
Fundamental 30%
Chip        30%
Technical   40%

目前：
Technical V2 → 保留
Overall V2   → 保留
Stage V2     → 保留

仍屬：
RESEARCH

不要因單日 Snapshot 修改模型。
3. Current Stage
目前正式 Stage：
AVOID
WATCH
SETUP
READY
BREAKOUT
EXTENDED
WAITING_DATA

Ranking：
Research Priority
→ Overall DESC

Action Priority
→ BREAKOUT
→ READY
→ SETUP
→ Overall DESC

4. Current Production Data Flow
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

5. V3 UI
主要前端：
docs/index.html
docs/app.js
docs/styles.css

目前：
首頁      ✅
排行      ✅
市場      ✅
我的      ✅
Watchlist ✅
Holdings  ✅

市場頁目前：
市場
├─ 族群資金       ✅ V1
├─ 分析師觀點     ✅ V1
├─ ETF 持股異動   ⏳ NEXT
└─ 金控股觀察     ⏳

6. Sector Domain — COMPLETED V1
已完成資料表：
sector_master
stock_sector_rel
sector_snapshot_daily

已完成：
scripts/sync_v3_industry_sector.py
scripts/build_v3_sector_snapshot.py
scripts/export_v3_sectors.py

JSON：
docs/data/latest/sectors.json

GitHub Actions：
已串入族群每日流程

UI 已完成：
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

目前：
不調整族群 Threshold。

7. Analyst Domain — COMPLETED V1
7.1 Analysts
目前：
A001 鐘崑禎
A002 王倚隆
A003 黎志建
A004 陳於晨
A005 林睿閎

7.2 Database
已建立：
analyst_master
analyst_source
analyst_comment
analyst_comment_stock
analyst_comment_sector
analyst_comment_factor

已修正：
analyst_source URL Unique Index

正確應為：
UNIQUE (analyst_id, source_url)

不是：
UNIQUE (source_url)

注意：
scripts/init_v3_analyst_schema.py 在正式 Commit 前仍需確認已同步成 Composite Unique Index。

7.3 Seed
已建立：
scripts/seed_v3_analyst_master.py

5 位分析師已 Seed DEV。
7.4 YouTube Metadata
已建立：
scripts/sync_v3_analyst_youtube.py

目前：
5 位分析師
每位 15 支
總計 75 支

只保存：
video_id
title
published_at
source URL
author

沒有保存：
Transcript
完整字幕
影片內容

8. Analyst Export
已建立：
scripts/export_v3_analysts.py

產生：
docs/data/latest/analysts.json

目前：
Analysts = 5
Comments = 75

9. Analyst UI — COMPLETED V1
已整合：
市場
→ 分析師觀點

不是獨立系統。
目前功能：
5 位分析師
影片日期
影片標題
來源
YouTube 原始連結

今日
3 日
7 日
30 日
全部

目前已測試：
V3 分析師 UI OK

10. Analyst Deep Content — DEFERRED
已研究：
youtube-transcript-api
yt-dlp
faster-whisper

結果：
75 支影片
YouTube Transcript 可取得 33
不可取得 42

Coverage = 44%

也發現：
IpBlocked
TranscriptsDisabled

Whisper fallback：
已成功驗證

small Model 可以在本機 CPU 執行。
但是：
長影片處理時間較長
GitHub Actions 成本 / 時間 / IP 問題仍需研究

因此目前決策：
分析師內容深度分析放到最後階段。

目前正式 Analyst V1：
Metadata + YouTube Link

暫時不做：
Transcript Production
Whisper Production
內容摘要
股票辨識
族群辨識
Factor 辨識
GitHub Actions Whisper

目前也決定：
不使用 OpenAI
不使用相關 LLM

11. Temporary Analyst Research Scripts
以下屬研究 / 測試用途，不是 Production：
test_v3_analyst_youtube_transcript.py
test_v3_analyst_youtube_transcript_coverage.py
test_v3_analyst_whisper_fallback.py
sync_v3_analyst_youtube_transcript.py
analyze_v3_analyst_transcript_local.py

目前：
不加入 GitHub Actions。

後續再決定保留、移入 research、或刪除。
12. Current Cleanup Before Analyst Commit
需確認：
scripts/init_v3_analyst_schema.py

已將：
UNIQUE(source_url)

正式修正為：
UNIQUE(analyst_id, source_url)

避免全新 DEV 初始化時重新產生錯誤 Index。
另外確認需要 Commit 的正式 Analyst 檔案後再統一 Commit。
13. Current Market Roadmap
目前：
族群資金
✅ V1

分析師觀點
✅ V1 Metadata

ETF 持股異動
⏳ 下一階段

金控股觀察
⏳ 後續

分析師 Transcript / Whisper
⏸ 最後階段

14. NEXT ACTION
下一個正式 Domain：
ETF 持股異動
先不要做 UI。
第一步：
確認 ETF 官方公開資料來源
↓
確認每日持股是否可取得
↓
確認 Shares / Weight 欄位
↓
確認歷史資料可否回補
↓
再設計 Schema

目前候選 ETF：
0050
0056
00878
00919
00929

實際清單需在資料來源確認後再定案。
ETF V1 目標：
當日
5D
20D

新進
加碼
減碼
剔除

至少顯示：
ETF
股票代號
股票名稱
目前持股
前期持股
持股變化
目前權重
權重變化
異動類型

ETF：
不直接影響 Overall

15. Do Not Restart
下一次不要：
- 重做 V3 Score Engine
- 重做 Technical V2
- 重做 Overall V2
- 重做 Stage V2
- 重新 Historical Backfill
- 重做 V3 首頁
- 重做族群 Schema
- 重做 sectors.json
- 重做族群 UI
- 重做 Analyst Schema
- 重做 5 位 Analyst Seed
- 重抓已存在的 75 支 YouTube Metadata
- 現在繼續做 Whisper / Transcript
- 操作 Turso PROD
16. Development Instruction
下一次開始時：
讀 AGENTS.md
↓
讀 METHOD.md
↓
讀 GO.md

然後直接：
開始 ETF 持股異動 Domain 的公開資料來源確認與 Schema 規劃。

若修改程式：
1. 優先完整檔案。
2. 一次一個步驟。
3. 發生 ERROR 只處理第一個。
4. DEV only。
5. 功能完成後再 Commit。

---

## 之後固定怎麼維護

以後不用三份一起大改。

例如我們做完 ETF：

```text
AGENTS.md
→ 不動

METHOD.md
→ 補 ETF 最終資料來源、Schema、計算方法

GO.md
→ ETF V1 ✅
→ 下一步改成金控股

如果只是修一個 Bug：
三份都不用改

如果我們 Backtest 後改了 Stage：
METHOD.md
→ 更新模型方法

GO.md
→ 記錄目前已採用新版 Stage

AGENTS.md
→ 不動

如果你改了「以後不能碰 PROD」這種開發規則：
AGENTS.md
→ 才需要改

這樣三份 MD 就不會再越寫越大，也不會出現「AGENTS 說下一步 A、GO 卻說下一步 B」的衝突。
目前我會把 GO.md 視為唯一的進度交接點，下一次從：
ETF 持股異動 → 先確認官方資料來源

開始。