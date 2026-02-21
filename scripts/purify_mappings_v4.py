import sqlite3

DB_PATH = "vera.db"

def comprehensive_mappings_v4():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Clear existing map
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
        ('GICS', '4520', 'Software', 'CN:STOCK:159852', 'CN:INDEX:000905', 'CN', 'CN Software Sub'),
        ('GICS', 'FIN', 'Fintech', 'CN:STOCK:159851', 'CN:INDEX:000905', 'CN', 'CN Fintech'),
        ('GICS', 'SEC', 'Securities', 'CN:STOCK:512880', 'CN:INDEX:000300', 'CN', 'CN Securities'),
        
        # --- HK Market (HSI/HSTECH) ---
        ('GICS', '40', 'Financials', 'HK:STOCK:02800', 'HSI', 'HK', 'HK Financials Fallback'),
        ('GICS', '50', 'Communication Services', 'HK:STOCK:03033', 'HSTECH', 'HK', 'HK Tech Proxy'),
        ('GICS', '45', 'Information Technology', 'HK:STOCK:03033', 'HSTECH', 'HK', 'HK Tech Proxy'),
        ('GICS', '20', 'Industrials', 'HK:STOCK:02800', 'HSI', 'HK', 'HK Industrials Fallback'),
        ('GICS', '25', 'Consumer Discretionary', 'HK:STOCK:03033', 'HSTECH', 'HK', 'HK Consumer Disc (Alibaba)'),
        
        # User Specific Schemes (High Priority)
        ('HK_USER', 'HK_BLUE', 'HK Blue Chips', 'HK:STOCK:02800', 'HSI', 'HK', 'HSI Benchmark'),
        ('HK_USER', 'HK_TECH', 'HK Tech Leaders', 'HK:STOCK:03033', 'HSTECH', 'HK', 'HSTECH Benchmark'),
    ]
    
    cursor.executemany("""
        INSERT INTO sector_proxy_map (scheme, sector_code, sector_name, proxy_etf_id, market_index_id, market, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, mappings)
    
    # 2. Add missing sector codes to asset_classification for CN Securities/Fintech if they are generic Financials (40)
    # We'll map them more specifically based on names
    cursor.execute("UPDATE asset_classification SET sector_code='SEC', sector_name='Securities' WHERE asset_id='CN:STOCK:600030'")
    cursor.execute("UPDATE asset_classification SET sector_code='FIN', sector_name='Fintech' WHERE asset_id='CN:STOCK:601519'")

    # 3. Final Name cleanup
    cursor.execute("UPDATE assets SET symbol_name = '中信银行 (00998)' WHERE asset_id = 'HK:STOCK:00998'")
    cursor.execute("UPDATE assets SET symbol_name = '中远海控 (01919)' WHERE asset_id = 'HK:STOCK:01919'")
    
    conn.commit()
    conn.close()
    print("Mapping v4 Success.")

if __name__ == "__main__":
    comprehensive_mappings_v4()
