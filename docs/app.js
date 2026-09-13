"use strict";


const DATA_BASE =
    "./data/latest";


const WATCHLIST_KEY =
    "stockwavescanner.v2.watchlist";


const state = {

    status: null,

    market: null,

    top10: null,

    stocks: [],

    stockMap: new Map(),

    digest: null,

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


async function loadJson(
    fileName
) {

    const response =
        await fetch(
            `${DATA_BASE}/${fileName}?t=${Date.now()}`,
            {
                cache: "no-store",
            }
        );

    if (!response.ok) {

        throw new Error(
            `${fileName}: HTTP ${response.status}`
        );
    }

    return await response.json();
}


async function loadData() {

    try {

        const [
            status,
            market,
            top10,
            stocks,
            digest,
        ] =
            await Promise.all([
                loadJson(
                    "status.json"
                ),
                loadJson(
                    "market.json"
                ),
                loadJson(
                    "top10.json"
                ),
                loadJson(
                    "stocks.json"
                ),
                loadJson(
                    "analyst_digest.json"
                ),
            ]);

        state.status =
            status;

        state.market =
            market;

        state.top10 =
            top10;

        state.stocks =
            stocks.stocks || [];

        state.digest =
            digest;

        state.stockMap =
            new Map(
                state.stocks.map(
                    stock => [
                        stock.stock_id,
                        stock,
                    ]
                )
            );

        document
            .getElementById(
                "headerStatus"
            )
            .textContent =
                status.data_date
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

    const home =
        document.getElementById(
            "page-home"
        );

    home.innerHTML = `
        <div class="empty-state">
            <div class="empty-icon">⚠</div>
            <div>UI 已啟用，但最新資料尚未發布。</div>
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
        .classList.add(
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


function renderAll() {

    if (
        !state.status
    ) {

        return;
    }

    renderHome();

    renderTop10();

    renderResearch();

    renderWatchlist();
}


function renderHome() {

    const page =
        document.getElementById(
            "page-home"
        );

    const regime =
        state.market?.regime
        || {};

    const coverage =
        state.status?.coverage
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
                    state.status.data_date
                    || "--"
                )}
                ・
                Model：
                ${escapeHtml(
                    state.status.model_version
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
            資料完整度
        </div>

        <div class="card">

            ${coverageRow(
                "股價歷史",
                coverage.price
            )}

            ${coverageRow(
                "法人籌碼",
                coverage.institutional
            )}

            ${coverageRow(
                "TDCC",
                coverage.tdcc
            )}

            ${coverageRow(
                "月營收 24M",
                coverage.revenue
            )}

            ${coverageRow(
                "季財報 8Q",
                coverage.financial
            )}

            ${coverageRow(
                "完整可評分",
                coverage.overall
            )}

        </div>


        <div class="section-title">
            系統狀態
        </div>

        <div class="card">

            ${
                renderSyncRows(
                    state.status.sync_state
                    || []
                )
            }

        </div>

    `;
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


function coverageRow(
    name,
    item
) {

    const value =
        item
        || {
            ready: 0,
            total: 0,
            percent: 0,
        };

    return `

        <div class="progress-row">

            <div class="progress-header">

                <span class="progress-name">
                    ${escapeHtml(
                        name
                    )}
                </span>

                <span class="progress-value">
                    ${value.ready || 0}
                    /
                    ${value.total || 0}
                    ・
                    ${formatNumber(
                        value.percent,
                        1
                    )}%
                </span>

            </div>

            <div class="progress-track">

                <div
                    class="progress-fill"
                    style="
                        width:
                        ${Math.max(
                            0,
                            Math.min(
                                100,
                                value.percent || 0
                            )
                        )}%
                    "
                ></div>

            </div>

        </div>
    `;
}


function renderSyncRows(
    rows
) {

    if (
        !rows.length
    ) {

        return `
            <div class="metric-sub">
                尚無 Sync State
            </div>
        `;
    }

    return rows
        .map(
            row => `

                <div class="sync-row">

                    <div>

                        <div class="sync-name">
                            ${escapeHtml(
                                row.dataset
                            )}
                        </div>

                        <div class="sync-date">
                            ${
                                escapeHtml(
                                    row.last_data_date
                                    || "--"
                                )
                            }
                        </div>

                    </div>

                    <div>
                        ${statusBadge(
                            row.status
                        )}
                    </div>

                </div>
            `
        )
        .join("");
}


function renderTop10() {

    const page =
        document.getElementById(
            "page-top10"
        );

    const rows =
        state.top10?.rows
        || [];

    if (
        !rows.length
    ) {

        const readiness =
            state.top10
                ?.readiness
            || {};

        page.innerHTML = `

            <div class="section-title">
                今日 TOP10
            </div>

            <div class="empty-state">

                <div class="empty-icon">
                    ◷
                </div>

                <div>
                    TOP10 等待資料補齊
                </div>

                <div class="metric-sub">
                    ${
                        escapeHtml(
                            state.top10
                                ?.message
                            ||
                            "尚未產生排名"
                        )
                    }
                </div>

                <div
                    style="
                        margin-top: 16px;
                    "
                >

                    完整資料：
                    ${
                        readiness.ready
                        || 0
                    }
                    /
                    ${
                        readiness.total
                        || 0
                    }

                </div>

            </div>
        `;

        return;
    }

    page.innerHTML = `

        <div class="section-title">
            今日 TOP10
        </div>

        <div class="stock-list">

            ${
                rows
                .map(
                    row => {

                        const stock =
                            state.stockMap.get(
                                row.stock_id
                            )
                            || row;

                        return stockRowHtml(
                            stock,
                            row.rank
                        );
                    }
                )
                .join("")
            }

        </div>
    `;

    bindStockRows(
        page
    );
}


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

            renderResearchList(
                input.value
            );
        }
    );

    renderResearchList(
        ""
    );
}


function renderResearchList(
    query
) {

    const container =
        document.getElementById(
            "researchList"
        );

    if (
        !container
    ) {

        return;
    }

    const normalized =
        String(
            query
            || ""
        )
        .trim()
        .toLowerCase();

    let rows =
        state.stocks;

    if (
        normalized
    ) {

        rows =
            rows.filter(
                stock => {

                    const searchable = [
                        stock.stock_id,
                        stock.stock_name,
                        stock.short_name,
                        stock.industry_name,
                        stock.market,
                    ]
                    .filter(Boolean)
                    .join(" ")
                    .toLowerCase();

                    return searchable.includes(
                        normalized
                    );
                }
            );
    }

    if (
        !normalized
    ) {

        rows =
            [...rows]
            .sort(
                (
                    a,
                    b
                ) => {

                    const aChange =
                        a.latest
                            ?.change_pct
                        ?? -99999;

                    const bChange =
                        b.latest
                            ?.change_pct
                        ?? -99999;

                    return (
                        bChange
                        -
                        aChange
                    );
                }
            );
    }

    rows =
        rows.slice(
            0,
            120
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
    rank = null
) {

    const latest =
        stock.latest
        || {};

    const readiness =
        stock.readiness
        || {};

    const change =
        latest.change_pct;

    return `

        <div
            class="stock-row"
            data-stock-id="${escapeHtml(
                stock.stock_id
            )}"
        >

            <div>

                <div class="stock-title">

                    ${
                        rank !== null
                        ?
                        `<span class="badge badge-blue">
                            #${rank}
                        </span>`
                        :
                        ""
                    }

                    <span>
                        ${escapeHtml(
                            stock.short_name
                            ||
                            stock.stock_name
                        )}
                    </span>

                    <span class="stock-code">
                        ${escapeHtml(
                            stock.stock_id
                        )}
                    </span>

                </div>

                <div class="stock-meta">

                    <span class="badge badge-blue">
                        ${escapeHtml(
                            stock.market
                        )}
                    </span>

                    ${
                        statusBadge(
                            readiness.overall
                        )
                    }

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

            </div>

            <div class="stock-price">

                <div class="stock-price-main">
                    ${formatNumber(
                        latest.close,
                        2
                    )}
                </div>

                <div
                    class="
                        stock-change
                        ${changeClass(
                            change
                        )}
                    "
                >
                    ${formatPercent(
                        change
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
                    stockId
                )
        )
        .filter(Boolean);

    if (
        !rows.length
    ) {

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
                    從研究頁打開個股後即可加入
                </div>

            </div>
        `;

        return;
    }

    page.innerHTML = `

        <div class="section-title">
            自選股票
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


function showStockDetail(
    stockId
) {

    const stock =
        state.stockMap.get(
            stockId
        );

    if (
        !stock
    ) {

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

    const latest =
        stock.latest
        || {};

    const technical =
        stock.technical
        || {};

    const institutional =
        stock.institutional
        || {};

    const tdcc =
        stock.tdcc
        || {};

    const revenue =
        stock.fundamental
            ?.revenue
        || {};

    const financial =
        stock.fundamental
            ?.financial
        || {};

    const scores =
        stock.scores
        || {};

    const readiness =
        stock.readiness
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
                        ||
                        stock.stock_name
                    )}
                </div>

                <div class="detail-code">
                    ${escapeHtml(
                        stock.stock_id
                    )}
                    ・
                    ${escapeHtml(
                        stock.market
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
                        latest.close,
                        2
                    )}
                </div>

                <div
                    class="
                        metric-sub
                        ${changeClass(
                            latest.change_pct
                        )}
                    "
                >
                    ${formatPercent(
                        latest.change_pct
                    )}
                </div>

            </div>

            <div class="card metric-card">

                <div class="metric-label">
                    Stage
                </div>

                <div class="metric-value">
                    ${escapeHtml(
                        stock.stage
                            ?.label
                        ||
                        "--"
                    )}
                </div>

                <div class="metric-sub">
                    ${escapeHtml(
                        stock.action
                        ||
                        "--"
                    )}
                </div>

            </div>

        </div>


        <div class="score-grid">

            ${scoreBox(
                "Strength",
                scores.strength
            )}

            ${scoreBox(
                "Timing",
                scores.timing
            )}

            ${scoreBox(
                "Buy Priority",
                scores.buy_priority
            )}

        </div>


        <div class="detail-section">

            <div class="detail-section-title">
                資料完整度
            </div>

            ${keyValue(
                "股價",
                readinessStatus(
                    readiness.price
                )
            )}

            ${keyValue(
                "法人",
                readinessStatus(
                    readiness.institutional
                )
            )}

            ${keyValue(
                "TDCC",
                readinessStatus(
                    readiness.tdcc
                )
            )}

            ${keyValue(
                "月營收",
                readinessStatus(
                    readiness.revenue
                )
            )}

            ${keyValue(
                "季財報",
                readinessStatus(
                    readiness.financial
                )
            )}

            ${keyValue(
                "完整度",
                `${
                    formatNumber(
                        readiness.percent,
                        1
                    )
                }%`
            )}

        </div>


        <div class="detail-section">

            <div class="detail-section-title">
                技術資料
            </div>

            ${keyValue(
                "MA20",
                formatNumber(
                    technical.ma20,
                    2
                )
            )}

            ${keyValue(
                "MA60",
                formatNumber(
                    technical.ma60,
                    2
                )
            )}

            ${keyValue(
                "ATR14",
                formatNumber(
                    technical.atr14,
                    2
                )
            )}

            ${keyValue(
                "5D Return",
                formatPercent(
                    technical.return_5d_pct
                )
            )}

            ${keyValue(
                "10D Return",
                formatPercent(
                    technical.return_10d_pct
                )
            )}

            ${keyValue(
                "20D Return",
                formatPercent(
                    technical.return_20d_pct
                )
            )}

            ${keyValue(
                "Volume Ratio 20D",
                formatNumber(
                    technical.volume_ratio_20,
                    2
                )
            )}

        </div>


        <div class="detail-section">

            <div class="detail-section-title">
                法人籌碼
            </div>

            ${keyValue(
                "外資今日",
                formatInteger(
                    institutional.foreign_net_latest
                )
            )}

            ${keyValue(
                "外資 5D",
                formatInteger(
                    institutional.foreign_5d_net
                )
            )}

            ${keyValue(
                "外資 20D",
                formatInteger(
                    institutional.foreign_20d_net
                )
            )}

            ${keyValue(
                "投信 5D",
                formatInteger(
                    institutional.trust_5d_net
                )
            )}

            ${keyValue(
                "自營商 5D",
                formatInteger(
                    institutional.dealer_5d_net
                )
            )}

        </div>


        <div class="detail-section">

            <div class="detail-section-title">
                TDCC
            </div>

            ${keyValue(
                "資料日",
                tdcc.data_date
                || "--"
            )}

            ${keyValue(
                "大戶持股 %",
                formatPercentRaw(
                    tdcc.large_holder_pct
                )
            )}

            ${keyValue(
                "散戶持股 %",
                formatPercentRaw(
                    tdcc.retail_holder_pct
                )
            )}

            ${keyValue(
                "大戶變化",
                formatPercentRaw(
                    tdcc.large_holder_change
                )
            )}

        </div>


        <div class="detail-section">

            <div class="detail-section-title">
                月營收
            </div>

            ${keyValue(
                "月份",
                revenue.revenue_month
                || "--"
            )}

            ${keyValue(
                "月營收",
                formatInteger(
                    revenue.revenue
                )
            )}

            ${keyValue(
                "YoY",
                formatPercent(
                    revenue.revenue_yoy_pct
                )
            )}

            ${keyValue(
                "MoM",
                formatPercent(
                    revenue.revenue_mom_pct
                )
            )}

            ${keyValue(
                "歷史",
                `${
                    revenue.history_months
                    || 0
                } / 24 月`
            )}

        </div>


        <div class="detail-section">

            <div class="detail-section-title">
                季財報
            </div>

            ${keyValue(
                "期間",
                financial.period
                || "--"
            )}

            ${keyValue(
                "EPS",
                formatNumber(
                    financial.eps,
                    2
                )
            )}

            ${keyValue(
                "毛利率",
                formatPercentRaw(
                    financial.gross_margin_pct
                )
            )}

            ${keyValue(
                "營業利益率",
                formatPercentRaw(
                    financial.operating_margin_pct
                )
            )}

            ${keyValue(
                "淨利率",
                formatPercentRaw(
                    financial.net_margin_pct
                )
            )}

            ${keyValue(
                "歷史",
                `${
                    financial.history_quarters
                    || 0
                } / 8 季`
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
                        value="${
                            escapeHtml(
                                position.avg_cost
                                ?? ""
                            )
                        }"
                    >
                </label>

                <label class="position-label">
                    股數

                    <input
                        id="positionShares"
                        class="position-input"
                        type="number"
                        step="1"
                        value="${
                            escapeHtml(
                                position.shares
                                ?? ""
                            )
                        }"
                    >
                </label>

            </div>

            ${
                positionSummary(
                    stock,
                    position
                )
            }

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


function scoreBox(
    name,
    value
) {

    return `

        <div class="score-box">

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
                        0
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


function readinessStatus(
    status
) {

    if (
        status === "READY"
    ) {

        return "READY";
    }

    return "補資料中";
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
            stock.latest
                ?.close
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
            <div
                class="metric-sub"
                style="
                    margin-top: 10px;
                "
            >
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

        <div
            style="
                margin-top: 10px;
            "
        >

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


function getWatchlist() {

    try {

        const raw =
            localStorage.getItem(
                WATCHLIST_KEY
            );

        if (
            !raw
        ) {

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

        first_buy_date:
            old.first_buy_date
            ||
            null,
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
            ${
                escapeHtml(
                    normalized
                    || "WAIT"
                )
            }
        </span>
    `;
}


function changeClass(
    value
) {

    const number =
        Number(
            value
        );

    if (
        !Number.isFinite(
            number
        )
        ||
        number === 0
    ) {

        return "neutral";
    }

    return (
        number > 0
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

    const number =
        Number(
            value
        );

    if (
        !Number.isFinite(
            number
        )
    ) {

        return "--";
    }

    return number
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

    const number =
        Number(
            value
        );

    if (
        !Number.isFinite(
            number
        )
    ) {

        return "--";
    }

    return Math.round(
        number
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

    const number =
        Number(
            value
        );

    if (
        !Number.isFinite(
            number
        )
    ) {

        return "--";
    }

    const sign =
        number > 0
        ?
        "+"
        :
        "";

    return (
        `${sign}${number.toFixed(2)}%`
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

    const number =
        Number(
            value
        );

    if (
        !Number.isFinite(
            number
        )
    ) {

        return "--";
    }

    return (
        `${number.toFixed(2)}%`
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