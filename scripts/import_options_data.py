"""
期权数据导入示例脚本
Options Data Import Example

演示如何导入期权链数据并进行 CSP 评估
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any
import uuid
import re

def import_options_from_csv(csv_path, db_path="vera.db"):
    """
    从 CSV 文件导入期权数据
    支持自动映射字段和智能解析
    """
    print(f"\n📥 开始导入期权数据: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"❌ 读取 CSV 失败: {e}")
        return {"success_count": 0, "failed_count": 0, "assets_covered": [], "failed_assets": [], "market_counts": {}, "details": []}

    print(f"   读取到 {len(df)} 条期权记录")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    imported = 0
    failed = 0
    assets_covered = set()
    failed_assets = set()
    market_counts = {}
    details = []

    # 预定义的列名映射 (基于字节码常量)
    col_map = {
        'underlying_symbol': ['underlying_symbol', 'symbol'],
        'option_type': ['Type', 'option_type'],
        'strike': ['strike', 'Strike'],
        'expiry': ['expiry_date', 'ExpiryDate'],
        'market_price': ['last_price', 'Market_Price', 'market_price'],
        'bid': ['bid'],
        'ask': ['ask'],
        'iv': ['implied_volatility_%', 'implied_volatility', 'IV'],
        'delta': ['delta', 'Delta'],
        'gamma': ['gamma', 'Gamma'],
        'theta': ['theta', 'Theta'],
        'vega': ['vega', 'Vega'],
        'rho': ['rho', 'Rho']
    }

    def get_val(row, keys, default=None):
        for k in keys:
            if k in row and pd.notna(row[k]):
                return row[k]
        return default

    for idx, row in df.iterrows():
        symbol_raw = get_val(row, col_map['underlying_symbol'])
        if not symbol_raw:
            failed += 1
            continue

        # 查找标的资产 ID
        cursor.execute("SELECT asset_id FROM assets WHERE asset_id = ? OR symbol = ?", (str(symbol_raw), str(symbol_raw)))
        res = cursor.fetchone()
        
        if not res and '.HK' not in str(symbol_raw):
            # 尝试补充 .HK 后缀查找
            cursor.execute("SELECT asset_id FROM assets WHERE symbol = ?", (str(symbol_raw) + ".HK",))
            res = cursor.fetchone()

        if not res:
            failed += 1
            failed_assets.add(str(symbol_raw))
            details.append(f"行 {idx}: 找不到标的资产 {symbol_raw}")
            continue

        underlying_asset_id = res[0]
        assets_covered.add(underlying_asset_id)

        # 解析期权类型
        option_type = str(get_val(row, col_map['option_type'], '')).upper()
        if 'P' in option_type:
            option_type = 'P'
        elif 'C' in option_type:
            option_type = 'C'
        else:
            # 尝试从代码中解析 \d([CP])\d
            opt_sym = str(row.get('option_symbol', ''))
            match = re.search(r'\d([CP])\d', opt_sym)
            if match:
                option_type = match.group(1)
            else:
                option_type = 'UNKNOWN'

        strike = get_val(row, col_map['strike'])
        expiry = get_val(row, col_map['expiry'])
        market_price = get_val(row, col_map['market_price'], 0.0)
        
        iv = get_val(row, col_map['iv'], 0.0)
        if iv > 10.0: # 假设百分比形式
            iv = iv / 100.0

        delta = get_val(row, col_map['delta'])
        gamma = get_val(row, col_map['gamma'])
        theta = get_val(row, col_map['theta'])
        vega = get_val(row, col_map['vega'])
        rho = get_val(row, col_map['rho'])

        # 生成 ID
        option_id = f"{underlying_asset_id}_{option_type}_{strike}_{expiry}".replace(' ', '_')

        try:
            cursor.execute("""
                INSERT OR REPLACE INTO options_chain (
                    option_id, underlying_asset_id, option_type, strike_price, expiry_date,
                    market_price, theoretical_price, bid_price, ask_price, last_price,
                    delta, gamma, theta, vega, rho,
                    implied_volatility, volume, open_interest, data_source, quote_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                option_id, underlying_asset_id, option_type, strike, str(expiry),
                market_price, row.get('theoretical_price'), get_val(row, col_map['bid']), get_val(row, col_map['ask']), market_price,
                delta, gamma, theta, vega, rho,
                iv, row.get('volume', 0), row.get('open_interest', 0), 'csv_import', datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            imported += 1
            
            # 统计市场数据
            mkt = underlying_asset_id.split(':')[0] if ':' in underlying_asset_id else 'UNKNOWN'
            if mkt not in market_counts:
                market_counts[mkt] = {'rows': 0, 'asset_count': 0, 'assets': set()}
            market_counts[mkt]['rows'] += 1
            market_counts[mkt]['assets'].add(underlying_asset_id)
            
        except Exception as e:
            failed += 1
            details.append(f"行 {idx}: 导入失败 {e}")

    conn.commit()
    conn.close()

    # 转换统计中的 set 为 count
    final_market_counts = {}
    for mkt, data in market_counts.items():
        final_market_counts[mkt] = {
            'rows': data['rows'],
            'asset_count': len(data['assets'])
        }

    print(f"\n✅ 导入完成:")
    print(f"   成功: {imported} 条")
    print(f"   失败: {failed}")
    print(f"   覆盖资产: {len(assets_covered)} 个")

    return {
        "success_count": imported,
        "failed_count": failed,
        "assets_covered": list(assets_covered),
        "failed_assets": list(failed_assets),
        "market_counts": final_market_counts,
        "details": details
    }

def import_options_from_dict(options_data: List[Dict[str, Any]], db_path: str = "vera.db"):
    """
    从字典列表导入期权数据
    """
    print(f"\n📥 开始导入 {len(options_data)} 条期权数据")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    imported = 0
    failed = 0

    for opt in options_data:
        try:
            option_id = opt.get('option_id') or str(uuid.uuid4())
            cursor.execute("""
                INSERT OR REPLACE INTO options_chain (
                    option_id, underlying_asset_id, option_type, strike_price, expiry_date,
                    market_price, theoretical_price, bid_price, ask_price, last_price,
                    delta, gamma, theta, vega, rho, implied_volatility,
                    volume, open_interest, data_source, quote_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                option_id, opt.get('underlying_asset_id'), opt.get('Type'), opt.get('Strike'), opt.get('ExpiryDate'),
                opt.get('Market_Price'), opt.get('Theoretical_Price'), opt.get('Bid_Price'), opt.get('Ask_Price'), opt.get('Last_Price'),
                opt.get('Delta'), opt.get('Gamma'), opt.get('Theta'), opt.get('Vega'), opt.get('Rho'), opt.get('IV'),
                opt.get('Volume'), opt.get('Open_Interest'), opt.get('data_source', 'api_import'), 
                opt.get('quote_time') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            imported += 1
        except Exception as e:
            failed += 1
            print(f"   ❌ 导入失败: {e}")

    conn.commit()
    conn.close()
    
    print(f"\n✅ 导入完成:")
    print(f"   成功: {imported} 条")
    print(f"   失败: {failed}")
    
    return imported, failed

def query_options_chain(underlying_symbol: str, db_path: str = "vera.db"):
    """
    查询指定标的的期权链
    """
    conn = sqlite3.connect(db_path)
    query = """
        SELECT 
            oc.*,
            a.symbol as underlying_symbol
        FROM options_chain oc
        JOIN assets a ON oc.underlying_asset_id = a.asset_id
        WHERE a.symbol = ?
        ORDER BY oc.expiry_date, oc.strike_price
    """
    df = pd.read_sql_query(query, conn, params=(underlying_symbol,))
    conn.close()
    return df

def example_import_msft_options():
    print("示例：导入微软的期权数据")
    print("\n" + "="*70)
    print("示例：导入微软 (MSFT) 期权数据")
    print("="*70)
    
    expiry_date = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    
    options_data = [
        {
            'underlying_asset_id': 'US:STOCK:MSFT',
            'Type': 'P',
            'Strike': 400.0,
            'ExpiryDate': expiry_date,
            'Market_Price': 5.2,
            'Theoretical_Price': 5.1,
            'IV': 0.28,
            'Delta': -0.25,
            'Gamma': 0.05,
            'Theta': -0.03,
            'Vega': 0.15,
            'Rho': -0.02,
            'data_source': 'example'
        },
        {
            'underlying_asset_id': 'US:STOCK:MSFT',
            'Type': 'P',
            'Strike': 390.0,
            'ExpiryDate': expiry_date,
            'Market_Price': 3.8,
            'Theoretical_Price': 3.7,
            'IV': 0.26,
            'Delta': -0.2,
            'Gamma': 0.04,
            'Theta': -0.025,
            'Vega': 0.12,
            'Rho': -0.015,
            'data_source': 'example'
        }
    ]
    
    import_options_from_dict(options_data)
    
    df = query_options_chain('MSFT')
    if not df.empty:
        print(f"\n📊 查询 MSFT 期权链:")
        print(f"   找到 {len(df)} 条期权记录:\n")
        print(df[['option_type', 'strike_price', 'expiry_date', 'market_price', 'delta', 'implied_volatility']].to_string(index=False))
    else:
        print("\n   ⚠️  没有找到期权数据")

if __name__ == "__main__":
    example_import_msft_options()
