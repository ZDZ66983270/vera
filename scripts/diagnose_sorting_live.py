
import sys
import os
sys.path.append(os.getcwd())
import re
from engine.universe_manager import get_universe_assets_v2
from engine.asset_resolver import _infer_market

def diagnose():
    print("--- 1. Verification of Data Source ---")
    universe_df = get_universe_assets_v2()
    asset_meta_map = {row['asset_id']: row for row in universe_df}
    
    print(f"Loaded {len(asset_meta_map)} assets.")
    
    # Check specific assets
    targets = ["HK:STOCK:00005", "US:STOCK:AAPL", "HK:STOCK:00700"]
    for t in targets:
        if t in asset_meta_map:
            print(f"[{t}] Found in map. Market raw: '{asset_meta_map[t].get('market')}'")
        else:
            print(f"[{t}] NOT found in map.")

    print("\n--- 2. Sort Key Logic Simulation ---")
    def get_sort_key(s):
        s_u = s.upper()
        meta = asset_meta_map.get(s)
        
        m_o = 3
        m = meta.get('market') if meta else None
        
        if not m:
            m = _infer_market(s)
            
        print(f"   > [{s}] m='{m}'")

        if m == 'HK': m_o = 0
        elif m == 'US': m_o = 1
        elif m == 'CN': m_o = 2
        
        t_o = 3
        t = meta.get('asset_type') if meta else None
        
        if not t:
            if (":INDEX:" in s_u or s_u in ['HSI', 'HSTECH', 'SPX', 'NDX', 'DJI']): t = 'INDEX'
            elif (":ETF:" in s_u) or (":STOCK:" in s_u and s_u.split(":")[-1].startswith(("51", "15", "58"))): t = 'ETF'
            else: t = 'EQUITY'
            
        if t in ['EQUITY', 'STOCK']: t_o = 0 
        elif t == 'ETF': t_o = 1             
        elif t == 'INDEX': t_o = 2           
        
        d = re.findall(r'\d+', s)
        if d:
            code_part = d[-1]
            if m == 'HK': code_part = code_part.zfill(5)
            try: return (m_o, t_o, 0, int(code_part))
            except: pass
        
        return (m_o, t_o, 1, s_u)

    print("Sorting targets...")
    sorted_targets = sorted(targets, key=get_sort_key)
    print("\n--- Resulting Order ---")
    for t in sorted_targets:
        print(t)

if __name__ == "__main__":
    diagnose()
