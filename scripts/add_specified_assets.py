import sys
import os
import sqlite3

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

try:
    from db.connection import get_connection
    from engine.universe_manager import add_to_universe
except ImportError:
    # Fallback
    sys.path.append(os.getcwd())
    from db.connection import get_connection
    from engine.universe_manager import add_to_universe

def add_assets():
    print("Adding specified assets...")
    
    # 1. Get benchmark info for reference assets
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get TSM benchmarks
    cursor.execute("SELECT sector_proxy_id, market_index_id FROM asset_universe WHERE asset_id='US:STOCK:TSM'")
    tsm_row = cursor.fetchone()
    tsm_etf = tsm_row[0] if tsm_row else None
    tsm_index = tsm_row[1] if tsm_row else None
    print(f"TSM Benchmarks: ETF={tsm_etf}, Index={tsm_index}")
    
    # Get 0P00014FO3 benchmarks
    cursor.execute("SELECT sector_proxy_id, market_index_id FROM asset_universe WHERE asset_id='US:TRUST:0P00014FO3'")
    trust_row = cursor.fetchone()
    trust_etf = trust_row[0] if trust_row else None
    trust_index = trust_row[1] if trust_row else None
    print(f"Reference Trust Benchmarks: ETF={trust_etf}, Index={trust_index}")
    
    conn.close()

    # 2. Add US:STOCK:MU (Micron Technology)
    # Match TSM
    print("\nAdding US:STOCK:MU...")
    add_to_universe(
        raw_symbol="MU",
        source_id="yahoo",
        name="美光科技",
        market="US",
        asset_type="STOCK",
        benchmark_etf=tsm_etf,
        benchmark_index=tsm_index
    )
    
    # 3. Add US:TRUST:0P00000B12 (Franklin Income)
    # Match 0P00014FO3
    print("\nAdding US:TRUST:0P00000B12...")
    add_to_universe(
        raw_symbol="0P00000B12",
        source_id="yahoo",
        name="富兰克林入息基金MDis",
        market="US",
        asset_type="TRUST", # Or FUND? implied TRUST from ID
        benchmark_etf=trust_etf,
        benchmark_index=trust_index
    )

    # 4. Add US:TRUST:0P0001T7E6 (PIMCO Income)
    # Match 0P00014FO3
    print("\nAdding US:TRUST:0P0001T7E6...")
    add_to_universe(
        raw_symbol="0P0001T7E6",
        source_id="yahoo",
        name="PIMCO收益增长基金",
        market="US",
        asset_type="TRUST",
        benchmark_etf=trust_etf,
        benchmark_index=trust_index
    )
    
    print("\nDone adding assets.")

if __name__ == "__main__":
    add_assets()
