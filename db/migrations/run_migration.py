#!/usr/bin/env python3
"""
数据库迁移脚本执行器
运行数据来源追踪字段的迁移
"""

import sqlite3
import os
from pathlib import Path

def run_migration():
    """执行数据库迁移"""
    # 数据库路径
    db_path = Path(__file__).parent.parent / "vera.db"
    migration_file = Path(__file__).parent / "001_add_data_source_tracking.sql"
    
    if not db_path.exists():
        print(f"❌ 数据库文件不存在: {db_path}")
        return False
    
    if not migration_file.exists():
        print(f"❌ 迁移文件不存在: {migration_file}")
        return False
    
    print(f"📂 数据库路径: {db_path}")
    print(f"📄 迁移文件: {migration_file}")
    
    # 读取迁移SQL
    with open(migration_file, 'r', encoding='utf-8') as f:
        migration_sql = f.read()
    
    # 连接数据库
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(financial_history)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'data_source' in columns:
            print("⚠️  字段已存在，跳过迁移")
            return True
        
        # 执行迁移
        print("🚀 开始执行迁移...")
        
        # 分割SQL语句并逐条执行
        statements = [s.strip() for s in migration_sql.split(';') if s.strip() and not s.strip().startswith('--')]
        
        for i, statement in enumerate(statements, 1):
            if statement:
                print(f"  [{i}/{len(statements)}] 执行: {statement[:50]}...")
                cursor.execute(statement)
        
        conn.commit()
        print("✅ 迁移成功完成！")
        
        # 验证
        cursor.execute("PRAGMA table_info(financial_history)")
        new_columns = [row[1] for row in cursor.fetchall()]
        
        expected_fields = ['data_source', 'import_timestamp', 'imported_by', 'source_file_name', 'source_confidence']
        for field in expected_fields:
            if field in new_columns:
                print(f"  ✓ {field}")
            else:
                print(f"  ✗ {field} (缺失)")
        
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    exit(0 if success else 1)
