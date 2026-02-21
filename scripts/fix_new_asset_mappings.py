#!/usr/bin/env python3
"""
修复新资产的symbol映射和注册问题
"""
import sqlite3
from datetime import datetime

DB_PATH = "vera.db"

def fix_new_assets():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("修复新资产symbol映射和注册")
    print("=" * 80)
    
    # 1. 删除重复的600536.SH
    print("\n[1] 清理重复资产...")
    cursor.execute("DELETE FROM assets WHERE asset_id = '600536.SH'")
    if cursor.rowcount > 0:
        print(f"  ✅ 删除了 600536.SH (US|EQUITY)")
    
    # 2. 为新资产注册到 assets 表
    print("\n[2] 注册新资产到 assets 表...")
    
    new_assets = [
        # HK
        ('00700.HK', '腾讯控股', 'HK', 'stock'),
        ('HK:STOCK:00700', '腾讯控股', 'HK', 'stock'),
        # CN Indices
        ('000016.SS', '上证50指数', 'CN', 'index'),
        ('000300.SS', '沪深300指数', 'CN', 'index'),
        ('000905.SS', '中证500指数', 'CN', 'index'),
        # CN ETFs
        ('159662.SZ', '交运ETF', 'CN', 'etf'),
        ('159751.SZ', '港股科技ETF', 'CN', 'etf'),
        ('159852.SZ', '软件ETF', 'CN', 'etf'),
        ('512800.SH', '银行ETF', 'CN', 'etf'),
        ('513190.SH', '港股金融ETF', 'CN', 'etf'),
        ('516020.SH', '化工ETF', 'CN', 'etf'),
    ]
    
    for asset_id, name, market, asset_type in new_assets:
        cursor.execute("SELECT 1 FROM assets WHERE asset_id = ?", (asset_id,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO assets (asset_id, symbol_name, market, asset_type, industry)
                VALUES (?, ?, ?, ?, ?)
            """, (asset_id, name, market, asset_type, asset_type.title()))
            print(f"  ✅ 添加: {asset_id} ({name})")
        else:
            print(f"  ℹ️  已存在: {asset_id}")
    
    # 3. 注册 symbol mapping
    print("\n[3] 注册 symbol mapping...")
    
    symbol_mappings = [
        # HK
        ('HK:STOCK:00700', '00700.HK', 'csv_import', 10),
        ('HK:STOCK:00700', '00700', 'trading_symbol', 20),
        # CN Indices (使用 .SS 作为canonical)
        ('000016.SS', '000016.SH', 'csv_import', 10),
        ('000300.SS', '000300.SH', 'csv_import', 10),
        ('000905.SS', '000905.SH', 'csv_import', 10),
        # CN ETFs
        ('159662.SZ', '159662', 'trading_symbol', 10),
        ('159751.SZ', '159751', 'trading_symbol', 10),
        ('159852.SZ', '159852', 'trading_symbol', 10),
        ('512800.SH', '512800', 'trading_symbol', 10),
        ('513190.SH', '513190', 'trading_symbol', 10),
        ('516020.SH', '516020', 'trading_symbol', 10),
    ]
    
    for canonical_id, symbol, source, priority in symbol_mappings:
        cursor.execute("""
            INSERT OR REPLACE INTO asset_symbol_map 
            (canonical_id, symbol, source, priority, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, datetime('now'), datetime('now'))
        """, (canonical_id, symbol, source, priority))
        print(f"  ✅ 映射: {canonical_id} <- {symbol}")
    
    # 4. 验证
    print("\n" + "=" * 80)
    print("验证结果")
    print("=" * 80)
    
    # 检查重复
    cursor.execute("""
        SELECT asset_id, COUNT(*) as cnt
        FROM assets
        WHERE asset_id LIKE '%600536%'
        GROUP BY asset_id
    """)
    dups = cursor.fetchall()
    print(f"\n600536相关资产: {dups}")
    
    # 检查新资产的mapping
    cursor.execute("""
        SELECT canonical_id, symbol 
        FROM asset_symbol_map 
        WHERE canonical_id IN ('159751.SZ', '000016.SS', '00700.HK', 'HK:STOCK:00700')
        ORDER BY canonical_id, priority
    """)
    mappings = cursor.fetchall()
    print(f"\n新资产映射数: {len(mappings)}")
    for canonical_id, symbol in mappings[:5]:
        print(f"  {canonical_id} <- {symbol}")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ 修复完成！")

if __name__ == "__main__":
    fix_new_assets()
