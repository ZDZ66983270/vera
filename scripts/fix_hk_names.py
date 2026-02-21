import sqlite3

DB_PATH = "vera.db"

def final_hk_name_fix():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Precise map for HK assets that were missing names
    updates = [
        ("HK:STOCK:00700", "腾讯控股"),
        ("HK:STOCK:00005", "汇丰控股"),
        ("HK:STOCK:00998", "中信银行 (00998)"),
        ("HK:STOCK:01919", "中远海控 (01919)"),
        ("HK:STOCK:09988", "阿里巴巴"),
        ("HK:STOCK:02800", "盈富基金"),
        ("HK:STOCK:03033", "南方恒生科技")
    ]
    
    for aid, name in updates:
        cursor.execute("UPDATE assets SET symbol_name = ? WHERE asset_id = ?", (name, aid))
        print(f"Updated {aid} to {name}")
        
    conn.commit()
    conn.close()
    print("Database HK Names Fixed.")

if __name__ == "__main__":
    final_hk_name_fix()
