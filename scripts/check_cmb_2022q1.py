import sqlite3
import pandas as pd

def check_cmb_data():
    conn = sqlite3.connect('vera.db')
    
    # Target Asset and Date
    asset_id = "CN:STOCK:600036"
    report_date = "2022-03-31"
    
    print(f"🔍 Checking Data for {asset_id} @ {report_date}...")
    
    query = f"""
    SELECT *
    FROM financial_history 
    WHERE asset_id = '{asset_id}' AND report_date = '{report_date}'
    """
    
    df = pd.read_sql_query(query, conn)
    
    if df.empty:
        print("❌ No record found!")
    else:
        print("✅ Record found:")
        # Transpose for easier reading of many columns
        print(df.T.to_string())
        
    conn.close()

if __name__ == "__main__":
    check_cmb_data()
