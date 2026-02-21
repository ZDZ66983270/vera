from engine.universe_manager import add_to_universe, get_universe_assets_v2
from db.connection import get_connection

def revert_and_verify():
    asset_id = "CN:STOCK:600309"
    # Revert Name
    new_name = "万华化学"
    print(f"Reverting {asset_id} to '{new_name}'...")
    add_to_universe(raw_symbol=asset_id, name=new_name, market="CN", asset_type="EQUITY")
    
    # Verify Data
    rows = get_universe_assets_v2()
    for r in rows:
        if r['asset_id'] == asset_id:
            print(f"Asset: {r['symbol_name']}")
            print(f"Last Data Date: {r.get('last_data_date')}")
            print(f"Data Duration: {r.get('data_duration_years')} years")
            break

if __name__ == "__main__":
    revert_and_verify()
