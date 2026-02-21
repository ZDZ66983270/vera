import sqlite3

DB_PATH = "vera.db"

def migrate_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("--- Migrating Assets Table ---")
    
    # 1. Standardize CN Stocks in assets table
    cursor.execute("SELECT asset_id, symbol_name FROM assets WHERE asset_id LIKE '%.SH' OR asset_id LIKE '%.SZ' OR asset_id LIKE '%.SS'")
    cn_legacy = cursor.fetchall()
    for aid, name in cn_legacy:
        code = aid.split('.')[0]
        # Heuristic to distinguish INDEX vs STOCK for legacy
        # In this project, 000xxx.SS is usually index, 60xxxx.SH is stock
        atype = "INDEX" if (code.startswith("000") and aid.endswith(".SS")) else "STOCK"
        new_id = f"CN:{atype}:{code}"
        
        # Check if already exists
        exists = cursor.execute("SELECT 1 FROM assets WHERE asset_id = ?", (new_id,)).fetchone()
        if exists:
            # Transfer anything important? For now just delete legacy
            cursor.execute("DELETE FROM assets WHERE asset_id = ?", (aid,))
            print(f"Deleted legacy CN asset {aid} (kept {new_id})")
        else:
            cursor.execute("UPDATE assets SET asset_id = ?, market='CN', asset_type=? WHERE asset_id = ?", (new_id, atype, aid))
            print(f"Standardized {aid} -> {new_id}")

    # 2. Standardize HK Stocks in assets table
    # Standard format: HK:STOCK:00700 (5 digits)
    cursor.execute("SELECT asset_id FROM assets WHERE asset_id LIKE '%.HK' OR asset_id LIKE 'HK:STOCK:%'")
    hk_assets = cursor.fetchall()
    for (aid,) in hk_assets:
        code = aid.replace('HK:STOCK:', '').replace('.HK', '')
        if code.isdigit():
            new_id = f"HK:STOCK:{code.zfill(5)}"
            if aid != new_id:
                # Check for collisions
                exists = cursor.execute("SELECT 1 FROM assets WHERE asset_id = ?", (new_id,)).fetchone()
                if exists:
                    cursor.execute("DELETE FROM assets WHERE asset_id = ?", (aid,))
                    print(f"Deleted duplicate HK asset {aid} (kept {new_id})")
                else:
                    cursor.execute("UPDATE assets SET asset_id = ? WHERE asset_id = ?", (new_id, aid))
                    print(f"Renamed {aid} -> {new_id}")

    # 3. Create missing US index records if needed or fix them
    # Ensure SPX, NDX, DJI are US and INDEX
    indices = [('SPX', 'S&P 500'), ('NDX', 'Nasdaq 100'), ('DJI', 'Dow Jones')]
    for aid, name in indices:
        cursor.execute("UPDATE assets SET market='US', asset_type='INDEX' WHERE asset_id=?", (aid,))
        if cursor.rowcount == 0:
            cursor.execute("INSERT INTO assets (asset_id, symbol_name, market, asset_type) VALUES (?, ?, 'US', 'INDEX')", (aid, name))
            print(f"Inserted US index {aid}")
        else:
            print(f"Updated US index {aid}")

    print("\n--- Migrating Price Cache Table ---")
    
    # Standardize symbols in price cache
    # This is a big one. We'll do it in chunks or pattern by pattern.
    
    # CN: 123456.SH or 123456.SZ -> CN:STOCK:123456
    # Note: We need to know if it's index or stock. 
    # For now, let's assume if it exists in assets, we use that type.
    
    # Step 1: CN Stocks/Indices
    cursor.execute("SELECT DISTINCT symbol FROM vera_price_cache WHERE symbol LIKE '%.SH' OR symbol LIKE '%.SZ' OR symbol LIKE '%.SS'")
    symbols = cursor.fetchall()
    for (sym,) in symbols:
        code = sym.split('.')[0]
        # Resolve to standard ID using assets table as source of truth
        cursor.execute("SELECT asset_id FROM assets WHERE asset_id LIKE ? AND asset_id LIKE '%:' || ?", ('CN:%', code))
        row = cursor.fetchone()
        
        if not row:
            # Fallback heuristic
            atype = "INDEX" if (code.startswith("000") and sym.endswith(".SS")) else "STOCK"
            new_id = f"CN:{atype}:{code}"
        else:
            new_id = row[0]
        
        # Merge records: If new_id already has trade_date, DELETE the legacy one or let OR REPLACE handle it?
        # ON CONFLICT in vera_price_cache is (symbol, trade_date).
        # We need to handle potential conflicts during update.
        
        # Strategy: Select legacy records, INSERT OR REPLACE into new_id, then DELETE legacy.
        cursor.execute("SELECT trade_date, open, high, low, close, volume, source FROM vera_price_cache WHERE symbol = ?", (sym,))
        rows = cursor.fetchall()
        for r in rows:
            cursor.execute("""
                INSERT INTO vera_price_cache (symbol, trade_date, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, trade_date) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, volume=excluded.volume, source=excluded.source
            """, (new_id, *r))
        
        cursor.execute("DELETE FROM vera_price_cache WHERE symbol = ?", (sym,))
        print(f"PriceCache: Migrated {sym} -> {new_id} ({len(rows)} rows)")

    # Step 2: HK Stocks
    cursor.execute("SELECT DISTINCT symbol FROM vera_price_cache WHERE symbol LIKE '%.HK'")
    symbols = cursor.fetchall()
    for (sym,) in symbols:
        code = sym.split('.')[0]
        new_id = f"HK:STOCK:{code.zfill(5)}"
        
        cursor.execute("SELECT trade_date, open, high, low, close, volume, source FROM vera_price_cache WHERE symbol = ?", (sym,))
        rows = cursor.fetchall()
        for r in rows:
            cursor.execute("""
                INSERT INTO vera_price_cache (symbol, trade_date, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, trade_date) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, volume=excluded.volume, source=excluded.source
            """, (new_id, *r))
            
        cursor.execute("DELETE FROM vera_price_cache WHERE symbol = ?", (sym,))
        print(f"PriceCache: Migrated {sym} -> {new_id} ({len(rows)} rows)")

    # Step 3: US Indices (^GSPC, ^NDX, ^DJI, etc)
    cursor.execute("SELECT DISTINCT symbol FROM vera_price_cache WHERE symbol LIKE '^%'")
    symbols = cursor.fetchall()
    mappings = {
        '^GSPC': 'SPX',
        '^NDX': 'NDX',
        '^DJI': 'DJI',
        '^HSI': 'HSI',
        '^HSTECH': 'HSTECH'
    }
    for (old_sym,) in symbols:
        new_id = mappings.get(old_sym, old_sym.replace('^', ''))
        
        cursor.execute("SELECT trade_date, open, high, low, close, volume, source FROM vera_price_cache WHERE symbol = ?", (old_sym,))
        rows = cursor.fetchall()
        for r in rows:
            cursor.execute("""
                INSERT INTO vera_price_cache (symbol, trade_date, open, high, low, close, volume, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(symbol, trade_date) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close, volume=excluded.volume, source=excluded.source
            """, (new_id, *r))
            
        cursor.execute("DELETE FROM vera_price_cache WHERE symbol = ?", (old_sym,))
        print(f"PriceCache: Migrated {old_sym} -> {new_id} ({len(rows)} rows)")

    print("\n--- Cleaning up duplicates in Price Cache (if any) ---")
    # This is tricky without a temporary table if trade_date constraint is violated.
    # Actually ON CONFLICT during update isn't possible in SQLite UPDATE.
    # Let's just do a simple deduplication if needed.
    
    print("\n--- Updating asset_classification ---")
    cursor.execute("SELECT DISTINCT asset_id FROM asset_classification")
    ac_assets = cursor.fetchall()
    for (old_aid,) in ac_assets:
        try:
            # Re-use standardized IDs logic
            if old_aid.endswith(".HK"):
                new_id = f"HK:STOCK:{old_aid.split('.')[0].zfill(5)}"
            elif old_aid.endswith((".SS", ".SZ", ".SH")):
                code = old_aid.split('.')[0]
                atype = "INDEX" if (code.startswith("000") and old_aid.endswith(".SS")) else "STOCK"
                new_id = f"CN:{atype}:{code}"
            else:
                new_id = old_aid
            
            if old_aid != new_id:
                cursor.execute("UPDATE asset_classification SET asset_id = ? WHERE asset_id = ?", (new_id, old_aid))
                print(f"Classification: {old_aid} -> {new_id}")
        except Exception as e:
            print(f"Error migrating classification {old_aid}: {e}")

    print("\n--- Updating sector_proxy_map ---")
    # market_index_id might use legacy format
    cursor.execute("SELECT DISTINCT market_index_id FROM sector_proxy_map WHERE market_index_id IS NOT NULL")
    indices = cursor.fetchall()
    for (old_idx,) in indices:
        if old_idx == "000300.SS":
            new_idx = "CN:INDEX:000300"
        elif old_idx == "^GSPC":
            new_idx = "SPX"
        elif old_idx == "HSI":
            new_idx = "HSI" # Standardized
        else:
            new_idx = old_idx
            
        if old_idx != new_idx:
            cursor.execute("UPDATE sector_proxy_map SET market_index_id = ? WHERE market_index_id = ?", (new_idx, old_idx))
            print(f"SectorProxy: {old_idx} -> {new_idx}")

    print("\n--- Updating asset_symbol_map ---")
    cursor.execute("SELECT canonical_id, symbol FROM asset_symbol_map")
    rows = cursor.fetchall()
    for cid, sym in rows:
        new_cid = cid
        if cid.endswith(".HK"):
            new_cid = f"HK:STOCK:{cid.split('.')[0].zfill(5)}"
        elif cid.endswith((".SS", ".SZ", ".SH")):
            code = cid.split('.')[0]
            atype = "INDEX" if (code.startswith("000") and cid.endswith(".SS")) else "STOCK"
            new_cid = f"CN:{atype}:{code}"
        elif cid == "^GSPC":
            new_cid = "SPX"
        elif cid == "^NDX":
            new_cid = "NDX"
        elif cid == "^DJI":
            new_cid = "DJI"
            
        if cid != new_cid:
            # Handle unique constraint by DELETE then INSERT or REPLACE
            cursor.execute("SELECT source, priority, is_active, note FROM asset_symbol_map WHERE canonical_id=? AND symbol=?", (cid, sym))
            info = cursor.fetchone()
            cursor.execute("DELETE FROM asset_symbol_map WHERE canonical_id=? AND symbol=?", (cid, sym))
            cursor.execute("""
                INSERT OR REPLACE INTO asset_symbol_map (canonical_id, symbol, source, priority, is_active, note)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (new_cid, sym, *info))
            print(f"SymbolMap: {cid} -> {new_cid} (sym: {sym})")

    conn.commit()
    conn.close()
    print("\nMigration Complete.")

if __name__ == "__main__":
    migrate_database()
