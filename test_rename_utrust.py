from engine.universe_manager import add_to_universe, get_universe_assets_v2
from db.connection import get_connection

def test_rename_utrust():
    # Target the specific problematic asset
    asset_id = "US:UTRUST:0P00014FO3"
    new_name = "BlackRock System Analysis Fund"
    
    conn = get_connection()
    # Check current state
    curr = conn.execute("SELECT symbol_name FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    print(f"Current DB Name: {curr[0] if curr else 'Not Found'}")
    
    print(f"Updating {asset_id} to '{new_name}'...")
    
    # Update
    add_to_universe(raw_symbol=asset_id, name=new_name, market="US", asset_type="UTRUST")
    
    # Check DB directly
    row = conn.execute("SELECT symbol_name FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    print(f"New DB Value: {row[0]}")
    conn.close()
    
    # Check Logic
    rows = get_universe_assets_v2()
    found = False
    for r in rows:
        if r['asset_id'] == asset_id:
            print(f"Logic Value: {r['symbol_name']}")
            found = True
            break
    if not found:
        print("Logic: Asset not found in universe!")

if __name__ == "__main__":
    test_rename_utrust()
