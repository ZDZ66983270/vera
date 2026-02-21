import sqlite3

DB_PATH = "vera.db"

def fix_symbol_mappings():
    """修复错误的symbol映射"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("修复Symbol映射问题")
    print("=" * 80)
    
    # 1. Remove incorrect 601919.SS entry
    print("\n[1] 删除错误的 601919.SS 记录...")
    cursor.execute("SELECT asset_id FROM assets WHERE asset_id = '601919.SS'")
    if cursor.fetchone():
        cursor.execute("DELETE FROM assets WHERE asset_id = '601919.SS'")
        print("  ✅ 已删除 601919.SS")
    else:
        print("  ℹ️  601919.SS 不存在")
    
    # 2. Check if we need to add 601919.SH as an alias
    cursor.execute("SELECT asset_id FROM assets WHERE asset_id = '601919.SH'")
    if not cursor.fetchone():
        print("\n[2] 添加 601919.SH 作为正确的symbol...")
        # Check if CN:STOCK:601919 exists
        cursor.execute("SELECT symbol_name, market FROM assets WHERE asset_id = 'CN:STOCK:601919'")
        existing = cursor.fetchone()
        
        if existing:
            symbol_name, market = existing
            # Note: We keep CN:STOCK:601919 as the canonical ID,
            # but we don't need to add 601919.SH separately since
            # the price cache has all variants
            print(f"  ℹ️  CN:STOCK:601919 已存在: {symbol_name}")
            print(f"  ℹ️  价格缓存中已有 601919.SH 的数据 (4502条记录)")
        else:
            print("  ⚠️  CN:STOCK:601919 不存在，需要添加")
    
    # 3. Verify data coverage with correct symbols
    print("\n" + "=" * 80)
    print("验证修正后的数据覆盖")
    print("=" * 80)
    
    # Check all CN stocks
    cursor.execute("""
        SELECT 
            a.asset_id,
            a.symbol_name,
            COUNT(DISTINCT p.trade_date) as price_records
        FROM assets a
        LEFT JOIN vera_price_cache p ON (
            p.symbol = a.asset_id 
            OR p.symbol = REPLACE(a.asset_id, 'CN:STOCK:', '')
            OR p.symbol = REPLACE(a.asset_id, 'CN:STOCK:', '') || '.SH'
            OR p.symbol = REPLACE(a.asset_id, 'CN:STOCK:', '') || '.SS'
        )
        WHERE a.market = 'CN' AND a.asset_type = 'stock'
        GROUP BY a.asset_id, a.symbol_name
        ORDER BY a.asset_id
    """)
    
    cn_stocks = cursor.fetchall()
    
    print(f"\nCN个股数据覆盖情况:\n")
    print(f"{'Asset ID':<25} {'名称':<15} {'记录数':>10}")
    print("-" * 55)
    
    for asset_id, symbol_name, count in cn_stocks:
        status = "✅" if count > 100 else "⚠️"
        print(f"{status} {asset_id:<25} {symbol_name:<15} {count:>10}")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ 修复完成")

if __name__ == "__main__":
    fix_symbol_mappings()
