-- 1) 个股 -> 板块 ETF 映射（手工维护）
CREATE TABLE IF NOT EXISTS asset_sector_map (
    asset_id TEXT NOT NULL,         -- canonical，例如 AAPL
    sector_etf_id TEXT NOT NULL,    -- canonical，例如 XLK
    sector_name TEXT,               -- Technology / Financials ...
    scheme TEXT DEFAULT 'GICS',     -- GICS / custom
    is_active INTEGER DEFAULT 1,
    updated_at TEXT,
    PRIMARY KEY (asset_id, scheme)
);

-- 2) 三层对照结果快照（前端直接读）
CREATE TABLE IF NOT EXISTS risk_overlay_snapshot (
    snapshot_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    
    -- Layer 1: Individual
    ind_dd_state TEXT,
    ind_path_risk TEXT,
    ind_vol_regime TEXT,
    ind_position_pct REAL,
    
    -- Layer 2: Sector
    sector_etf_id TEXT,
    sector_dd_state TEXT,
    sector_path_risk TEXT,
    stock_vs_sector_rs_3m REAL,
    sector_alignment TEXT,          -- aligned / negative_divergence / positive_divergence
    
    -- Layer 3: Market
    market_index_id TEXT,           -- SPX
    market_dd_state TEXT,
    market_path_risk TEXT,
    growth_vs_market_rs_3m REAL,    -- NDX vs SPX
    value_vs_market_rs_3m REAL,     -- DJI vs SPX
    market_regime_label TEXT,       -- Healthy Differentiation / Systemic Compression / Systemic Stress ...
    
    -- Explain (Rule Engine output)
    overlay_summary TEXT,           -- 1-2 行自然语言结论
    overlay_flags TEXT,             -- JSON string of triggered rules
    
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_overlay_asset_date 
ON risk_overlay_snapshot(asset_id, as_of_date);
