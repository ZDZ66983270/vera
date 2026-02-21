#!/usr/bin/env python3
"""
CSV新资产检测工具
在导入market_data_daily_full.csv之前，检测其中的新资产
"""
import pandas as pd
import sqlite3
from collections import defaultdict

DB_PATH = "vera.db"
CSV_PATH = "imports/market_data_daily_full.csv"

def detect_market(symbol):
    """根据symbol推断市场"""
    if '.HK' in symbol or symbol.startswith('HK:'):
        return 'HK'
    elif '.SS' in symbol or '.SH' in symbol or '.SZ' in symbol or symbol.startswith('CN:'):
        return 'CN'
    else:
        return 'US'

def detect_asset_type(symbol, symbol_name):
    """根据symbol和name推断资产类型"""
    name_lower = (symbol_name or '').lower()
    
    # ETF检测
    if 'etf' in name_lower or symbol in ['SPY', 'QQQ', 'DIA', 'IWM', 'GLD', 'TLT']:
        return 'etf'
    elif symbol.startswith('XL') or symbol.startswith('VT') or symbol.startswith('VY'):
        return 'etf'
    elif symbol.startswith('159') or symbol.startswith('512') or symbol.startswith('513') or symbol.startswith('516'):
        return 'etf'
    elif symbol in ['2800.HK', '3033.HK']:
        return 'etf'
    
    # Index检测
    if symbol.startswith('^') or symbol in ['SPX', 'NDX', 'DJI', 'HSI', 'HSTECH', 'HSCE', 'HSCC']:
        return 'index'
    elif symbol.startswith('000') and '.SS' in symbol:
        return 'index'
    elif symbol.startswith('CN:INDEX:'):
        return 'index'
    
    # 默认Stock
    return 'stock'

def detect_new_assets_from_csv(csv_path=CSV_PATH, db_path=DB_PATH):
    """从CSV中检测新资产"""
    print("=" * 80)
    print("CSV新资产检测工具")
    print("=" * 80)
    
    # 1. 读取CSV
    print(f"\n[1] 读取CSV: {csv_path}")
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        csv_symbols = set(df['symbol'].unique())
        print(f"    CSV中包含 {len(csv_symbols)} 个唯一symbol")
    except Exception as e:
        print(f"    ❌ 读取CSV失败: {e}")
        return []
    
    # 2. 查询数据库现有资产
    print(f"\n[2] 查询数据库现有资产...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 获取所有asset_id
    cursor.execute("SELECT DISTINCT asset_id FROM assets")
    existing_assets = set(row[0] for row in cursor.fetchall())
    
    # 获取所有mapped symbols
    cursor.execute("SELECT DISTINCT symbol FROM asset_symbol_map WHERE is_active = 1")
    mapped_symbols = set(row[0] for row in cursor.fetchall())
    
    # 获取所有alias
    cursor.execute("SELECT DISTINCT alias_id FROM symbol_alias")
    alias_symbols = set(row[0] for row in cursor.fetchall())
    
    all_known = existing_assets | mapped_symbols | alias_symbols
    print(f"    数据库中已知 {len(all_known)} 个symbol")
    
    # 3. 找出新symbol
    new_symbols = csv_symbols - all_known
    
    print(f"\n[3] 检测结果:")
    print(f"    CSV总symbol: {len(csv_symbols)}")
    print(f"    已存在: {len(csv_symbols - new_symbols)}")
    print(f"    ✨ 新增: {len(new_symbols)}")
    
    if new_symbols:
        print(f"\n[4] 新增资产详情:")
        
        # 按市场分组
        by_market = defaultdict(list)
        
        for sym in sorted(new_symbols):
            # 获取该symbol的样例数据
            sample = df[df['symbol'] == sym].iloc[0]
            market = detect_market(sym)
            asset_type = detect_asset_type(sym, str(sample.get('symbol', '')))
            
            by_market[market].append({
                'symbol': sym,
                'type': asset_type,
                'sample_date': sample.get('timestamp', 'N/A'),
                'close': sample.get('close', 'N/A')
            })
        
        # 按市场输出
        for market in ['HK', 'US', 'CN']:
            if market in by_market:
                assets = by_market[market]
                print(f"\n    {market}市场 ({len(assets)}个):")
                
                # 按类型分组
                by_type = defaultdict(list)
                for asset in assets:
                    by_type[asset['type']].append(asset)
                
                for asset_type in ['stock', 'etf', 'index']:
                    if asset_type in by_type:
                        print(f"      {asset_type.upper()}:")
                        for asset in by_type[asset_type]:
                            print(f"        - {asset['symbol']:<20} (最新: {asset['sample_date']}, 价格: {asset['close']})")
    else:
        print("\n    ✅ CSV中没有新资产")
    
    conn.close()
    
    return list(new_symbols)

if __name__ == "__main__":
    new_assets = detect_new_assets_from_csv()
    
    if new_assets:
        print(f"\n{'=' * 80}")
        print("建议操作:")
        print("=" * 80)
        print("1. 检查新资产是否应该添加到 asset_classification.csv")
        print("2. 如果需要，运行 import_asset_classification.py 导入分类")
        print("3. 运行 import_market_data_full.py 导入价格数据")
