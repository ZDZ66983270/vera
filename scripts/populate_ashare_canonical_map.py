#!/usr/bin/env python3
"""
Populate asset_symbol_map with A-share canonical mappings
Maps .SS and .SH suffixes to base symbol (canonical)
"""
import sqlite3
from datetime import datetime

DB_PATH = "vera.db"

# A-share mappings: both .SS and .SH → base symbol
mappings = [
    # 600309 - 万华化学
    {"canonical_id": "600309", "symbol": "600309.SS", "source": "ashare_map", "priority": 10},
    {"canonical_id": "600309", "symbol": "600309.SH", "source": "ashare_map", "priority": 10},
    
    # 601919 - 中远海控
    {"canonical_id": "601919", "symbol": "601919.SS", "source": "ashare_map", "priority": 10},
    {"canonical_id": "601919", "symbol": "601919.SH", "source": "ashare_map", "priority": 10},
    
    # 601998 - 中信银行
    {"canonical_id": "601998", "symbol": "601998.SS", "source": "ashare_map", "priority": 10},
    {"canonical_id": "601998", "symbol": "601998.SH", "source": "ashare_map", "priority": 10},
    
    # 000001 - 平安银行
    {"canonical_id": "000001", "symbol": "000001.SS", "source": "ashare_map", "priority": 10},
    {"canonical_id": "000001", "symbol": "000001.SZ", "source": "ashare_map", "priority": 10},
]

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for m in mappings:
        cursor.execute("""
            INSERT INTO asset_symbol_map (canonical_id, symbol, source, priority, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(canonical_id, symbol) DO UPDATE SET
                source = excluded.source,
                priority = excluded.priority,
                updated_at = excluded.updated_at
        """, (m["canonical_id"], m["symbol"], m["source"], m["priority"], timestamp, timestamp))
        print(f"✓ Mapped {m['symbol']} → {m['canonical_id']}")
    
    conn.commit()
    conn.close()
    print(f"\n✅ Successfully created {len(mappings)} A-share canonical mappings")

if __name__ == "__main__":
    main()
