from engine.universe_manager import add_to_universe, get_universe_assets_v2
from db.connection import get_connection

def test_rename():
    # 1. Pick an asset (e.g. valid canonical ID)
    asset_id = "CN:STOCK:600309"
    new_name = "TestingRename"
    
    print(f"Updating {asset_id} to {new_name}...")
    
    # 2. Call add_to_universe with canonical ID as symbol
    add_to_universe(raw_symbol=asset_id, name=new_name, market="CN", asset_type="EQUITY")
    
    # 3. Check DB directly
    conn = get_connection()
    row = conn.execute("SELECT symbol_name FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    print(f"DB Value: {row[0]}")
    
    # 4. Check get_universe_assets_v2
    rows = get_universe_assets_v2()
    for r in rows:
        if r['asset_id'] == asset_id:
            print(f"Logic Value: {r['symbol_name']}")
            break
            
    conn.close()

if __name__ == "__main__":
    test_rename()
