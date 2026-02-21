#!/usr/bin/env python3
"""
财报日期修正脚本
将 financial_history 表中的非标准会计期末日期回溯到对应的会计期间截止日
"""

import sqlite3
from datetime import datetime
from pathlib import Path
import csv

def infer_period_end(report_date_str):
    """
    根据报告日期推断会计期末日期
    
    Args:
        report_date_str: 原始报告日期 (YYYY-MM-DD)
    
    Returns:
        推断的会计期末日期 (YYYY-MM-DD)
    """
    try:
        date = datetime.strptime(report_date_str, "%Y-%m-%d")
        year = date.year
        month = date.month
        
        # 规则：根据月份推断最可能的会计期间
        if month <= 4:
            # 1-4月发布 -> 可能是上一年年报(12-31)或当年一季报(03-31)
            # 优先一季报（4月通常已过一季报披露期）
            if month == 4:
                return f"{year}-03-31"
            else:
                return f"{year-1}-12-31"
        elif month <= 7:
            # 5-7月发布 -> 一季报(03-31)或半年报(06-30)
            # 优先半年报（7月通常已过半年报披露期）
            if month >= 6:
                return f"{year}-06-30"
            else:
                return f"{year}-03-31"
        elif month <= 10:
            # 8-10月发布 -> 半年报(06-30)或三季报(09-30)
            # 优先三季报
            if month >= 9:
                return f"{year}-09-30"
            else:
                return f"{year}-06-30"
        else:
            # 11-12月发布 -> 三季报(09-30)
            return f"{year}-09-30"
    except:
        return None

def get_db_connection():
    """获取数据库连接"""
    db_path = Path(__file__).parent.parent / "db" / "vera.db"
    return sqlite3.connect(db_path)

def scan_non_standard_dates(conn):
    """
    扫描非标准会计期末日期记录
    
    Returns:
        list of dict: 需要修正的记录 [{asset_id, old_date, inferred_date}, ...]
    """
    cursor = conn.cursor()
    
    # 查询所有非标准期末日期的记录
    sql = """
        SELECT DISTINCT asset_id, report_date
        FROM financial_history
        WHERE substr(report_date, 6) NOT IN ('03-31', '06-30', '09-30', '12-31')
        ORDER BY asset_id, report_date
    """
    
    cursor.execute(sql)
    results = []
    
    for row in cursor.fetchall():
        asset_id, old_date = row
        inferred_date = infer_period_end(old_date)
        if inferred_date:
            results.append({
                "asset_id": asset_id,
                "old_date": old_date,
                "inferred_date": inferred_date
            })
    
    return results

def preview_corrections(corrections):
    """
    打印修正预览
    
    Args:
        corrections: 修正列表
    """
    print("\n" + "="*80)
    print("修正预览 (Preview of Corrections)")
    print("="*80)
    
    if not corrections:
        print("✅ 所有日期均符合标准会计期末格式，无需修正。")
        return
    
    print(f"发现 {len(corrections)} 条需要修正的记录：\n")
    
    # 按公司分组显示
    asset_groups = {}
    for c in corrections:
        if c["asset_id"] not in asset_groups:
            asset_groups[c["asset_id"]] = []
        asset_groups[c["asset_id"]].append(c)
    
    for asset_id, records in asset_groups.items():
        print(f"📊 {asset_id}")
        for r in records:
            print(f"   {r['old_date']} → {r['inferred_date']}")
        print()

def backup_data(conn, corrections):
    """
    备份原始数据到临时表
    
    Args:
        conn: 数据库连接
        corrections: 修正列表
    """
    cursor = conn.cursor()
    
    # 创建备份表
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_table = f"financial_history_backup_{timestamp}"
    
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS {backup_table} AS
        SELECT * FROM financial_history WHERE 1=0
    """)
    
    # 插入要修改的记录
    for c in corrections:
        cursor.execute(f"""
            INSERT INTO {backup_table}
            SELECT * FROM financial_history
            WHERE asset_id = ? AND report_date = ?
        """, (c["asset_id"], c["old_date"]))
    
    conn.commit()
    print(f"✅ 已备份 {len(corrections)} 条记录到表: {backup_table}")
    return backup_table

def apply_corrections(conn, corrections, backup_table):
    """
    应用修正到数据库
    
    Args:
        conn: 数据库连接
        corrections: 修正列表
        backup_table: 备份表名
    """
    cursor = conn.cursor()
    success_count = 0
    
    for c in corrections:
        try:
            # 更新 report_date
            cursor.execute("""
                UPDATE financial_history
                SET report_date = ?
                WHERE asset_id = ? AND report_date = ?
            """, (c["inferred_date"], c["asset_id"], c["old_date"]))
            
            if cursor.rowcount > 0:
                success_count += 1
        except sqlite3.IntegrityError:
            # 如果目标日期已存在记录，跳过（避免主键冲突）
            print(f"⚠️  {c['asset_id']} 的 {c['inferred_date']} 已存在记录，跳过 {c['old_date']}")
    
    conn.commit()
    print(f"\n✅ 成功修正 {success_count} / {len(corrections)} 条记录")
    print(f"💾 可通过备份表 {backup_table} 进行回滚")

def save_correction_log(corrections, log_path):
    """
    保存修正日志到 CSV
    
    Args:
        corrections: 修正列表
        log_path: 日志文件路径
    """
    with open(log_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["asset_id", "old_date", "inferred_date"])
        writer.writeheader()
        writer.writerows(corrections)
    
    print(f"📄 修正日志已保存: {log_path}")

def main():
    """主函数"""
    print("\n" + "="*80)
    print("财报日期修正脚本 - Financial Report Date Correction")
    print("="*80 + "\n")
    
    conn = get_db_connection()
    
    try:
        # 1. 扫描需要修正的记录
        print("🔍 正在扫描非标准会计期末日期...")
        corrections = scan_non_standard_dates(conn)
        
        # 2. 预览修正
        preview_corrections(corrections)
        
        if not corrections:
            return
        
        # 3. 确认执行
        print("\n" + "-"*80)
        confirm = input("是否执行修正？(y/n): ").strip().lower()
        
        if confirm != 'y':
            print("❌ 用户取消操作")
            return
        
        # 4. 备份数据
        print("\n📦 正在备份原始数据...")
        backup_table = backup_data(conn, corrections)
        
        # 5. 应用修正
        print("\n🔧 正在应用修正...")
        apply_corrections(conn, corrections, backup_table)
        
        # 6. 保存日志
        log_path = Path(__file__).parent / f"report_date_corrections_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        save_correction_log(corrections, log_path)
        
        print("\n" + "="*80)
        print("✅ 修正完成！")
        print("="*80)
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()
