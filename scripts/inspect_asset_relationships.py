import sqlite3
import pandas as pd
from engine.asset_resolver import resolve_sector_context
from config import DEFAULT_MARKET_INDEX

def main():
    conn = sqlite3.connect("vera.db")
    
    # 1. Get all assets that have some classification OR are just Equities
    # For now, let's focus on those in asset_classification to show the explicit mappings
    # AND some example unmapped ones if needed.
    # The user asked for "correspondence", so clearly established links are most important.
    
    query = """
    SELECT DISTINCT asset_id 
    FROM asset_classification 
    WHERE is_active = 1
    """
    
    try:
        classified_assets = [r[0] for r in conn.execute(query).fetchall()]
    except Exception as e:
        print(f"Error querying asset_classification: {e}")
        classified_assets = []
    
    if not classified_assets:
        print("No assets found in asset_classification table.")
        # Fallback: just pick some random equities from assets
        print("Falling back to sample equities from assets table...")
        query_assets = "SELECT id FROM assets WHERE region IS NOT NULL LIMIT 10"
        classified_assets = [r[0] for r in conn.execute(query_assets).fetchall()]

    conn.close()

    if not classified_assets:
        print("No equities found in DB.")
        return

    results = []
    for asset_id in classified_assets:
        try:
            ctx = resolve_sector_context(asset_id)
            # Fetch name for display nicely
            # (Context doesn't have asset name, we can fetch it or ignore)
            results.append({
                "Asset": asset_id,
                "Sector": f"{ctx.sector_name} ({ctx.sector_code})" if ctx.sector_name else "-",
                "Sector ETF": ctx.proxy_etf_id or "-",
                "Market Index": ctx.market_index_id or "-",
                "Growth Proxy": ctx.growth_proxy,
                "Value Proxy": ctx.value_proxy
            })
        except Exception as e:
            print(f"Error resolving {asset_id}: {e}")

    df = pd.DataFrame(results)
    if not df.empty:
        print("### 🔗 Asset ↔ Sector ETF ↔ Market Index Mappings")
        print(df.to_markdown(index=False))
    else:
        print("No mappings generated.")

if __name__ == "__main__":
    main()
