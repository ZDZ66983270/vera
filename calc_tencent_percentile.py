
import pandas as pd

try:
    df = pd.read_csv('tencent_pe.csv', sep='|', header=None, names=['date', 'pe'])
    current_pe = 24.2  # From screenshot
    
    total = len(df)
    lower = df[df['pe'] < current_pe]
    lower_count = len(lower)
    
    percentile = (lower_count / total) * 100 if total > 0 else 0
    
    print(f"Total History Records: {total}")
    print(f"Date Range: {df['date'].min()} ~ {df['date'].max()}")
    print(f"Records < {current_pe}: {lower_count}")
    print(f"Calculated Percentile: {percentile:.2f}%")
    
    # Check stats
    print(f"Min PE: {df['pe'].min()}")
    print(f"Max PE: {df['pe'].max()}")
    print(f"Median PE: {df['pe'].median()}")
    
except Exception as e:
    print(str(e))
