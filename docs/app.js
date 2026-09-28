"use strict";

const DATA_FILE = "./data/latest/v3_ui.json";
const SECTOR_FILE = "./data/latest/sectors.json";
const ANALYST_FILE = "./data/latest/analysts.json";
const WATCHLIST_KEY = "stockwavescanner.v3.watchlist";

const state = {
    ui: null,
    market: {},
    researchPriority: [],
    actionPriority: [],
    stocks: [],
    stockMap: new Map(),

    sectorData: null,
    sectors: [],

    analystData: null,
    analysts: [],
    analystPeriod: 7,

    etfData: null,
    etfs: [],
    etfPeriod: "1d",
    etfSelectedId: "ALL",
    etfChangeType: "CHANGED",

    currentPage: "home",
};

document.addEventListener("DOMContentLoaded", async () => {
    bindNavigation();
    bindDetailOverlay();
    await loadData();
    renderAll();
});

async function loadJson(url) {
    const response = await fetch(
        `${url}?t=${Date.now()}`,
        {
            cache: "no-store",
        }
    );

    if (!response.ok) {
        throw new Error(
            `HTTP ${response.status}`
        );
    }

    return await response.json();
}

async function loadData() {
    try {
        const payload = await loadJson(
            DATA_FILE
        );

        let sectorPayload = null;

        try {
            sectorPayload = await loadJson(
                SECTOR_FILE
            );
        }
        catch (error) {
            console.warn(
                "Sector data unavailable",
                error
            );
        }

        let analystPayload = null;

        try {
            analystPayload = await loadJson(
                ANALYST_FILE
            );
        }
        catch (error) {
            console.warn(
                "Analyst data unavailable",
                error
            );
        }

        state.ui = payload;

        state.market =
            payload.market
            || {};

        state.researchPriority =
            payload.research_priority?.rows
            || [];

        state.actionPriority =
            payload.action_priority?.rows
            || [];

        state.stocks =
            payload.stocks
            || [];

        state.stockMap =
            new Map(
                state.stocks.map(
                    stock => [
                        String(
                            stock.stock_id
                        ),
                        stock,
                    ]
                )
            );

        state.sectorData =
            sectorPayload;

        state.sectors =
            sectorPayload?.sectors
            || [];

        state.analystData =
            analystPayload;

        state.analysts =
            analystPayload?.analysts
            || [];

        state.etfData =
            payload.etf
            || null;

        state.etfs =
            payload.etf?.etfs
            || [];

        document
            .getElementById(
                "headerStatus"
            )
            .textContent =
                payload.data_date
                || "READY";
    }
    catch (error) {
        console.error(
            error
        );

        document
            .getElementById(
                "headerStatus"
            )
            .textContent =
                "資料尚未發布";

        renderLoadError(
            error
        );
    }
}

function renderLoadError(error) {
    const page =
        document.getElementById(
            "page-home"
        );

    if (!page) {
        return;
    }

    page.innerHTML = `
        <div class="empty-state">

            <div class="empty-icon">
                ⚠
            </div>

            <div>
                V3 UI 已啟用，但最新資料尚未發布。
            </div>

            <div class="metric-sub">
                ${escapeHtml(
                    error.message
                )}
            </div>

        </div>
    `;
}

function bindNavigation() {
    document
        .querySelectorAll(
            ".nav-item"
        )
        .forEach(
            button => {

                button.addEventListener(
                    "click",
                    () => {
                        switchPage(
                            button.dataset.page
                        );
                    }
                );
            }
        );
}

function switchPage(page) {
    state.currentPage =
        page;

    document
        .querySelectorAll(
            ".page"
        )
        .forEach(
            element => {
                element.classList.remove(
                    "active"
                );
            }
        );

    document
        .querySelectorAll(
            ".nav-item"
        )
        .forEach(
            element => {
                element.classList.remove(
                    "active"
                );
            }
        );

    document
        .getElementById(
            `page-${page}`
        )
        ?.classList.add(
            "active"
        );

    let mainPage =
        page;

    if (
        page === "research"
    ) {
        mainPage =
            "top10";
    }

    if (
        page === "analysts"
    ) {
        mainPage =
            "market";
    }

    if (
        page === "watchlist"
        ||
        page === "holdings"
    ) {
        mainPage =
            "my";
    }

    document
        .querySelector(
            `.nav-item[data-page="${mainPage}"]`
        )
        ?.classList.add(
            "active"
        );

    if (
        page === "research"
    ) {
        renderResearch();

        setTimeout(
            () => {
                document
                    .getElementById(
                        "stockSearch"
                    )
                    ?.focus();
            },
            50
        );
    }

    if (
        page === "watchlist"
    ) {
        renderWatchlist();
    }

    if (
        page === "holdings"
    ) {
        renderHoldings();
    }

    if (
        page === "my"
    ) {
        renderMy();
    }

    if (
        page === "market"
    ) {
        renderMarket();
    }

    if (
        page === "analysts"
    ) {
        renderAnalysts();
    }
}

function renderAll() {
    if (
        !state.ui
    ) {
        return;
    }

    renderHome();

    renderTop10();

    renderMarket();

    renderAnalysts();

    renderMy();

    renderResearch();

    renderWatchlist();

    renderHoldings();
}

function renderHome() {
    const page =
        document.getElementById(
            "page-home"
        );

    if (!page) {
        return;
    }

    const regime =
        state.market?.regime
        || {};

    const twse =
        state.market
            ?.indices
            ?.TWSE
        || {};

    const tpex =
        state.market
            ?.indices
            ?.TPEX
        || {};

    const summary =
        state.ui?.summary
        || {};

    const scores =
        summary.scores
        || {};

    const stages =
        summary.stage_distribution
        || {};

    const actionRows =
        state.actionPriority.slice(
            0,
            10
        );

    page.innerHTML = `

        <div class="hero-card">

            <div class="hero-label">
                今日市場環境
            </div>

            <div class="hero-value">
                ${escapeHtml(
                    regime.label
                    || "資料補齊中"
                )}
            </div>

            <div class="hero-description">
                ${escapeHtml(
                    regime.description
                    || ""
                )}
            </div>

            <div class="metric-sub">
                資料日：
                ${escapeHtml(
                    state.ui.data_date
                    || "--"
                )}
                ・
                Model：
                ${escapeHtml(
                    state.ui.model_version
                    || "--"
                )}
            </div>

        </div>


        <div class="grid-2">

            ${marketIndexCard(
                "上市 TAIEX",
                twse
            )}

            ${marketIndexCard(
                "上櫃 TPEX",
                tpex
            )}

        </div>


        <div class="section-title">
            V3 評分概況
        </div>

        <div class="score-summary-grid">

            ${summaryMetric(
                "可評分股票",
                scores.ready_count,
                "檔"
            )}

            ${summaryMetric(
                "Overall 平均",
                scores.overall_avg,
                ""
            )}

            ${summaryMetric(
                "基本面平均",
                scores.fundamental_avg,
                ""
            )}

            ${summaryMetric(
                "籌碼面平均",
                scores.chip_avg,
                ""
            )}

            ${summaryMetric(
                "技術面平均",
                scores.technical_avg,
                ""
            )}

        </div>


        <div class="section-title">
            Stage 分布
        </div>

        <div class="stage-summary-grid">

            ${stageSummaryBox(
                "BREAKOUT",
                "突破確認",
                stages.BREAKOUT
            )}

            ${stageSummaryBox(
                "READY",
                "接近買點",
                stages.READY
            )}

            ${stageSummaryBox(
                "SETUP",
                "型態準備",
                stages.SETUP
            )}

            ${stageSummaryBox(
                "WATCH",
                "持續觀察",
                stages.WATCH
            )}

            ${stageSummaryBox(
                "EXTENDED",
                "漲幅延伸",
                stages.EXTENDED
            )}

            ${stageSummaryBox(
                "AVOID",
                "暫不關注",
                stages.AVOID
            )}

        </div>


        <div class="section-header">

            <div>

                <div class="section-title no-margin">
                    今日優先觀察
                </div>

                <div class="section-subtitle">
                    BREAKOUT → READY → SETUP
                </div>

            </div>

            <div class="section-count">
                ${state.actionPriority.length} 檔
            </div>

        </div>


        <div class="stock-list">

            ${
                actionRows.length

                ?

                actionRows
                    .map(
                        stock =>
                            stockRowHtml(
                                stock,
                                stock.rank,
                                true
                            )
                    )
                    .join("")

                :

                `
                <div class="empty-state">
                    目前沒有優先觀察股票
                </div>
                `
            }

        </div>


        <div class="section-header">

            <div>

                <div class="section-title no-margin">
                    個股研究排行
                </div>

                <div class="section-subtitle">
                    Overall Score TOP10
                </div>

            </div>

        </div>


        <div class="stock-list">

            ${
                state.researchPriority
                    .slice(
                        0,
                        5
                    )
                    .map(
                        stock =>
                            stockRowHtml(
                                stock,
                                stock.rank
                            )
                    )
                    .join("")
            }

        </div>
    `;

    bindStockRows(
        page
    );
}

function marketIndexCard(
    title,
    item
) {
    return `

        <div class="card metric-card">

            <div class="metric-label">
                ${escapeHtml(
                    title
                )}
            </div>

            <div class="metric-value">
                ${formatNumber(
                    item.close,
                    2
                )}
            </div>

            <div class="metric-sub">
                MA20：
                ${formatNumber(
                    item.ma20,
                    2
                )}
                ・
                MA60：
                ${formatNumber(
                    item.ma60,
                    2
                )}
            </div>

            <div class="metric-sub">
                ${statusBadge(
                    item.status
                )}
                ${item.history_days || 0}
                日
            </div>

        </div>
    `;
}

function summaryMetric(
    label,
    value,
    suffix
) {
    return `

        <div class="summary-metric">

            <div class="summary-metric-label">
                ${escapeHtml(
                    label
                )}
            </div>

            <div class="summary-metric-value">

                ${formatNumber(
                    value,
                    value === null
                    ||
                    value === undefined
                    ?
                    0
                    :
                    1
                )}

                ${escapeHtml(
                    suffix
                    || ""
                )}

            </div>

        </div>
    `;
}

function stageSummaryBox(
    code,
    label,
    count
) {
    return `

        <div class="
            stage-summary-box
            stage-${escapeHtml(
                code.toLowerCase()
            )}
        ">

            <div class="stage-summary-count">
                ${formatInteger(
                    count
                    || 0
                )}
            </div>

            <div class="stage-summary-label">
                ${escapeHtml(
                    label
                )}
            </div>

        </div>
    `;
}

function renderTop10() {
    const page =
        document.getElementById(
            "page-top10"
        );

    if (!page) {
        return;
    }

    const rows =
        state.researchPriority;

    page.innerHTML = `

        <div class="page-intro">

            <div class="page-intro-title">
                個股排行
            </div>

            <div class="page-intro-description">
                綜合評分用來找值得優先研究的股票；
                是否接近可行動位置，仍需搭配 Stage 與 Trade Plan。
            </div>

        </div>


        <div class="ranking-toolbar">

            <button
                id="openResearch"
                class="secondary-button no-top-margin"
            >
                搜尋 / 篩選全部個股
            </button>

        </div>


        <div class="section-header">

            <div>

                <div class="section-title no-margin">
                    個股研究排行
                </div>

                <div class="section-subtitle">
                    Overall Score 由高至低
                </div>

            </div>

            <div class="section-count">
                TOP ${rows.length}
            </div>

        </div>


        <div class="stock-list">

            ${
                rows.length

                ?

                rows
                    .map(
                        stock =>
                            stockRowHtml(
                                stock,
                                stock.rank
                            )
                    )
                    .join("")

                :

                `
                <div class="empty-state">
                    尚未產生研究排行
                </div>
                `
            }

        </div>
    `;

    document
        .getElementById(
            "openResearch"
        )
        ?.addEventListener(
            "click",
            () => {
                switchPage(
                    "research"
                );
            }
        );

    bindStockRows(
        page
    );
}

function renderMarket() {
    const page =
        document.getElementById(
            "page-market"
        );

    if (!page) {
        return;
    }

    const summary =
        state.sectorData?.summary
        || {};

    const distribution =
        summary.status_distribution
        || {};

    const sectors =
        state.sectors
        || [];

    page.innerHTML = `

        <div class="page-intro">

            <div class="page-intro-title">
                市場觀察
            </div>

            <div class="page-intro-description">
                族群頁用來觀察目前市場資金偏好的產業方向，
                不直接影響個股 Overall 評分。
            </div>

        </div>


        ${
            sectors.length

            ?

            `

            <div class="sector-summary-grid">

                ${sectorSummaryMetric(
                    "產業族群",
                    summary.sector_count
                    ?? sectors.length,
                    "個"
                )}

                ${sectorSummaryMetric(
                    "強勢",
                    distribution.STRONG
                    || 0,
                    "個"
                )}

                ${sectorSummaryMetric(
                    "轉強",
                    distribution.IMPROVING
                    || 0,
                    "個"
                )}

                ${sectorSummaryMetric(
                    "資料日",
                    state.sectorData?.data_date
                    || "--",
                    ""
                )}

            </div>


            <div class="section-header">

                <div>

                    <div class="section-title no-margin">
                        族群資金
                    </div>

                    <div class="section-subtitle">
                        技術強度、族群廣度、法人與大戶變化
                    </div>

                </div>

                <div class="section-count">
                    ${sectors.length} 個族群
                </div>

            </div>


            <div
                id="sectorPeriodFilters"
                class="filter-bar sector-filter-bar"
            >

                <button
                    class="filter-button active"
                    data-sector-period="strength"
                >
                    綜合強度
                </button>

                <button
                    class="filter-button"
                    data-sector-period="1d"
                >
                    當日
                </button>

                <button
                    class="filter-button"
                    data-sector-period="5d"
                >
                    5 日
                </button>

                <button
                    class="filter-button"
                    data-sector-period="20d"
                >
                    20 日
                </button>

            </div>


            <div
                id="sectorList"
                class="sector-list"
            ></div>

            `

            :

            `

            <div class="empty-state">

                <div class="empty-icon">
                    ◉
                </div>

                <div>
                    族群資料尚未發布
                </div>

                <div class="metric-sub">
                    等待 sectors.json 產生後即可顯示。
                </div>

            </div>

            `
        }


        <div class="section-header">

            <div>

                <div class="section-title no-margin">
                    其他市場觀察
                </div>

                <div class="section-subtitle">
                    後續 Domain 依序接入
                </div>

            </div>

        </div>


        <div class="feature-grid">

            <button
                id="openAnalysts"
                class="feature-card feature-button"
            >

                <div class="feature-icon">
                    ◇
                </div>

                <div class="feature-title">
                    分析師觀點
                </div>

                <div class="feature-description">
                    整理近期分析師公開內容與研究主題。
                </div>

                <div class="feature-meta">
                    今日・近3日・近7日・近30日
                </div>

                <div class="feature-status feature-status-ready">
                    已啟用
                </div>

                <div class="feature-link">
                    查看分析師觀點 →
                </div>

            </button>

            <button
                id="openEtfs"
                class="feature-card feature-button"
            >

                <div class="feature-icon">
                    ⇅
                </div>

                <div class="feature-title">
                    ETF 持股異動
                </div>

                <div class="feature-description">
                    比較官方 ETF 持股 Snapshot，
                    查看新進、增加、減少與剔除。
                </div>

                <div class="feature-meta">
                    當日・近5日・近20日
                </div>

                <div class="feature-status feature-status-ready">
                    已啟用
                </div>

                <div class="feature-link">
                    查看 ETF 持股異動 →
                </div>

            </button>

            ${featureCardHtml(
                "$",
                "金控股觀察",
                "使用金融業專屬 KPI，觀察獲利、股息、法人與金融環境。",
                "金融股專屬觀察",
                "待建置"
            )}

        </div>

        <div
            id="etfDomainPanel"
            style="display:none;"
        ></div>
    `;

    document
        .querySelectorAll(
            "#sectorPeriodFilters .filter-button"
        )
        .forEach(
            button => {

                button.addEventListener(
                    "click",
                    () => {

                        document
                            .querySelectorAll(
                                "#sectorPeriodFilters .filter-button"
                            )
                            .forEach(
                                item => {
                                    item.classList.remove(
                                        "active"
                                    );
                                }
                            );

                        button.classList.add(
                            "active"
                        );

                        renderSectorList(
                            button.dataset.sectorPeriod
                            || "strength"
                        );
                    }
                );
            }
        );

    if (
        sectors.length
    ) {
        renderSectorList(
            "strength"
        );
    }

    document
        .getElementById(
            "openAnalysts"
        )
        ?.addEventListener(
            "click",
            () => {
                switchPage(
                    "analysts"
                );
            }
        );

    document
        .getElementById(
            "openEtfs"
        )
        ?.addEventListener(
            "click",
            () => {

                const panel =
                    document.getElementById(
                        "etfDomainPanel"
                    );

                if (!panel) {
                    return;
                }

                panel.style.display =
                    "block";

                renderEtfDomain();

                panel.scrollIntoView({
                    behavior: "smooth",
                    block: "start",
                });
            }
        );    
}

// ============================================================
// ETF HOLDINGS
// ============================================================

function renderEtfDomain() {

    const container =
        document.getElementById(
            "etfDomainPanel"
        );

    if (!container) {
        return;
    }

    const etfs =
        state.etfs
        || [];

    if (!etfs.length) {

        container.innerHTML = `

            <div class="empty-state">

                <div class="empty-icon">
                    ⇅
                </div>

                <div>
                    ETF 持股資料尚未發布
                </div>

            </div>
        `;

        return;
    }

    container.innerHTML = `

        <div class="section-header">

            <div>

                <div class="section-title no-margin">
                    ETF 持股異動
                </div>

                <div class="section-subtitle">
                    官方持股 Snapshot 比較，
                    不代表實際市場買進或賣出
                </div>

            </div>

            <div class="section-count">
                ${etfs.length} 檔 ETF
            </div>

        </div>


        <div
            id="etfPeriodFilters"
            class="filter-bar"
        >

            ${etfFilterButton(
                "1d",
                "當日",
                state.etfPeriod === "1d"
            )}

            ${etfFilterButton(
                "5d",
                "5 日",
                state.etfPeriod === "5d"
            )}

            ${etfFilterButton(
                "20d",
                "20 日",
                state.etfPeriod === "20d"
            )}

        </div>


        <div
            id="etfSelectFilters"
            class="filter-bar"
        >

            ${etfSelectButton(
                "ALL",
                "全部 ETF",
                state.etfSelectedId === "ALL"
            )}

            ${
                etfs
                    .map(
                        etf =>
                            etfSelectButton(
                                etf.etf_id,
                                etf.etf_id,
                                state.etfSelectedId
                                    === etf.etf_id
                            )
                    )
                    .join("")
            }

        </div>


        <div
            id="etfChangeFilters"
            class="filter-bar"
        >

            ${etfChangeButton(
                "CHANGED",
                "有異動",
                state.etfChangeType
                    === "CHANGED"
            )}

            ${etfChangeButton(
                "NEW",
                "新進",
                state.etfChangeType
                    === "NEW"
            )}

            ${etfChangeButton(
                "INCREASE",
                "持股增加",
                state.etfChangeType
                    === "INCREASE"
            )}

            ${etfChangeButton(
                "DECREASE",
                "持股減少",
                state.etfChangeType
                    === "DECREASE"
            )}

            ${etfChangeButton(
                "REMOVED",
                "剔除",
                state.etfChangeType
                    === "REMOVED"
            )}

            ${etfChangeButton(
                "ALL",
                "全部",
                state.etfChangeType
                    === "ALL"
            )}

        </div>


        <div
            id="etfSummary"
        ></div>


        <div
            id="etfList"
        ></div>


        <div class="analyst-disclaimer">

            ETF 異動為不同日期官方持股快照之差異，
            不等同 ETF 在市場中的實際買進或賣出交易。
            5 日與 20 日需累積足夠歷史 Snapshot 後才會顯示。

        </div>
    `;

    bindEtfFilters();

    renderEtfList();
}


function etfFilterButton(
    value,
    label,
    active
) {

    return `

        <button
            class="
                filter-button
                ${active ? "active" : ""}
            "
            data-etf-period="${escapeHtml(
                value
            )}"
        >
            ${escapeHtml(
                label
            )}
        </button>
    `;
}


function etfSelectButton(
    value,
    label,
    active
) {

    return `

        <button
            class="
                filter-button
                ${active ? "active" : ""}
            "
            data-etf-id="${escapeHtml(
                value
            )}"
        >
            ${escapeHtml(
                label
            )}
        </button>
    `;
}


function etfChangeButton(
    value,
    label,
    active
) {

    return `

        <button
            class="
                filter-button
                ${active ? "active" : ""}
            "
            data-etf-change="${escapeHtml(
                value
            )}"
        >
            ${escapeHtml(
                label
            )}
        </button>
    `;
}


function bindEtfFilters() {

    document
        .querySelectorAll(
            "#etfPeriodFilters .filter-button"
        )
        .forEach(
            button => {

                button.addEventListener(
                    "click",
                    () => {

                        state.etfPeriod =
                            button.dataset.etfPeriod
                            || "1d";

                        renderEtfDomain();
                    }
                );
            }
        );


    document
        .querySelectorAll(
            "#etfSelectFilters .filter-button"
        )
        .forEach(
            button => {

                button.addEventListener(
                    "click",
                    () => {

                        state.etfSelectedId =
                            button.dataset.etfId
                            || "ALL";

                        renderEtfDomain();
                    }
                );
            }
        );


    document
        .querySelectorAll(
            "#etfChangeFilters .filter-button"
        )
        .forEach(
            button => {

                button.addEventListener(
                    "click",
                    () => {

                        state.etfChangeType =
                            button.dataset.etfChange
                            || "CHANGED";

                        renderEtfDomain();
                    }
                );
            }
        );
}


function renderEtfList() {

    const container =
        document.getElementById(
            "etfList"
        );

    const summary =
        document.getElementById(
            "etfSummary"
        );

    if (!container) {
        return;
    }

    const periodKey =
        state.etfPeriod
        || "1d";

    const selectedId =
        state.etfSelectedId
        || "ALL";

    const changeFilter =
        state.etfChangeType
        || "CHANGED";

    let etfs =
        [...state.etfs];

    if (
        selectedId !== "ALL"
    ) {

        etfs =
            etfs.filter(
                etf =>
                    String(
                        etf.etf_id
                    )
                    === selectedId
            );
    }

    const sections = [];

    let totalChanges = 0;

    let availableCount = 0;

    for (
        const etf
        of etfs
    ) {

        const period =
            etf.periods?.[
                periodKey
            ]
            || {};

        if (
            !period.available
        ) {

            sections.push(
                etfUnavailableHtml(
                    etf,
                    period,
                    periodKey
                )
            );

            continue;
        }

        availableCount += 1;

        let changes =
            period.changes
            || [];

        if (
            changeFilter
            === "CHANGED"
        ) {

            changes =
                changes.filter(
                    item =>
                        item.change_type
                        !== "UNCHANGED"
                );
        }
        else if (
            changeFilter
            !== "ALL"
        ) {

            changes =
                changes.filter(
                    item =>
                        item.change_type
                        === changeFilter
                );
        }

        totalChanges +=
            changes.length;

        sections.push(
            etfCardHtml(
                etf,
                period,
                changes
            )
        );
    }

    if (summary) {

        summary.innerHTML = `

            <div class="sector-summary-grid">

                ${sectorSummaryMetric(
                    "ETF",
                    etfs.length,
                    "檔"
                )}

                ${sectorSummaryMetric(
                    "已有期間資料",
                    availableCount,
                    "檔"
                )}

                ${sectorSummaryMetric(
                    "符合異動",
                    totalChanges,
                    "筆"
                )}

                ${sectorSummaryMetric(
                    "期間",
                    etfPeriodLabel(
                        periodKey
                    ),
                    ""
                )}

            </div>
        `;
    }

    container.innerHTML =
        sections.length
        ?
        sections.join("")
        :
        `

        <div class="empty-state">
            尚無 ETF 資料
        </div>
        `;

    bindEtfStockRows(
        container
    );
}


function etfUnavailableHtml(
    etf,
    period,
    periodKey
) {

    const holdings =
        etf.latest_holdings
        || [];

    return `

        <div class="analyst-card">

            <div class="analyst-card-header">

                <div>

                    <div class="analyst-name">

                        ${escapeHtml(
                            etf.etf_id
                        )}

                        ${escapeHtml(
                            etf.etf_name
                            || ""
                        )}

                    </div>

                    <div class="analyst-org">

                        ${escapeHtml(
                            etf.issuer_name
                            || ""
                        )}

                        ・最新基準日：

                        ${escapeHtml(
                            etf.latest_date
                            || "--"
                        )}

                    </div>

                </div>

                <div class="analyst-count">
                    ${holdings.length} 檔
                </div>

            </div>


            <div class="etf-history-notice">

                <div class="etf-history-title">

                    ${escapeHtml(
                        etfPeriodLabel(
                            periodKey
                        )
                    )}
                    異動資料尚未累積完成

                </div>

                <div class="metric-sub">

                    目前 Snapshot：
                    ${formatInteger(
                        period.available_snapshots
                        ?? etf.snapshot_count
                        ?? 0
                    )}

                    ／

                    需要：
                    ${formatInteger(
                        period.required_snapshots
                        ?? "--"
                    )}

                </div>

                <div class="metric-sub">
                    以下先顯示最新官方持股，
                    不代表本期間的新進、增加或減少。
                </div>

            </div>


            <div class="etf-current-holdings">

                ${
                    holdings.length

                    ?

                    holdings
                        .map(
                            item =>
                                etfCurrentHoldingRowHtml(
                                    etf,
                                    item
                                )
                        )
                        .join("")

                    :

                    `

                    <div class="empty-state">
                        尚無最新持股資料
                    </div>
                    `
                }

            </div>

        </div>
    `;
}


function etfCurrentHoldingRowHtml(
    etf,
    item
) {

    const stockExists =
        state.stockMap.has(
            String(
                item.stock_id
            )
        );

    const hasShares =
        item.shares !== null
        &&
        item.shares !== undefined;

    return `

        <div
            class="stock-row"
            data-etf-stock-id="${escapeHtml(
                item.stock_id
            )}"
            style="
                ${stockExists
                    ? "cursor:pointer;"
                    : ""}
            "
        >

            <div class="stock-main">

                <div class="stock-title">

                    <span>
                        ${escapeHtml(
                            item.stock_name
                            || "--"
                        )}
                    </span>

                    <span class="stock-code">
                        ${escapeHtml(
                            item.stock_id
                        )}
                    </span>

                </div>


                <div class="score-inline">

                    ${
                        hasShares

                        ?

                        `

                        <span>
                            持股
                            <strong>
                                ${formatInteger(
                                    item.shares
                                )}
                            </strong>
                            股
                        </span>
                        `

                        :

                        ""
                    }


                    <span>
                        權重
                        <strong>
                            ${formatMaybePercent(
                                item.weight_pct,
                                2
                            )}
                        </strong>
                    </span>


                    ${
                        item.market_value !== null
                        &&
                        item.market_value !== undefined

                        ?

                        `

                        <span>
                            市值
                            ${formatInteger(
                                item.market_value
                            )}
                        </span>
                        `

                        :

                        ""
                    }

                </div>

            </div>


            <div class="stock-price">

                <div class="stock-price-main">
                    ${formatMaybePercent(
                        item.weight_pct,
                        2
                    )}
                </div>

                <div class="metric-sub">
                    持股權重
                </div>

            </div>

        </div>
    `;
}


function etfCardHtml(
    etf,
    period,
    changes
) {

    return `

        <div class="analyst-card">

            <div class="analyst-card-header">

                <div>

                    <div class="analyst-name">

                        ${escapeHtml(
                            etf.etf_id
                        )}

                        ${escapeHtml(
                            etf.etf_name
                            || ""
                        )}

                    </div>

                    <div class="analyst-org">

                        ${escapeHtml(
                            etf.issuer_name
                            || ""
                        )}

                        ・

                        ${escapeHtml(
                            period.previous_date
                            || "--"
                        )}

                        →

                        ${escapeHtml(
                            period.current_date
                            || "--"
                        )}

                    </div>

                </div>

                <div class="analyst-count">
                    ${changes.length} 筆
                </div>

            </div>


            <div>

                ${
                    changes.length
                    ?
                    changes
                        .map(
                            change =>
                                etfChangeRowHtml(
                                    etf,
                                    change
                                )
                        )
                        .join("")
                    :
                    `

                    <div class="empty-state">
                        此篩選條件沒有異動資料
                    </div>
                    `
                }

            </div>

        </div>
    `;
}


function etfChangeRowHtml(
    etf,
    item
) {

    const stockExists =
        state.stockMap.has(
            String(
                item.stock_id
            )
        );

    const metricType =
        item.metric_type
        || etf.default_change_metric
        || "SHARES";

    const changeValue =
        metricType === "SHARES"
        ?
        item.shares_change
        :
        item.weight_change_pct;

    return `

        <div
            class="stock-row"
            data-etf-stock-id="${escapeHtml(
                item.stock_id
            )}"
            style="
                ${stockExists
                    ? "cursor:pointer;"
                    : ""}
            "
        >

            <div class="stock-main">

                <div class="stock-title">

                    <span>
                        ${escapeHtml(
                            item.stock_name
                            || "--"
                        )}
                    </span>

                    <span class="stock-code">
                        ${escapeHtml(
                            item.stock_id
                        )}
                    </span>

                    ${etfChangeBadge(
                        item.change_type
                    )}

                </div>


                <div class="score-inline">

                    ${
                        metricType
                        === "SHARES"

                        ?

                        `

                        <span>
                            前期
                            ${formatInteger(
                                item.previous_shares
                            )}
                        </span>

                        <span>
                            目前
                            ${formatInteger(
                                item.current_shares
                            )}
                        </span>

                        <span>
                            變化
                            <strong class="${changeClass(
                                changeValue
                            )}">
                                ${formatSignedInteger(
                                    changeValue
                                )}
                            </strong>
                        </span>
                        `

                        :

                        `

                        <span>
                            前期權重
                            ${formatMaybePercent(
                                item.previous_weight_pct,
                                2
                            )}
                        </span>

                        <span>
                            目前權重
                            ${formatMaybePercent(
                                item.current_weight_pct,
                                2
                            )}
                        </span>

                        <span>
                            權重變化
                            <strong class="${changeClass(
                                changeValue
                            )}">
                                ${formatSignedNumber(
                                    changeValue,
                                    2
                                )}%
                            </strong>
                        </span>
                        `
                    }

                </div>


                ${
                    metricType
                    === "SHARES"
                    &&
                    (
                        item.current_weight_pct
                        !== null
                        &&
                        item.current_weight_pct
                        !== undefined
                    )

                    ?

                    `

                    <div class="metric-sub">

                        目前權重：
                        ${formatMaybePercent(
                            item.current_weight_pct,
                            2
                        )}

                        ${
                            item.weight_change_pct
                            !== null
                            &&
                            item.weight_change_pct
                            !== undefined

                            ?

                            `・權重變化
                            <span class="${changeClass(
                                item.weight_change_pct
                            )}">
                                ${formatSignedNumber(
                                    item.weight_change_pct,
                                    2
                                )}%
                            </span>`

                            :

                            ""
                        }

                    </div>
                    `

                    :

                    ""
                }

            </div>


            <div class="stock-price">

                <div class="metric-sub">
                    ${escapeHtml(
                        metricType === "SHARES"
                        ? "股數"
                        : "權重"
                    )}
                </div>

            </div>

        </div>
    `;
}


function etfChangeBadge(
    changeType
) {

    const type =
        String(
            changeType
            || "UNCHANGED"
        )
        .toUpperCase();

    const labels = {

        NEW:
            "新進",

        INCREASE:
            "持股增加",

        DECREASE:
            "持股減少",

        REMOVED:
            "剔除",

        UNCHANGED:
            "持平",
    };

    let cssClass =
        "badge";

    if (
        type === "NEW"
        ||
        type === "INCREASE"
    ) {

        cssClass +=
            " badge-ready";
    }
    else if (
        type === "DECREASE"
        ||
        type === "REMOVED"
    ) {

        cssClass +=
            " badge-wait";
    }

    return `

        <span class="${cssClass}">
            ${escapeHtml(
                labels[type]
                || type
            )}
        </span>
    `;
}


function etfPeriodLabel(
    period
) {

    const labels = {

        "1d":
            "當日",

        "5d":
            "近 5 日",

        "20d":
            "近 20 日",
    };

    return (
        labels[
            period
        ]
        || period
    );
}


function bindEtfStockRows(
    root
) {

    root
        ?.querySelectorAll(
            "[data-etf-stock-id]"
        )
        .forEach(
            element => {

                element.addEventListener(
                    "click",
                    () => {

                        const stockId =
                            String(
                                element.dataset.etfStockId
                                || ""
                            );

                        if (
                            state.stockMap.has(
                                stockId
                            )
                        ) {

                            showStockDetail(
                                stockId
                            );
                        }
                    }
                );
            }
        );
}

function renderAnalysts() {
    const page =
        document.getElementById(
            "page-analysts"
        );

    if (!page) {
        return;
    }

    const analysts =
        state.analysts
        || [];

    page.innerHTML = `

        <div class="page-back-row">

            <button
                id="backToMarketFromAnalysts"
                class="text-button"
            >
                ← 返回市場觀察
            </button>

        </div>


        <div class="page-intro">

            <div class="page-intro-title">
                分析師觀點
            </div>

            <div class="page-intro-description">
                整理公開來源中近期分析師發布的內容。
                此 Domain 不直接影響個股 Overall 評分。
            </div>

        </div>


        <div
            id="analystPeriodFilters"
            class="filter-bar analyst-filter-bar"
        >

            <button
                class="filter-button"
                data-analyst-period="1"
            >
                今日
            </button>

            <button
                class="filter-button"
                data-analyst-period="3"
            >
                3 日
            </button>

            <button
                class="filter-button active"
                data-analyst-period="7"
            >
                7 日
            </button>

            <button
                class="filter-button"
                data-analyst-period="30"
            >
                30 日
            </button>

            <button
                class="filter-button"
                data-analyst-period="0"
            >
                全部
            </button>

        </div>


        <div
            id="analystSummary"
            class="analyst-summary"
        ></div>


        <div
            id="analystList"
            class="analyst-list"
        ></div>


        <div class="analyst-disclaimer">

            本頁依公開來源進行資訊整理。
            目前僅顯示來源標題、日期及原始連結等公開 Metadata，
            尚未進行逐字稿擷取、AI 摘要或投資立場判讀。
            實際觀點請以原始來源為準。

        </div>
    `;

    document
        .getElementById(
            "backToMarketFromAnalysts"
        )
        ?.addEventListener(
            "click",
            () => {
                switchPage(
                    "market"
                );
            }
        );

    document
        .querySelectorAll(
            "#analystPeriodFilters .filter-button"
        )
        .forEach(
            button => {

                button.addEventListener(
                    "click",
                    () => {

                        document
                            .querySelectorAll(
                                "#analystPeriodFilters .filter-button"
                            )
                            .forEach(
                                item => {
                                    item.classList.remove(
                                        "active"
                                    );
                                }
                            );

                        button.classList.add(
                            "active"
                        );

                        state.analystPeriod =
                            Number(
                                button.dataset.analystPeriod
                                || 7
                            );

                        renderAnalystList();
                    }
                );
            }
        );

    if (!analysts.length) {

        const list =
            document.getElementById(
                "analystList"
            );

        if (list) {
            list.innerHTML = `

                <div class="empty-state">

                    <div class="empty-icon">
                        ◇
                    </div>

                    <div>
                        分析師資料尚未發布
                    </div>

                    <div class="metric-sub">
                        等待 analysts.json 產生後即可顯示。
                    </div>

                </div>
            `;
        }

        return;
    }

    renderAnalystList();
}


function renderAnalystList() {
    const container =
        document.getElementById(
            "analystList"
        );

    const summary =
        document.getElementById(
            "analystSummary"
        );

    if (!container) {
        return;
    }

    const days =
        Number(
            state.analystPeriod
            ?? 7
        );

    let visibleCount = 0;

    const sections = [];

    for (
        const analyst
        of state.analysts
    ) {

        const comments =
            (
                analyst.comments
                || []
            )
            .filter(
                item =>
                    analystWithinDays(
                        item.published_at_tw
                        || item.published_at,
                        days
                    )
            );

        if (!comments.length) {
            continue;
        }

        visibleCount +=
            comments.length;

        sections.push(
            analystCardHtml(
                analyst,
                comments
            )
        );
    }

    if (summary) {

        summary.innerHTML = `

            <span>
                分析師
                <strong>
                    ${formatInteger(
                        state.analysts.length
                    )}
                </strong>
                位
            </span>

            <span>
                顯示
                <strong>
                    ${formatInteger(
                        visibleCount
                    )}
                </strong>
                筆
            </span>

            <span>
                資料更新
                <strong>
                    ${escapeHtml(
                        formatAnalystDateTime(
                            state.analystData
                                ?.generated_at
                        )
                    )}
                </strong>
            </span>
        `;
    }

    if (!sections.length) {

        container.innerHTML = `

            <div class="empty-state">

                <div class="empty-icon">
                    ◇
                </div>

                <div>
                    此期間沒有分析師資料
                </div>

            </div>
        `;

        return;
    }

    container.innerHTML =
        sections.join("");
}


function analystCardHtml(
    analyst,
    comments
) {
    return `

        <div class="analyst-card">

            <div class="analyst-card-header">

                <div>

                    <div class="analyst-name">
                        ${escapeHtml(
                            analyst.display_name
                            || analyst.analyst_name
                            || "--"
                        )}
                    </div>

                    <div class="analyst-org">
                        ${escapeHtml(
                            analyst.organization_name
                            || ""
                        )}
                    </div>

                </div>

                <div class="analyst-count">
                    ${comments.length} 筆
                </div>

            </div>


            <div class="analyst-comment-list">

                ${
                    comments
                        .map(
                            comment =>
                                analystCommentHtml(
                                    comment
                                )
                        )
                        .join("")
                }

            </div>

        </div>
    `;
}


function analystCommentHtml(
    comment
) {
    return `

        <a
            class="analyst-comment"
            href="${escapeHtml(
                comment.source_url
                || "#"
            )}"
            target="_blank"
            rel="noopener noreferrer"
        >

            <div class="analyst-comment-meta">

                <span>
                    ${escapeHtml(
                        formatAnalystDateTime(
                            comment.published_at_tw
                            || comment.published_at
                        )
                    )}
                </span>

                <span class="analyst-source">
                    ${escapeHtml(
                        comment.source_name
                        || comment.source_type
                        || "來源"
                    )}
                </span>

            </div>

            <div class="analyst-comment-title">
                ${escapeHtml(
                    comment.title
                    || "--"
                )}
            </div>

            <div class="analyst-comment-link">
                查看原始內容 →
            </div>

        </a>
    `;
}


function analystWithinDays(
    value,
    days
) {
    if (!value) {
        return false;
    }

    if (days === 0) {
        return true;
    }

    const date =
        new Date(
            value
        );

    if (
        Number.isNaN(
            date.getTime()
        )
    ) {
        return false;
    }

    const now =
        new Date();

    if (days === 1) {

        return (
            date.getFullYear()
            === now.getFullYear()
            &&
            date.getMonth()
            === now.getMonth()
            &&
            date.getDate()
            === now.getDate()
        );
    }

    const cutoff =
        new Date(
            now.getTime()
            -
            days
            *
            24
            *
            60
            *
            60
            *
            1000
        );

    return (
        date >= cutoff
    );
}


function formatAnalystDateTime(
    value
) {
    if (!value) {
        return "--";
    }

    const date =
        new Date(
            value
        );

    if (
        Number.isNaN(
            date.getTime()
        )
    ) {
        return String(
            value
        );
    }

    return new Intl.DateTimeFormat(
        "zh-TW",
        {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
        }
    ).format(
        date
    );
}


function sectorSummaryMetric(
    label,
    value,
    suffix
) {
    return `

        <div class="sector-summary-card">

            <div class="sector-summary-label">
                ${escapeHtml(
                    label
                )}
            </div>

            <div class="sector-summary-value">

                ${escapeHtml(
                    String(
                        value
                        ?? "--"
                    )
                )}

                ${escapeHtml(
                    suffix
                    || ""
                )}

            </div>

        </div>
    `;
}

function renderSectorList(
    period = "strength"
) {
    const container =
        document.getElementById(
            "sectorList"
        );

    if (!container) {
        return;
    }

    const rows =
        [...state.sectors];

    rows.sort(
        (
            a,
            b
        ) => {

            if (
                period === "1d"
            ) {
                return (
                    Number(
                        b.returns
                            ?.return_1d_pct
                        ?? -999
                    )
                    -
                    Number(
                        a.returns
                            ?.return_1d_pct
                        ?? -999
                    )
                );
            }

            if (
                period === "5d"
            ) {
                return (
                    Number(
                        b.returns
                            ?.return_5d_pct
                        ?? -999
                    )
                    -
                    Number(
                        a.returns
                            ?.return_5d_pct
                        ?? -999
                    )
                );
            }

            if (
                period === "20d"
            ) {
                return (
                    Number(
                        b.returns
                            ?.return_20d_pct
                        ?? -999
                    )
                    -
                    Number(
                        a.returns
                            ?.return_20d_pct
                        ?? -999
                    )
                );
            }

            return (
                Number(
                    b.technical_score
                    ?? -999
                )
                -
                Number(
                    a.technical_score
                    ?? -999
                )
            );
        }
    );

    container.innerHTML =
        rows
            .map(
                (
                    sector,
                    index
                ) =>
                    sectorRowHtml(
                        sector,
                        index + 1
                    )
            )
            .join("");

    container
        .querySelectorAll(
            ".sector-row"
        )
        .forEach(
            element => {

                element.addEventListener(
                    "click",
                    event => {

                        if (
                            event.target.closest(
                                ".sector-member-stock"
                            )
                        ) {
                            return;
                        }

                        toggleSectorMembers(
                            element.dataset.sectorId
                        );
                    }
                );
            }
        );

    container
        .querySelectorAll(
            ".sector-member-stock"
        )
        .forEach(
            button => {

                button.addEventListener(
                    "click",
                    event => {

                        event.stopPropagation();

                        const stockId =
                            button.dataset.stockId;

                        if (
                            state.stockMap.has(
                                String(
                                    stockId
                                )
                            )
                        ) {
                            showStockDetail(
                                stockId
                            );
                        }
                    }
                );
            }
        );
}

function sectorRowHtml(
    sector,
    rank
) {
    const returns =
        sector.returns
        || {};

    const institutional =
        sector.institutional
        || {};

    const members =
        sector.members
        || [];

    return `

        <div class="sector-card">

            <div
                class="sector-row"
                data-sector-id="${escapeHtml(
                    sector.sector_id
                )}"
            >

                <div class="sector-main">

                    <div class="sector-title-row">

                        <span class="rank-badge">
                            #${rank}
                        </span>

                        <span class="sector-name">
                            ${escapeHtml(
                                sector.sector_name
                                || "--"
                            )}
                        </span>

                        ${sectorStatusBadge(
                            sector.status
                        )}

                    </div>


                    <div class="sector-return-grid">

                        ${sectorReturnMetric(
                            "當日",
                            returns.return_1d_pct
                        )}

                        ${sectorReturnMetric(
                            "5日",
                            returns.return_5d_pct
                        )}

                        ${sectorReturnMetric(
                            "20日",
                            returns.return_20d_pct
                        )}

                    </div>


                    <div class="sector-stats">

                        <span>
                            強度
                            <strong>
                                ${formatNumber(
                                    sector.technical_score,
                                    1
                                )}
                            </strong>
                        </span>

                        <span>
                            廣度
                            ${formatNumber(
                                sector.breadth_score,
                                1
                            )}
                        </span>

                        <span>
                            上漲
                            ${formatMaybePercent(
                                sector.up_ratio_pct,
                                0
                            )}
                        </span>

                        <span>
                            MA20上
                            ${formatMaybePercent(
                                sector.above_ma20_ratio_pct,
                                0
                            )}
                        </span>

                        <span>
                            新高
                            ${formatInteger(
                                sector.new_high_count
                            )}
                        </span>

                    </div>


                    <div class="sector-flow-row">

                        <span>
                            外資
                            <strong class="${changeClass(
                                institutional.foreign_net
                            )}">
                                ${formatSignedInteger(
                                    institutional.foreign_net
                                )}
                            </strong>
                        </span>

                        <span>
                            投信
                            <strong class="${changeClass(
                                institutional.trust_net
                            )}">
                                ${formatSignedInteger(
                                    institutional.trust_net
                                )}
                            </strong>
                        </span>

                        <span>
                            自營
                            <strong class="${changeClass(
                                institutional.dealer_net
                            )}">
                                ${formatSignedInteger(
                                    institutional.dealer_net
                                )}
                            </strong>
                        </span>

                        <span>
                            大戶
                            <strong class="${changeClass(
                                sector.large_holder_change
                            )}">
                                ${formatSignedNumber(
                                    sector.large_holder_change,
                                    4
                                )}
                            </strong>
                        </span>

                    </div>

                </div>


                <div class="sector-side">

                    <div class="sector-score">
                        ${formatNumber(
                            sector.technical_score,
                            1
                        )}
                    </div>

                    <div class="metric-sub">
                        ${formatInteger(
                            sector.stock_count
                        )}
                        檔
                    </div>

                    <div class="sector-expand">
                        成分股 ${members.length} ▼
                    </div>

                </div>

            </div>


            <div
                id="sector-members-${escapeHtml(
                    safeDomId(
                        sector.sector_id
                    )
                )}"
                class="sector-members"
            >

                ${
                    members.length

                    ?

                    members
                        .map(
                            member => {

                                const exists =
                                    state.stockMap.has(
                                        String(
                                            member.stock_id
                                        )
                                    );

                                return `

                                    <button
                                        class="sector-member-stock"
                                        data-stock-id="${escapeHtml(
                                            member.stock_id
                                        )}"
                                        ${exists ? "" : "disabled"}
                                    >

                                        <span>
                                            ${escapeHtml(
                                                member.short_name
                                                || "--"
                                            )}
                                        </span>

                                        <span class="stock-code">
                                            ${escapeHtml(
                                                member.stock_id
                                            )}
                                        </span>

                                    </button>
                                `;
                            }
                        )
                        .join("")

                    :

                    `
                    <div class="sector-member-empty">
                        尚無成分股資料
                    </div>
                    `
                }

            </div>

        </div>
    `;
}

function sectorReturnMetric(
    label,
    value
) {
    return `

        <div class="sector-return-item">

            <span>
                ${escapeHtml(
                    label
                )}
            </span>

            <strong class="${changeClass(
                value
            )}">
                ${formatPercent(
                    value
                )}
            </strong>

        </div>
    `;
}

function sectorStatusBadge(
    status
) {
    const normalized =
        String(
            status
            || "WAITING_DATA"
        )
        .toUpperCase();

    const labels = {

        STRONG:
            "強勢",

        IMPROVING:
            "轉強",

        NEUTRAL:
            "中性",

        WEAK:
            "偏弱",

        WAITING_DATA:
            "資料補齊中",
    };

    return `

        <span class="
            sector-status
            sector-status-${escapeHtml(
                normalized.toLowerCase()
            )}
        ">
            ${escapeHtml(
                labels[
                    normalized
                ]
                || normalized
            )}
        </span>
    `;
}

function toggleSectorMembers(
    sectorId
) {
    document
        .getElementById(
            `sector-members-${safeDomId(
                sectorId
            )}`
        )
        ?.classList
        .toggle(
            "open"
        );
}

function safeDomId(
    value
) {
    return String(
        value
        ?? ""
    )
    .replace(
        /[^a-zA-Z0-9_-]/g,
        "_"
    );
}

function featureCardHtml(
    icon,
    title,
    description,
    meta,
    status
) {
    return `

        <div class="feature-card">

            <div class="feature-icon">
                ${escapeHtml(
                    icon
                )}
            </div>

            <div class="feature-title">
                ${escapeHtml(
                    title
                )}
            </div>

            <div class="feature-description">
                ${escapeHtml(
                    description
                )}
            </div>

            <div class="feature-meta">
                ${escapeHtml(
                    meta
                )}
            </div>

            <div class="feature-status">
                ${escapeHtml(
                    status
                )}
            </div>

        </div>
    `;
}

function renderMy() {
    const page =
        document.getElementById(
            "page-my"
        );

    if (!page) {
        return;
    }

    const watchlist =
        getWatchlist();

    const watchCount =
        Object
            .keys(
                watchlist
            )
            .length;

    const holdingCount =
        Object
            .values(
                watchlist
            )
            .filter(
                item =>
                    Number(
                        item.shares
                        || 0
                    ) > 0
            )
            .length;

    page.innerHTML = `

        <div class="page-intro">

            <div class="page-intro-title">
                我的股票
            </div>

            <div class="page-intro-description">
                將「正在觀察」與「已經持有」分開管理。
            </div>

        </div>


        <div class="feature-grid">

            <button
                id="openWatchlist"
                class="feature-card feature-button"
            >

                <div class="feature-icon">
                    ♡
                </div>

                <div class="feature-title">
                    Watchlist
                </div>

                <div class="feature-description">
                    查看目前正在追蹤的股票、評分與 Stage。
                </div>

                <div class="feature-count">
                    ${watchCount} 檔
                </div>

                <div class="feature-link">
                    查看自選股票 →
                </div>

            </button>


            <button
                id="openHoldings"
                class="feature-card feature-button"
            >

                <div class="feature-icon">
                    ▣
                </div>

                <div class="feature-title">
                    Holdings
                </div>

                <div class="feature-description">
                    管理持有成本、股數、損益、Stage 與風險。
                </div>

                <div class="feature-count">
                    ${holdingCount} 檔
                </div>

                <div class="feature-link">
                    查看持股 →
                </div>

            </button>

        </div>
    `;

    document
        .getElementById(
            "openWatchlist"
        )
        ?.addEventListener(
            "click",
            () => {
                switchPage(
                    "watchlist"
                );
            }
        );

    document
        .getElementById(
            "openHoldings"
        )
        ?.addEventListener(
            "click",
            () => {
                switchPage(
                    "holdings"
                );
            }
        );
}

function renderResearch() {
    const page =
        document.getElementById(
            "page-research"
        );

    if (!page) {
        return;
    }

    page.innerHTML = `

        <div class="page-back-row">

            <button
                id="backToRanking"
                class="text-button"
            >
                ← 返回個股排行
            </button>

        </div>


        <div class="search-box">

            <input
                id="stockSearch"
                class="search-input"
                type="search"
                placeholder="輸入股票代號、名稱或產業"
                autocomplete="off"
            >

        </div>


        <div
            id="researchFilters"
            class="filter-bar"
        >

            <button
                class="filter-button active"
                data-stage="ALL"
            >
                全部
            </button>

            <button
                class="filter-button"
                data-stage="BREAKOUT"
            >
                突破
            </button>

            <button
                class="filter-button"
                data-stage="READY"
            >
                進場訊號
            </button>

            <button
                class="filter-button"
                data-stage="SETUP"
            >
                蓄勢
            </button>

            <button
                class="filter-button"
                data-stage="WATCH"
            >
                觀察
            </button>

            <button
                class="filter-button"
                data-stage="EXTENDED"
            >
                漲幅延伸
            </button>

            <button
                class="filter-button"
                data-stage="AVOID"
            >
                暫不關注
            </button>

        </div>


        <div
            id="researchList"
            class="stock-list"
        ></div>
    `;

    document
        .getElementById(
            "backToRanking"
        )
        ?.addEventListener(
            "click",
            () => {
                switchPage(
                    "top10"
                );
            }
        );

    document
        .getElementById(
            "stockSearch"
        )
        ?.addEventListener(
            "input",
            renderResearchList
        );

    document
        .querySelectorAll(
            "#researchFilters .filter-button"
        )
        .forEach(
            button => {

                button.addEventListener(
                    "click",
                    () => {

                        document
                            .querySelectorAll(
                                "#researchFilters .filter-button"
                            )
                            .forEach(
                                item => {
                                    item.classList.remove(
                                        "active"
                                    );
                                }
                            );

                        button.classList.add(
                            "active"
                        );

                        renderResearchList();
                    }
                );
            }
        );

    renderResearchList();
}

function renderResearchList() {
    const container =
        document.getElementById(
            "researchList"
        );

    if (!container) {
        return;
    }

    const query =
        String(
            document
                .getElementById(
                    "stockSearch"
                )
                ?.value
            || ""
        )
        .trim()
        .toLowerCase();

    const stageFilter =
        document
            .querySelector(
                "#researchFilters .filter-button.active"
            )
            ?.dataset
            ?.stage
        || "ALL";

    let rows =
        [...state.stocks];

    if (
        query
    ) {
        rows =
            rows.filter(
                stock =>
                    [
                        stock.stock_id,
                        stock.short_name,
                        stock.industry_name,
                        stock.market,
                    ]
                    .filter(
                        Boolean
                    )
                    .join(
                        " "
                    )
                    .toLowerCase()
                    .includes(
                        query
                    )
            );
    }

    if (
        stageFilter !== "ALL"
    ) {
        rows =
            rows.filter(
                stock =>
                    stock.stage?.code
                    === stageFilter
            );
    }

    rows.sort(
        (
            a,
            b
        ) =>
            Number(
                b.score?.overall
                ?? -999
            )
            -
            Number(
                a.score?.overall
                ?? -999
            )
    );

    rows =
        rows.slice(
            0,
            150
        );

    if (
        !rows.length
    ) {
        container.innerHTML = `

            <div class="empty-state">
                找不到符合條件的股票
            </div>
        `;

        return;
    }

    container.innerHTML =
        rows
            .map(
                stock =>
                    stockRowHtml(
                        stock
                    )
            )
            .join("");

    bindStockRows(
        container
    );
}

function stockRowHtml(
    stock,
    rank = null,
    showAction = false
) {
    const price =
        stock.price
        || {};

    const score =
        stock.score
        || {};

    const stage =
        stock.stage
        || {};

    return `

        <div
            class="stock-row"
            data-stock-id="${escapeHtml(
                stock.stock_id
            )}"
        >

            <div class="stock-main">

                <div class="stock-title">

                    ${
                        rank !== null

                        ?

                        `
                        <span class="rank-badge">
                            #${rank}
                        </span>
                        `

                        :

                        ""
                    }

                    <span>
                        ${escapeHtml(
                            stock.short_name
                            || "--"
                        )}
                    </span>

                    <span class="stock-code">
                        ${escapeHtml(
                            stock.stock_id
                        )}
                    </span>

                </div>


                <div class="stock-meta">

                    ${stageBadge(
                        stage.code,
                        stage.label
                    )}

                    ${
                        stock.industry_name

                        ?

                        `
                        <span class="badge badge-blue">
                            ${escapeHtml(
                                stock.industry_name
                            )}
                        </span>
                        `

                        :

                        ""
                    }

                </div>


                <div class="score-inline">

                    <span>
                        Overall
                        <strong>
                            ${formatNumber(
                                score.overall,
                                1
                            )}
                        </strong>
                    </span>

                    <span>
                        基本
                        ${formatNumber(
                            score.fundamental,
                            0
                        )}
                    </span>

                    <span>
                        籌碼
                        ${formatNumber(
                            score.chip,
                            0
                        )}
                    </span>

                    <span>
                        技術
                        ${formatNumber(
                            score.technical,
                            0
                        )}
                    </span>

                </div>


                ${
                    showAction
                    &&
                    stock.action

                    ?

                    `
                    <div class="stock-action">
                        ${escapeHtml(
                            stock.action
                        )}
                    </div>
                    `

                    :

                    ""
                }

            </div>


            <div class="stock-price">

                <div class="stock-price-main">
                    ${formatNumber(
                        price.close,
                        2
                    )}
                </div>

                <div class="
                    stock-change
                    ${changeClass(
                        price.change_pct
                    )}
                ">
                    ${formatPercent(
                        price.change_pct
                    )}
                </div>

            </div>

        </div>
    `;
}

function bindStockRows(
    root
) {
    root
        ?.querySelectorAll(
            ".stock-row"
        )
        .forEach(
            element => {

                element.addEventListener(
                    "click",
                    () => {
                        showStockDetail(
                            element.dataset.stockId
                        );
                    }
                );
            }
        );
}

function renderWatchlist() {
    const page =
        document.getElementById(
            "page-watchlist"
        );

    if (!page) {
        return;
    }

    const watchlist =
        getWatchlist();

    const rows =
        Object
            .keys(
                watchlist
            )
            .map(
                stockId =>
                    state.stockMap.get(
                        String(
                            stockId
                        )
                    )
            )
            .filter(
                Boolean
            );

    if (
        !rows.length
    ) {
        page.innerHTML = `

            <div class="page-back-row">

                <button
                    id="backFromWatchlist"
                    class="text-button"
                >
                    ← 返回我的股票
                </button>

            </div>


            <div class="section-title">
                Watchlist
            </div>


            <div class="empty-state">

                <div class="empty-icon">
                    ♡
                </div>

                <div>
                    尚未加入自選股票
                </div>

                <div class="metric-sub">
                    從排行或個股搜尋開啟股票後即可加入。
                </div>

            </div>
        `;

        bindBackToMy(
            "backFromWatchlist"
        );

        return;
    }

    rows.sort(
        (
            a,
            b
        ) =>
            Number(
                b.score?.overall
                ?? 0
            )
            -
            Number(
                a.score?.overall
                ?? 0
            )
    );

    page.innerHTML = `

        <div class="page-back-row">

            <button
                id="backFromWatchlist"
                class="text-button"
            >
                ← 返回我的股票
            </button>

        </div>


        <div class="section-header">

            <div>

                <div class="section-title no-margin">
                    Watchlist
                </div>

                <div class="section-subtitle">
                    ${rows.length} 檔觀察股票
                </div>

            </div>

        </div>


        <div class="stock-list">

            ${
                rows
                    .map(
                        stock =>
                            stockRowHtml(
                                stock
                            )
                    )
                    .join("")
            }

        </div>
    `;

    bindBackToMy(
        "backFromWatchlist"
    );

    bindStockRows(
        page
    );
}

function renderHoldings() {
    const page =
        document.getElementById(
            "page-holdings"
        );

    if (!page) {
        return;
    }

    const rows =
        Object
            .values(
                getWatchlist()
            )
            .filter(
                item =>
                    Number(
                        item.shares
                        || 0
                    ) > 0
            )
            .map(
                item => ({
                    position:
                        item,

                    stock:
                        state.stockMap.get(
                            String(
                                item.stock_id
                            )
                        ),
                })
            )
            .filter(
                item =>
                    Boolean(
                        item.stock
                    )
            );

    if (
        !rows.length
    ) {
        page.innerHTML = `

            <div class="page-back-row">

                <button
                    id="backFromHoldings"
                    class="text-button"
                >
                    ← 返回我的股票
                </button>

            </div>


            <div class="section-title">
                Holdings
            </div>


            <div class="empty-state">

                <div class="empty-icon">
                    ▣
                </div>

                <div>
                    尚未建立持股資料
                </div>

                <div class="metric-sub">
                    在個股明細輸入平均成本與股數後，
                    會自動出現在 Holdings。
                </div>

            </div>
        `;

        bindBackToMy(
            "backFromHoldings"
        );

        return;
    }

    rows.sort(
        (
            a,
            b
        ) =>
            Number(
                b.stock.score?.overall
                ?? 0
            )
            -
            Number(
                a.stock.score?.overall
                ?? 0
            )
    );

    page.innerHTML = `

        <div class="page-back-row">

            <button
                id="backFromHoldings"
                class="text-button"
            >
                ← 返回我的股票
            </button>

        </div>


        <div class="section-header">

            <div>

                <div class="section-title no-margin">
                    Holdings
                </div>

                <div class="section-subtitle">
                    ${rows.length} 檔持股
                </div>

            </div>

        </div>


        <div class="holding-list">

            ${
                rows
                    .map(
                        item =>
                            holdingRowHtml(
                                item.stock,
                                item.position
                            )
                    )
                    .join("")
            }

        </div>
    `;

    bindBackToMy(
        "backFromHoldings"
    );

    bindStockRows(
        page
    );
}

function bindBackToMy(
    buttonId
) {
    document
        .getElementById(
            buttonId
        )
        ?.addEventListener(
            "click",
            () => {
                switchPage(
                    "my"
                );
            }
        );
}

function holdingRowHtml(
    stock,
    position
) {
    const shares =
        Number(
            position.shares
            || 0
        );

    const avgCost =
        Number(
            position.avg_cost
            || 0
        );

    const latest =
        Number(
            stock.price?.close
            || 0
        );

    const cost =
        shares
        *
        avgCost;

    const marketValue =
        shares
        *
        latest;

    const pnl =
        marketValue
        -
        cost;

    const returnPct =
        cost > 0
        ?
        pnl
        /
        cost
        *
        100
        :
        0;

    return `

        <div
            class="stock-row"
            data-stock-id="${escapeHtml(
                stock.stock_id
            )}"
        >

            <div class="stock-main">

                <div class="stock-title">

                    <span>
                        ${escapeHtml(
                            stock.short_name
                            || "--"
                        )}
                    </span>

                    <span class="stock-code">
                        ${escapeHtml(
                            stock.stock_id
                        )}
                    </span>

                </div>


                <div class="stock-meta">

                    ${stageBadge(
                        stock.stage?.code,
                        stock.stage?.label
                    )}

                </div>


                <div class="holding-metrics">

                    <span>
                        成本
                        ${formatNumber(
                            avgCost,
                            2
                        )}
                    </span>

                    <span>
                        ${formatInteger(
                            shares
                        )}
                        股
                    </span>

                    <span>
                        損益
                        ${formatInteger(
                            pnl
                        )}
                    </span>

                    <span class="${changeClass(
                        returnPct
                    )}">
                        ${formatPercent(
                            returnPct
                        )}
                    </span>

                </div>

            </div>


            <div class="stock-price">

                <div class="stock-price-main">
                    ${formatNumber(
                        latest,
                        2
                    )}
                </div>

                <div class="metric-sub">
                    市值
                    ${formatInteger(
                        marketValue
                    )}
                </div>

            </div>

        </div>
    `;
}

function showStockDetail(
    stockId
) {
    const stock =
        state.stockMap.get(
            String(
                stockId
            )
        );

    if (!stock) {
        return;
    }

    const overlay =
        document.getElementById(
            "detailOverlay"
        );

    const container =
        document.getElementById(
            "detailContent"
        );

    const price =
        stock.price
        || {};

    const score =
        stock.score
        || {};

    const technical =
        stock.technical_detail
        || {};

    const stage =
        stock.stage
        || {};

    const trade =
        stock.trade_plan
        || {};

    const watchlist =
        getWatchlist();

    const position =
        watchlist[
            stockId
        ]
        || {};

    const isWatching =
        Boolean(
            watchlist[
                stockId
            ]
        );

    container.innerHTML = `

        <div class="detail-header">

            <div>

                <div class="detail-stock-name">
                    ${escapeHtml(
                        stock.short_name
                        || "--"
                    )}
                </div>

                <div class="detail-code">

                    ${escapeHtml(
                        stock.stock_id
                    )}

                    ・

                    ${escapeHtml(
                        stock.market
                        || "--"
                    )}

                    ${
                        stock.industry_name

                        ?

                        `・ ${escapeHtml(
                            stock.industry_name
                        )}`

                        :

                        ""
                    }

                </div>

            </div>


            <button
                id="detailClose"
                class="close-button"
            >
                ×
            </button>

        </div>


        <div class="grid-2">

            <div class="card metric-card">

                <div class="metric-label">
                    最新價格
                </div>

                <div class="metric-value">
                    ${formatNumber(
                        price.close,
                        2
                    )}
                </div>

                <div class="
                    metric-sub
                    ${changeClass(
                        price.change_pct
                    )}
                ">
                    ${formatPercent(
                        price.change_pct
                    )}
                </div>

            </div>


            <div class="card metric-card">

                <div class="metric-label">
                    交易階段
                </div>

                <div class="metric-value stage-title">

                    ${stageBadge(
                        stage.code,
                        stage.label
                    )}

                </div>

                <div class="metric-sub">
                    ${escapeHtml(
                        stock.action
                        || "--"
                    )}
                </div>

            </div>

        </div>


        <div class="detail-section">

            <div class="detail-section-title">
                V3 綜合評分
            </div>

            <div class="score-grid score-grid-4">

                ${scoreBox(
                    "綜合",
                    score.overall,
                    true
                )}

                ${scoreBox(
                    "基本面",
                    score.fundamental
                )}

                ${scoreBox(
                    "籌碼面",
                    score.chip
                )}

                ${scoreBox(
                    "技術面",
                    score.technical
                )}

            </div>

        </div>


        <div class="detail-section">

            <div class="detail-section-title">
                技術面結構
            </div>

            ${keyValue(
                "趨勢結構",
                formatNumber(
                    technical.trend_structure,
                    1
                )
            )}

            ${keyValue(
                "價格位置",
                formatNumber(
                    technical.price_position,
                    1
                )
            )}

            ${keyValue(
                "動能品質",
                formatNumber(
                    technical.momentum_quality,
                    1
                )
            )}

            ${keyValue(
                "MA20 / MA60 乖離",
                formatPercent(
                    technical.ma20_ma60_pct
                )
            )}

            ${keyValue(
                "股價 / MA20 乖離",
                formatPercent(
                    technical.close_ma20_pct
                )
            )}

            ${keyValue(
                "距 MA20 ATR",
                formatNumber(
                    technical.close_ma20_atr,
                    2
                )
            )}

        </div>


        <div class="detail-section">

            <div class="detail-section-title">
                Trade Plan
            </div>

            ${keyValue(
                "買進參考區",
                priceRange(
                    trade.buy_zone_low,
                    trade.buy_zone_high
                )
            )}

            ${keyValue(
                "距買進區",
                formatPercent(
                    trade.distance_to_buy_zone_pct
                )
            )}

            ${keyValue(
                "突破價",
                formatNumber(
                    trade.breakout_price,
                    2
                )
            )}

            ${keyValue(
                "距突破價",
                formatPercent(
                    trade.breakout_distance_pct
                )
            )}

            ${keyValue(
                "風險價",
                formatNumber(
                    trade.risk_price,
                    2
                )
            )}

            ${keyValue(
                "目前風險",
                formatPercentRaw(
                    trade.current_risk_pct
                )
            )}

            ${keyValue(
                "目標參考區",
                priceRange(
                    trade.target_low,
                    trade.target_high
                )
            )}

            ${keyValue(
                "風險報酬比",
                formatNumber(
                    trade.reward_risk_ratio,
                    2
                )
            )}

        </div>


        <div class="detail-section">

            <div class="detail-section-title">
                我的自選 / 持股
            </div>


            <div class="position-grid">

                <label class="position-label">

                    平均成本

                    <input
                        id="positionAvgCost"
                        class="position-input"
                        type="number"
                        step="0.01"
                        value="${escapeHtml(
                            position.avg_cost
                            ?? ""
                        )}"
                    >

                </label>


                <label class="position-label">

                    股數

                    <input
                        id="positionShares"
                        class="position-input"
                        type="number"
                        step="1"
                        value="${escapeHtml(
                            position.shares
                            ?? ""
                        )}"
                    >

                </label>

            </div>


            ${positionSummary(
                stock,
                position
            )}


            <button
                id="saveWatchlist"
                class="primary-button"
            >
                ${
                    isWatching
                    ?
                    "更新自選 / 持股"
                    :
                    "加入自選股票"
                }
            </button>


            ${
                isWatching

                ?

                `
                <button
                    id="removeWatchlist"
                    class="secondary-button"
                >
                    移除自選股票
                </button>
                `

                :

                ""
            }

        </div>
    `;

    document
        .getElementById(
            "detailClose"
        )
        ?.addEventListener(
            "click",
            hideStockDetail
        );

    document
        .getElementById(
            "saveWatchlist"
        )
        ?.addEventListener(
            "click",
            () => {
                saveWatchlistPosition(
                    stock
                );
            }
        );

    document
        .getElementById(
            "removeWatchlist"
        )
        ?.addEventListener(
            "click",
            () => {

                removeWatchlist(
                    stockId
                );

                hideStockDetail();

                renderWatchlist();

                renderHoldings();

                renderMy();
            }
        );

    overlay.classList.add(
        "open"
    );
}

function bindDetailOverlay() {
    const overlay =
        document.getElementById(
            "detailOverlay"
        );

    overlay
        ?.addEventListener(
            "click",
            event => {

                if (
                    event.target
                    === overlay
                ) {
                    hideStockDetail();
                }
            }
        );
}

function hideStockDetail() {
    document
        .getElementById(
            "detailOverlay"
        )
        ?.classList.remove(
            "open"
        );
}

function scoreBox(
    name,
    value,
    primary = false
) {
    return `

        <div class="
            score-box
            ${primary ? "score-box-primary" : ""}
        ">

            <div class="score-name">
                ${escapeHtml(
                    name
                )}
            </div>

            <div class="score-value">

                ${
                    value === null
                    ||
                    value === undefined

                    ?

                    "--"

                    :

                    formatNumber(
                        value,
                        1
                    )
                }

            </div>

        </div>
    `;
}

function keyValue(
    label,
    value
) {
    return `

        <div class="key-value">

            <span class="key-label">
                ${escapeHtml(
                    label
                )}
            </span>

            <span class="key-data">
                ${escapeHtml(
                    String(
                        value
                        ?? "--"
                    )
                )}
            </span>

        </div>
    `;
}

function stageBadge(
    code,
    label
) {
    const normalized =
        String(
            code
            || "UNKNOWN"
        )
        .toUpperCase();

    return `

        <span class="
            stage-badge
            stage-badge-${escapeHtml(
                normalized.toLowerCase()
            )}
        ">
            ${escapeHtml(
                label
                || normalized
            )}
        </span>
    `;
}

function statusBadge(
    status
) {
    const normalized =
        String(
            status
            || ""
        )
        .toUpperCase();

    const ready =
        [
            "READY",
            "SUCCESS",
            "STORED",
        ]
        .includes(
            normalized
        );

    return `

        <span class="
            badge
            ${ready ? "badge-ready" : "badge-wait"}
        ">
            ${escapeHtml(
                normalized
                || "WAIT"
            )}
        </span>
    `;
}

function getWatchlist() {
    try {
        const raw =
            localStorage.getItem(
                WATCHLIST_KEY
            );

        return (
            raw
            ?
            JSON.parse(
                raw
            )
            || {}
            :
            {}
        );
    }
    catch {
        return {};
    }
}

function saveWatchlistPosition(
    stock
) {
    const watchlist =
        getWatchlist();

    const old =
        watchlist[
            stock.stock_id
        ]
        || {};

    const avgCost =
        document
            .getElementById(
                "positionAvgCost"
            )
            ?.value
        || "";

    const shares =
        document
            .getElementById(
                "positionShares"
            )
            ?.value
        || "";

    watchlist[
        stock.stock_id
    ] = {

        stock_id:
            stock.stock_id,

        added_at:
            old.added_at
            ||
            new Date()
                .toISOString(),

        avg_cost:
            avgCost
            ?
            Number(
                avgCost
            )
            :
            null,

        shares:
            shares
            ?
            Number(
                shares
            )
            :
            0,
    };

    localStorage.setItem(
        WATCHLIST_KEY,
        JSON.stringify(
            watchlist
        )
    );

    renderWatchlist();

    renderHoldings();

    renderMy();

    showStockDetail(
        stock.stock_id
    );
}

function removeWatchlist(
    stockId
) {
    const watchlist =
        getWatchlist();

    delete watchlist[
        stockId
    ];

    localStorage.setItem(
        WATCHLIST_KEY,
        JSON.stringify(
            watchlist
        )
    );

    renderWatchlist();

    renderHoldings();

    renderMy();
}

function positionSummary(
    stock,
    position
) {
    const shares =
        Number(
            position.shares
            || 0
        );

    const avgCost =
        Number(
            position.avg_cost
            || 0
        );

    const latest =
        Number(
            stock.price?.close
            || 0
        );

    if (
        shares <= 0
        ||
        avgCost <= 0
        ||
        latest <= 0
    ) {
        return `

            <div class="position-hint">
                輸入平均成本與股數後，
                即可查看未實現損益。
            </div>
        `;
    }

    const cost =
        shares
        *
        avgCost;

    const marketValue =
        shares
        *
        latest;

    const pnl =
        marketValue
        -
        cost;

    const returnPct =
        cost
        ?
        pnl
        /
        cost
        *
        100
        :
        0;

    return `

        <div class="position-summary">

            ${keyValue(
                "投入成本",
                formatInteger(
                    cost
                )
            )}

            ${keyValue(
                "目前市值",
                formatInteger(
                    marketValue
                )
            )}

            ${keyValue(
                "未實現損益",
                formatInteger(
                    pnl
                )
            )}

            ${keyValue(
                "報酬率",
                formatPercent(
                    returnPct
                )
            )}

        </div>
    `;
}

function changeClass(
    value
) {
    const numeric =
        Number(
            value
        );

    if (
        !Number.isFinite(
            numeric
        )
        ||
        numeric === 0
    ) {
        return "neutral";
    }

    return (
        numeric > 0
        ?
        "positive"
        :
        "negative"
    );
}

function formatNumber(
    value,
    digits = 2
) {
    if (
        value === null
        ||
        value === undefined
        ||
        value === ""
    ) {
        return "--";
    }

    const numeric =
        Number(
            value
        );

    if (
        !Number.isFinite(
            numeric
        )
    ) {
        return "--";
    }

    return numeric
        .toLocaleString(
            "zh-TW",
            {
                minimumFractionDigits:
                    digits,

                maximumFractionDigits:
                    digits,
            }
        );
}

function formatInteger(
    value
) {
    if (
        value === null
        ||
        value === undefined
        ||
        value === ""
    ) {
        return "--";
    }

    const numeric =
        Number(
            value
        );

    if (
        !Number.isFinite(
            numeric
        )
    ) {
        return "--";
    }

    return Math
        .round(
            numeric
        )
        .toLocaleString(
            "zh-TW"
        );
}

function formatPercent(
    value
) {
    if (
        value === null
        ||
        value === undefined
        ||
        value === ""
    ) {
        return "--";
    }

    const numeric =
        Number(
            value
        );

    if (
        !Number.isFinite(
            numeric
        )
    ) {
        return "--";
    }

    return (
        `${numeric > 0 ? "+" : ""}`
        +
        `${numeric.toFixed(2)}%`
    );
}

function formatMaybePercent(
    value,
    digits = 0
) {
    if (
        value === null
        ||
        value === undefined
        ||
        value === ""
    ) {
        return "--";
    }

    const numeric =
        Number(
            value
        );

    if (
        !Number.isFinite(
            numeric
        )
    ) {
        return "--";
    }

    return (
        `${numeric.toFixed(
            digits
        )}%`
    );
}

function formatPercentRaw(
    value
) {
    if (
        value === null
        ||
        value === undefined
        ||
        value === ""
    ) {
        return "--";
    }

    const numeric =
        Number(
            value
        );

    if (
        !Number.isFinite(
            numeric
        )
    ) {
        return "--";
    }

    return (
        `${numeric.toFixed(2)}%`
    );
}

function formatSignedInteger(
    value
) {
    if (
        value === null
        ||
        value === undefined
        ||
        value === ""
    ) {
        return "--";
    }

    const numeric =
        Number(
            value
        );

    if (
        !Number.isFinite(
            numeric
        )
    ) {
        return "--";
    }

    const formatted =
        Math
            .round(
                numeric
            )
            .toLocaleString(
                "zh-TW"
            );

    return (
        numeric > 0
        ?
        `+${formatted}`
        :
        formatted
    );
}

function formatSignedNumber(
    value,
    digits = 2
) {
    if (
        value === null
        ||
        value === undefined
        ||
        value === ""
    ) {
        return "--";
    }

    const numeric =
        Number(
            value
        );

    if (
        !Number.isFinite(
            numeric
        )
    ) {
        return "--";
    }

    const formatted =
        numeric.toFixed(
            digits
        );

    return (
        numeric > 0
        ?
        `+${formatted}`
        :
        formatted
    );
}

function priceRange(
    low,
    high
) {
    if (
        low === null
        ||
        low === undefined
        ||
        high === null
        ||
        high === undefined
    ) {
        return "--";
    }

    return (
        `${formatNumber(
            low,
            2
        )} ~ ${formatNumber(
            high,
            2
        )}`
    );
}

function escapeHtml(
    value
) {
    return String(
        value
        ?? ""
    )
    .replace(
        /&/g,
        "&amp;"
    )
    .replace(
        /</g,
        "&lt;"
    )
    .replace(
        />/g,
        "&gt;"
    )
    .replace(
        /"/g,
        "&quot;"
    )
    .replace(
        /'/g,
        "&#039;"
    );
}