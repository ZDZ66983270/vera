
import sqlite3
import os

def migrate_banking_columns():
    db_path = "/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/vera.db"
    if not os.path.exists(db_path):
        print("Database not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables = ["financial_history", "financial_fundamentals"]
    new_cols = [
        ("tier1_capital_ratio", "REAL"),
        ("capital_adequacy_ratio", "REAL")
    ]

    for table in tables:
        # Check existing columns
        cursor.execute(f"PRAGMA table_info({table})")
        existing_cols = [r[1] for r in cursor.fetchall()]
        
        for col_name, col_type in new_cols:
            if col_name not in existing_cols:
                print(f"Adding {col_name} to {table}...")
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")

    conn.commit()
    conn.close()
    print("Migration finished.")

if __name__ == "__main__":
    migrate_banking_columns()
