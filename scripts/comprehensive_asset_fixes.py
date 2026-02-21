import sqlite3
import csv

DB_PATH = "vera.db"

def comprehensive_asset_fixes():
    """综合修复资产问题"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("综合资产修复")
    print("=" * 80)
    
    fixes = []
    
    # 问题1: 修复 600536.SH 的market和asset_type
    print("\n[1] 修复 600536.SH 的 market 和 asset_type...")
    cursor.execute("""
        UPDATE assets 
        SET market = 'CN', asset_type = 'stock'
        WHERE asset_id = '600536.SH'
    """)
    if cursor.rowcount > 0:
        fixes.append("600536.SH: US|EQUITY -> CN|stock")
        print("  ✅ 600536.SH: US|EQUITY -> CN|stock")
    
    # 问题2: 检查并修复 ^SPX vs SPX
    print("\n[2] 检查 SPX symbol...")
    cursor.execute("SELECT asset_id, symbol_name FROM assets WHERE asset_id IN ('SPX', '^SPX', '^GSPC')")
    spx_records = cursor.fetchall()
    print(f"  当前SPX相关记录: {spx_records}")
    
    # 如果有^GSPC，确保它也被标记为index
    cursor.execute("SELECT asset_id FROM assets WHERE asset_id = '^GSPC'")
    if not cursor.fetchone():
        print("  ℹ️  ^GSPC 不存在，当前使用 SPX 作为标普500指数")
    
    # 问题3: 验证所有asset的market归属和asset_type
    print("\n[3] 验证所有资产的 market 和 asset_type...")
    
    # 确保所有 .HK 结尾的都是 HK 市场
    cursor.execute("""
        UPDATE assets 
        SET market = 'HK'
        WHERE (asset_id LIKE '%.HK' OR asset_id LIKE 'HK:%')
          AND market != 'HK'
    """)
    if cursor.rowcount > 0:
        fixes.append(f"修复了 {cursor.rowcount} 个HK资产的market")
        print(f"  ✅ 修复了 {cursor.rowcount} 个 .HK 资产的 market")
    
    # 确保所有 .SS/.SH/.SZ 或 CN: 开头的都是 CN 市场
    cursor.execute("""
        UPDATE assets 
        SET market = 'CN'
        WHERE (asset_id LIKE '%.SS' 
           OR asset_id LIKE '%.SH' 
           OR asset_id LIKE '%.SZ'
           OR asset_id LIKE 'CN:%')
          AND market != 'CN'
    """)
    if cursor.rowcount > 0:
        fixes.append(f"修复了 {cursor.rowcount} 个CN资产的market")
        print(f"  ✅ 修复了 {cursor.rowcount} 个 CN 资产的 market")
    
    # 其他都是US市场（除非已经正确分类）
    cursor.execute("""
        UPDATE assets 
        SET market = COALESCE(market, 'US')
        WHERE market IS NULL OR market = ''
    """)
    if cursor.rowcount > 0:
        fixes.append(f"设置了 {cursor.rowcount} 个资产的默认market为US")
    
    # 问题4: 提供CSV新增资产检测方法
    print("\n[4] CSV新增资产检测方法...")
    print("  建议方案:")
    print("  - 方法A: 导入前先查询: SELECT DISTINCT symbol FROM market_data_daily_full.csv")
    print("  - 方法B: 导入时记录: INSERT OR IGNORE + 检查affected rows")
    print("  - 方法C: 导入后对比: 查询上次导入时间后的新记录")
    
    # 最终验证
    print("\n" + "=" * 80)
    print("修复后的市场归属统计")
    print("=" * 80)
    
    cursor.execute("""
        SELECT market, asset_type, COUNT(*) as count
        FROM assets
        GROUP BY market, asset_type
        ORDER BY 
            CASE market WHEN 'HK' THEN 1 WHEN 'US' THEN 2 WHEN 'CN' THEN 3 ELSE 4 END,
            CASE asset_type WHEN 'stock' THEN 1 WHEN 'etf' THEN 2 WHEN 'index' THEN 3 WHEN 'EQUITY' THEN 4 ELSE 5 END
    """)
    
    stats = cursor.fetchall()
    print(f"\n{'市场':<8} {'类型':<10} {'数量':>6}")
    print("-" * 28)
    for market, asset_type, count in stats:
        status = "⚠️" if asset_type == "EQUITY" else "✅"
        print(f"{status} {market or 'N/A':<8} {asset_type or 'N/A':<10} {count:>6}")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ 修复完成！共 {len(fixes)} 项修复")
    for fix in fixes:
        print(f"  - {fix}")
    
    return len(fixes)

if __name__ == "__main__":
    comprehensive_asset_fixes()
