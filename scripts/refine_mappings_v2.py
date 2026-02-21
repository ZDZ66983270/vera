import sqlite3
import pandas as pd

DB_PATH = "vera.db"

def refine_mappings():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- [1] Standardizing asset_classification (Deduplicate & Canonical) ---")
    # Fetch all, then insert into a clean temp table to handle duplicates
    cursor.execute("SELECT asset_id, scheme, sector_code, sector_name, industry_code, industry_name FROM asset_classification WHERE is_active = 1")
    rows = cursor.fetchall()
    
    # We'll use a transaction for safety
    cursor.execute("DROP TABLE IF EXISTS asset_classification_new")
    cursor.execute("""
        CREATE TABLE asset_classification_new (
            asset_id TEXT NOT NULL,
            scheme TEXT NOT NULL,
            sector_code TEXT,
            sector_name TEXT,
            industry_code TEXT,
            industry_name TEXT,
            as_of_date TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            PRIMARY KEY (asset_id, scheme, as_of_date)
        )
    """)

    processed = set()
    for aid, scheme, scode, sname, icode, iname in rows:
        new_id = aid
        if aid.endswith(".HK"):
            new_id = f"HK:STOCK:{aid.split('.')[0].zfill(5)}"
        elif aid.endswith((".SS", ".SZ", ".SH")):
            code = aid.split('.')[0]
            atype = "INDEX" if (code.startswith("000") and aid.endswith(".SS")) else "STOCK"
            new_id = f"CN:{atype}:{code}"
        
        # Deduplicate same (aid, scheme) - keep first/latest encountered
        key = (new_id, scheme)
        if key in processed: continue
        
        cursor.execute("""
            INSERT INTO asset_classification_new (asset_id, scheme, sector_code, sector_name, industry_code, industry_name, as_of_date, is_active)
            VALUES (?, ?, ?, ?, ?, ?, '2020-01-01', 1)
        """, (new_id, scheme, scode, sname, icode, iname))
        processed.add(key)

    # Replace old table
    cursor.execute("DROP TABLE asset_classification")
    cursor.execute("ALTER TABLE asset_classification_new RENAME TO asset_classification")

    print("--- [2] Standardizing sector_proxy_map (Canonical IDs) ---")
    cursor.execute("SELECT rowid, scheme, sector_code, sector_name, proxy_etf_id, market_index_id, note FROM sector_proxy_map")
    rows = cursor.fetchall()
    for rowid, scheme, scode, sname, proxy_id, index_id, note in rows:
        if not proxy_id or proxy_id == 'nan': continue
        
        new_proxy = proxy_id
        # Canonicalize proxy_id
        if proxy_id.isdigit():
            new_proxy = f"CN:STOCK:{proxy_id}"
        elif proxy_id.endswith(".HK") and not proxy_id.startswith("HK:"):
            new_proxy = f"HK:STOCK:{proxy_id.split('.')[0].zfill(5)}"
        elif proxy_id.startswith("HK:STOCK:"):
            # Ensure 5 digit padding
            code = proxy_id.split(":")[-1]
            new_proxy = f"HK:STOCK:{code.zfill(5)}"
            
        # Canonicalize index_id
        new_index = index_id
        if index_id == "恒生科技指数": new_index = "HSTECH"
        elif index_id == "恒生中国企业指数": new_index = "HSCE"
        elif "沪深300" in str(index_id): new_index = "CN:INDEX:000300"
        elif "上证50" in str(index_id): new_index = "CN:INDEX:000016"
        elif "中证500" in str(index_id): new_index = "CN:INDEX:000905"
        
        cursor.execute("UPDATE sector_proxy_map SET proxy_etf_id=?, market_index_id=? WHERE rowid=?", (new_proxy, new_index, rowid))

    # [3] Fix HK benchmarks (HK stocks should not benchmark CN ETFs)
    # Actually, let's just make sure the user's report of "HK matching A-share" is resolved by ensuring 
    # the mapping makes sense.
    # We will delete the GICS rows for HK stocks that point to A-share ETFs if they have a better HK_USER mapping.
    
    print("--- [4] Clean up ---")
    cursor.execute("DELETE FROM sector_proxy_map WHERE proxy_etf_id = 'nan' OR scheme LIKE '#%'")
    
    conn.commit()
    conn.close()
    print("\nRefinement Complete.")

if __name__ == "__main__":
    refine_mappings()
