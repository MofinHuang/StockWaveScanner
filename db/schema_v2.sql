-- ============================================================
-- StockWaveScanner V2
-- Turso / libSQL Schema
-- Version: V2.1 Draft 1
-- Target: stockwave-dev first
-- ============================================================

PRAGMA foreign_keys = ON;


-- ============================================================
-- 1. STOCK MASTER
-- ============================================================

CREATE TABLE IF NOT EXISTS stock_master (
    stock_id               TEXT PRIMARY KEY,
    stock_name             TEXT NOT NULL,
    short_name             TEXT,
    market                 TEXT NOT NULL,
    security_type          TEXT NOT NULL DEFAULT 'COMMON_STOCK',

    industry_code          TEXT,
    industry_name          TEXT,

    listed_date            TEXT,
    issued_common_shares   INTEGER,

    source_date            TEXT,
    is_active              INTEGER NOT NULL DEFAULT 1,

    created_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (market IN ('TWSE', 'TPEX')),
    CHECK (is_active IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_stock_master_market
    ON stock_master (market);

CREATE INDEX IF NOT EXISTS idx_stock_master_industry
    ON stock_master (industry_code);

CREATE INDEX IF NOT EXISTS idx_stock_master_active
    ON stock_master (is_active);


-- ============================================================
-- 2. MARKET INDEX DAILY
-- ============================================================

CREATE TABLE IF NOT EXISTS market_index_daily (
    market                 TEXT NOT NULL,
    index_code             TEXT NOT NULL,
    trade_date             TEXT NOT NULL,

    open                    REAL NOT NULL,
    high                    REAL NOT NULL,
    low                     REAL NOT NULL,
    close                   REAL NOT NULL,

    volume                  REAL,
    turnover                REAL,

    source                  TEXT,
    created_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        market,
        index_code,
        trade_date
    ),

    CHECK (market IN ('TWSE', 'TPEX'))
);

CREATE INDEX IF NOT EXISTS idx_market_index_date
    ON market_index_daily (trade_date);

CREATE INDEX IF NOT EXISTS idx_market_index_code_date
    ON market_index_daily (index_code, trade_date);


-- ============================================================
-- 3. STOCK PRICE DAILY
-- ============================================================

CREATE TABLE IF NOT EXISTS stock_price_daily (
    stock_id               TEXT NOT NULL,
    trade_date             TEXT NOT NULL,

    open                    REAL,
    high                    REAL,
    low                     REAL,
    close                   REAL NOT NULL,

    volume                  INTEGER,
    turnover                REAL,
    trade_count             INTEGER,

    source                  TEXT,
    created_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        stock_id,
        trade_date
    ),

    FOREIGN KEY (stock_id)
        REFERENCES stock_master (stock_id)
);

CREATE INDEX IF NOT EXISTS idx_stock_price_date
    ON stock_price_daily (trade_date);

CREATE INDEX IF NOT EXISTS idx_stock_price_stock_date
    ON stock_price_daily (stock_id, trade_date DESC);


-- ============================================================
-- 4. INSTITUTIONAL DAILY
-- ============================================================

CREATE TABLE IF NOT EXISTS institutional_daily (
    stock_id               TEXT NOT NULL,
    trade_date             TEXT NOT NULL,

    foreign_buy            INTEGER,
    foreign_sell           INTEGER,
    foreign_net            INTEGER,

    trust_buy              INTEGER,
    trust_sell             INTEGER,
    trust_net              INTEGER,

    dealer_buy             INTEGER,
    dealer_sell            INTEGER,
    dealer_net             INTEGER,

    foreign_data_status    TEXT NOT NULL DEFAULT 'INSUFFICIENT_DATA',

    source                  TEXT,
    created_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        stock_id,
        trade_date
    ),

    FOREIGN KEY (stock_id)
        REFERENCES stock_master (stock_id),

    CHECK (
        foreign_data_status IN (
            'STORED',
            'ZERO_INFERRED',
            'INSUFFICIENT_DATA'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_institutional_date
    ON institutional_daily (trade_date);

CREATE INDEX IF NOT EXISTS idx_institutional_stock_date
    ON institutional_daily (stock_id, trade_date DESC);


-- ============================================================
-- 5. TDCC DISTRIBUTION
-- ============================================================

CREATE TABLE IF NOT EXISTS tdcc_distribution (
    stock_id               TEXT NOT NULL,
    data_date              TEXT NOT NULL,
    holder_level           TEXT NOT NULL,

    holder_count           INTEGER,
    shares                 INTEGER,
    percentage             REAL,

    source                  TEXT NOT NULL DEFAULT 'TDCC',
    created_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        stock_id,
        data_date,
        holder_level
    )
);

CREATE INDEX IF NOT EXISTS idx_tdcc_date
    ON tdcc_distribution (data_date);

CREATE INDEX IF NOT EXISTS idx_tdcc_stock_date
    ON tdcc_distribution (stock_id, data_date DESC);


-- ============================================================
-- 6. MONTHLY REVENUE
-- ============================================================

CREATE TABLE IF NOT EXISTS monthly_revenue (
    stock_id               TEXT NOT NULL,
    revenue_month          TEXT NOT NULL,

    revenue                REAL,

    revenue_mom_pct        REAL,
    revenue_yoy_pct        REAL,

    cumulative_revenue     REAL,
    cumulative_yoy_pct     REAL,

    source                  TEXT,
    created_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        stock_id,
        revenue_month
    ),

    FOREIGN KEY (stock_id)
        REFERENCES stock_master (stock_id)
);

CREATE INDEX IF NOT EXISTS idx_monthly_revenue_month
    ON monthly_revenue (revenue_month);

CREATE INDEX IF NOT EXISTS idx_monthly_revenue_stock_month
    ON monthly_revenue (stock_id, revenue_month DESC);


-- ============================================================
-- 7. QUARTERLY FINANCIAL
-- ============================================================
--
-- 注意：
-- 不同產業財報 Schema 不完全一致。
--
-- V2 第一版只保存跨產業可合理 Normalize 的共通指標。
-- 無法可靠取得的欄位使用 NULL，不得用 0 假裝。
--
-- report_type 用於區分：
-- GENERAL
-- FINANCIAL_HOLDING
-- BANK
-- INSURANCE
-- SECURITIES
-- OTHER
-- ============================================================

CREATE TABLE IF NOT EXISTS quarterly_financial (
    stock_id               TEXT NOT NULL,
    fiscal_year            INTEGER NOT NULL,
    fiscal_quarter         INTEGER NOT NULL,

    report_type            TEXT NOT NULL DEFAULT 'GENERAL',

    revenue                REAL,
    gross_profit           REAL,
    operating_income       REAL,
    net_income             REAL,
    eps                    REAL,

    gross_margin_pct       REAL,
    operating_margin_pct   REAL,
    net_margin_pct         REAL,

    source                  TEXT,
    source_date             TEXT,

    created_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (
        stock_id,
        fiscal_year,
        fiscal_quarter
    ),

    FOREIGN KEY (stock_id)
        REFERENCES stock_master (stock_id),

    CHECK (fiscal_quarter BETWEEN 1 AND 4),

    CHECK (
        report_type IN (
            'GENERAL',
            'FINANCIAL_HOLDING',
            'BANK',
            'INSURANCE',
            'SECURITIES',
            'OTHER'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_quarterly_financial_period
    ON quarterly_financial (
        fiscal_year,
        fiscal_quarter
    );

CREATE INDEX IF NOT EXISTS idx_quarterly_financial_stock_period
    ON quarterly_financial (
        stock_id,
        fiscal_year DESC,
        fiscal_quarter DESC
    );


-- ============================================================
-- 8. SYNC STATE
-- ============================================================
--
-- 用來記錄每個 Dataset 最後一次同步狀態。
--
-- dataset examples:
-- stock_master_twse
-- stock_master_tpex
-- market_index_twse
-- market_index_tpex
-- stock_price_twse
-- stock_price_tpex
-- institutional_twse
-- institutional_tpex
-- tdcc
-- monthly_revenue_twse
-- monthly_revenue_tpex
-- quarterly_financial_twse
-- quarterly_financial_tpex
-- ============================================================

CREATE TABLE IF NOT EXISTS sync_state (
    dataset                 TEXT PRIMARY KEY,

    last_data_date          TEXT,
    last_success_at         TEXT,
    last_attempt_at         TEXT,

    status                  TEXT NOT NULL DEFAULT 'NEVER_RUN',

    records_processed       INTEGER,
    error_message           TEXT,

    updated_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CHECK (
        status IN (
            'NEVER_RUN',
            'RUNNING',
            'SUCCESS',
            'PARTIAL',
            'FAILED'
        )
    )
);


-- ============================================================
-- 9. SCHEMA META
-- ============================================================

CREATE TABLE IF NOT EXISTS schema_meta (
    schema_key              TEXT PRIMARY KEY,
    schema_value            TEXT NOT NULL,
    updated_at              TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO schema_meta (
    schema_key,
    schema_value,
    updated_at
)
VALUES (
    'schema_version',
    'V2.1-DRAFT-1',
    CURRENT_TIMESTAMP
)
ON CONFLICT(schema_key)
DO UPDATE SET
    schema_value = excluded.schema_value,
    updated_at = CURRENT_TIMESTAMP;


-- ============================================================
-- END
-- ============================================================