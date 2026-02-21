import sqlite3
import os

def cleanup_market_and_financial_data():
    db_path = "vera.db"
    
    if not os.path.exists(db_path):
        print(f"错误: 找不到数据库文件 {db_path}")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 定义要清理的表
        tables_to_clear = [
            "vera_price_cache",           # 行情数据
            "financial_history",          # 财务历史
            "fundamentals_annual",        # 年度财务
            "fundamentals_facts"          # 财务事实
        ]
        
        print("开始清理行情和财报数据...")
        print("=" * 50)

        for table in tables_to_clear:
            # 检查表是否存在
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';")
            if not cursor.fetchone():
                print(f"⚠️  表 {table} 不存在，跳过")
                continue

            # 获取当前行数
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            before_count = cursor.fetchone()[0]
            
            # 执行清理
            cursor.execute(f"DELETE FROM {table}")
            
            # 获取清理后行数
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            after_count = cursor.fetchone()[0]
            
            print(f"✓ {table}")
            print(f"  清理前: {before_count:,} 行")
            print(f"  清理后: {after_count} 行")
            print("-" * 50)

        # 提交更改
        conn.commit()
        
        # 整理数据库空间
        print("正在整理数据库空间 (VACUUM)...")
        cursor.execute("VACUUM")
        print("=" * 50)
        print("✓ 清理完成")

    except sqlite3.Error as e:
        print(f"数据库错误: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    cleanup_market_and_financial_data()
