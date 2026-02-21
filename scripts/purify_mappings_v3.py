import sqlite3

DB_PATH = "vera.db"

def populate_clean_mappings():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Clear existing map to start fresh (Standardized & Purified)
    cursor.execute("DELETE FROM sector_proxy_map")
    
    # Base Data for All Markets (GICS Scheme)
    # Format: (scheme, sector_code, sector_name, proxy_etf_id, market_index_id, market, note)
    mappings = [
        # --- US Market (SPX) ---
        ('GICS', '10', 'Energy', 'XLE', 'SPX', 'US', 'US Energy'),
        ('GICS', '15', 'Materials', 'XLB', 'SPX', 'US', 'US Materials'),
        ('GICS', '20', 'Industrials', 'XLI', 'SPX', 'US', 'US Industrials'),
        ('GICS', '25', 'Consumer Discretionary', 'XLY', 'SPX', 'US', 'US Consumer Disc'),
        ('GICS', '30', 'Consumer Staples', 'XLP', 'SPX', 'US', 'US Consumer Staples'),
        ('GICS', '35', 'Health Care', 'XLV', 'SPX', 'US', 'US Health Care'),
        ('GICS', '40', 'Financials', 'XLF', 'SPX', 'US', 'US Financials'),
        ('GICS', '45', 'Information Technology', 'XLK', 'SPX', 'US', 'US Tech'),
        ('GICS', '50', 'Communication Services', 'XLC', 'SPX', 'US', 'US Comm'),
        ('GICS', '55', 'Utilities', 'XLU', 'SPX', 'US', 'US Utilities'),
        ('GICS', '60', 'Real Estate', 'XLRE', 'SPX', 'US', 'US Real Estate'),
        
        # --- CN Market (A-shares) ---
        ('GICS', '40', 'Financials', 'CN:STOCK:512800', 'CN:INDEX:000300', 'CN', 'CN Banks'),
        ('GICS', '45', 'Information Technology', 'CN:STOCK:159852', 'CN:INDEX:000905', 'CN', 'CN Software'),
        ('GICS', '15', 'Materials', 'CN:STOCK:516020', 'CN:INDEX:000016', 'CN', 'CN Chemicals'),
        ('GICS', '20', 'Industrials', 'CN:STOCK:159662', 'CN:INDEX:000016', 'CN', 'CN Transport'),
        ('GICS', '40', 'Securities', 'CN:STOCK:512880', 'CN:INDEX:000300', 'CN', 'CN Securities'),
        ('GICS', '40', 'Fintech', 'CN:STOCK:159851', 'CN:INDEX:000905', 'CN', 'CN Fintech'),
        
        # --- HK Market (HSI/HSTECH) ---
        ('GICS', '40', 'Financials', 'HK:STOCK:02800', 'HSI', 'HK', 'HK Blue Chip Proxy'),
        ('HK_USER', 'HK_BLUE', 'HK Blue Chips', 'HK:STOCK:02800', 'HSI', 'HK', 'HSI Benchmark'),
        ('HK_USER', 'HK_TECH', 'HK Tech Leaders', 'HK:STOCK:03033', 'HSTECH', 'HK', 'HSTECH Benchmark'),
        # Add GICS 50/45 for HK to ensure coverage
        ('GICS', '50', 'Communication Services', 'HK:STOCK:03033', 'HSTECH', 'HK', 'HK Tech Proxy'),
        ('GICS', '45', 'Information Technology', 'HK:STOCK:03033', 'HSTECH', 'HK', 'HK Tech Proxy'),
    ]
    
    cursor.executemany("""
        INSERT INTO sector_proxy_map (scheme, sector_code, sector_name, proxy_etf_id, market_index_id, market, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, mappings)
    
    # 2. Fix names and markets in Assets table
    # We use a comprehensive update
    assets_updates = [
        ('HK:STOCK:01919', '中远海控 (HK)', 'HK'),
        ('HK:STOCK:00998', '中信银行 (HK)', 'HK'),
        ('HK:STOCK:00700', '腾讯控股', 'HK'),
        ('HK:STOCK:00005', '汇丰控股', 'HK'),
        ('HK:STOCK:09988', '阿里巴巴', 'HK'),
        ('CN:STOCK:600536', '中国软件', 'CN'),
        ('CN:STOCK:601919', '中远海控', 'CN'),
        ('CN:STOCK:600030', '中信证券', 'CN'),
        ('CN:STOCK:601998', '中信银行', 'CN'),
        ('SPX', '标普500', 'US'),
        ('HSI', '恒生指数', 'HK'),
        ('HSTECH', '恒生科技', 'HK')
    ]
    for aid, name, mkt in assets_updates:
        cursor.execute("UPDATE assets SET symbol_name = ?, market = ? WHERE asset_id = ?", (name, mkt, aid))
        
    conn.commit()
    conn.close()
    print("Mapping Purification & Naming Fix Success.")

if __name__ == "__main__":
    populate_clean_mappings()
