import pandas as pd
from engine.snapshot_builder import run_overlay_rules

def test_enhanced_attribution_rules():
    print("Testing Enhanced Three-Layer Risk Attribution Logic...")
    
    # Scene 1: Sector drag (Stock follows weak sector)
    ind1 = {"ind_dd_state": "D4", "ind_path_risk": "MID"}
    sec1 = {"sector_dd_state": "D4", "stock_vs_sector_rs_3m": -0.01, "sector_vs_market_rs_3m": -0.08}
    mkt1 = {"market_dd_state": "D0", "market_path_risk": "LOW"}
    
    summary1, flags1 = run_overlay_rules(ind1, sec1, mkt1)
    print(f"\nScenario 1: Sector Drag")
    print(f"  Summary: {summary1}")
    print(f"  Flags: {[f['code'] for f in flags1]}")
    if "DIV_SECTOR_MKT_NEG" in [f['code'] for f in flags1]:
        print("  ✓ Correctly identified SECTOR drag vs market.")

    # Scene 2: Stock outlier in strong sector (Strong Sector, Weak Stock)
    ind2 = {"ind_dd_state": "D4", "ind_path_risk": "MID"}
    sec2 = {"sector_dd_state": "D0", "stock_vs_sector_rs_3m": -0.15, "sector_vs_market_rs_3m": 0.08}
    mkt2 = {"market_dd_state": "D0", "market_path_risk": "LOW"}
    
    summary2, flags2 = run_overlay_rules(ind2, sec2, mkt2)
    print(f"\nScenario 2: Individual Weakness in Strong Sector")
    print(f"  Summary: {summary2}")
    print(f"  Flags: {[f['code'] for f in flags2]}")
    if "DIV_STOCK_SECTOR_NEG" in [f['code'] for f in flags2] and "DIV_SECTOR_MKT_POS" in [f['code'] for f in flags2]:
        print("  ✓ Correctly identified Individual outlier.")
    
    # Scene 3: Strong stock in weak market/sector (Alpha)
    ind3 = {"ind_dd_state": "D0", "ind_path_risk": "LOW"}
    sec3 = {"sector_dd_state": "D4", "stock_vs_sector_rs_3m": 0.12, "sector_vs_market_rs_3m": -0.06}
    mkt3 = {"market_dd_state": "D0", "market_path_risk": "LOW"}
    
    summary3, flags3 = run_overlay_rules(ind3, sec3, mkt3)
    print(f"\nScenario 3: Alpha Outlier (Strong Stock, Weak Sector)")
    print(f"  Summary: {summary3}")
    print(f"  Flags: {[f['code'] for f in flags3]}")
    if "DIV_STOCK_SECTOR_POS" in [f['code'] for f in flags3]:
        print("  ✓ Correctly identified Alpha strength.")

if __name__ == "__main__":
    test_enhanced_attribution_rules()
