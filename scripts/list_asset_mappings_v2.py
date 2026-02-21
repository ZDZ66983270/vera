import sqlite3
import pandas as pd

DB_PATH = "vera.db"

def list_mappings():
    conn = sqlite3.connect(DB_PATH)
    
    # 1. Get ALL assets that are stocks
    query_assets = "SELECT asset_id, symbol_name, market FROM assets WHERE asset_type IN ('stock', 'EQUITY')"
    df_assets = pd.read_sql_query(query_assets, conn)
    
    # 2. Get LATEST classifications
    query_ac = """
    SELECT asset_id, scheme, sector_code, sector_name, MAX(as_of_date)
    FROM asset_classification
    WHERE is_active = 1
    GROUP BY asset_id, scheme
    """
    df_ac = pd.read_sql_query(query_ac, conn)
    
    # 3. Get Sector Proxy Map
    query_sp = "SELECT * FROM sector_proxy_map WHERE is_active = 1"
    df_sp = pd.read_sql_query(query_sp, conn)
    
    conn.close()
    
    # Merge and Filter
    results = []
    
    for _, asset in df_assets.iterrows():
        aid = asset['asset_id']
        mkt = asset['market']
        name = asset['symbol_name']
        
        # Find classification
        asset_class = df_ac[df_ac['asset_id'] == aid]
        if asset_class.empty:
            continue
            
        for _, ac_row in asset_class.iterrows():
            scheme = ac_row['scheme']
            scode = ac_row['sector_code']
            sname = ac_row['sector_name']
            
            # Find proxies
            proxies = df_sp[(df_sp['scheme'] == scheme) & (df_sp['sector_code'] == scode)]
            
            for _, sp_row in proxies.iterrows():
                proxy_etf = sp_row['proxy_etf_id']
                mkt_idx = sp_row['market_index_id']
                note = str(sp_row['note']).lower()
                
                # Heuristic Filter to avoid cross-market noise
                skip = False
                if mkt == 'US':
                    if 'cn ' in note or 'hk ' in note: skip = True
                    if mkt_idx and any(cn in str(mkt_idx) for cn in ['指数', '.SS', '.SZ']): skip = True
                elif mkt == 'CN':
                    if 'us ' in note or 'hk ' in note: skip = True
                    if mkt_idx and any(us in str(mkt_idx).upper() for us in ['SPX', 'NDX', 'DJI', '^']): skip = True
                elif mkt == 'HK':
                    # For HK, we prefer HK_USER scheme or specific HK notes
                    if scheme != 'HK_USER' and 'hk ' not in note: skip = True
                
                if not skip:
                    results.append({
                        "市场": mkt,
                        "个股 ID": aid,
                        "名称": name,
                        "行业": sname,
                        "对标 ETF": proxy_etf,
                        "市场指数": mkt_idx
                    })

    df_final = pd.DataFrame(results).drop_duplicates()
    
    if df_final.empty:
        print("未找到符合筛选条件的对应关系。")
        return

    # Group by market for better display
    for market, group in df_final.groupby("市场"):
        print(f"\n===== {market} 市场 =====")
        display_df = group.drop(columns=["市场"])
        print(display_df.to_markdown(index=False))

if __name__ == "__main__":
    list_mappings()
