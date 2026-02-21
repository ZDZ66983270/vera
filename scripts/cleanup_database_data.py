import sqlite3
import os

DB_PATH = 'vera.db'

# Tables to clear
TABLES_TO_CLEAR = [
    'vera_price_cache',
    'vera_snapshot',
    'vera_risk_metrics',
    'financial_history',
    'fundamentals_annual',
    'fundamentals_facts',
    'analysis_snapshot',
    'risk_card_snapshot',
    'risk_overlay_snapshot',
    'market_risk_snapshot',
    'sector_risk_snapshot',
    'drawdown_state_history',
    'risk_events',
    'behavior_flags',
    'decision_log',
    'metric_details',
    'quality_snapshot'
]

def cleanup():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"Starting database cleanup for {DB_PATH}...")

    try:
        # Disable foreign key constraints temporarily to allow truncation
        cursor.execute("PRAGMA foreign_keys = OFF;")

        for table in TABLES_TO_CLEAR:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count_before = cursor.fetchone()[0]
            
            cursor.execute(f"DELETE FROM {table}")
            
            print(f"Cleared table: {table:<25} (Rows deleted: {count_before})")

        conn.commit()
        
        # Vacuum the database to reclaim space
        print("Vacuuming database...")
        cursor.execute("PRAGMA foreign_keys = ON;") # Restore foreign keys
        cursor.execute("VACUUM")
        
        print("\nCleanup completed successfully.")

        
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    cleanup()
