import sys
import os
import pandas as pd
import sqlite3

# Add project root to path
sys.path.append(os.getcwd())
try:
    from db.connection import get_connection
except ImportError:
    sys.path.append(os.path.dirname(os.getcwd()))
    from db.connection import get_connection

def check_us_coverage():
    conn = get_connection()
    
    # 1. Total US Stocks
    us_assets = conn.execute("""
        SELECT asset_id, symbol_name 
        FROM assets 
        WHERE market = 'US' AND asset_type = 'EQUITY'
    """).fetchall()
    
    total_us = len(us_assets)
    print(f"Total US Stocks: {total_us}")
    
    if total_us == 0:
        return

    # 2. Check Financial History (EPS TTM)
    # Count how many have at least one EPS TTM record
    # And check for recent data (e.g. within last 1 year)
    print("\n--- Financial History (EPS TTM) ---")
    
    has_eps_count = 0
    has_recent_eps_count = 0
    
    # Get all US asset IDs
    us_ids = [r[0] for r in us_assets]
    id_str = ",".join([f"'{x}'" for x in us_ids])
    
    # Batch query stats
    # Group by asset_id
    query_fin = f"""
        SELECT asset_id, count(*), max(report_date)
        FROM financial_history
        WHERE asset_id IN ({id_str}) AND eps_ttm IS NOT NULL
        GROUP BY asset_id
    """
    
    fin_stats = pd.read_sql_query(query_fin, conn)
    has_eps_set = set(fin_stats['asset_id'].tolist())
    has_eps_count = len(has_eps_set)
    
    # Check recency (e.g., report_date > 2024-01-01)
    recent_mask = fin_stats['max(report_date)'] >= '2024-01-01'
    has_recent_eps_count = recent_mask.sum()
    
    print(f"Stocks with ANY EPS TTM records: {has_eps_count} ({has_eps_count/total_us*100:.1f}%)")
    print(f"Stocks with RECENT EPS TTM (>= 2024-01-01): {has_recent_eps_count} ({has_recent_eps_count/total_us*100:.1f}%)")
    
    # 3. Check Price Cache (PE)
    print("\n--- Price Cache (PE) ---")
    
    # This might be heavy, so let's count distored users
    query_pe = f"""
        SELECT symbol, count(*), max(trade_date)
        FROM vera_price_cache
        WHERE symbol IN ({id_str}) AND pe IS NOT NULL AND pe != 0
        GROUP BY symbol
    """
    
    pe_stats = pd.read_sql_query(query_pe, conn)
    has_pe_set = set(pe_stats['symbol'].tolist())
    has_pe_count = len(has_pe_set)
    
    # Check recency
    recent_pe_mask = pe_stats['max(trade_date)'] >= '2024-12-01'
    has_recent_pe_count = recent_pe_mask.sum()
    
    print(f"Stocks with ANY PE records: {has_pe_count} ({has_pe_count/total_us*100:.1f}%)")
    print(f"Stocks with RECENT PE (>= 2024-12-01): {has_recent_pe_count} ({has_recent_pe_count/total_us*100:.1f}%)")

    # 4. Check Sample (TSLA, AAPL, NVDA)
    samples = ['US:STOCK:TSLA', 'US:STOCK:AAPL', 'US:STOCK:NVDA']
    print("\n--- Sample Check ---")
    for s in samples:
        if s in us_ids:
            # Fin
            fin_rows = conn.execute(f"SELECT count(*), max(report_date) FROM financial_history WHERE asset_id='{s}' AND eps_ttm IS NOT NULL").fetchone()
            # PE
            pe_rows = conn.execute(f"SELECT count(*), max(trade_date) FROM vera_price_cache WHERE symbol='{s}' AND pe IS NOT NULL").fetchone()
            
            print(f"{s}:")
            print(f"  EPS TTM Records: {fin_rows[0]} (Last: {fin_rows[1]})")
            print(f"  PE Records:      {pe_rows[0]} (Last: {pe_rows[1]})")
        else:
            print(f"{s}: Not found in DB")

    conn.close()

if __name__ == "__main__":
    check_us_coverage()
