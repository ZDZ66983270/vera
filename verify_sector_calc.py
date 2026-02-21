from analysis.sector_overlay import build_sector_overlay
from engine.asset_resolver import resolve_sector_context
from datetime import datetime

def verify_sector_overlay(symbol):
    print(f"Verifying sector overlay for {symbol}...")
    
    # 1. Resolve Sector Context
    today = datetime.now().strftime("%Y-%m-%d")
    ctx = resolve_sector_context(symbol, as_of_date=today)
    
    if not ctx:
        print("Failed to resolve sector context.")
        return

    print(f"Sector: {ctx.sector_name}")
    print(f"Proxy ETF: {ctx.proxy_etf_id}")
    
    if not ctx.proxy_etf_id:
        print("No Proxy ETF identified.")
        return

    # DEBUG: Check price data
    from data.price_cache import load_price_series
    import pandas as pd
    end = pd.to_datetime(datetime.now().strftime("%Y-%m-%d"))
    start = (end - pd.Timedelta(days=10 * 365)).strftime("%Y-%m-%d")
    prices = load_price_series(ctx.proxy_etf_id, start, end.strftime("%Y-%m-%d"))
    if prices is None:
        print(f"Prices for {ctx.proxy_etf_id} is None")
    elif prices.empty:
        print(f"Prices for {ctx.proxy_etf_id} is Empty")
    else:
        print(f"Prices for {ctx.proxy_etf_id}: {len(prices)} rows")
        print(f"Date Range: {prices.index.min()} to {prices.index.max()}")
        
    # 2. Build Overlay
    try:
        overlay = build_sector_overlay(
            asset_id=symbol,
            as_of_date=today,
            proxy_etf_id=ctx.proxy_etf_id,
            sector_name=ctx.sector_name,
            market_index_id="^GSPC", # Placeholder
            snapshot_id="DEBUG_TEST"
        )
        
        print("\n--- Overlay Result ---")
        print(f"Sector Position Pct: {overlay.get('sector_position_pct')}")
        print(f"Sector State: {overlay.get('sector_dd_state')}")
        
    except Exception as e:
        print(f"Error building overlay: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_sector_overlay("CN:STOCK:600036")
