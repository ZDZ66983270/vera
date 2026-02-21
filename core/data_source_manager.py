import sqlite3
from typing import List, Dict, Optional
from db.connection import get_connection
from utils.canonical_resolver import resolve_canonical_symbol
from utils.stock_name_fetcher import get_stock_name
from engine.asset_resolver import resolve_asset

def get_universe_assets_v2(conn=None) -> List[Dict]:
    """Fetch all active assets in the universe with detailed attributes."""
    own_conn = False
    if conn is None:
        conn = get_connection()
        own_conn = True
    
    try:
        cursor = conn.cursor()
        # Join assets, universe, latest classification, and price stats
        query = """
            SELECT 
                u.asset_id, 
                u.primary_symbol,
                a.name, 
                a.market, 
                a.asset_type,
                ac.scheme,
                ac.sector_code,
                ac.sector_name,
                ac.industry_code,
                ac.industry_name,
                u.sector_proxy_id AS benchmark_etf,
                u.market_index_id AS benchmark_index,
                stats.last_date,
                stats.duration_years,
                fhs.last_report,
                fhs.report_duration
            FROM asset_universe u
            JOIN assets a ON u.asset_id = a.asset_id
            LEFT JOIN (
                SELECT * FROM asset_classification 
                WHERE is_active = 1 
                GROUP BY asset_id 
                HAVING MAX(as_of_date)
            ) ac ON u.asset_id = ac.asset_id
            LEFT JOIN (
                SELECT 
                    COALESCE(m.canonical_id, p.symbol) as effective_id,
                    MAX(p.trade_date) as last_date,
                    (JULIANDAY(MAX(p.trade_date)) - JULIANDAY(MIN(p.trade_date))) / 365.25 as duration_years
                FROM vera_price_cache p
                LEFT JOIN asset_symbol_map m ON p.symbol = m.symbol
                GROUP BY effective_id
            ) stats ON u.asset_id = stats.effective_id
            LEFT JOIN (
                SELECT 
                    asset_id,
                    MAX(report_date) as last_report,
                    (JULIANDAY(MAX(report_date)) - JULIANDAY(MIN(report_date))) / 365.25 as report_duration
                FROM financial_history
                GROUP BY asset_id
            ) fhs ON u.asset_id = fhs.asset_id
            WHERE u.is_active = 1
            ORDER BY 
            CASE a.market WHEN 'HK' THEN 0 WHEN 'US' THEN 1 WHEN 'CN' THEN 2 ELSE 3 END ASC,
            CASE a.asset_type WHEN 'EQUITY' THEN 0 WHEN 'STOCK' THEN 0 WHEN 'ETF' THEN 1 WHEN 'INDEX' THEN 2 ELSE 3 END ASC,
            a.asset_id ASC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        return [
            {
                "asset_id": r[0],
                "primary_symbol": r[1],
                "symbol_name": r[2],
                "market": r[3],
                "asset_type": r[4],
                "scheme": r[5],
                "sector_code": r[6],
                "sector_name": r[7],
                "industry_code": r[8],
                "industry_name": r[9],
                "benchmark_etf": r[10],
                "benchmark_index": r[11],
                "last_data_date": r[12],
                "data_duration_years": round(r[13], 2) if r[13] is not None else 0.0,
                "last_report_date": r[14],
                "report_duration_years": round(r[15], 2) if r[15] is not None else 0.0
            } for r in rows
        ]
    finally:
        if own_conn:
            conn.close()

def add_to_universe(
    raw_symbol: str, 
    source_id: str = "yahoo", 
    name: Optional[str] = None,
    market: Optional[str] = None,
    asset_type: Optional[str] = None,
    scheme: str = 'GICS',
    sector_code: Optional[str] = None,
    sector_name: Optional[str] = None,
    industry_code: Optional[str] = None,
    industry_name: Optional[str] = None,
    benchmark_etf: Optional[str] = None,
    benchmark_index: Optional[str] = None
):
    """
    Register a new asset into the system and universe with full metadata.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        from datetime import datetime
        now_date = datetime.now().strftime("%Y-%m-%d")
        
        # 1. Resolve Canonical ID
        from utils.canonical_resolver import resolve_canonical_symbol
        canonical_id = resolve_canonical_symbol(conn, raw_symbol, asset_type_hint=asset_type, market_hint=market)
        
        # 2. Heuristics for missing info
        if not name:
            name = get_stock_name(raw_symbol)
        
        asset_info = resolve_asset(canonical_id)
        final_market = market or asset_info.market
        final_type = asset_type or asset_info.asset_type
        
        # 3. Insert into assets (Base table)
        cursor.execute("""
            INSERT INTO assets (asset_id, name, market, asset_type, industry)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(asset_id) DO UPDATE SET
                name = excluded.name,
                market = excluded.market,
                asset_type = excluded.asset_type
        """, (canonical_id, name, final_market, final_type, industry_name or 'Unknown'))
        
        # 4. Insert into symbol mapping for the asset itself
        cursor.execute("""
            INSERT OR REPLACE INTO asset_symbol_map (canonical_id, symbol, source, priority, is_active)
            VALUES (?, ?, ?, 50, 1)
        """, (canonical_id, raw_symbol, source_id))
        
        # 5. Canonicalize Benchmarks if provided
        final_benchmark_etf = benchmark_etf
        final_benchmark_index = benchmark_index
        
        def _ensure_benchmark_mapping(canonical_id: str, conn):
            """Ensure a benchmark's canonical ID is mapped to its price cache symbol."""
            if not canonical_id:
                return
            # Check if mapping already exists
            existing = cursor.execute(
                "SELECT 1 FROM asset_symbol_map WHERE canonical_id = ? AND is_active = 1 LIMIT 1",
                (canonical_id,)
            ).fetchone()
            if existing:
                return
            
            # Derive the price cache symbol from canonical ID
            # E.g., HK:INDEX:HSI -> HSI, HK:ETF:02800 -> 02800.HK
            from utils.canonical_resolver import resolve_symbol_for_provider
            try:
                provider_symbol = resolve_symbol_for_provider(canonical_id, "yahoo")
                cursor.execute("""
                    INSERT OR IGNORE INTO asset_symbol_map (canonical_id, symbol, source, priority, is_active)
                    VALUES (?, ?, 'yahoo', 50, 1)
                """, (canonical_id, provider_symbol))
            except:
                pass
        
        try:
            if benchmark_etf:
                final_benchmark_etf = resolve_canonical_symbol(conn, benchmark_etf, asset_type_hint="ETF", market_hint=final_market)
                _ensure_benchmark_mapping(final_benchmark_etf, conn)
            if benchmark_index:
                final_benchmark_index = resolve_canonical_symbol(conn, benchmark_index, asset_type_hint="INDEX", market_hint=final_market)
                _ensure_benchmark_mapping(final_benchmark_index, conn)
        except:
            pass # Fallback to raw if resolution fails

        # 6. Insert into universe
        cursor.execute("""
            INSERT OR REPLACE INTO asset_universe 
            (asset_id, primary_source, primary_symbol, sector_proxy_id, market_index_id, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (canonical_id, source_id, raw_symbol, final_benchmark_etf, final_benchmark_index))
        
        # 6. Insert into classification if provided
        # Ensure scheme has a default if passed as None explicitly
        if not scheme:
            scheme = 'GICS'
            
        if scheme and (sector_code or industry_code or sector_name or industry_name):
            cursor.execute("""
                INSERT INTO asset_classification 
                (asset_id, scheme, sector_code, sector_name, industry_code, industry_name, as_of_date, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(asset_id, scheme, as_of_date) DO UPDATE SET
                    sector_code = excluded.sector_code,
                    sector_name = excluded.sector_name,
                    industry_code = excluded.industry_code,
                    industry_name = excluded.industry_name
            """, (canonical_id, scheme, sector_code, sector_name, industry_code, industry_name, now_date))

        conn.commit()
        return canonical_id
    finally:
        conn.close()

def remove_from_universe(asset_id: str):
    """Deactivate an asset from the universe."""
    conn = get_connection()
    try:
        conn.execute("UPDATE asset_universe SET is_active = 0 WHERE asset_id = ?", (asset_id,))
        conn.commit()
    finally:
        conn.close()
