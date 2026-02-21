import sys
import os
import sqlite3

# Add project root to path
sys.path.append(os.getcwd())

try:
    from db.connection import get_db_path
    DB_PATH = get_db_path()
except ImportError:
    # Fallback
    DB_PATH = "metrics/vera.db" if os.path.exists("metrics/vera.db") else "vera.db"

def migrate():
    print(f"Migrating database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Columns to add
    # Name -> Type
    new_cols = {
        "net_interest_income": "REAL",
        "net_fee_income": "REAL",
        "provision_expense": "REAL",
        "total_loans": "REAL",
        # "npl_loans": "REAL", # Using existing npl_balance
        "loan_loss_allowance": "REAL",
        "core_tier1_capital_ratio": "REAL",
        "operating_profit": "REAL",
        "operating_cash_flow": "REAL",
        "return_on_invested_capital": "REAL",
        "gross_margin": "REAL"
    }
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(financial_history)")
    existing = {row[1] for row in cursor.fetchall()}
    
    added_count = 0
    for col, dtype in new_cols.items():
        if col not in existing:
            try:
                print(f"Adding column {col} ({dtype})...")
                cursor.execute(f"ALTER TABLE financial_history ADD COLUMN {col} {dtype}")
                added_count += 1
            except Exception as e:
                print(f"Error adding {col}: {e}")
        else:
            print(f"Column {col} already exists.")
            
    conn.commit()
    conn.close()
    print(f"Migration complete. Added {added_count} columns.")

if __name__ == "__main__":
    migrate()
