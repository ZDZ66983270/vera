# VERA Database Structure

**Generated**: 2025-12-24  
**Database**: `vera.db` (SQLite)  
**Total Tables**: 18

---

## Table of Contents

1. [Core Data Tables](#core-data-tables)
   - [vera_price_cache](#vera_price_cache)
   - [assets](#assets)
   - [financial_history](#financial_history)
2. [Symbol Mapping Tables](#symbol-mapping-tables)
   - [asset_symbol_map](#asset_symbol_map)
   - [symbol_alias](#symbol_alias)
   - [asset_sector_map](#asset_sector_map)
3. [Analysis & Risk Tables](#analysis--risk-tables)
   - [analysis_snapshot](#analysis_snapshot)
   - [risk_card_snapshot](#risk_card_snapshot)
   - [risk_overlay_snapshot](#risk_overlay_snapshot)
   - [market_risk_snapshot](#market_risk_snapshot)
   - [drawdown_state_history](#drawdown_state_history)
   - [risk_events](#risk_events)
4. [Behavior & Decision Tables](#behavior--decision-tables)
   - [behavior_flags](#behavior_flags)
   - [decision_log](#decision_log)
5. [Configuration Tables](#configuration-tables)
   - [user_risk_profiles](#user_risk_profiles)
6. [Legacy/Utility Tables](#legacyutility-tables)
   - [vera_snapshot](#vera_snapshot)
   - [vera_risk_metrics](#vera_risk_metrics)
   - [metric_details](#metric_details)

---

## Core Data Tables

### vera_price_cache

**Purpose**: Canonical price data storage with raw symbol audit trail

**Schema**:
```sql
CREATE TABLE vera_price_cache (
    symbol TEXT,              -- ❗ Canonical Symbol (如 SPX, 600309, TSLA)
    trade_date DATE,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    source TEXT,              -- Format: {source}|raw:{raw_symbol}|note:{optional}
    PRIMARY KEY (symbol, trade_date)
);
```

**Key Points**:
- `symbol` **MUST** be canonical (no `.SS`/`.SH` suffixes)
- `source` format: `yahoo|raw:^GSPC|note:adjusted`
- All writes go through `save_daily_price()` for automatic canonical mapping

---

### assets

**Purpose**: Asset master data (stocks, ETFs, indices)

**Schema**:
```sql
CREATE TABLE assets (
    asset_id TEXT PRIMARY KEY,
    symbol_name TEXT,
    market TEXT,              -- US/HK/CN
    industry TEXT,
    asset_type TEXT,          -- STOCK/ETF_SECTOR/ETF_MARKET/INDEX
    index_role TEXT,
    asset_role TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
```

---

### financial_history

**Purpose**: Fundamental data (EPS, BPS, dividends, bank metrics)

**Schema**:
```sql
CREATE TABLE financial_history (
    asset_id TEXT,
    report_date DATE,
    eps_ttm REAL,
    bps REAL,
    revenue_ttm REAL,
    net_profit_ttm REAL,
    dividend_amount REAL,
    buyback_amount REAL,
    -- Bank-specific metrics
    npl_ratio REAL,
    special_mention_ratio REAL,
    provision_coverage REAL,
    allowance_to_loan REAL,
    overdue_90_loans REAL,
    npl_balance REAL,
    PRIMARY KEY (asset_id, report_date),
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE
);
```

---

## Symbol Mapping Tables

### asset_symbol_map

**Purpose**: Canonical symbol resolver (multiple raw symbols → single canonical_id)

**Schema**:
```sql
CREATE TABLE asset_symbol_map (
    canonical_id TEXT NOT NULL,  -- e.g., SPX, 600309
    symbol TEXT NOT NULL,         -- e.g., ^GSPC, 600309.SS
    source TEXT,
    priority INTEGER DEFAULT 50,
    is_active INTEGER DEFAULT 1,
    note TEXT,
    created_at TEXT,
    updated_at TEXT,
    PRIMARY KEY (canonical_id, symbol)
);

CREATE INDEX idx_symbol_lookup ON asset_symbol_map (symbol, is_active);
```

**Examples**:
- `SPX` ← {`SPX`, `^SPX`, `^GSPC`}
- `600309` ← {`600309.SS`, `600309.SH`}

---

### symbol_alias

**Purpose**: Legacy symbol aliases

**Schema**:
```sql
CREATE TABLE symbol_alias (
    canonical_id TEXT NOT NULL,
    alias_id TEXT NOT NULL,
    source TEXT,
    created_at TEXT,
    PRIMARY KEY (canonical_id, alias_id)
);
```

---

### asset_sector_map

**Purpose**: Stock-to-sector ETF mapping (for sector overlay analysis)

**Schema**:
```sql
CREATE TABLE asset_sector_map (
    asset_id TEXT NOT NULL,
    sector_etf_id TEXT NOT NULL,
    scheme TEXT DEFAULT 'default',
    is_active INTEGER DEFAULT 1,
    updated_at TEXT,
    PRIMARY KEY (asset_id, scheme)
);
```

---

## Analysis & Risk Tables

### analysis_snapshot

**Purpose**: Core analysis snapshot container (未在输出中显示完整schema，需补充)

_Note: Schema not fully captured. Contains `snapshot_id`, timestamps, and foreign keys to risk/fundamental data._

---

### risk_card_snapshot

**Purpose**: 2D Risk Matrix snapshot (Position × Path Risk)

**Schema**:
```sql
CREATE TABLE risk_card_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    anchor_date DATE NOT NULL,
    
    -- Position Risk
    price_percentile REAL,          -- 0~1 历史价位分位
    position_zone TEXT,             -- LOW/MID/HIGH
    position_interpretation TEXT,
    
    -- Path Risk
    max_drawdown REAL,
    drawdown_stage REAL,            -- 0~1 在回撤区间中的位置
    volatility_percentile REAL,
    path_zone TEXT,                 -- LOW/MID/HIGH
    path_interpretation TEXT,
    
    -- Risk Quadrant
    risk_quadrant TEXT,             -- Q1/Q2/Q3/Q4
    system_notes TEXT,              -- JSON 数组
    
    -- Market Context (optional)
    market_index_asset_id TEXT,
    market_amplification_level REAL,
    alpha_headroom REAL,
    market_regime_label TEXT,
    market_regime_notes TEXT,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(snapshot_id) REFERENCES analysis_snapshot(snapshot_id) ON DELETE CASCADE
);
```

---

### risk_overlay_snapshot

**Purpose**: 3-Layer Risk Overlay (Individual/Sector/Market)

_Note: Schema not shown in output. Contains individual, sector, and market risk layers with summary and flags._

---

### market_risk_snapshot

**Purpose**: Market-level risk assessment

**Schema**:
```sql
CREATE TABLE market_risk_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    index_asset_id TEXT NOT NULL,
    as_of_date DATE NOT NULL,
    index_risk_state TEXT,
    drawdown REAL,
    volatility REAL,
    volume_anomaly REAL,
    method_profile_id TEXT DEFAULT 'default',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(index_asset_id, as_of_date, method_profile_id)
);
```

---

### drawdown_state_history

**Purpose**: D-State evolution tracking

_Note: Schema not shown in output. Tracks D0-D5 state transitions over time._

---

### risk_events

**Purpose**: Risk event log (secondary drawdown, failed recovery, structural collapse)

**Schema**:
```sql
CREATE TABLE risk_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT NOT NULL,
    event_type TEXT NOT NULL,         -- SECONDARY_DRAWDOWN/FAILED_RECOVERY/STRUCTURAL_COLLAPSE
    event_start_date DATE NOT NULL,
    event_end_date DATE,              -- NULL if ongoing
    
    -- State transition
    state_from TEXT NOT NULL,
    state_to TEXT NOT NULL,
    
    -- Severity
    severity_level TEXT NOT NULL,     -- 极危险/危险/警示
    
    -- Context snapshot
    volatility_at_event REAL,
    volume_change REAL,
    
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id) ON DELETE CASCADE
);

CREATE INDEX idx_risk_events_asset ON risk_events(asset_id, event_start_date DESC);
```

---

## Behavior & Decision Tables

### behavior_flags

**Purpose**: Behavioral risk warnings (FOMO, panic sell, etc.)

**Schema**:
```sql
CREATE TABLE behavior_flags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id TEXT NOT NULL,
    risk_card_id INTEGER NOT NULL,
    asset_id TEXT NOT NULL,
    anchor_date DATE NOT NULL,
    
    flag_code TEXT NOT NULL,          -- e.g., FOMO_RISK
    flag_level TEXT NOT NULL,         -- INFO/WARN/ALERT
    flag_dimension TEXT NOT NULL,     -- POSITION/PATH/COMBINED
    
    flag_title TEXT NOT NULL,
    flag_description TEXT NOT NULL,
    
    trigger_context TEXT,             -- JSON: 触发时的指标快照
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(snapshot_id) REFERENCES analysis_snapshot(snapshot_id) ON DELETE CASCADE,
    FOREIGN KEY(risk_card_id) REFERENCES risk_card_snapshot(id) ON DELETE CASCADE
);
```

---

### decision_log

**Purpose**: User decision recording (for backtesting)

**Schema**:
```sql
CREATE TABLE decision_log (
    decision_id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id TEXT NOT NULL,
    action TEXT NOT NULL,             -- Buy/Sell/Hold
    context_note TEXT,
   created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES analysis_snapshot(snapshot_id) ON DELETE CASCADE
);
```

---

## Configuration Tables

### user_risk_profiles

**Purpose**: User risk tolerance questionnaire results

**Schema**:
```sql
CREATE TABLE user_risk_profiles (
    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    risk_tolerance_level TEXT NOT NULL,  -- CONSERVATIVE/BALANCED/AGGRESSIVE
    
    -- Scoring details
    total_score INTEGER NOT NULL,
    answer_set TEXT,                      -- JSON: {"Q1": "A", ...}
    
    -- Display preferences
    drawdown_emphasis TEXT,               -- HIGH/MEDIUM/LOW
    warning_verbosity TEXT,               -- DETAILED/STANDARD/MINIMAL
    color_intensity TEXT,                 -- LOW/NORMAL/GRAYSCALE
    
    profile_version TEXT DEFAULT 'v1',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## Legacy/Utility Tables

### vera_snapshot

**Purpose**: Legacy snapshot container

**Schema**:
```sql
CREATE TABLE vera_snapshot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    anchor_date DATE,
    created_at DATETIME
);
```

---

### vera_risk_metrics

**Purpose**: Legacy metric storage

**Schema**:
```sql
CREATE TABLE vera_risk_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL,
    window INTEGER,
    parameters TEXT,              -- JSON
    unit TEXT,                    -- %, days, ratio
    computed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES vera_snapshot(id) ON DELETE CASCADE
);
```

---

### metric_details

**Purpose**: Detailed metric breakdown

**Schema**:
```sql
CREATE TABLE metric_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id TEXT NOT NULL,
    metric_key TEXT NOT NULL,        -- e.g., max_drawdown, pe_ratio
    value REAL NOT NULL,
    percentile REAL,                 -- 0.0 - 1.0
    FOREIGN KEY (snapshot_id) REFERENCES analysis_snapshot(snapshot_id) ON DELETE CASCADE
);
```

---

## Critical Design Principles

### 1. Canonical Symbol System

**❗ RED LINE**: Never write raw symbols directly to `vera_price_cache.symbol`

- All symbols **MUST** pass through `resolve_canonical_symbol()`
- Use `asset_symbol_map` for .SS/.SH/^-prefixed symbols
- `source` field preserves raw symbol audit trail

### 2. Source Field Format

```
{source_name}|raw:{raw_symbol}|note:{optional}
```

**Examples**:
- `yahoo|raw:^GSPC|note:adjusted`
- `manual_csv|raw:600309.SS`
- `import_csv|batch:20251224_005500`

### 3. Snapshot Architecture

- `analysis_snapshot`: Master container
- `risk_card_snapshot`: 2D Risk Matrix
- `risk_overlay_snapshot`: 3-Layer Overlay
- `behavior_flags`: Behavioral warnings
- `decision_log`: User actions

All linked via `snapshot_id` for temporal consistency.

---

## Table Dependencies (Foreign Keys)

```
assets
  └─ financial_history (asset_id)
  └─ risk_events (asset_id)

analysis_snapshot (snapshot_id)
  ├─ risk_card_snapshot
  ├─ behavior_flags
  ├─ decision_log
  └─ metric_details

risk_card_snapshot (id)
  └─ behavior_flags (risk_card_id)

vera_snapshot (id)
  └─ vera_risk_metrics (snapshot_id)
```

---

## Data Flow (Import → Analysis → Display)

```
1. CSV/OCR Import
   ↓ (import_prices_csv.py / ocr_data_ingest.py)
2. resolve_canonical_symbol()
   ↓ (utils/canonical_resolver.py)
3. save_daily_price()
   ↓ (data/price_cache.py)
4. vera_price_cache (canonical storage)
   ↓
5. run_snapshot()
   ↓ (engine/snapshot_builder.py)
6. analysis_snapshot + risk_card_snapshot + risk_overlay_snapshot
   ↓
7. generate_dashboard_data()
   ↓ (analysis/dashboard.py)
8. app.py (Streamlit UI)
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-12-24 00:55
