import sqlite3

DB_PATH = "vera.db"

def fix_asset_classifications():
    """修复资产分类和市场归属"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("修复资产分类")
    print("=" * 80)
    
    fixes = {
        'asset_type_updates': [],
        'market_updates': []
    }
    
    # 1. Fix asset_type based on asset_id patterns
    print("\n[1] 修复 asset_type...")
    
    # ETFs
    etf_patterns = [
        ('2800.HK', 'etf'),
        ('3033.HK', 'etf'),
        ('DIA', 'etf'),
        ('GLD', 'etf'),
        ('IWM', 'etf'),
        ('QQQ', 'etf'),
        ('SPY', 'etf'),
        ('TLT', 'etf'),
        ('USMV', 'etf'),
        ('VTV', 'etf'),
        ('VUG', 'etf'),
        ('VYM', 'etf'),
        ('XLB', 'etf'),
        ('XLC', 'etf'),
        ('XLE', 'etf'),
        ('XLF', 'etf'),
        ('XLI', 'etf'),
        ('XLK', 'etf'),
        ('XLP', 'etf'),
        ('XLRE', 'etf'),
        ('XLU', 'etf'),
        ('XLV', 'etf'),
        ('XLY', 'etf'),
    ]
    
    for asset_id_pattern, asset_type in etf_patterns:
        cursor.execute("UPDATE assets SET asset_type = ? WHERE asset_id = ?", (asset_type, asset_id_pattern))
        if cursor.rowcount > 0:
            fixes['asset_type_updates'].append((asset_id_pattern, asset_type))
    
    # Update CN ETFs (contain 'ETF' or start with 159/512/513/516)
    cursor.execute("""
       UPDATE assets 
        SET asset_type = 'etf' 
        WHERE (asset_id LIKE 'CN:STOCK:159%' 
           OR asset_id LIKE 'CN:STOCK:512%' 
           OR asset_id LIKE 'CN:STOCK:513%'
           OR asset_id LIKE 'CN:STOCK:516%'
           OR symbol_name LIKE '%ETF%')
          AND asset_type != 'etf'
    """)
    
    etf_count = cursor.rowcount
    if etf_count > 0:
        print(f"  ✅ 更新了 {etf_count} 个 CN ETF")
    
    # Indices
    index_patterns = [
        ('^SPX', 'index'),
        ('^GSPC', 'index'),
        ('DJI', 'index'),
        ('NDX', 'index'),
        ('SPX', 'index'),
        ('HSI', 'index'),
        ('HSTECH', 'index'),
        ('HSCE', 'index'),
        ('HSCC', 'index'),
    ]
    
    for asset_id_pattern, asset_type in index_patterns:
        cursor.execute("UPDATE assets SET asset_type = ? WHERE asset_id LIKE ?", (asset_type, asset_id_pattern + '%'))
        if cursor.rowcount > 0:
            fixes['asset_type_updates'].append((asset_id_pattern, asset_type))
    
    # CN Indices
    cursor.execute("""
        UPDATE assets 
        SET asset_type = 'index' 
        WHERE asset_id LIKE 'CN:INDEX:%'
        OR asset_id LIKE '000001.SS%'
       OR asset_id LIKE '000016.SS%'
        OR asset_id LIKE '000300.SS%'
        OR asset_id LIKE '000905.SS%'
    """)
    
    index_count = cursor.rowcount
    if index_count > 0:
        print(f"  ✅ 更新了 {index_count} 个指数")
    
    # Remaining should be stocks
    cursor.execute("""
        UPDATE assets 
        SET asset_type = 'stock'
        WHERE asset_type IS NULL OR asset_type = '' OR asset_type = 'EQUITY'
    """)
    
    stock_count = cursor.rowcount
    if stock_count > 0:
        print(f"  ✅ 更新了 {stock_count} 个股票")
    
    # 2. Fix market attribution
    print("\n[2] 修复市场归属...")
    
    # Fix HK indices that are marked as US
    hk_indices = ['HSI', 'HSTECH', 'HSCE', 'HSCC']
    for index_symbol in hk_indices:
        cursor.execute("UPDATE assets SET market = 'HK' WHERE asset_id = ? AND market != 'HK'", (index_symbol,))
        if cursor.rowcount > 0:
            fixes['market_updates'].append((index_symbol, 'US -> HK'))
            print(f"  ✅ {index_symbol}: US -> HK")
    
    # 3. Summary
    print("\n" + "=" * 80)
    print("修复后的资产统计")
    print("=" * 80)
    
    cursor.execute("""
        SELECT market, asset_type, COUNT(*) 
        FROM assets 
        WHERE market IS NOT NULL AND asset_type IS NOT NULL
        GROUP BY market, asset_type
        ORDER BY 
            CASE market WHEN 'HK' THEN 1 WHEN 'US' THEN 2 WHEN 'CN' THEN 3 ELSE 4 END,
            CASE asset_type WHEN 'stock' THEN 1 WHEN 'etf' THEN 2 WHEN 'index' THEN 3 ELSE 4 END
    """)
    
    stats = cursor.fetchall()
    
    print(f"\n{'市场':<6} {'类型':<8} {'数量':>6}")
    print("-" * 25)
    for market, asset_type, count in stats:
        print(f"{market:<6} {asset_type:<8} {count:>6}")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ 修复完成！")
    print(f"   - asset_type 更新: {len(fixes['asset_type_updates'])} 个资产")
    print(f"   - market 更新: {len(fixes['market_updates'])} 个资产")

if __name__ == "__main__":
    fix_asset_classifications()
