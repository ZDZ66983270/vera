import sqlite3
import sys
import os

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH

def clear_tables():
    print(f"Connecting to database at {DB_PATH}...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return

    # Tables to clear
    tables_to_clear = [
        "vera_price_cache",
        "drawdown_state_history",
        "risk_events",
        "financial_history",
        "fundamentals_facts",
        "vera_snapshot",
        "analysis_snapshot",
        "metric_details",
        "vera_risk_metrics",
        "risk_card_snapshot",
        "behavior_flags",
        "decision_log"
    ]

    # Tables to preserve (for verification)
    tables_to_preserve = [
        "assets",
        "user_risk_profiles"
    ]

    print("\n--- Pre-Cleanup Status ---")
    for table in tables_to_clear + tables_to_preserve:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table}: {count} rows")
        except sqlite3.OperationalError:
            print(f"{table}: (Table not found or error)")

    print("\n--- Executing Cleanup ---")
    for table in tables_to_clear:
        try:
            print(f"Clearing {table}...")
            cursor.execute(f"DELETE FROM {table}")
        except sqlite3.OperationalError as e:
            print(f"Error clearing {table}: {e}")
            
    conn.commit()
    print("Cleanup committed.")

    print("\n--- Post-Cleanup Status ---")
    all_cleared = True
    for table in tables_to_clear:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table}: {count} rows")
            if count > 0:
                all_cleared = False
        except sqlite3.OperationalError:
            pass # Ignore if table doesn't exist

    print("\n--- Verification of Preserved Tables ---")
    for table in tables_to_preserve:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"{table}: {count} rows")
        except sqlite3.OperationalError:
            print(f"{table}: (Table not found)")

    conn.close()
    
    if all_cleared:
        print("\nSUCCESS: All specified tables cleared successfully.")
    else:
        print("\nWARNING: Some tables were not fully cleared.")

if __name__ == "__main__":
    confirm = input("Are you sure you want to clear these tables? This cannot be undone. (yes/no): ")
    if confirm.lower() == "yes":
        clear_tables()
    else:
        print("Operation cancelled.")
