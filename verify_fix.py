import sqlite3
import pandas as pd

def verify_fix():
    conn = sqlite3.connect('vera.db')
    
    # The updated query logic
    query = """
    SELECT 
        u.asset_id, 
        u.primary_symbol,
        stats.last_date,
        stats.duration_years
    FROM asset_universe u
    LEFT JOIN (
        SELECT 
            COALESCE(m.canonical_id, p.symbol) as effective_id,
            MAX(p.trade_date) as last_date,
            (JULIANDAY(MAX(p.trade_date)) - JULIANDAY(MIN(p.trade_date))) / 365.25 as duration_years
        FROM vera_price_cache p
        LEFT JOIN asset_symbol_map m ON p.symbol = m.symbol
        GROUP BY effective_id
    ) stats ON u.asset_id = stats.effective_id
    WHERE u.asset_id IN ('CN:STOCK:600036', 'HK:STOCK:03968')
    """
    
    print("Running verification query...")
    df = pd.read_sql(query, conn)
    print(df)
    conn.close()

if __name__ == "__main__":
    verify_fix()
