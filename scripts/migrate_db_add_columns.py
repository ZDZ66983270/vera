import sqlite3

def migrate():
    conn = sqlite3.connect('vera.db')
    cursor = conn.cursor()
    
    cols_to_add = [
        "common_equity_begin REAL",
        "common_equity_end REAL",
        "shares_outstanding REAL",
        "shares_diluted REAL",
        "treasury_shares REAL",
        "dividends_paid REAL",
        "dps REAL",
        "operating_cashflow REAL",
        "cash_and_equivalents REAL",
        "total_debt REAL"
    ]
    
    print("🚀 Starting Schema Migration...")
    
    for col_def in cols_to_add:
        try:
            sql = f"ALTER TABLE financial_history ADD COLUMN {col_def}"
            cursor.execute(sql)
            print(f"✅ Added column: {col_def}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"ℹ️  Column exists, skipping: {col_def}")
            else:
                print(f"❌ Error adding {col_def}: {e}")
                
    conn.commit()
    conn.close()
    print("✨ Migration Finished.")

if __name__ == "__main__":
    migrate()
