import sqlite3

DB_PATH = "vera.db"

def final_nuclear_fix():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- [1] Forcing Asset Names ---")
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
    }
    for aid, name in names.items():
        cursor.execute("UPDATE assets SET symbol_name = ? WHERE asset_id = ?", (name, aid))

    print("--- [2] Standardizing Classification Schemes ---")
    # Mapping legacy/custom schemes to GICS for universal sector mapping
    cursor.execute("UPDATE asset_classification SET scheme = 'GICS' WHERE scheme IN ('GICS_CUSTOM', 'GICS_CORE', 'GICS_V2')")
    # For HK USER schemes, keep them but ensure they exist in proxy map
    cursor.execute("UPDATE asset_classification SET scheme = 'HK_USER' WHERE scheme = 'HK_STRATEGY'")

    print("--- [3] Ensuring Sector Proxy Map is Bulletproof ---")
    # Ensure we have common GICS codes mapped for HK
    # 40 (Financials), 50 (Comm), 45 (IT), 25 (Consumer), 20 (Industrials), 15 (Materials)
    hk_proxies = [
        ('GICS', '40', 'Financials', 'HK:STOCK:02800', 'HSI', 'HK', 'HK Financials'),
        ('GICS', '50', 'Communication Services', 'HK:STOCK:03033', 'HSTECH', 'HK', 'HK Tech'),
        ('GICS', '45', 'Information Technology', 'HK:STOCK:03033', 'HSTECH', 'HK', 'HK Tech'),
        ('GICS', '25', 'Consumer Discretionary', 'HK:STOCK:03033', 'HSTECH', 'HK', 'HK Consumer'),
        ('GICS', '20', 'Industrials', 'HK:STOCK:02800', 'HSI', 'HK', 'HK Industrials'),
        ('GICS', '15', 'Materials', 'HK:STOCK:02800', 'HSI', 'HK', 'HK Materials'),
    ]
    for p in hk_proxies:
        cursor.execute("""
            INSERT OR REPLACE INTO sector_proxy_map (scheme, sector_code, sector_name, proxy_etf_id, market_index_id, market, note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, p)

    conn.commit()
    conn.close()
    print("Nuclear Fix Complete.")

if __name__ == "__main__":
    final_nuclear_fix()
