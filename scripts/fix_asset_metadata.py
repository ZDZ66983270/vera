import sqlite3

def fix_metadata():
    db_path = "vera.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Update Asset Types
    updates = [
        ("MSFT", "EQUITY", "Microsoft"),
        ("HSTECH", "INDEX", "Hang Seng TECH Index"),
        ("HSI", "INDEX", "Hang Seng Index"),
        ("09988.HK", "EQUITY", "Alibaba (HK)"),
        ("01919.HK", "EQUITY", "COSCO Shipping"),
        ("600309", "EQUITY", "Wanhua Chemical"),
        ("601919", "EQUITY", "COSCO Shipping (CN)"),
        ("601998", "EQUITY", "CITIC Bank (CN)"),
        ("2800.HK", "ETF", "Tracker Fund of Hong Kong"),
        ("3033.HK", "ETF", "Hang Seng TECH ETF"),
        ("WORLD:CRYPTO:BTC-USD", "CRYPTO", "Bitcoin"),
    ]
    
    print("Updating asset metadata...")
    for symbol, atype, name in updates:
        # Update type
        cursor.execute("UPDATE assets SET asset_type = ? WHERE asset_id = ?", (atype, symbol))
        # Update name if currently missing or placeholder
        cursor.execute("UPDATE assets SET symbol_name = ? WHERE asset_id = ? AND (symbol_name IS NULL OR symbol_name = '-' OR symbol_name = symbol_name)", (name, symbol))
        
    conn.commit()
    conn.close()
    print("✅ Asset metadata updated.")

if __name__ == "__main__":
    fix_metadata()
