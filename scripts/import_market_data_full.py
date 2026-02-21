#!/usr/bin/env python3
"""
导入市场数据从 market_data_daily_full.csv
- 将 OHLCV 数据导入 vera_price_cache
- 将基本面数据导入 financial_history（从PE/PB反推EPS/BPS）
- 避免重复导入
- 更新缺失的基本面字段
"""

import sqlite3
import pandas as pd
from datetime import datetime
import sys

DB_PATH = "vera.db"
CSV_PATH = "imports/market_data_daily_full.csv"

def parse_timestamp(ts_str):
    """解析时间戳为日期"""
    try:
        return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").date()
    except:
        try:
            return datetime.strptime(ts_str, "%Y-%m-%d").date()
        except:
            return None

def import_market_data():
    """主导入函数"""
    print(f"[1] 读取 CSV 文件: {CSV_PATH}")
    df = pd.read_csv(CSV_PATH)
    print(f"   - 共 {len(df)} 行数据")
    print(f"   - 列: {list(df.columns)}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 统计
    stats = {
        "price_inserted": 0,
        "price_skipped": 0,
        "fundamental_inserted": 0,
        "fundamental_updated": 0,
        "errors": 0
    }
    
    print("\n[2] 开始导入数据...")
    
    for idx, row in df.iterrows():
        if idx % 1000 == 0:
            print(f"   处理进度: {idx}/{len(df)}")
        
        try:
            symbol = row['symbol']
            trade_date = parse_timestamp(row['timestamp'])
            
            if not trade_date:
                stats["errors"] += 1
                continue
            
            # Resolve to Canonical ID
            from utils.canonical_resolver import resolve_canonical_symbol
            canonical_id = resolve_canonical_symbol(symbol) or symbol
            
            # === Part 1: 导入 OHLCV 到 vera_price_cache ===
            cursor.execute("""
                SELECT 1 FROM vera_price_cache 
                WHERE symbol = ? AND trade_date = ?
            """, (canonical_id, trade_date))
            
            if cursor.fetchone() is None:
                # 插入新记录
                cursor.execute("""
                    INSERT INTO vera_price_cache 
                    (symbol, trade_date, open, high, low, close, volume, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    canonical_id, trade_date,
                    float(row['open']) if pd.notna(row['open']) else None,
                    float(row['high']) if pd.notna(row['high']) else None,
                    float(row['low']) if pd.notna(row['low']) else None,
                    float(row['close']) if pd.notna(row['close']) else None,
                    int(row['volume']) if pd.notna(row['volume']) else None,
                    'import_csv'
                ))
                stats["price_inserted"] += 1
            else:
                stats["price_skipped"] += 1
            
            # === Part 2: 导入/更新基本面到 financial_history ===
            close_price = float(row['close']) if pd.notna(row['close']) else None
            pe = float(row['pe']) if pd.notna(row['pe']) else None
            pb = float(row['pb']) if pd.notna(row['pb']) else None
            ps = float(row['ps']) if pd.notna(row['ps']) else None
            div_yield = float(row['dividend_yield']) if pd.notna(row['dividend_yield']) else None
            
            # 检查是否有基本面数据可导入
            has_fundamentals = any([pe, pb, ps, div_yield])
            
            if has_fundamentals and close_price:
                # 反推 EPS/BPS
                eps_ttm = (close_price / pe) if (pe and pe > 0) else None
                bps = (close_price / pb) if (pb and pb > 0) else None
                
                # Use Canonical ID for storage
                from utils.canonical_resolver import resolve_canonical_symbol
                canonical_id = resolve_canonical_symbol(symbol) or symbol
                
                # 检查是否已存在
                cursor.execute("""
                    SELECT eps_ttm, bps, revenue_ttm, dividend_amount 
                    FROM financial_history
                    WHERE asset_id = ? AND report_date = ?
                """, (canonical_id, trade_date))
                
                existing = cursor.fetchone()
                
                if existing is None:
                    # 插入新记录
                    cursor.execute("""
                        INSERT INTO financial_history 
                        (asset_id, report_date, eps_ttm, bps, revenue_ttm, dividend_amount)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        canonical_id, trade_date,
                        eps_ttm, bps,
                        None,  # revenue_ttm 暂不计算（需要PS和市值）
                        None   # dividend_amount 暂不计算（需要股本数据）
                    ))
                    stats["fundamental_inserted"] += 1
                else:
                    # 更新缺失字段
                    old_eps, old_bps, old_rev, old_div = existing
                    need_update = False
                    
                    updates = []
                    params = []
                    
                    if eps_ttm and not old_eps:
                        updates.append("eps_ttm = ?")
                        params.append(eps_ttm)
                        need_update = True
                    
                    if bps and not old_bps:
                        updates.append("bps = ?")
                        params.append(bps)
                        need_update = True
                    
                    if need_update:
                        params.extend([canonical_id, trade_date])
                        cursor.execute(f"""
                            UPDATE financial_history 
                            SET {', '.join(updates)}
                            WHERE asset_id = ? AND report_date = ?
                        """, params)
                        stats["fundamental_updated"] += 1
                        stats["fundamental_updated"] += 1
        
        except Exception as e:
            print(f"   错误 (行 {idx}): {e}")
            stats["errors"] += 1
            continue
    
    conn.commit()
    conn.close()
    
    print("\n[3] 导入完成!")
    print(f"   - 价格数据插入: {stats['price_inserted']}")
    print(f"   - 价格数据跳过(已存在): {stats['price_skipped']}")
    print(f"   - 基本面插入: {stats['fundamental_inserted']}")
    print(f"   - 基本面更新: {stats['fundamental_updated']}")
    print(f"   - 错误: {stats['errors']}")
    
    return stats

if __name__ == "__main__":
    try:
        stats = import_market_data()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 导入失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
