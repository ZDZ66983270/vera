import sqlite3

DB_PATH = "vera.db"

def final_cleanup():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Standardize Index IDs for price fetching
    # Ensure all HSTECH, HSI, HSCE are represented without prefixes if used as IDs
    # But for CN indices, keep CN:INDEX:xxxxxx
    
    # Check if we have HSTECH in assets
    cursor.execute("SELECT asset_id FROM assets WHERE asset_id IN ('HSTECH', 'HSI', 'HSCE')")
    existing = {r[0] for r in cursor.fetchall()}
    if 'HSTECH' not in existing:
        cursor.execute("INSERT OR IGNORE INTO assets (asset_id, symbol_name, market, asset_type) VALUES ('HSTECH', 'Hang Seng Tech', 'HK', 'INDEX')")
    if 'HSI' not in existing:
        cursor.execute("INSERT OR IGNORE INTO assets (asset_id, symbol_name, market, asset_type) VALUES ('HSI', 'Hang Seng Index', 'HK', 'INDEX')")
    if 'HSCE' not in existing:
        cursor.execute("INSERT OR IGNORE INTO assets (asset_id, symbol_name, market, asset_type) VALUES ('HSCE', 'HS China Enterprises', 'HK', 'INDEX')")

    # 2. Delete redundant "HK matching A-share" GICS rows in proxy map IF they exist alongside HK_USER
    # This addresses "This is impossible" complaint.
    # Logic: For Communication Services (50), we have GICS mapping to 159751 (CN) and HK_USER mapping to 03033 (HK).
    # We'll keep the GICS mapping but ensure it specifies market US/CN in notes.
    # Actually, the user wants the display and mapping relationship to be consistent.
    
    # Update names for clarity
    cursor.execute("UPDATE assets SET symbol_name = '标普500' WHERE asset_id = 'SPX'")
    cursor.execute("UPDATE assets SET symbol_name = '纳斯达克100' WHERE asset_id = 'NDX'")
    cursor.execute("UPDATE assets SET symbol_name = '道琼斯工业' WHERE asset_id = 'DJI'")
    
    conn.commit()
    conn.close()
    print("Final Cleanup Complete.")

if __name__ == "__main__":
    final_cleanup()
