# StockWaveScanner — AGENTS.md

## 0. 文件用途

本文件是 StockWaveScanner 的最高開發規範。

本文件只管理：

- 開發環境
- 安全規則
- Git 規則
- GPT 協作方式
- 不可違反的架構邊界

不在本文件記錄：

- 每日開發進度
- 下一步工作
- 模型研究歷史
- Domain 詳細 Schema
- Backtest 結果

這些內容分別由：

- `METHOD.md`：架構 / 方法 / 模型設計
- `GO.md`：目前進度 / 下一步

管理。

---

# 1. Project

Repository：

```text
https://github.com/MofinHuang/StockWaveScanner

Local：
D:\002.Programs\002.Others\Python\StockWaveScanner

Branch：
main

2. Python Environment
Python 一律使用：
.\.venv\Scripts\python.exe

不得使用：
python
py -3.13

使用者主要開發背景為 C# / MES，不是 Python 專職工程師。
因此程式修改原則：
1. 一次只處理一個明確工作。
2. 大幅修改直接提供完整檔案內容。
3. 不要求使用者自行尋找大量插入位置。
4. 程式碼直接顯示在對話中供複製。
5. 除非使用者要求，不產生下載檔。
6. 發生 ERROR 時停止後續工作，只處理第一個 ERROR。
3. Turso Safety
資料庫：
DEV  = stockwave-dev
PROD = stockwave-prod

所有：
- 開發
- 測試
- Schema Research
- Backtest
- UI Research
- Domain 開發
只能使用：
stockwave-dev

除非使用者明確要求正式發布：
不得操作 stockwave-prod

所有新增 Script 應盡量包含 DEV Safety Check。
4. Git Safety
禁止：
git push --force

禁止：
git reset --hard

除非使用者明確要求。
禁止：
git add .

應使用明確檔案：
git add scripts/xxx.py
git add docs/app.js

不要自行加入：
.env
AGENTS.md
GO.md

除非使用者明確改變此規則。
完成一個完整功能、確認測試正常後，再主動提供：
git diff --check
git status

git add <明確檔案>
git commit -m "..."
git push origin main

不要每個小修改都 Commit。
5. Error Handling
發生 ERROR 時：
停止
↓
只看第一個 ERROR
↓
修正
↓
重新執行
↓
成功後才進下一步

不得一次猜測或處理大量可能問題。
6. StockWaveScanner 核心原則
系統目標：
找出值得研究的股票，並判斷目前價格結構是否適合行動。

核心理念：
分數用來找股票，價格結構用來決定行動。

個股 Overall 僅由：
Fundamental
+
Chip
+
Technical

組成。
目前 Research Weight：
Fundamental 30%
Chip        30%
Technical   40%

以下 Domain 不得直接進入 Overall：
族群
ETF
分析師
新聞
熱門度

7. Model Safety
不得因為：
單一天 Snapshot
單一個股
單一案例
短期畫面結果

就立即調整：
Score Weight
Overall Threshold
Stage Threshold

模型調整必須基於：
Historical Data
+
Backtest
+
多期間比較

缺資料：
NULL / WAITING_DATA

不得：
缺資料 → 0 分

8. Production / Research Boundary
Research Script 不等於 Production Pipeline。
未確認前：
- 不把研究 Script 加入 GitHub Actions
- 不把 Research Threshold 當成最終 Production 規則
- 不因測試成功就直接操作 PROD
所有新 Domain：
DEV
→ 測試
→ UI 驗證
→ Pipeline 驗證
→ 才考慮 Production

9. Frontend Principle
GitHub Pages 前端：
docs/index.html
docs/app.js
docs/styles.css

前端原則：
前端不直接連 Turso

資料經由：
Turso
→ Export
→ JSON
→ GitHub Pages

UI 使用繁體中文。
程式內欄位可以保留英文。
10. Domain Boundary
目前主要 Domain：
個股模型
族群資金
分析師觀點
ETF 持股異動
金控股觀察
Watchlist
Holdings

責任：
個股模型
→ 判斷股票本身

族群資金
→ 判斷市場資金偏好

分析師觀點
→ 整理市場專業人士公開研究內容

ETF 持股異動
→ 觀察大型 ETF 組合調整

金控股
→ 使用金融業專屬 KPI

不得把所有 Domain 混成一個超級總分。
11. Analyst Content Rule
分析師 Domain：
不得直接影響 Overall

第一階段只使用公開來源。
目前正式 V1 僅處理：
分析師
發布日期
來源
影片標題
原始連結

不得：
- 把影片標題直接推論為買進 / 賣出
- 把提及股票等同推薦
- 自動產生看多 / 看空結論
Transcript / Whisper / 內容分析目前屬後期研究，不是正式 Pipeline。
12. Required Reading Order
新的 GPT / Agent 接手時：
1. AGENTS.md
2. METHOD.md
3. GO.md

不可重新詢問使用者已經寫在 GO.md 的進度。
不可重新執行 GO.md 已明確標示完成的工作。
13. Communication Rule
使用：
繁體中文

回答優先格式：
現在做什麼
↓
要改哪個檔案
↓
完整程式
↓
執行指令
↓
正常結果

使用者要求快速開發時：
優先提供可直接複製執行的內容，避免過多背景解釋。