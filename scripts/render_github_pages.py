from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


INDEX_HTML = r'''<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0b1220">
  <title>StockWaveScanner</title>
  <style>
    :root { color-scheme: dark; --bg:#07111f; --panel:#0d1b2a; --panel2:#132338; --text:#e6edf7; --muted:#93a4b8; --line:#23364d; --ok:#39d98a; --bad:#ff6b6b; --warn:#ffc857; --accent:#65a8ff; }
    * { box-sizing:border-box; }
    body { margin:0; background:linear-gradient(180deg,#07111f 0%,#0a1524 100%); color:var(--text); font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI","Noto Sans TC",sans-serif; }
    .wrap { max-width:1180px; margin:0 auto; padding:18px 14px 44px; }
    header { display:flex; gap:12px; align-items:flex-start; justify-content:space-between; flex-wrap:wrap; margin-bottom:18px; }
    h1 { margin:0; font-size:clamp(24px,5vw,38px); letter-spacing:.2px; }
    h2 { margin:22px 0 10px; font-size:18px; }
    .sub { color:var(--muted); margin-top:5px; font-size:14px; }
    .pill { border:1px solid var(--line); border-radius:999px; padding:7px 10px; font-weight:700; font-size:13px; background:rgba(255,255,255,.03); }
    .ok { color:var(--ok); } .bad { color:var(--bad); } .warn { color:var(--warn); }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; }
    .card { background:rgba(13,27,42,.92); border:1px solid var(--line); border-radius:14px; padding:14px; min-width:0; }
    .label { color:var(--muted); font-size:12px; margin-bottom:7px; }
    .value { font-size:25px; font-weight:800; line-height:1.1; overflow-wrap:anywhere; }
    .small { font-size:13px; color:var(--muted); margin-top:5px; }
    .steps { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:8px; }
    .step { padding:11px 12px; border-radius:12px; border:1px solid var(--line); background:var(--panel); }
    .step strong { display:block; margin-bottom:4px; }
    .toolbar { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:10px; }
    input, select { background:#0a1626; color:var(--text); border:1px solid var(--line); border-radius:10px; padding:10px 11px; font:inherit; min-height:42px; }
    input { flex:1 1 240px; }
    .table-wrap { overflow:auto; border:1px solid var(--line); border-radius:14px; background:var(--panel); }
    table { border-collapse:collapse; width:100%; min-width:1160px; }
    th, td { padding:10px 9px; border-bottom:1px solid var(--line); text-align:right; font-size:13px; white-space:nowrap; }
    th { position:sticky; top:0; z-index:1; background:#102037; color:#b9c8da; }
    th:nth-child(2),th:nth-child(3),th:nth-child(4),td:nth-child(2),td:nth-child(3),td:nth-child(4) { text-align:left; }
    tr:last-child td { border-bottom:0; }
    .pass { color:var(--ok); font-weight:800; } .fail { color:#aab8c8; } .up { color:#ff7b7b; font-weight:800; } .down { color:#58d68d; font-weight:800; } .flat { color:#c2cfdd; }
    .errorbox { margin-top:12px; border:1px solid #633; background:#29181c; border-radius:12px; padding:12px; color:#ffd7d7; white-space:pre-wrap; overflow:auto; }
    footer { color:var(--muted); font-size:12px; margin-top:26px; line-height:1.7; }
    a { color:var(--accent); }
    @media (max-width:640px) { .wrap{padding:14px 10px 34px}.card{padding:12px}.value{font-size:22px}.grid{grid-template-columns:repeat(2,minmax(0,1fr))} }
  </style>
</head>
<body>
<div class="wrap">
  <header>
    <div><h1>StockWaveScanner</h1><div class="sub" id="subtitle">讀取資料中…</div></div>
    <div class="pill" id="runPill">RUNNING</div>
  </header>

  <h2>每日流程</h2>
  <div class="steps" id="steps"></div>
  <div id="errorArea"></div>

  <h2>資料 Coverage</h2>
  <div class="grid" id="coverage"></div>

  <h2>策略 PASS</h2>
  <div class="grid" id="strategy"></div>

  <h2>最新資料日期</h2>
  <div class="grid" id="dates"></div>

  <h2>Ranking</h2>
  <div class="toolbar">
    <input id="search" placeholder="搜尋股票代號 / 名稱">
    <select id="filter"><option value="all">全部</option><option value="PASS">Final PASS</option><option value="chip">Chip PASS</option><option value="breakout">Breakout PASS</option><option value="sleep">Sleep PASS</option></select>
  </div>
  <div class="small" id="count"></div>
  <div class="table-wrap"><table>
    <thead><tr><th>#</th><th>代號</th><th>名稱</th><th>市場</th><th>今日收盤</th><th>漲跌</th><th>漲跌幅</th><th>成交量</th><th>Sleep</th><th>Foreign</th><th>TDCC</th><th>Chip</th><th>Breakout</th><th>Total</th><th>Final</th></tr></thead>
    <tbody id="ranking"></tbody>
  </table></div>

  <footer>
    此頁面只呈現既有 StockWaveScanner 資料與策略結果；不在前端重新定義策略規則。<br>
    JSON：<a href="summary.json">summary.json</a> · <a href="status.json">status.json</a> · <a href="ranking.json">ranking.json</a>
  </footer>
</div>
<script>
const names={validate_db:'DB 檢查',price_twse:'TWSE Price',price_tpex:'TPEx Price',foreign_twse:'TWSE Foreign',foreign_tpex:'TPEx Foreign',tdcc_latest:'TDCC Latest',ranking_snapshot:'Ranking'};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function card(label,value,small=''){return `<div class="card"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div>${small?`<div class="small">${esc(small)}</div>`:''}</div>`}
function statusClass(s){return s==='SUCCESS'?'ok':s==='ERROR'?'bad':s==='BLOCKED'?'warn':''}
let rows=[];
function num(v,d=2){if(v===null||v===undefined||v==='')return '-';const n=Number(v);return Number.isFinite(n)?n.toLocaleString('zh-TW',{minimumFractionDigits:0,maximumFractionDigits:d}):'-'}
function signed(v,d=2){if(v===null||v===undefined||v==='')return '-';const n=Number(v);if(!Number.isFinite(n))return '-';return `${n>0?'+':''}${num(n,d)}`}
function moveClass(v){const n=Number(v);return n>0?'up':n<0?'down':'flat'}
function renderRanking(){const q=document.querySelector('#search').value.trim().toLowerCase();const f=document.querySelector('#filter').value;const filtered=rows.filter(r=>{const text=`${r.stock_id} ${r.stock_name}`.toLowerCase();if(q&&!text.includes(q))return false;if(f==='PASS'&&r.status!=='PASS')return false;if(f==='chip'&&r.chip_status!=='PASS')return false;if(f==='breakout'&&r.breakout_status!=='PASS')return false;if(f==='sleep'&&r.sleep_status!=='PASS')return false;return true;});document.querySelector('#count').textContent=`顯示 ${filtered.length} / ${rows.length} 檔`;document.querySelector('#ranking').innerHTML=filtered.map(r=>`<tr><td>${r.rank}</td><td>${esc(r.stock_id)}</td><td>${esc(r.stock_name)}</td><td>${esc(r.market)}</td><td><strong>${num(r.close,2)}</strong></td><td class="${moveClass(r.change)}">${signed(r.change,2)}</td><td class="${moveClass(r.change_pct)}">${r.change_pct===null||r.change_pct===undefined?'-':signed(r.change_pct,2)+'%'}</td><td>${num(r.volume,0)}</td><td>${r.sleep_score}</td><td>${r.foreign_score}</td><td>${r.tdcc_score}</td><td>${r.chip_score}</td><td>${r.breakout_score}</td><td><strong>${r.total_score}</strong></td><td class="${r.status==='PASS'?'pass':'fail'}">${esc(r.status)}</td></tr>`).join('');}
async function load(){let status={status:'ERROR',steps:[]}, summary=null;try{status=await (await fetch('status.json',{cache:'no-store'})).json()}catch(e){}try{summary=await (await fetch('summary.json',{cache:'no-store'})).json()}catch(e){}try{rows=await (await fetch('ranking.json',{cache:'no-store'})).json()}catch(e){rows=[]}
 const pill=document.querySelector('#runPill');pill.textContent=status.status||'UNKNOWN';pill.className='pill '+statusClass(status.status);
 document.querySelector('#subtitle').textContent=summary?`資料基準日 ${summary.reference_date} · 網頁產生 ${summary.generated_at}`:`排程日期 ${status.requested_date||'-'} · 本次資料尚未完成`;
 document.querySelector('#steps').innerHTML=(status.steps||[]).map(s=>`<div class="step"><strong>${esc(names[s.name]||s.name)}</strong><span class="${statusClass(s.status)}">${esc(s.status)}</span></div>`).join('')||'<div class="step">尚無執行紀錄</div>';
 const failed=(status.steps||[]).find(s=>s.status==='ERROR');if(failed){document.querySelector('#errorArea').innerHTML=`<div class="errorbox"><strong>${esc(names[failed.name]||failed.name)} 失敗</strong>\n${esc((failed.log_tail||[]).slice(-8).join('\n'))}</div>`}
 if(summary){document.querySelector('#coverage').innerHTML=[card('Active',summary.active_stocks,`TWSE ${summary.active_twse} / TPEx ${summary.active_tpex}`),card('Price ≥30日',summary.price_ready),card('Foreign ready',summary.foreign_ready),card('TDCC ≥4 dates',summary.tdcc_ready),card('Ranking ready',summary.ranking_ready),card('Ranking rows',summary.ranking_rows)].join('');document.querySelector('#strategy').innerHTML=[card('Sleep PASS',summary.sleep_pass),card('Foreign PASS',summary.foreign_pass),card('TDCC PASS',summary.tdcc_pass),card('Chip PASS',summary.chip_pass),card('Breakout PASS',summary.breakout_pass),card('Final PASS',summary.final_pass)].join('');const d=summary.latest_dates||{};document.querySelector('#dates').innerHTML=[card('TWSE Price',d.twse_price||'-'),card('TPEx Price',d.tpex_price||'-'),card('TWSE Foreign',d.twse_foreign||'-'),card('TPEx Foreign',d.tpex_foreign||'-'),card('TDCC',d.tdcc||'-')].join('')}else{document.querySelector('#coverage').innerHTML=card('狀態','尚無可發布 snapshot');document.querySelector('#strategy').innerHTML='';document.querySelector('#dates').innerHTML=''}renderRanking();}
document.querySelector('#search').addEventListener('input',renderRanking);document.querySelector('#filter').addEventListener('change',renderRanking);load();
</script>
</body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="產生 GitHub Pages 靜態網站")
    parser.add_argument("--runtime-dir", default="runtime")
    parser.add_argument("--output-dir", default="docs")
    args = parser.parse_args()

    runtime = Path(args.runtime_dir)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)

    (output / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (output / ".nojekyll").write_text("", encoding="utf-8")

    mapping = {
        "run_status.json": "status.json",
        "summary.json": "summary.json",
        "ranking.json": "ranking.json",
    }
    for source_name, target_name in mapping.items():
        source = runtime / source_name
        target = output / target_name
        if source.exists():
            shutil.copyfile(source, target)
        else:
            fallback = [] if target_name == "ranking.json" else {}
            target.write_text(json.dumps(fallback, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] GitHub Pages output: {output / 'index.html'}")


if __name__ == "__main__":
    main()
