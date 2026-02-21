
import pandas as pd
from db.connection import get_connection

def inspect_financial_years():
    conn = get_connection()
    
    print("\n--- 1. Financial History (Legacy/OCR) ---")
    try:
        df_hist = pd.read_sql("""
            SELECT asset_id, count(DISTINCT strftime('%Y', report_date)) as year_count, 
                   min(report_date) as start_date, max(report_date) as end_date
            FROM financial_history
            GROUP BY asset_id
            ORDER BY year_count DESC
        """, conn)
        if not df_hist.empty:
            print(df_hist.to_string())
        else:
            print("No records found.")
    except Exception as e:
        print(f"Error querying financial_history: {e}")

    print("\n\n--- 2. Financial Fundamentals (Detailed Annual) ---")
    try:
        df_fund = pd.read_sql("""
            SELECT asset_id, count(DISTINCT strftime('%Y', as_of_date)) as year_count,
                   min(as_of_date) as start_date, max(as_of_date) as end_date
            FROM financial_fundamentals
            GROUP BY asset_id
            ORDER BY year_count DESC
        """, conn)
        if not df_fund.empty:
            print(df_fund.to_string())
        else:
            print("No records found.")
    except Exception as e:
        print(f"Error querying financial_fundamentals: {e}")

    print("\n\n--- 3. Fundamentals Facts (New Standardized) ---")
    try:
        df_facts = pd.read_sql("""
            SELECT asset_id, count(DISTINCT strftime('%Y', as_of_date)) as year_count,
                   min(as_of_date) as start_date, max(as_of_date) as end_date
            FROM fundamentals_facts
            GROUP BY asset_id
            ORDER BY year_count DESC
        """, conn)
        if not df_facts.empty:
            print(df_facts.to_string())
        else:
            print("No records found.")
    except Exception as e:
        print(f"Error querying fundamentals_facts: {e}")

    conn.close()

if __name__ == "__main__":
    inspect_financial_years()
