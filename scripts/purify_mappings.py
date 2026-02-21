import sqlite3

DB_PATH = "vera.db"

def purify_mappings():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Clean up sector_proxy_map to ensure market consistency
    # Strategy: 
    # - If proxy_etf_id is HK:STOCK:xxxxxx, it's for HK market.
    # - If proxy_etf_id is CN:STOCK:xxxxxx, it's for CN market.
    # - If proxy_etf_id is US Ticker (no prefix), it's for US market.
    
    # Actually, we can just delete the "impossible" ones.
    # Case 1: GICS Communication Services in HK matching CN ETF
    # We want to keep GICS for other things but not for HK stocks if it's matching A-shares.
    
    cursor.execute("SELECT rowid, scheme, sector_code, proxy_etf_id, note FROM sector_proxy_map")
    rows = cursor.fetchall()
    for rowid, scheme, scode, pid, note in rows:
        if not pid: continue
        
        # Heuristic: If note mentions HK and ETF is CN:STOCK, or vice versa
        is_cn_etf = pid.startswith("CN:")
        is_hk_etf = pid.startswith("HK:") or pid.endswith(".HK")
        is_us_etf = not (is_cn_etf or is_hk_etf)
        
        lower_note = str(note).lower()
        if "hk " in lower_note and is_cn_etf:
            print(f"Deleting cross-market mapping: {scheme}|{scode}|{pid} ({note})")
            cursor.execute("DELETE FROM sector_proxy_map WHERE rowid = ?", (rowid,))
        elif "cn " in lower_note and is_hk_etf:
            print(f"Deleting cross-market mapping: {scheme}|{scode}|{pid} ({note})")
            cursor.execute("DELETE FROM sector_proxy_map WHERE rowid = ?", (rowid,))
        elif "us " in lower_note and (is_cn_etf or is_hk_etf):
            print(f"Deleting cross-market mapping: {scheme}|{scode}|{pid} ({note})")
            cursor.execute("DELETE FROM sector_proxy_map WHERE rowid = ?", (rowid,))

    # 2. Add missing HK sector proxies if needed
    # (Optional, but let's just make the existing ones correct)
    
    conn.commit()
    conn.close()
    print("Purification Complete.")

if __name__ == "__main__":
    purify_mappings()
