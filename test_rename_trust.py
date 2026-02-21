from engine.universe_manager import add_to_universe, get_universe_assets_v2
from db.connection import get_connection

def test_rename_trust():
    # Target the newly migrated asset
    asset_id = "US:TRUST:0P00014FO3"
    new_name = "BlackRock Verified Trust Fund"
    
    conn = get_connection()
    # Check current state (Should be migrated)
    curr = conn.execute("SELECT symbol_name, asset_type FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    if not curr:
        print(f"Error: Asset {asset_id} not found! Migration might have failed.")
        return
        
    print(f"Current DB Name: {curr[0]}, Type: {curr[1]}")
    
    print(f"Updating {asset_id} to '{new_name}'...")
    
    # Update using canonical ID
    add_to_universe(raw_symbol=asset_id, name=new_name, market="US", asset_type="TRUST")
    
    # Check DB directly
    row = conn.execute("SELECT symbol_name, asset_type FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    print(f"New DB Value: {row[0]}, Type: {row[1]}")
    conn.close()
    
    # Check Logic
    rows = get_universe_assets_v2()
    found = False
    for r in rows:
        if r['asset_id'] == asset_id:
            print(f"Logic Value: {r['symbol_name']}, Type: {r['asset_type']}")
            found = True
            break
    if not found:
        print("Logic: Asset not found in universe!")

if __name__ == "__main__":
    test_rename_trust()
