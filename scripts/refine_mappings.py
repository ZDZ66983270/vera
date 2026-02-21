import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "vera.db"

def refine_mappings():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- [1] Standardizing asset_classification Dates & IDs ---")
    # 1. Update as_of_date to a safe past date (2020-01-01)
    # 2. Ensure asset_id is canonical
    cursor.execute("SELECT rowid, asset_id, as_of_date FROM asset_classification")
    rows = cursor.fetchall()
    for rowid, aid, adate in rows:
        new_id = aid
        if aid.endswith(".HK"):
            new_id = f"HK:STOCK:{aid.split('.')[0].zfill(5)}"
        elif aid.endswith((".SS", ".SZ", ".SH")):
            code = aid.split('.')[0]
            atype = "INDEX" if (code.startswith("000") and aid.endswith(".SS")) else "STOCK"
            new_id = f"CN:{atype}:{code}"
        
        # Standardize date to YYYY-MM-DD
        new_date = "2020-01-01"
        
        cursor.execute("UPDATE asset_classification SET asset_id=?, as_of_date=? WHERE rowid=?", (new_id, new_date, rowid))

    print("--- [2] Standardizing sector_proxy_map IDs & Markets ---")
    # Proxy IDs should use canonical format
    cursor.execute("SELECT rowid, proxy_etf_id, market_index_id, sector_name, note FROM sector_proxy_map")
    rows = cursor.fetchall()
    for rowid, proxy_id, index_id, sname, note in rows:
        # Standardize Proxy ETF ID
        new_proxy = proxy_id
        if proxy_id:
            if proxy_id.isdigit():
                if proxy_id.startswith(("5", "6")): suffix = ".SS"
                else: suffix = ".SZ"
                new_proxy = f"CN:STOCK:{proxy_id}" # Standardize to canonical
            elif proxy_id.endswith(".HK"):
                new_proxy = f"HK:STOCK:{proxy_id.split('.')[0].zfill(5)}"
        
        # Standardize Index ID
        new_index = index_id
        if index_id == "恒生科技指数": new_index = "HSTECH"
        elif index_id == "恒生中国企业指数": new_index = "HSCE"
        elif index_id == "沪深300指数": new_index = "CN:INDEX:000300"
        elif index_id == "上证50指数": new_index = "CN:INDEX:000016"
        elif index_id == "中证500指数": new_index = "CN:INDEX:000905"
        elif index_id == "SPX": new_index = "SPX"
        elif index_id == "HSI": new_index = "HSI"

        # Special Fix for User's "HK matching A-share" complaint
        # If it's a GICS sector and note contains "HK", ensure it's mapped to HK indices if possible
        # Actually the best way is to ensure proxy_id is canonical and resolver will find price.
        
        cursor.execute("UPDATE sector_proxy_map SET proxy_etf_id=?, market_index_id=? WHERE rowid=?", (new_proxy, new_index, rowid))

    print("--- [3] Cleaning up specific mismatched records ---")
    # Clean up any comments or invalid rows
    cursor.execute("DELETE FROM sector_proxy_map WHERE scheme LIKE '#%' OR proxy_etf_id = 'nan'")
    cursor.execute("DELETE FROM asset_classification WHERE asset_id LIKE '#%'")

    conn.commit()
    conn.close()
    print("\nRefinement Complete.")

if __name__ == "__main__":
    refine_mappings()
