
# engine/asset_resolver.py
from dataclasses import dataclass
import sqlite3
from db.connection import get_connection

@dataclass(frozen=True)
class AssetKey:
    asset_id: str
    symbol: str
    market: str
    asset_type: str  # EQUITY/ETF/INDEX
    index_role: str | None = None

def _infer_market(symbol: str) -> str:
    s = symbol.upper()
    if s.startswith("CN:"):
        return "CN"
    if s.startswith("HK:") or s.endswith(".HK"):
        return "HK"
    if s.endswith(".SS") or s.endswith(".SZ") or s.endswith(".SH"):
        return "CN"
    # Fallback: check if it's a 4 or 5-digit HK code
    if s.isdigit() and len(s) in [4, 5]:
        return "HK"
    return "US"

def _infer_asset_type(symbol: str) -> str:
    s = symbol.upper()
    if ":INDEX:" in s or s.startswith("^") or s in {"SPX", "NDX", "DJI", "HSI", "HSTECH", "000300"}:
        return "INDEX"
    if ":TRUST:" in s:
        return "TRUST"
    if ":CRYPTO:" in s:
        return "CRYPTO"
    if ":ETF:" in s:
        return "ETF"
    if ":STOCK:" in s:
        # Some things in STOCK namespace might be ETFs (e.g. 512880) - Fallback for old data
        code = s.split(":")[-1]
        if code.startswith(("51", "15", "58")): return "ETF"
        return "EQUITY"
    
    # Common US sector ETFs
    if s in {"XLK","XLF","XLE","XLY","XLP","XLV","XLI","XLB","XLU","XLC","IWM","QQQ","SPY", "DIA"}:
        return "ETF"
    # Common HK ETFs (4 digits usually, or standardized)
    if s.isdigit() and len(s) == 4:
        # Common HK ETF ranges
        if s.startswith(('2', '3', '9')):
            return "ETF"
    if s in {"2800.HK", "3033.HK", "2822.HK", "2828.HK", "3067.HK", "HK:STOCK:02800", "HK:STOCK:03033"}:
        return "ETF"
    
    return "EQUITY"

def resolve_asset(symbol: str) -> AssetKey:
    """
    Resolve symbol -> AssetKey. Prefer DB; fallback to heuristic.
    """
    conn = get_connection()
    cur = conn.cursor()

    # 1. Standardize the symbol first
    from utils.canonical_resolver import resolve_canonical_symbol
    try:
        canonical_id = resolve_canonical_symbol(conn, symbol)
    except Exception:
        canonical_id = symbol.upper()

    row = cur.execute(
        "SELECT asset_id, name, market, asset_type, index_role FROM assets WHERE asset_id = ?",
        (canonical_id,)
    ).fetchone()
    conn.close()

    if row:
        asset_id, _, market, asset_type, index_role = row
        market = market or _infer_market(asset_id)
        asset_type = asset_type or _infer_asset_type(asset_id)
        return AssetKey(asset_id=asset_id, symbol=symbol, market=market, asset_type=asset_type, index_role=index_role)

    market = _infer_market(canonical_id)
    asset_type = _infer_asset_type(canonical_id)
    index_role = "MARKET" if asset_type == "INDEX" else None
    return AssetKey(asset_id=canonical_id, symbol=symbol, market=market, asset_type=asset_type, index_role=index_role)

def resolve_market_index(market: str) -> AssetKey:
    market = (market or "US").upper()
    if market == "US":
        sym = "SPX"
    elif market == "HK":
        sym = "HSI"
    else:
        # CN: CSI 300
        sym = "CN:INDEX:000300"
    return AssetKey(asset_id=sym, symbol=sym, market=market, asset_type="INDEX", index_role="MARKET")

@dataclass
class SectorContext:
    asset_id: str
    sector_code: str | None
    sector_name: str | None
    proxy_etf_id: str | None
    market_index_id: str | None
    growth_proxy: str | None = "QQQ" # Default US assumption, logic can be refined
    value_proxy: str | None = "DIA"  # Default US assumption

def resolve_sector_context(asset_id: str, as_of_date: str = None) -> SectorContext:
    """
    Full Context Resolution for Overlay:
    1. Check asset_universe for explicit benchmark overrides (ETF/Index)
    2. Fallback to Sector -> Proxy ETF (via sector_proxy_map)
    3. Fallback to Asset -> Market Index (via resolve_asset -> resolve_market_index)
    """
    if not as_of_date:
        from datetime import datetime
        as_of_date = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. Resolve basic asset info & Default Market Index
    asset_key = resolve_asset(asset_id)
    market_cat = asset_key.market # US, CN, HK
    
    mkt_idx_key = resolve_market_index(market_cat)
    default_market_index_id = mkt_idx_key.asset_id

    # Defaults for Growth/Value proxies based on market
    g_proxy, v_proxy = None, None
    if market_cat == "US":
        g_proxy, v_proxy = "US:ETF:QQQ", "US:ETF:DIA"
    elif market_cat == "CN":
        g_proxy, v_proxy = "CN:INDEX:399006", "CN:INDEX:000016"
    elif market_cat == "HK":
        g_proxy, v_proxy = "HK:INDEX:HSTECH", "HK:INDEX:HSI"

    # 2. Check asset_universe for overrides
    universe_row = cur.execute(
        "SELECT sector_proxy_id, market_index_id FROM asset_universe WHERE asset_id = ? AND is_active = 1",
        (asset_id,)
    ).fetchone()
    
    u_proxy_id = universe_row['sector_proxy_id'] if universe_row else None
    u_market_index_id = universe_row['market_index_id'] if universe_row else None

    # 3. Query Sector Mapping (Fallback)
    # ❗ RELAXED: Prioritize the LATEST classification even if it's 'future' relative to as_of_date
    # as we usually want the current best metadata for the asset.
    query = """
    SELECT 
        ac.sector_code, 
        ac.sector_name,
        sp.proxy_etf_id,
        sp.market_index_id
    FROM asset_classification ac
    LEFT JOIN sector_proxy_map sp 
           ON ac.scheme = sp.scheme 
          AND ac.sector_code = sp.sector_code
          AND sp.is_active = 1
          AND sp.market = ?
    WHERE ac.asset_id = ? 
      AND ac.is_active = 1
    ORDER BY ABS(JULIANDAY(ac.as_of_date) - JULIANDAY(?)) ASC, ac.as_of_date DESC
    LIMIT 1
    """
    
    row = cur.execute(query, (market_cat, asset_id, as_of_date)).fetchone()
    
    sec_code, sec_name, m_proxy_id, m_specific_idx = None, None, None, None
    if row:
        sec_code = row['sector_code']
        sec_name = row['sector_name']
        m_proxy_id = row['proxy_etf_id']
        m_specific_idx = row['market_index_id']

    # 4. Hierarchical Selection
    final_proxy_id = u_proxy_id if u_proxy_id else m_proxy_id
    
    # ❗ NAME FALLBACK: If we have a proxy ETF but no sector name (e.g. override in Universe)
    # try to get the proxy's own name from assets table
    if final_proxy_id and not sec_name:
        proxy_row = cur.execute("SELECT name FROM assets WHERE asset_id = ?", (final_proxy_id,)).fetchone()
        if proxy_row and proxy_row[0]:
            sec_name = proxy_row[0]
            
    conn.close()
    
    # Index: Universe Override > Mapping Entry > Market Default
    final_index_id = u_market_index_id if u_market_index_id else (m_specific_idx if m_specific_idx else default_market_index_id)
    
    # ❗ RED LINE: Ensure everything returned is Canonical
    def _canon(sid):
        if not sid: return None
        from utils.canonical_resolver import resolve_canonical_symbol
        try:
            conn_c = get_connection()
            res = resolve_canonical_symbol(conn_c, sid)
            conn_c.close()
            return res
        except: return sid.upper()

    return SectorContext(
        asset_id=asset_id,
        sector_code=sec_code,
        sector_name=sec_name,
        proxy_etf_id=_canon(final_proxy_id),
        market_index_id=_canon(final_index_id),
        growth_proxy=_canon(g_proxy),
        value_proxy=_canon(v_proxy)
    )
