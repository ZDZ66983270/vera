import sqlite3

DB_PATH = "vera.db"

def check_conflicts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("检查 Asset 定义冲突")
    print("=" * 80)
    
    # 1. Check assets that exist in both tables but have different sector/industry
    cursor.execute("""
        SELECT 
            a.asset_id,
            a.industry as assets_industry,
            ac.sector_name as classification_sector,
            ac.industry_name as classification_industry
        FROM assets a
        INNER JOIN asset_classification ac ON a.asset_id = ac.asset_id
        WHERE a.industry IS NOT NULL 
          AND a.industry != ''
          AND (a.industry != ac.sector_name OR a.industry IS NULL)
        ORDER BY a.asset_id
    """)
    
    conflicts = cursor.fetchall()
    
    if conflicts:
        print(f"\n发现 {len(conflicts)} 个冲突需要解决：\n")
        for asset_id, assets_industry, classification_sector, classification_industry in conflicts:
            print(f"  {asset_id}:")
            print(f"    - assets 表:           {assets_industry}")
            print(f"    - classification 表:  {classification_sector} / {classification_industry}")
        
        print(f"\n正在更新 assets 表以保留 classification 中的定义...")
        
        # Update assets table with classification data
        cursor.execute("""
            UPDATE assets
            SET industry = (
                SELECT sector_name 
                FROM asset_classification 
                WHERE asset_classification.asset_id = assets.asset_id
                LIMIT 1
            )
            WHERE asset_id IN (
                SELECT asset_id FROM asset_classification
            )
        """)
        
        updated = cursor.rowcount
        print(f"✅ 已更新 {updated} 条记录")
    else:
        print("✅ 未发现 asset 定义冲突")
    
    print("\n" + "=" * 80)
    print("检查 Sector Proxy 映射完整性")
    print("=" * 80)
    
    # 2. Check if all classified assets have proxy mappings
    cursor.execute("""
        SELECT DISTINCT
            ac.sector_code,
            ac.sector_name,
            COUNT(DISTINCT ac.asset_id) as asset_count
        FROM asset_classification ac
        LEFT JOIN sector_proxy_map spm 
            ON ac.scheme = spm.scheme AND ac.sector_code = spm.sector_code
        WHERE spm.proxy_etf_id IS NULL
          AND ac.scheme = 'GICS'
        GROUP BY ac.sector_code, ac.sector_name
    """)
    
    missing_mappings = cursor.fetchall()
    
    if missing_mappings:
        print(f"\n发现 {len(missing_mappings)} 个板块缺少 ETF 映射：\n")
        for sector_code, sector_name, asset_count in missing_mappings:
            print(f"  Sector {sector_code} ({sector_name}): {asset_count} 个资产")
        print("\n⚠️  这些板块的资产将无法进行板块相对强度分析")
    else:
        print("✅ 所有板块都有对应的 ETF 映射")
    
    # 3. Summary statistics
    print("\n" + "=" * 80)
    print("数据库摘要")
    print("=" * 80)
    
    cursor.execute("SELECT COUNT(*) FROM assets")
    total_assets = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT asset_id) FROM asset_classification")
    classified_assets = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM sector_proxy_map")
    total_mappings = cursor.fetchone()[0]
    
    print(f"\n  总资产数:           {total_assets}")
    print(f"  已分类资产数:       {classified_assets}")
    print(f"  板块代理映射数:     {total_mappings}")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    check_conflicts()
