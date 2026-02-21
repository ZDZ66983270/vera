
from engine.asset_resolver import resolve_sector_context
from analysis.market_regime import build_market_regime
from datetime import datetime

def debug_resolver():
    asset_id = "00005.HK"
    as_of_date = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Resolve Context
    print(f"Resolving context for {asset_id}...")
    ctx = resolve_sector_context(asset_id, as_of_date)
    print(f"Context Result: {ctx}")
    print(f"Sector: {ctx.sector_name}")
    print(f"Proxy: {ctx.proxy_etf_id}")
    print(f"Market Index: {ctx.market_index_id}")
    
    target_market = ctx.market_index_id or "^GSPC"
    print(f"Target Market for Regime: {target_market}")

    # 2. Build Regime
    print(f"Building regime for {target_market}...")
    regime = build_market_regime(as_of_date, asset_id=target_market)
    print(f"Regime Label: {regime.get('market_index')}")

if __name__ == "__main__":
    debug_resolver()
