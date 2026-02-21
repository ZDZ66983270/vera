import sqlite3
import pandas as pd

def check_etf_data_v4():
    conn = sqlite3.connect('vera.db')
    cursor = conn.cursor()
    
    try:
        # 1. Check asset_classification schema
        cursor.execute("PRAGMA table_info(asset_classification)")
        cols = [r[1] for r in cursor.fetchall()]
        print(f"asset_classification columns: {cols}")
        
        # Decide category column
        cat_col = 'sub_category' if 'sub_category' in cols else ('search_type' if 'search_type' in cols else 'category')
        print(f"Using category column: {cat_col}")
        
        # 2. Find ETFs and their symbols
        query = f"""
        SELECT a.asset_id, a.primary_symbol as symbol, c.{cat_col}
        FROM asset_universe a
        JOIN asset_classification c ON a.asset_id = c.asset_id
        WHERE c.{cat_col} LIKE '%ETF%'
          OR c.{cat_col} IN ('ETF', 'Index', 'Fund')
        LIMIT 10
        """
        etfs = pd.read_sql(query, conn)
        print("\nSample ETFs found:")
        print(etfs)
        
        if etfs.empty:
            print("No ETFs found.")
            return

        symbols = etfs['symbol'].dropna().unique().tolist()
        asset_ids = etfs['asset_id'].unique().tolist()
        
        # 3. Check vera_price_cache (uses symbol)
        placeholders = ','.join('?' for _ in symbols)
        if symbols:
            q_price = f"""
            SELECT symbol, trade_date, close, pe, pe_ttm
            FROM vera_price_cache
            WHERE symbol IN ({placeholders})
            AND trade_date > '2024-01-01'
            ORDER BY trade_date DESC
            LIMIT 20
            """
            print("\nChecking vera_price_cache for PE/PE_TTM:")
            prices = pd.read_sql(q_price, conn, params=symbols)
            print(prices)
            
            # Count non-nulls
            if not prices.empty:
                print("Non-null counts in sample:")
                print(prices[['pe', 'pe_ttm']].count())
        else:
             print("No symbols to check in price cache.")

        # 4. Check fundamentals_facts (uses asset_id)
        placeholders_id = ','.join('?' for _ in asset_ids)
        if asset_ids:
            q_fund = f"""
            SELECT asset_id, as_of_date, pe_ttm, pe_ttm_raw
            FROM fundamentals_facts
            WHERE asset_id IN ({placeholders_id})
            ORDER BY as_of_date DESC
            LIMIT 10
            """
            print("\nChecking fundamentals_facts for PE_TTM:")
            funds = pd.read_sql(q_fund, conn, params=asset_ids)
            print(funds)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    check_etf_data_v4()
