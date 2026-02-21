
from datetime import datetime
from data.fetch_fundamentals import fetch_fundamentals
from db.connection import get_connection

def debug_tsla():
    symbol = "TSLA"
    # match the date used in app: 2025-12-29
    as_of_date = datetime(2025, 12, 29)
    
    print(f"Fetching fundamentals for {symbol} as of {as_of_date}...")
    fund, bank = fetch_fundamentals(symbol, as_of_date)
    
    print("\n--- Result ---")
    print(f"PE TTM: {fund.pe_ttm}")
    print(f"EPS seems to be used: {fund.net_profit_ttm} (maybe not directly visible)")
    print(f"Full Fundamentals: {fund}")

    # Check DB manually
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM financial_history WHERE asset_id='TSLA' ORDER BY report_date DESC LIMIT 1").fetchone()
    print("\n--- DB Latest Row ---")
    if row:
        print(dict(row))
    else:
        print("No DB row found")
        
    date_row = cur.execute("SELECT * FROM financial_history WHERE asset_id='TSLA' AND report_date <= '2025-12-29' ORDER BY report_date DESC LIMIT 1").fetchone()
    print("\n--- DB Query Matching Row ---")
    if date_row:
        print(dict(date_row))
    else:
        print("No matching record found for <= 2025-12-29")
    conn.close()

if __name__ == "__main__":
    debug_tsla()
