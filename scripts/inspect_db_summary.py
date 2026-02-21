import sqlite3
import pandas as pd

def main():
    db_path = "vera.db"
    conn = sqlite3.connect(db_path)
    
    # 1. Total Count
    try:
        total = conn.execute("SELECT COUNT(*) FROM vera_price_cache").fetchone()[0]
        print(f"📊 **Total Records in Price Cache**: {total:,}\n")
    except Exception as e:
        print(f"Error counting records: {e}")
        return

    # 2. Detailed Breakdown
    query = """
    WITH LatestPrices AS (
        SELECT 
            symbol, 
            trade_date, 
            close,
            ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY trade_date DESC) as rn,
            COUNT(*) OVER (PARTITION BY symbol) as cnt,
            MIN(trade_date) OVER (PARTITION BY symbol) as start_date
        FROM vera_price_cache
    )
    SELECT 
        lp.symbol as "Symbol",
        COALESCE(a.asset_type, 'Unknown') as "Type",
        COALESCE(a.symbol_name, '-') as "Name",
        lp.trade_date as "Latest Date",
        lp.close as "Latest Close",
        lp.cnt as "Count",
        lp.start_date as "Start Date"
    FROM LatestPrices lp
    LEFT JOIN assets a ON lp.symbol = a.asset_id
    WHERE lp.rn = 1
    ORDER BY "Type", "Symbol"
    """
    
    try:
        df = pd.read_sql(query, conn)
        # Format close price
        df["Latest Close"] = df["Latest Close"].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "-")
        
        print("### 📋 Asset Details (Latest Snapshot)")
        print(df.to_markdown(index=False))
    except Exception as e:
        print(f"Error querying details: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
