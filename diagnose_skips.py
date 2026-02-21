
import pandas as pd
import numpy as np

def diagnose_skip(csv_path):
    df = pd.read_csv(csv_path)
    df.columns = [c.strip().lower() for c in df.columns]
    
    # Simulate csv_handler logic
    mapping = {
        'revenue': ['revenue', 'revenue_ttm', '营收', '营业收入'],
        'net_income': ['net_income', 'net_profit', 'net_income_ttm', 'net_profit_ttm', '净利润'],
        'total_assets': ['total_assets', '总资产', '资产总计']
    }
    
    def find_col(keys):
        for c in df.columns:
            if any(k in c for k in keys): return c
        return None
        
    rev_col = find_col(mapping['revenue'])
    ni_col = find_col(mapping['net_income'])
    asset_col = find_col(mapping['total_assets'])
    
    print(f"Detected columns: Rev={rev_col}, NI={ni_col}, Asset={asset_col}")
    
    skipped = 0
    skips = {} # Reason: Count
    
    for i, row in df.iterrows():
        rev = row.get(rev_col)
        ni = row.get(ni_col)
        ast = row.get(asset_col)
        
        # Check if values are effectively None or Empty
        def is_empty(v):
            return pd.isna(v) or str(v).strip() == '' or str(v).strip() == '-'
            
        # Actual check from csv_handler logic:
        # It checks if fh_data is empty. 
        # fh_data is derived from fh_raw (mapping)
        # In current code, it seems there is NO explicit any(...) skip anymore?
        # WAIT, let's check line 497: if fh_data:
        
        # In fh_raw, we have many fields. If all extracted fields are None, it skips.
        
        extracted = []
        if not is_empty(rev): extracted.append('rev')
        if not is_empty(ni): extracted.append('ni')
        if not is_empty(ast): extracted.append('ast')
        
        if not extracted:
            skipped += 1
            reason = "No basic info (Rev/NI/Asset)"
            skips[reason] = skips.get(reason, 0) + 1
            if i < 200 and 'amzn' in str(row[0]).lower():
                # print(f"Row {i+2} ({row[0]}): Skipped because all core metrics are empty.")
                pass
        
    print(f"Total rows: {len(df)}")
    print(f"Rows with NO core data: {skipped}")
    for r, c in skips.items():
        print(f"  - {r}: {c}")

if __name__ == "__main__":
    diagnose_skip('/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/imports/all_financials.csv')
