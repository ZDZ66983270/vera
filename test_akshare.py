
import akshare as ak
import pandas as pd

symbol = "600030" # 中信证券

print(f"--- Fetching Financials for {symbol} ---")
try:
    # 新浪财经-财务报表-利润表
    # update: stock_financial_report_sina might be unstable. 
    # Let's try EastMoney: stock_financial_abstract
    # Or AkShare's specific financial sheet interfaces
    
    # 尝试 1: 新浪 (通常包含完整历史)
    # df = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
    # print(df.head())
    
    # 尝试 2: 东方财富-个股-财务指标-主要财务指标
    # stock_financial_analysis_indicator_em(symbol="600030")
    df_fin = ak.stock_financial_analysis_indicator_em(symbol=symbol)
    print("Financials (EM):")
    print(df_fin[["日期", "每股收益", "扣除非经常性损益后的净利润(元)"]].head())
    
except Exception as e:
    print(f"Financials Error: {e}")

print(f"\n--- Fetching Dividends for {symbol} ---")
try:
    # 东方财富-分红配送
    # stock_fhps_detail_em(symbol="600030")
    df_div = ak.stock_fhps_detail_em(symbol=symbol)
    print("Dividends (EM):")
    print(df_div.head())
    
except Exception as e:
    print(f"Dividend Error: {e}")
