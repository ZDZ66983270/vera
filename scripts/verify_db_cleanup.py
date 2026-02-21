import sqlite3
import os

DB_PATH = 'vera.db'

TABLES_TO_CLEAR = [
    'vera_price_cache', 'vera_snapshot', 'vera_risk_metrics',
    'financial_history', 'fundamentals_annual', 'fundamentals_facts',
    'analysis_snapshot', 'risk_card_snapshot', 'risk_overlay_snapshot',
    'market_risk_snapshot', 'sector_risk_snapshot', 'drawdown_state_history',
    'risk_events', 'behavior_flags', 'decision_log', 'metric_details', 'quality_snapshot'
]

TABLES_TO_PRESERVE = [
    'assets', 'asset_symbol_map', 'symbol_alias', 'asset_sector_map',
    'asset_classification', 'asset_universe', 'sector_proxy_map', 'user_risk_profiles'
]

def verify():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print(f"Verifying database state for {DB_PATH}...\n")
    
    all_passed = True

    print("--- Tables that should be EMPTY ---")
    for table in TABLES_TO_CLEAR:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            status = "PASS" if count == 0 else "FAIL"
            print(f"[{status}] {table:<25}: {count} rows")
            if count > 0:
                all_passed = False
        except sqlite3.OperationalError:
            print(f"[SKIP] {table:<25}: Table does not exist")

    print("\n--- Tables that should be PRESERVED ---")
    for table in TABLES_TO_PRESERVE:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            status = "PASS" if count > 0 else "INFO (Empty but preserved)"
            print(f"[{status}] {table:<25}: {count} rows")
        except sqlite3.OperationalError:
            print(f"[FAIL] {table:<25}: Table missing!")
            all_passed = False

    conn.close()
    
    if all_passed:
        print("\n✅ Verification SUCCESS: Market and financial data cleared, assets preserved.")
    else:
        print("\n❌ Verification FAILED: Some data remains or preserved tables are missing.")

if __name__ == "__main__":
    verify()
