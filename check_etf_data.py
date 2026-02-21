import sqlite3
import pandas as pd

def check_etf_pe():
    conn = sqlite3.connect('vera.db')
    
    # 1. Find some ETFs
    query_etfs = """
    SELECT a.asset_id, a.symbol, a.name, c.sub_category 
    FROM asset_universe a
    JOIN asset_classification c ON a.asset_id = c.asset_id
    WHERE c.sub_category IN ('ETF', 'Index ETF', 'Sector ETF', 'Bond ETF', 'Commodity ETF')
    LIMIT 10
    """
    
    try:
        etfs = pd.read_sql(query_etfs, conn)
        print(f"Found {len(etfs)} sample ETFs:")
        print(etfs)
        
        if etfs.empty:
            print("No ETFs found in asset_universe/classification.")
            return

        # 2. Check market_data_daily for these ETFs
        # Assuming table is market_data_daily and has pe, pe_ttm columns
        # Let's check table info first to be sure about column names
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(market_data_daily)")
        columns = [info[1] for info in cursor.fetchall()]
        print(f"\nColumns in market_data_daily: {columns}")
        
        pe_cols = [c for c in columns if 'pe' in c.lower()]
        print(f"PE related columns: {pe_cols}")
        
        if not pe_cols:
            print("No PE columns found in market_data_daily.")
        else:
            asset_ids = tuple(etfs['asset_id'].tolist())
            placeholders = ','.join('?' for _ in asset_ids)
            
            # Check latest data for these ETFs
            query_vals = f"""
            SELECT asset_id, trade_date, {', '.join(pe_cols)}
            FROM market_data_daily
            WHERE asset_id IN ({placeholders})
            ORDER BY trade_date DESC
            LIMIT 20
            """
            
            vals = pd.read_sql(query_vals, conn, params=asset_ids)
            print("\nRecent Valuation Data for sample ETFs:")
            print(vals)
            
            # Check coverage stats
            print("\nNon-null counts for sample data:")
            print(vals[pe_cols].count())

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_etf_pe()
