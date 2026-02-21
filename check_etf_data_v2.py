import sqlite3
import pandas as pd

def check_db_schema_and_etf_data():
    conn = sqlite3.connect('vera.db')
    cursor = conn.cursor()
    
    try:
        # 1. List all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        print("Tables in DB:", tables)
        
        target_table = 'market_data_daily'
        if target_table not in tables:
            print(f"ERROR: {target_table} not found!")
            # Fallback to check other potential tables
            return
            
        # 2. Inspect market_data_daily columns
        cursor.execute(f"PRAGMA table_info({target_table})")
        columns = [info[1] for info in cursor.fetchall()]
        print(f"\nColumns in {target_table}: {columns}")
        
        pe_cols = [c for c in columns if 'pe' in c.lower()]
        pb_cols = [c for c in columns if 'pb' in c.lower()]
        print(f"PE related columns: {pe_cols}")
        print(f"PB related columns: {pb_cols}")
        
        if not pe_cols:
            print("No PE columns found.")
        
        # 3. Find Global Index ETFs or Sector ETFs
        # We use asset_universe.primary_symbol or check classification
        query_etfs = """
        SELECT a.asset_id, a.primary_symbol, c.sub_category 
        FROM asset_universe a
        JOIN asset_classification c ON a.asset_id = c.asset_id
        WHERE c.sub_category LIKE '%ETF%'
        LIMIT 10
        """
        etfs = pd.read_sql(query_etfs, conn)
        print(f"\nFound {len(etfs)} sample ETFs:")
        print(etfs)
        
        if etfs.empty:
            print("No ETFs found.")
            return

        # 4. Check data for these ETFs
        asset_ids = tuple(etfs['asset_id'].tolist())
        placeholders = ','.join('?' for _ in asset_ids)
        
        check_cols = ['asset_id', 'trade_date'] + pe_cols + pb_cols
        query_vals = f"""
        SELECT {', '.join(check_cols)}
        FROM {target_table}
        WHERE asset_id IN ({placeholders})
        ORDER BY trade_date DESC
        LIMIT 20
        """
        
        vals = pd.read_sql(query_vals, conn, params=asset_ids)
        print("\nRecent Valuation Data for sample ETFs:")
        print(vals)
        
        # 5. Check aggregate non-nulls for ETFs
        print("\nChecking non-null counts for ALL ETFs in the DB:")
        # This might be heavy if many rows, let's limit to recent date or just a count queries
        
        # Check if any ETF has non-null PE
        count_query = f"""
        SELECT 
            COUNT(*) as total_rows,
            COUNT(pe_ttm) as pe_ttm_count,
            COUNT(pe_static) as pe_static_count
        FROM {target_table} md
        JOIN asset_classification c ON md.asset_id = c.asset_id
        WHERE c.sub_category LIKE '%ETF%'
          AND trade_date > '2025-01-01'
        """
        # Note: adjust date if DB is stale
        
        counts = pd.read_sql(count_query, conn)
        print("\nAggregate stats for ETFs (since 2025-01-01 maybe?):")
        print(counts)
        
        # Also check without date limit if counts are 0
        if counts['pe_ttm_count'].iloc[0] == 0:
             count_query_all = f"""
            SELECT 
                COUNT(pe_ttm) as pe_ttm_count_all_time,
                COUNT(pe_static) as pe_static_count_all_time
            FROM {target_table} md
            JOIN asset_classification c ON md.asset_id = c.asset_id
            WHERE c.sub_category LIKE '%ETF%'
            """
             counts_all = pd.read_sql(count_query_all, conn)
             print("\nAggregate stats for ETFs (All time):")
             print(counts_all)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_db_schema_and_etf_data()
