
import sqlite3
import pandas as pd
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_connection

def export_financial_history():
    conn = get_connection()
    
    print("Exporting financial_history to CSV...")
    
    try:
        # Read the entire table
        df = pd.read_sql_query("SELECT * FROM financial_history", conn)
        
        # Define output path
        output_path = "financial_history_export.csv"
        
        # Save to CSV
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        print(f"Successfully exported {len(df)} rows to {output_path}")
        
    except Exception as e:
        print(f"Error during export: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    export_financial_history()
