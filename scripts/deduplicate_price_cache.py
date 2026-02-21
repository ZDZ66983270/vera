#!/usr/bin/env python3
"""
清理 vera_price_cache 中的重复symbol数据
将旧的原始symbol (如 00005.HK) 迁移到典范ID (如 HK:STOCK:00005)
"""

import sqlite3
from db.connection import get_connection
from utils.canonical_resolver import resolve_canonical_symbol

def deduplicate_price_cache():
    """
    迁移策略：
    1. 找出所有非典范ID格式的symbol
    2. 尝试解析为典范ID（优先用映射表，失败则用启发式推断）
    3. 合并数据（保留最新的记录，去重）
    4. 删除旧记录
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. 找出所有symbol
    cursor.execute("SELECT DISTINCT symbol FROM vera_price_cache")
    all_symbols = [row[0] for row in cursor.fetchall()]
    
    # 2. 识别非典范ID格式的symbol（不包含冒号）
    non_canonical = [s for s in all_symbols if ':' not in s]
    
    print(f"发现 {len(non_canonical)} 个非典范ID格式的symbol需要处理...")
    
    migration_plan = []
    failed_resolution = []
    
    # 导入启发式推断工具
    from engine.asset_resolver import _infer_market, _infer_asset_type
    
    for raw_symbol in non_canonical:
        canonical = None
        
        # 尝试1: 通过映射表解析
        try:
            canonical = resolve_canonical_symbol(conn, raw_symbol)
            if canonical != raw_symbol:
                print(f"  ✓ {raw_symbol} → {canonical} (映射表)")
        except:
            pass
        
        # 尝试2: 启发式推断
        if not canonical or canonical == raw_symbol:
            try:
                m = _infer_market(raw_symbol)
                t = _infer_asset_type(raw_symbol)
                # 特殊处理
                t_map = {"EQUITY": "STOCK", "STOCK": "STOCK", "ETF": "ETF", "INDEX": "INDEX"}
                kind = t_map.get(t, "STOCK")
                
                code = raw_symbol.upper()
                if m == "HK":
                    code = code.replace(".HK", "").zfill(5)
                elif m == "CN":
                    for sfx in [".SS", ".SZ", ".SH"]:
                        code = code.replace(sfx, "")
                
                inferred = f"{m}:{kind}:{code}"
                if ':' in inferred:
                    canonical = inferred
                    print(f"  ✓ {raw_symbol} → {canonical} (启发式)")
            except Exception as e:
                print(f"  ✗ {raw_symbol} 启发式解析失败: {e}")
        
        # 添加到迁移计划
        if canonical and canonical != raw_symbol and ':' in canonical:
            migration_plan.append((raw_symbol, canonical))
        else:
            failed_resolution.append((raw_symbol, "无法推断典范ID"))
            print(f"  ✗ {raw_symbol} 无法解析")
    
    if not migration_plan:
        print("\n✅ 没有需要迁移的数据")
        conn.close()
        return
    
    print(f"\n准备迁移 {len(migration_plan)} 个symbol的数据...")
    
    # 3. 执行迁移
    for raw_symbol, canonical_id in migration_plan:
        # 统计
        count_old = cursor.execute(
            "SELECT COUNT(*) FROM vera_price_cache WHERE symbol = ?", 
            (raw_symbol,)
        ).fetchone()[0]
        
        print(f"\n迁移 {raw_symbol} → {canonical_id} ({count_old} 条记录)")
        
        # 更新symbol为典范ID（INSERT OR REPLACE会自动处理重复）
        cursor.execute("""
            INSERT OR REPLACE INTO vera_price_cache 
            (symbol, trade_date, open, high, low, close, volume, source)
            SELECT ?, trade_date, open, high, low, close, volume, source
            FROM vera_price_cache
            WHERE symbol = ?
        """, (canonical_id, raw_symbol))
        
        # 删除旧记录
        cursor.execute("DELETE FROM vera_price_cache WHERE symbol = ?", (raw_symbol,))
        
        print(f"  ✅ 完成")
    
    conn.commit()
    
    # 4. 最终报告
    print(f"\n✅ 迁移完成！")
    print(f"   - 成功迁移: {len(migration_plan)} 个symbol")
    if failed_resolution:
        print(f"   - 无法解析: {len(failed_resolution)} 个symbol")
        for sym, err in failed_resolution:
            print(f"     * {sym}: {err}")
    
    conn.close()

if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/Users/zhangzy/My Docs/Privates/22-AI编程/VERA')
    
    print("=" * 60)
    print("价格缓存数据去重与迁移")
    print("=" * 60)
    
    deduplicate_price_cache()
