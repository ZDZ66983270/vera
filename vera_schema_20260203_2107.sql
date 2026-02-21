CREATE TABLE vera_price_cache (
    symbol TEXT,
    trade_date DATE,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    source TEXT, pe REAL, pb REAL, ps REAL, eps REAL, dividend_yield REAL, turnover REAL, market_cap REAL, pct_change REAL, prev_close REAL, pe_ttm REAL,
    PRIMARY KEY (symbol, trade_date)
);
CREATE TABLE vera_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    anchor_date DATE,
    created_at DATETIME
);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE vera_risk_metrics (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,

    snapshot_id        INTEGER NOT NULL,
    metric_name        TEXT NOT NULL,     -- max_drawdown / volatility
    metric_value       REAL NOT NULL,

    window             INTEGER,           -- 252 / 60 / 5 等
    parameters         TEXT,              -- JSON 字符串

    unit               TEXT,              -- %, days, ratio
    computed_at        DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (snapshot_id)
        REFERENCES vera_snapshot(id)
        ON DELETE CASCADE
);
CREATE TABLE financial_history (
    asset_id           TEXT,
    report_date        DATE,
    eps_ttm            REAL,              -- 用于计算 PE
    bps                REAL,              -- 用于计算 PB
    revenue_ttm        REAL,              -- 用于计算 PS
    net_profit_ttm     REAL,              -- 用于计算 利润率
    dividend_amount    REAL,              -- 年度分红总额
    buyback_amount     REAL, npl_ratio REAL, special_mention_ratio REAL, provision_coverage REAL, allowance_to_loan REAL, overdue_90_loans REAL, npl_balance REAL, currency TEXT DEFAULT 'CNY', net_income_ttm REAL, operating_cashflow_ttm REAL, free_cashflow_ttm REAL, total_assets REAL, total_liabilities REAL, total_debt REAL, cash_and_equivalents REAL, net_debt REAL, debt_to_equity REAL, interest_coverage REAL, current_ratio REAL, dividend_yield REAL, payout_ratio REAL, buyback_ratio REAL, net_interest_income REAL, net_fee_income REAL, provision_expense REAL, total_loans REAL, loan_loss_allowance REAL, core_tier1_capital_ratio REAL, operating_profit REAL, return_on_invested_capital REAL, gross_margin REAL, operating_cash_flow REAL, roe REAL, net_margin REAL, tier1_capital_ratio REAL, capital_adequacy_ratio REAL, common_equity_begin REAL, common_equity_end REAL, shares_outstanding REAL, shares_diluted REAL, treasury_shares REAL, dividends_paid REAL, dps REAL, operating_cashflow REAL,              -- 年度回购总额
    PRIMARY KEY (asset_id, report_date),
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE
);
CREATE TABLE metric_details (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id        TEXT NOT NULL,
    metric_key         TEXT NOT NULL,     -- 指标名 (e.g., max_drawdown, pe_ratio)
    value              REAL NOT NULL,     -- 绝对值
    percentile         REAL,              -- 历史分位 (0.0 - 1.0)
    FOREIGN KEY (snapshot_id) REFERENCES analysis_snapshot(snapshot_id) ON DELETE CASCADE
);
CREATE TABLE decision_log (
    decision_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id        TEXT NOT NULL,     -- 必须关联当时的快照，用于后续复盘
    action             TEXT NOT NULL,     -- 操作 (Buy/Sell/Hold)
    context_note       TEXT,              -- 当时想法记录
    created_at         DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES analysis_snapshot(snapshot_id) ON DELETE CASCADE
);
CREATE TABLE drawdown_state_history (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id                TEXT NOT NULL,
    trade_date              DATE NOT NULL,
    
    -- 原始计算状态（未经转移规则验证）
    raw_state               TEXT NOT NULL,      -- D0-D6
    raw_metrics_snapshot    TEXT,               -- JSON: {peak, trough, recovery, current_dd}
    
    -- 确认后的状态（经过转移规则和确认期验证）
    confirmed_state         TEXT NOT NULL,      -- D0-D6
    confirm_counter         INTEGER DEFAULT 0,  -- 连续满足当前 raw_state 的天数
    days_in_state           INTEGER DEFAULT 0,  -- 在 confirmed_state 停留天数
    
    -- 转移标记
    is_transition           BOOLEAN DEFAULT 0,  -- 是否发生状态转移
    prev_state              TEXT,               -- 前一状态
    
    -- 版本控制
    state_version           TEXT DEFAULT 'v1.0', -- 状态规则版本
    
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(asset_id, trade_date),
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE
);
CREATE TABLE risk_events (
    event_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id                TEXT NOT NULL,
    event_type              TEXT NOT NULL,      -- SECONDARY_DRAWDOWN / FAILED_RECOVERY / STRUCTURAL_COLLAPSE
    event_start_date        DATE NOT NULL,
    event_end_date          DATE,               -- NULL if ongoing
    
    -- 状态转移信息
    state_from              TEXT NOT NULL,      -- 起始状态
    state_to                TEXT NOT NULL,      -- 目标状态
    
    -- 风险评级
    severity_level          TEXT NOT NULL,      -- 极危险 / 危险 / 警示
    
    -- 上下文快照
    volatility_at_event     REAL,
    volume_change           REAL,               -- 成交量变化
    
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE
);
CREATE TABLE user_risk_profiles (
    profile_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    risk_tolerance_level   TEXT NOT NULL,     -- CONSERVATIVE / BALANCED / AGGRESSIVE
    
    -- 得分明细 (JSON 存储或直接分数字段)
    total_score            INTEGER NOT NULL,
    answer_set             TEXT,              -- JSON: {"Q1": "A", ...}
    
    -- 展示层偏好
    drawdown_emphasis      TEXT,              -- HIGH / MEDIUM / LOW
    warning_verbosity      TEXT,              -- DETAILED / STANDARD / MINIMAL
    color_intensity        TEXT,              -- LOW / NORMAL / GRAYSCALE
    
    profile_version        TEXT DEFAULT 'v1',
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE risk_card_snapshot (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id            TEXT NOT NULL,
    asset_id               TEXT NOT NULL,
    anchor_date            DATE NOT NULL,

    -- 位置风险 (Position Risk)
    price_percentile       REAL,          -- 0 ~ 1 (历史价位分位)
    position_zone          TEXT,          -- LOW / MID / HIGH
    position_interpretation TEXT,

    -- 价格路径风险 (Path Risk)
    max_drawdown           REAL,          -- 历史最大回撤
    drawdown_stage         REAL,          -- 当前在回撤区间中的位置 (0~1)
    volatility_percentile  REAL,          -- 波动率分位 (0~1)
    path_zone              TEXT,          -- LOW / MID / HIGH
    path_interpretation    TEXT,

    -- 风险象限
    risk_quadrant          TEXT,          -- Q1 / Q2 / Q3 / Q4
    system_notes           TEXT,          -- JSON 数组：备注信息

    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP, market_index_asset_id TEXT, market_amplification_level REAL, alpha_headroom REAL, market_regime_label TEXT, market_regime_notes TEXT,
    FOREIGN KEY(snapshot_id) REFERENCES analysis_snapshot(snapshot_id) ON DELETE CASCADE
);
CREATE TABLE behavior_flags (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id            TEXT NOT NULL,
    risk_card_id           INTEGER NOT NULL,
    asset_id               TEXT NOT NULL,
    anchor_date            DATE NOT NULL,

    flag_code              TEXT NOT NULL, -- e.g. FOMO_RISK
    flag_level             TEXT NOT NULL, -- INFO / WARN / ALERT
    flag_dimension         TEXT NOT NULL, -- POSITION / PATH / COMBINED

    flag_title             TEXT NOT NULL,
    flag_description       TEXT NOT NULL,

    trigger_context        TEXT,          -- JSON：触发时的指标快照
    created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(snapshot_id) REFERENCES analysis_snapshot(snapshot_id) ON DELETE CASCADE,
    FOREIGN KEY(risk_card_id) REFERENCES risk_card_snapshot(id) ON DELETE CASCADE
);
CREATE TABLE market_risk_snapshot (id INTEGER PRIMARY KEY AUTOINCREMENT, index_asset_id TEXT NOT NULL, as_of_date DATE NOT NULL, index_risk_state TEXT, drawdown REAL, volatility REAL, volume_anomaly REAL, method_profile_id TEXT DEFAULT 'default', created_at DATETIME DEFAULT CURRENT_TIMESTAMP, market_position_pct REAL, market_amplification_level TEXT, market_amplification_score REAL, UNIQUE(index_asset_id, as_of_date, method_profile_id));
CREATE TABLE symbol_alias (
        canonical_id TEXT NOT NULL,
        alias_id TEXT NOT NULL,
        source TEXT,
        created_at TEXT,
        PRIMARY KEY (canonical_id, alias_id)
    );
CREATE TABLE asset_symbol_map (
          canonical_id TEXT NOT NULL,
          symbol TEXT NOT NULL,
          source TEXT,
          priority INTEGER DEFAULT 50,
          is_active INTEGER DEFAULT 1,
          note TEXT,
          created_at TEXT,
          updated_at TEXT,
          PRIMARY KEY (canonical_id, symbol)
        );
CREATE TABLE asset_sector_map (
    asset_id TEXT NOT NULL,         -- canonical，例如 AAPL
    sector_etf_id TEXT NOT NULL,    -- canonical，例如 XLK
    sector_name TEXT,               -- Technology / Financials ...
    scheme TEXT DEFAULT 'GICS',     -- GICS / custom
    is_active INTEGER DEFAULT 1,
    updated_at TEXT,
    PRIMARY KEY (asset_id, scheme)
);
CREATE TABLE risk_overlay_snapshot (
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
, sector_position_pct REAL);
CREATE TABLE sector_proxy_map (
      scheme       TEXT NOT NULL,           -- 'GICS'
      sector_code  TEXT NOT NULL,           -- e.g. '45'
      sector_name  TEXT,
      proxy_etf_id TEXT NOT NULL,           -- e.g. 'XLK'
      priority     INTEGER DEFAULT 50,
      is_active    INTEGER DEFAULT 1,
      note         TEXT, market_index_id TEXT, market TEXT,
      PRIMARY KEY(scheme, sector_code, proxy_etf_id)
    );
CREATE TABLE sector_risk_snapshot (
  snapshot_id TEXT NOT NULL,
  sector_etf_id TEXT NOT NULL,
  as_of_date DATE NOT NULL,
  sector_dd_state TEXT,
  sector_position_pct REAL,
  sector_rs_3m REAL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (snapshot_id, sector_etf_id, as_of_date)
);
CREATE TABLE IF NOT EXISTS "quality_snapshot_old" (
    snapshot_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,

    -- Business Quality（业务韧性）
    revenue_stability_flag TEXT,      -- STRONG | MID | WEAK
    cyclicality_flag TEXT,             -- LOW | MID | HIGH
    moat_proxy_flag TEXT,              -- STRONG | MID | WEAK

    -- Financial Quality（财务缓冲）
    balance_sheet_flag TEXT,           -- STRONG | MID | WEAK
    cashflow_coverage_flag TEXT,        -- STRONG | MID | WEAK
    leverage_risk_flag TEXT,            -- LOW | MID | HIGH

    -- Governance / Policy（制度缓冲）
    payout_consistency_flag TEXT,       -- POSITIVE | NEUTRAL | NEGATIVE
    dilution_risk_flag TEXT,            -- LOW | MID | HIGH
    regulatory_dependence_flag TEXT,    -- LOW | MID | HIGH

    -- 综合判断（不打分，只定性）
    quality_buffer_level TEXT,          -- STRONG | MODERATE | WEAK
    quality_summary TEXT,               -- ≤ 2 行自然语言解释
    quality_notes TEXT,                 -- JSON格式的notes（可选，MVP扩展）

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP, quality_template_name TEXT, piotroski_f_score INTEGER, gross_margin_stability_flag TEXT, cash_conversion_flag TEXT, roic_trend_flag TEXT,

    PRIMARY KEY (snapshot_id),
    FOREIGN KEY (snapshot_id) REFERENCES analysis_snapshot(snapshot_id),
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
);
CREATE TABLE assets_backup_20251225(
  asset_id TEXT,
  symbol_name TEXT,
  market TEXT,
  industry TEXT,
  created_at NUM,
  asset_type TEXT,
  index_role TEXT,
  asset_role TEXT,
  updated_at TEXT
);
CREATE TABLE fundamentals_facts (
    asset_id            TEXT NOT NULL,
    as_of_date          DATE NOT NULL,      -- 对应财报期 / 报告期
    currency            TEXT,

    -- 核心原始指标（来自财报 / 数据源）
    net_income_ttm      REAL,               -- TTM 净利润
    shares_outstanding  REAL,               -- 总股本（摊薄）
    book_value_per_sh   REAL,               -- 每股净资产（最近一期）

    -- 可选：如果数据源直接给了 ratio，就顺手存一份
    pe_ttm_raw          REAL,               -- 数据源原始 P/E (TTM)
    pb_raw              REAL,               -- 数据源原始 P/B

    -- VERA 规范化后的指标
    eps_ttm             REAL,               -- 归一化后的每股收益 (calculated)
    pe_ttm              REAL,               -- calculated: price / eps_ttm
    pb                  REAL,               -- calculated: price / bvps

    source              TEXT,               -- 'yahoo', 'akshare', etc.
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (asset_id, as_of_date)
);
CREATE TABLE IF NOT EXISTS "asset_classification" (
            asset_id TEXT NOT NULL,
            scheme TEXT NOT NULL,
            sector_code TEXT,
            sector_name TEXT,
            industry_code TEXT,
            industry_name TEXT,
            as_of_date TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            PRIMARY KEY (asset_id, scheme, as_of_date)
        );
CREATE TABLE asset_universe (
    asset_id        TEXT NOT NULL,
    primary_source  TEXT,
    primary_symbol  TEXT,
    sector_proxy_id TEXT,
    market_index_id TEXT,
    is_active       INTEGER DEFAULT 1,
    notes           TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (asset_id),
    FOREIGN KEY (asset_id)       REFERENCES assets(asset_id),
    FOREIGN KEY (sector_proxy_id) REFERENCES assets(asset_id),
    FOREIGN KEY (market_index_id) REFERENCES assets(asset_id)
);
CREATE INDEX idx_state_history_asset_date ON drawdown_state_history(asset_id, trade_date DESC);
CREATE INDEX idx_risk_events_asset ON risk_events(asset_id, event_start_date DESC);
CREATE INDEX idx_symbol_lookup
        ON asset_symbol_map (symbol, is_active);
CREATE INDEX idx_overlay_asset_date 
ON risk_overlay_snapshot(asset_id, as_of_date);
CREATE TABLE fundamentals_annual (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            fiscal_year INTEGER NOT NULL,
            total_revenue REAL,
            net_income REAL,
            total_assets REAL,
            total_liabilities REAL,
            total_debt REAL,
            cash_and_equivalents REAL,
            operating_cashflow REAL,
            shares_outstanding REAL, 
            eps_diluted REAL,
            UNIQUE(asset_id, fiscal_year)
        );
CREATE TABLE financial_fundamentals (
            asset_id TEXT PRIMARY KEY,
            as_of_date TEXT, -- YYYY-MM-DD
            revenue_ttm REAL,
            net_income_ttm REAL,
            operating_cashflow_ttm REAL,
            free_cashflow_ttm REAL,
            total_assets REAL,
            total_liabilities REAL,
            total_debt REAL,
            cash_and_equivalents REAL,
            net_debt REAL, -- Derived or stored
            debt_to_equity REAL,
            interest_coverage REAL,
            current_ratio REAL,
            dividend_yield REAL,
            payout_ratio REAL,
            buyback_ratio REAL,
            data_source TEXT,
            currency TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        , roe REAL, net_margin REAL, net_interest_income REAL, net_fee_income REAL, provision_expense REAL, total_loans REAL, core_tier1_capital_ratio REAL, npl_ratio REAL, npl_balance REAL, provision_coverage REAL, special_mention_ratio REAL, overdue_90_loans REAL, tier1_capital_ratio REAL, capital_adequacy_ratio REAL);
CREATE TABLE analysis_snapshot (
            snapshot_id TEXT PRIMARY KEY,
            asset_id TEXT,
            as_of_date TEXT,
            risk_level TEXT,
            valuation_status TEXT,
            quality_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        , valuation_anchor TEXT, payout_score REAL, is_value_trap INTEGER DEFAULT 0);
CREATE TABLE assets (asset_id TEXT PRIMARY KEY, symbol TEXT, name TEXT, region TEXT, sector TEXT, industry TEXT, market TEXT, asset_type TEXT, index_role TEXT);
CREATE TABLE quality_snapshot (
            snapshot_id TEXT NOT NULL,
            asset_id    TEXT NOT NULL,

            -- Business Quality（业务韧性）
            revenue_stability_flag    TEXT,  -- STRONG | MID | WEAK
            cyclicality_flag          TEXT,  -- LOW | MID | HIGH
            moat_proxy_flag           TEXT,  -- STRONG | MID | WEAK

            -- Financial Quality（财务缓冲）
            balance_sheet_flag        TEXT,  -- STRONG | MID | WEAK
            cashflow_coverage_flag    TEXT,  -- STRONG | MID | WEAK
            leverage_risk_flag        TEXT,  -- LOW | MID | HIGH

            -- Governance / Policy（制度缓冲）
            payout_consistency_flag   TEXT,  -- POSITIVE | NEUTRAL | NEGATIVE
            dilution_risk_flag        TEXT,  -- LOW | HIGH
            regulatory_dependence_flag TEXT, -- LOW | MID | HIGH

            -- 汇总
            quality_buffer_level      TEXT,  -- STRONG | MODERATE | WEAK
            quality_summary           TEXT,  -- ≤ 2 行解释
            quality_notes             TEXT,  -- 详细备注 (JSON)

            created_at DATETIME DEFAULT CURRENT_TIMESTAMP, quality_template_name TEXT DEFAULT 'General',
            PRIMARY KEY (snapshot_id, asset_id)
        );
