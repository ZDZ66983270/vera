
import sqlite3
import pandas as pd

DB_PATH = "data/stock_analyzer.db"

def verify_app_query():
    conn = sqlite3.connect(DB_PATH)
    try:
        query = """
        WITH latest_snapshots AS (
            SELECT 
                s.asset_id,
                s.as_of_date,
                s.created_at,
                s.valuation_status,
                s.risk_level,
                a.name as symbol_name,
                ROW_NUMBER() OVER (PARTITION BY s.asset_id ORDER BY s.created_at DESC) as rn
            FROM analysis_snapshot s
            JOIN assets a ON s.asset_id = a.id
        )
        SELECT asset_id, symbol_name, as_of_date, created_at, valuation_status, risk_level
        FROM latest_snapshots
        WHERE rn = 1
        ORDER BY created_at DESC
        """
        print("Executing app.py query...")
        df = pd.read_sql(query, conn)
        print("Query successful!")
        print(df.head())
    except Exception as e:
        print(f"Query failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_app_query()
