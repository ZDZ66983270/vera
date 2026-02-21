import sqlite3

DB_PATH = "vera.db"

def titan_fix():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- [1] Forcing Asset Names (Final) ---")
    names = {
        "HK:STOCK:00700": "腾讯控股",
        "HK:STOCK:00005": "汇丰控股",
        "HK:STOCK:00998": "中信银行 (00998)",
        "HK:STOCK:01919": "中远海控 (01919)",
        "HK:STOCK:09988": "阿里巴巴",
        "HK:STOCK:02800": "盈富基金",
        "HK:STOCK:03033": "南方恒生科技",
        "CN:STOCK:600536": "中国软件",
        "CN:STOCK:601919": "中远海控",
        "CN:STOCK:600030": "中信证券",
        "CN:STOCK:601998": "中信银行",
        "CN:STOCK:600309": "万华化学",
        "CN:STOCK:601519": "大智慧",
        "SPX": "标普500",
        "HSI": "恒生指数",
        "HSTECH": "恒生科技",
        "HSCE": "国企指数"
    }
    
    for aid, name in names.items():
        # Update assets table
        cursor.execute("UPDATE assets SET symbol_name = ? WHERE asset_id = ?", (name, aid))
        
        # Verify immediately
        cursor.execute("SELECT symbol_name FROM assets WHERE asset_id = ?", (aid,))
        actual = cursor.fetchone()
        if actual and actual[0] == name:
            print(f"Verified {aid} -> {name}")
        else:
            print(f"FAILED to verify {aid}. Actual: {actual}")

    print("--- [2] Standardizing Classification to GICS ---")
    cursor.execute("UPDATE asset_classification SET scheme = 'GICS' WHERE scheme LIKE 'GICS%'")
    
    print("--- [3] Purifying Sector Proxy Map ---")
    # Add market column if not exists (already exists but just in case)
    try:
        cursor.execute("ALTER TABLE sector_proxy_map ADD COLUMN market TEXT")
    except:
        pass
        
    cursor.execute("UPDATE assets SET market = 'HK' WHERE asset_id LIKE 'HK:%'")

    conn.commit()
    conn.close()
    print("Titan Fix Execution Finished.")

if __name__ == "__main__":
    titan_fix()
