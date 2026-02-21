import sqlite3
from datetime import datetime

DB_PATH = "vera.db"

def add_missing_cn_indices():
    """添加缺失的CN市场指数"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("添加缺失的CN市场指数")
    print("=" * 80)
    
    # Define missing indices
    missing_indices = [
        ('000016.SS', '上证50指数', 'index', 'CN'),
        ('000300.SS', '沪深300指数', 'index', 'CN'),
        ('000905.SS', '中证500指数', 'index', 'CN'),
    ]
    
    added = 0
    for asset_id, symbol_name, asset_type, market in missing_indices:
        # Check if exists
        cursor.execute("SELECT asset_id FROM assets WHERE asset_id = ?", (asset_id,))
        if cursor.fetchone():
            print(f"  ⚠️  {asset_id} 已存在，跳过")
            continue
        
        # Insert
        cursor.execute("""
            INSERT INTO assets (asset_id, symbol_name, asset_type, market, industry, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (asset_id, symbol_name, asset_type, market, 'Index', datetime.now()))
        
        print(f"  ✅ 添加: {asset_id} - {symbol_name}")
        added += 1
    
    conn.commit()
    
    # Verify
    print("\n" + "=" * 80)
    print("CN市场指数列表")
    print("=" * 80)
    
    cursor.execute("""
        SELECT asset_id, symbol_name, asset_type 
        FROM assets 
        WHERE market = 'CN' AND asset_type = 'index'
        ORDER BY asset_id
    """)
    
    indices = cursor.fetchall()
    print(f"\n共 {len(indices)} 个指数：\n")
    for asset_id, symbol_name, asset_type in indices:
        print(f"  {asset_id:<15} {symbol_name}")
    
    conn.close()
    print(f"\n✅ 完成！新增 {added} 个指数")

if __name__ == "__main__":
    add_missing_cn_indices()
