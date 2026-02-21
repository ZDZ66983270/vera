import sqlite3
import os

DB_PATH = "vera.db"

def investigate():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"🔍 Investigating Raw Database Rows in: {DB_PATH}\n")

    # Codes to check
    search_codes = ['01211', '000001', '000300']

    print(f"{'Asset ID':<25} | {'Name':<15} | {'Type':<10} | {'Market':<5} | {'Created At'}")
    print("-" * 80)

    for code in search_codes:
        # Use LIKE to find anything containing the code
        query = f"SELECT asset_id, symbol_name, asset_type, market, created_at FROM assets WHERE asset_id LIKE '%{code}%'"
        cursor.execute(query)
        rows = cursor.fetchall()
        
        if rows:
            for row in rows:
                aid, name, atype, mkt, created = row
                print(f"{aid:<25} | {name:<15} | {atype:<10} | {mkt:<5} | {created}")
        else:
            print(f"No records found searching for *{code}*")

    print("\n")
    
    # Check total counts again just to be pedantic
    cursor.execute("SELECT COUNT(*) FROM assets")
    total = cursor.fetchone()[0]
    print(f"Total row count in 'assets' table: {total}")

    conn.close()

if __name__ == "__main__":
    investigate()
