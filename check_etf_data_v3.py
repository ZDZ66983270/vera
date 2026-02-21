import sqlite3
import pandas as pd

def check_alternative_tables():
    conn = sqlite3.connect('vera.db')
    cursor = conn.cursor()
    
    tables_to_check = ['financial_history', 'vera_price_cache', 'financial_fundamentals', 'fundamentals_facts']
    
    try:
        for t in tables_to_check:
            print(f"\n--- Checking table: {t} ---")
            try:
                cursor.execute(f"PRAGMA table_info({t})")
                columns = [info[1] for info in cursor.fetchall()]
                print(f"Columns: {columns}")
                
                # Check for PE-like columns
                pe_like = [c for c in columns if 'pe' in c.lower() or 'val' in c.lower() or 'ttm' in c.lower()]
                if pe_like:
                    print(f"Found potential valuation columns: {pe_like}")
                    
                    # If this table has asset_id and valuation, let's check content for ETFs
                    if 'asset_id' in columns:
                        # Find ETFs
                        query_etfs = """
                        SELECT a.asset_id 
                        FROM asset_universe a
                        JOIN asset_classification c ON a.asset_id = c.asset_id
                        WHERE c.sub_category LIKE '%ETF%'
                        LIMIT 5
                        """
                        etf_ids = pd.read_sql(query_etfs, conn)['asset_id'].tolist()
                        
                        if etf_ids:
                             placeholders = ','.join('?' for _ in etf_ids)
                             query_sample = f"""
                             SELECT * FROM {t}
                             WHERE asset_id IN ({placeholders})
                             LIMIT 5
                             """
                             print("Sample data for ETFs:")
                             print(pd.read_sql(query_sample, conn, params=etf_ids))
                             
                             # Count non-nulls
                             col_checks = ", ".join([f"COUNT({c}) as {c}_count" for c in pe_like])
                             count_query = f"""
                             SELECT {col_checks}
                             FROM {t} t
                             JOIN asset_classification c ON t.asset_id = c.asset_id
                             WHERE c.sub_category LIKE '%ETF%'
                             """
                             print("Non-null counts for ETFs:")
                             print(pd.read_sql(count_query, conn))
                        else:
                            print("No ETFs found to check against.")

            except Exception as e:
                print(f"Error checking {t}: {e}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_alternative_tables()
