"use strict";


const DATA_FILE =
    "./data/latest/v3_ui.json";

const WATCHLIST_KEY =
    "stockwavescanner.v3.watchlist";


const state = {

    ui: null,

    market: null,

    researchPriority: [],

    actionPriority: [],

    stocks: [],

    stockMap: new Map(),

    currentPage: "home",
};


document.addEventListener(
    "DOMContentLoaded",
    async () => {

        bindNavigation();

        bindDetailOverlay();

        await loadData();

        renderAll();
    }
);


// ============================================================
// LOAD
// ============================================================


async function loadJson(
    url
) {

    const response =
        await fetch(
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

        const payload =
            await loadJson(
                DATA_FILE
            );

        state.ui =
            payload;

        state.market =
            payload.market || {};

        state.researchPriority =
            payload
                .research_priority
                ?.rows
            || [];

        state.actionPriority =
            payload
                .action_priority
                ?.rows
            || [];

        state.stocks =
            payload.stocks || [];

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


function renderLoadError(
    error
) {

    const page =
        document.getElementById(
            "page-home"
        );

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


// ============================================================
// NAVIGATION
// ============================================================


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


function switchPage(
    page
) {

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

    document
        .querySelector(
            `.nav-item[data-page="${page}"]`
        )
        ?.classList.add(
            "active"
        );

    if (
        page === "watchlist"
    ) {

        renderWatchlist();
    }

    if (
        page === "research"
    ) {

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
}


// ============================================================
// RENDER ALL
// ============================================================


function renderAll() {

    if (
        !state.ui
    ) {

        return;
    }

    renderHome();

    renderTop10();

    renderResearch();

    renderWatchlist();
}


// ============================================================
// HOME
// ============================================================


function renderHome() {

    const page =
        document.getElementById(
            "page-home"
        );

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
                    || value === undefined
                    ? 0
                    : 1
                )}
                ${escapeHtml(
                    suffix || ""
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
                    count || 0
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


// ============================================================
// TOP10 PAGE
// ============================================================


function renderTop10() {

    const page =
        document.getElementById(
            "page-top10"
        );

    const rows =
        state.researchPriority;

    page.innerHTML = `

        <div class="section-header">

            <div>

                <div class="section-title no-margin">
                    個股研究排行
                </div>

                <div class="section-subtitle">
                    依 Overall Score 由高至低排序
                </div>

            </div>

            <div class="section-count">
                TOP ${rows.length}
            </div>

        </div>


        <div class="ranking-note">

            <strong>研究排行</strong>
            用來找值得優先研究的股票。

            <br>

            是否接近可行動位置，
            仍需搭配 Stage 與 Trade Plan。

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

    bindStockRows(
        page
    );
}


// ============================================================
// RESEARCH PAGE
// ============================================================


function renderResearch() {

    const page =
        document.getElementById(
            "page-research"
        );

    page.innerHTML = `

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
                Ready
            </button>

            <button
                class="filter-button"
                data-stage="SETUP"
            >
                Setup
            </button>

            <button
                class="filter-button"
                data-stage="WATCH"
            >
                觀察
            </button>

        </div>


        <div
            id="researchList"
            class="stock-list"
        ></div>
    `;

    const input =
        document.getElementById(
            "stockSearch"
        );

    input.addEventListener(
        "input",
        () => {

            renderResearchList();
        }
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
                                item =>
                                    item.classList.remove(
                                        "active"
                                    )
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

    const input =
        document.getElementById(
            "stockSearch"
        );

    const query =
        String(
            input?.value
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

    if (query) {

        rows =
            rows.filter(
                stock => {

                    const searchable = [

                        stock.stock_id,

                        stock.short_name,

                        stock.industry_name,

                        stock.market,

                    ]
                    .filter(Boolean)
                    .join(" ")
                    .toLowerCase();

                    return searchable.includes(
                        query
                    );
                }
            );
    }

    if (
        stageFilter !== "ALL"
    ) {

        rows =
            rows.filter(
                stock =>
                    stock.stage?.code
                    ===
                    stageFilter
            );
    }

    rows.sort(
        (
            a,
            b
        ) => {

            const aOverall =
                Number(
                    a.score?.overall
                    ?? -999
                );

            const bOverall =
                Number(
                    b.score?.overall
                    ?? -999
                );

            return (
                bOverall
                -
                aOverall
            );
        }
    );

    rows =
        rows.slice(
            0,
            150
        );

    if (!rows.length) {

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


// ============================================================
// STOCK ROW
// ============================================================


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
                    && stock.action

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

                <div
                    class="
                        stock-change
                        ${changeClass(
                            price.change_pct
                        )}
                    "
                >
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
        .querySelectorAll(
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


// ============================================================
// WATCHLIST
// ============================================================


function renderWatchlist() {

    const page =
        document.getElementById(
            "page-watchlist"
        );

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
            .filter(Boolean);

    if (!rows.length) {

        page.innerHTML = `

            <div class="section-title">
                自選股票
            </div>

            <div class="empty-state">

                <div class="empty-icon">
                    ♡
                </div>

                <div>
                    尚未加入自選股票
                </div>

                <div class="metric-sub">
                    從個股頁或排行打開股票後即可加入
                </div>

            </div>
        `;

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

        <div class="section-header">

            <div>

                <div class="section-title no-margin">
                    自選股票
                </div>

                <div class="section-subtitle">
                    ${rows.length} 檔
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

    bindStockRows(
        page
    );
}


// ============================================================
// STOCK DETAIL
// ============================================================


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

                <div
                    class="
                        metric-sub
                        ${changeClass(
                            price.change_pct
                        )}
                    "
                >
                    ${formatPercent(
                        price.change_pct
                    )}
                </div>

            </div>


            <div class="card metric-card">

                <div class="metric-label">
                    Stage
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
                    "Overall",
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
                Technical V2
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
                "買進區間",
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
                "目標區間",
                priceRange(
                    trade.target_low,
                    trade.target_high
                )
            )}

            ${keyValue(
                "Reward / Risk",
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
        .addEventListener(
            "click",
            hideStockDetail
        );

    document
        .getElementById(
            "saveWatchlist"
        )
        .addEventListener(
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

    overlay.addEventListener(
        "click",
        event => {

            if (
                event.target
                ===
                overlay
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
        .classList.remove(
            "open"
        );
}


// ============================================================
// UI HELPERS
// ============================================================


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

    if (
        normalized === "READY"
        ||
        normalized === "SUCCESS"
        ||
        normalized === "STORED"
    ) {

        return `

            <span class="badge badge-ready">
                ${escapeHtml(
                    normalized
                )}
            </span>
        `;
    }

    return `

        <span class="badge badge-wait">
            ${escapeHtml(
                normalized
                || "WAIT"
            )}
        </span>
    `;
}


// ============================================================
// WATCHLIST STORAGE
// ============================================================


function getWatchlist() {

    try {

        const raw =
            localStorage.getItem(
                WATCHLIST_KEY
            );

        if (!raw) {

            return {};
        }

        return (
            JSON.parse(
                raw
            )
            || {}
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
            .value;

    const shares =
        document
            .getElementById(
                "positionShares"
            )
            .value;

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
        (
            pnl
            /
            cost
            *
            100
        )
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


// ============================================================
// FORMAT
// ============================================================


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

    return Math.round(
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

    const sign =
        numeric > 0
        ?
        "+"
        :
        "";

    return (
        `${sign}${numeric.toFixed(2)}%`
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