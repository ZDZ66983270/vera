import sqlite3

def debug_join():
    conn = sqlite3.connect("vera.db")
    cursor = conn.cursor()
    
    asset_id = "MSFT"
    as_of_date = "2025-12-24"
    
    print(f"Testing join for {asset_id} at {as_of_date}")
    
    query = """
    SELECT 
        ac.sector_code, 
        ac.sector_name,
        sp.proxy_etf_id
    FROM asset_classification ac
    LEFT JOIN sector_proxy_map sp 
           ON ac.scheme = sp.scheme 
          AND ac.sector_code = sp.sector_code
          AND sp.is_active = 1
    WHERE ac.asset_id = ? 
      AND ac.as_of_date <= ?
      AND ac.is_active = 1
    ORDER BY ac.as_of_date DESC, ac.scheme DESC
    LIMIT 1
    """
    
    row = cursor.execute(query, (asset_id, as_of_date)).fetchone()
    print(f"Result: {row}")
    
    # Check individual records
    print("\n--- Asset Classification ---")
    ac = cursor.execute("SELECT * FROM asset_classification WHERE asset_id=?", (asset_id,)).fetchall()
    print(ac)
    
    print("\n--- Sector Proxy ---")
    sp = cursor.execute("SELECT * FROM sector_proxy_map WHERE scheme='GICS' AND sector_code='45'").fetchall()
    print(sp)
    
    conn.close()

if __name__ == "__main__":
    debug_join()
