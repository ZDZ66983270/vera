import sqlite3

DB_PATH = "vera.db"

def validate_and_fix_asset_display():
    """验证并修复资产显示规则"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("资产显示规则验证与修复")
    print("=" * 80)
    
    # 1. Check for assets missing asset_type
    cursor.execute("""
        SELECT asset_id, symbol_name, market 
        FROM assets 
        WHERE asset_type IS NULL OR asset_type = ''
        ORDER BY asset_id
    """)
    
    missing_type = cursor.fetchall()
    
    if missing_type:
        print(f"\n发现 {len(missing_type)} 个资产缺少 asset_type，正在自动分类...")
        
        for asset_id, symbol_name, market in missing_type:
            # Determine asset_type based on asset_id pattern
            asset_type = None
            
            # ETF detection
            if any(etf_pattern in asset_id.upper() for etf_pattern in ['ETF', '159', '512', '513', '516', '3033', '2800']):
                asset_type = 'etf'
            # Index detection  
            elif asset_id.startswith('^') or asset_id.startswith('HSI') or asset_id.startswith('HSTECH') or asset_id.startswith('000'):
                asset_type = 'index'
            # CN Stock detection
            elif asset_id.startswith('CN:STOCK:'):
                asset_type = 'stock'
            # HK Stock detection
            elif asset_id.startswith('HK:STOCK:') or (market == 'HK' and '.HK' in asset_id):
                asset_type = 'stock'
            # US Stock detection (default for single ticker symbols)
            elif market == 'US' or (len(asset_id) <= 5 and asset_id.isalpha()):
                asset_type = 'stock'
            else:
                asset_type = 'stock'  # Default
            
            print(f"  {asset_id} -> {asset_type}")
            cursor.execute("UPDATE assets SET asset_type = ? WHERE asset_id = ?", (asset_type, asset_id))
        
        print(f"✅ 已更新 {len(missing_type)} 个资产的类型")
    else:
        print("✅ 所有资产都已正确分类")
    
    # 2. Check naming format compliance
    print("\n" + "=" * 80)
    print("检查命名格式合规性")
    print("=" * 80)
    
    cursor.execute("""
        SELECT asset_id, symbol_name, market, asset_type
        FROM assets
        ORDER BY 
            CASE market WHEN 'HK' THEN 1 WHEN 'US' THEN 2 WHEN 'CN' THEN 3 ELSE 4 END,
            CASE asset_type WHEN 'stock' THEN 1 WHEN 'etf' THEN 2 WHEN 'index' THEN 3 ELSE 4 END,
            asset_id
    """)
    
    all_assets = cursor.fetchall()
    
    print(f"\n按市场和类型排序的资产列表（前30个）：\n")
    print(f"{'市场':<6} {'类型':<8} {'Asset ID':<25} {'Display Name'}")
    print("-" * 80)
    
    for idx, (asset_id, symbol_name, market, asset_type) in enumerate(all_assets[:30]):
        market_str = market or 'N/A'
        type_str = asset_type or 'N/A'
        name_str = symbol_name or asset_id
        
        # Check if display name should include code
        if asset_id.startswith('CN:STOCK:'):
            # Extract code from CN:STOCK:600030 -> 600030
            code = asset_id.split(':')[-1]
            expected_display = f"{name_str} ({code})"
        elif '.HK' in asset_id or '.SH' in asset_id or '.SZ' in asset_id or '.SS' in asset_id:
            expected_display = f"{name_str} ({asset_id})"
        else:
            expected_display = f"{name_str} ({asset_id})"
        
        print(f"{market_str:<6} {type_str:<8} {asset_id:<25} {expected_display}")
    
    if len(all_assets) > 30:
        print(f"\n... 还有 {len(all_assets) - 30} 个资产未显示")
    
    # 3. Summary
    print("\n" + "=" * 80)
    print("统计摘要")
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

if __name__ == "__main__":
    validate_and_fix_asset_display()
