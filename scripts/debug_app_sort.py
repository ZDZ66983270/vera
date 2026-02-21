
import sys
import os
sys.path.append(os.getcwd())
import re
from engine.universe_manager import get_universe_assets_v2

def debug_sort():
    print("Fetching Universe...")
    universe_df = get_universe_assets_v2()
    print(f"Fetched {len(universe_df)} assets.")
    
    # 3. Stable Sorting Logic (Copied from app.py)
    asset_meta_map = {row['asset_id']: row for row in universe_df}
    
    def get_sort_key(s):
        s_u = s.upper()
        meta = asset_meta_map.get(s)
        
        m_o = 3
        m = meta.get('market') if meta else None
        
        # In app.py this fallback exists:
        if not m:
            # from engine.asset_resolver import _infer_market
            # m = _infer_market(s)
            pass 

        if m == 'HK': m_o = 0
        elif m == 'US': m_o = 1
        elif m == 'CN': m_o = 2
        
        t_o = 3
        t = meta.get('asset_type') if meta else None
        
        # In app.py fallback exists:
        if not t:
            if (":INDEX:" in s_u or s_u in ['HSI', 'HSTECH', 'SPX', 'NDX', 'DJI']): t = 'INDEX'
            elif (":ETF:" in s_u) or (":STOCK:" in s_u and s_u.split(":")[-1].startswith(("51", "15", "58"))): t = 'ETF'
            else: t = 'EQUITY'
            
        if t in ['EQUITY', 'STOCK']: t_o = 0  # 个股优先
        elif t == 'ETF': t_o = 1              # ETF次之
        elif t == 'INDEX': t_o = 2            # 指数最后
        
        d = re.findall(r'\d+', s)
        if d:
            code_part = d[-1]
            if m == 'HK': code_part = code_part.zfill(5)
            try: return (m_o, t_o, 0, int(code_part))
            except: pass
        return (m_o, t_o, 1, s_u)

    print("\n--- Testing Sort Keys ---")
    test_ids = ["US:STOCK:AAPL", "HK:STOCK:00005", "CN:STOCK:600519", "US:STOCK:TSLA"]
    
    # Also check what keys are in map
    print(f"Available Keys Sample: {list(asset_meta_map.keys())[:5]}")
    
    results = []
    for tid in test_ids:
        key = get_sort_key(tid)
        meta = asset_meta_map.get(tid)
        m = meta['market'] if meta else "MISSING"
        print(f"[{tid}] Market: {m} -> Key: {key}")
        results.append((tid, key))
        
    print("\nSorted Order:")
    for tid, key in sorted(results, key=lambda x: x[1]):
        print(tid)

    print("\n--- Inspecting Asset Universe IDs ---")
    from db.connection import get_connection
    conn = get_connection()
    u_rows = conn.execute("SELECT asset_id FROM asset_universe LIMIT 20").fetchall()
    print([r[0] for r in u_rows])
    conn.close()

if __name__ == "__main__":
    debug_sort()
