
import sys
import os
import yfinance as yf
import akshare as ak
import pandas as pd
import re
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.getcwd())
try:
    from db.connection import get_connection
except ImportError:
    # Fallback if run from scripts dir
    sys.path.append(os.path.dirname(os.getcwd()))
    from db.connection import get_connection

def save_to_db(asset_id, data_map):
    if not data_map:
        return 0
        
    conn = get_connection()
    c = conn.cursor()
    
    count = 0
    for date_str, stats in data_map.items():
        eps = stats.get("eps")
        ni = stats.get("ni")
        div = stats.get("div")
        
        if eps is None and ni is None and div is None:
            continue
            
        c.execute("""
            INSERT INTO financial_history (asset_id, report_date, eps_ttm, net_profit_ttm, dividend_amount)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(asset_id, report_date) DO UPDATE SET
                eps_ttm = COALESCE(excluded.eps_ttm, financial_history.eps_ttm),
                net_profit_ttm = COALESCE(excluded.net_profit_ttm, financial_history.net_profit_ttm),
                dividend_amount = COALESCE(excluded.dividend_amount, financial_history.dividend_amount)
        """, (asset_id, date_str, eps, ni, div))
        count += 1
        
    conn.commit()
    conn.close()
    return count

def fetch_ashare_history(asset_id, symbol_code):
    """
    Fetch A-share financials using AkShare.
    symbol_code: e.g. "600030"
    """
    print(f"Fetching A-share history for {asset_id} ({symbol_code})...")
    data_map = {}
    
    # 1. Financials (Sina) for EPS & Net Profit
    # Structure: We need to pull all history first to calculate TTM
    raw_records = []
    
    try:
        df_fin = ak.stock_financial_report_sina(stock=symbol_code, symbol="利润表")
        # Columns: 报告日, 基本每股收益, 净利润, ...
        # Date format: YYYYMMDD -> YYYY-MM-DD
        
        for _, row in df_fin.iterrows():
            date_raw = str(row.get("报告日", ""))
            if not date_raw: continue
            
            try:
                dt = datetime.strptime(date_raw, "%Y%m%d")
                date_str = dt.strftime("%Y-%m-%d")
            except:
                continue
                
            def _parse_val(v):
                try:
                    return float(v)
                except:
                    return None
            
            eps = _parse_val(row.get("基本每股收益"))
            ni = _parse_val(row.get("净利润")) 
            
            # Store raw YTD data
            raw_records.append({
                "date": dt,
                "date_str": date_str,
                "eps_ytd": eps,
                "ni_ytd": ni
            })
            
    except Exception as e:
        print(f"Error fetching financials for {asset_id}: {e}")
        return # Cannot proceed without financials

    # --- TTM Calculation Logic ---
    # Convert to DataFrame for indexing
    if raw_records:
        df_calc = pd.DataFrame(raw_records)
        df_calc.sort_values("date", inplace=True)
        df_calc.set_index("date", inplace=True)
        
        # Helper to get value by exact date
        def get_val(target_date, col):
            if target_date in df_calc.index:
                return df_calc.loc[target_date, col]
            return None

        for dt, row in df_calc.iterrows():
            date_str = row["date_str"]
            ytd_eps = row["eps_ytd"]
            ytd_ni = row["ni_ytd"]
            
            # Determine Quarter
            # Q1: 03-31, Q2: 06-30, Q3: 09-30, Q4 (Annual): 12-31
            # Note: Sometimes dates are slightly off? Usually standard.
            month = dt.month
            year = dt.year
            
            ttm_eps = None
            ttm_ni = None
            
            if month == 12:
                # Annual Report: YTD is TTM
                ttm_eps = ytd_eps
                ttm_ni = ytd_ni
            else:
                # Q1, Q2, Q3
                # Formula: TTM = Prev_Year_Annual + Current_YTD - Prev_Year_Same_Period_YTD
                prev_year_end = datetime(year - 1, 12, 31)
                # Handle leap years or slight shifts? AkShare dates are normalized usually.
                # Let's construct keys safely.
                # Find prev year same period end
                # e.g. 2024-03-31 -> 2023-03-31
                try:
                    prev_same_period = datetime(year - 1, month, dt.day) 
                except ValueError:
                    # Leap year 02-29 case (unlikely for quarters)
                    prev_same_period = datetime(year - 1, month, 28)

                prev_annual_eps = get_val(prev_year_end, "eps_ytd")
                prev_period_eps = get_val(prev_same_period, "eps_ytd")
                
                if ytd_eps is not None and prev_annual_eps is not None and prev_period_eps is not None:
                    ttm_eps = prev_annual_eps + ytd_eps - prev_period_eps
                else:
                    # Fallback: Just use YTD if we assume it's roughly annualized? No, that's bad.
                    # Or Fallback to last Annual?
                    # For now, if we can't calc TTM, we leave it None or use YTD (legacy behavior)?
                    # Using YTD caused the specific bug "Deep Decline" (-75% drop). 
                    # Better to return None (missing data) than wrong data?
                    # But then we have gaps. 
                    # COMPROMISE: If TTM fails, use YTD but maybe log it? 
                    # Actually, for Dividend Safety (Payout Ratio), YTD is terrible for Q1.
                    # Let's try to be strict. If missing history, cannot calc TTM.
                    # But for recent listings, we might only have YTD.
                    # Let's keep TTM as None if strict recalc fails.
                    pass

                # Same for Net Income
                prev_annual_ni = get_val(prev_year_end, "ni_ytd")
                prev_period_ni = get_val(prev_same_period, "ni_ytd")
                if ytd_ni is not None and prev_annual_ni is not None and prev_period_ni is not None:
                    ttm_ni = prev_annual_ni + ytd_ni - prev_period_ni

            if date_str not in data_map: data_map[date_str] = {}
            # Use TTM values if available, else YTD (fallback for Annual is logic, for others is fallback)
            # If ttm_eps is None (due to missing history), do we save YTD?
            # If we save YTD for Q1, we get the bug again.
            # So: Save TTM if available. If strict TTM missing, maybe save nothing for EPS?
            # Or Save YTD but we need to know it's YTD. DB schema doesn't distinguish.
            # Decision: SAVE TTM ONLY for eps_ttm column. 
            # If it's Annual, YTD is TTM.
            
            data_map[date_str]["eps"] = ttm_eps
            data_map[date_str]["ni"] = ttm_ni

    # 2. Dividends (EastMoney)
    try:
        df_div = ak.stock_fhps_detail_em(symbol=symbol_code)
        # Columns: '报告期', '现金分红-现金分红比例', ...
        
        for _, row in df_div.iterrows():
            date_raw = str(row.get("报告期", "")) # YYYY-MM-DD
            if not date_raw or date_raw == "NaT": continue
             # Normalize date
            try:
                dt = pd.to_datetime(date_raw)
                date_str = dt.strftime("%Y-%m-%d")
            except:
                continue

            val_raw = row.get("现金分红-现金分红比例")
            div_amount = 0.0
            
            try:
                v = float(val_raw)
                div_amount = v / 10.0
            except:
                pass
            
            if div_amount > 0:
                if date_str not in data_map: data_map[date_str] = {}
                data_map[date_str]["div"] = div_amount

    except Exception as e:
        print(f"Error fetching dividends for {asset_id}: {e}")
        
    count = save_to_db(asset_id, data_map)
    print(f"Saved {count} records for {asset_id}")


def fetch_yfinance_history(asset_id, yahoo_symbol=None):
    if not yahoo_symbol:
        # Simple heuristic
        if "HK:STOCK:" in asset_id:
            code = asset_id.split(":")[-1]
            yahoo_symbol = f"{int(code):04d}.HK" # 0005.HK
        elif "US:STOCK:" in asset_id:
            yahoo_symbol = asset_id.split(":")[-1]
        else:
            yahoo_symbol = asset_id
            
    print(f"Fetching HK/US history for {asset_id} (Yahoo: {yahoo_symbol})...")
    
    try:
        ticker = yf.Ticker(yahoo_symbol)
        
        # 1. Fetch Financials (Annual) for EPS & Net Income
        fin_df = ticker.financials
        
        data_map = {} # date -> {eps, ni, div}
        
        if not fin_df.empty:
            fin_T = fin_df.T 
            fin_T.index = pd.to_datetime(fin_T.index)
            
            for date, row in fin_T.iterrows():
                date_str = date.strftime("%Y-%m-%d")
                eps = row.get("Basic EPS")
                ni = row.get("Net Income")
                if pd.isna(eps): eps = None
                if pd.isna(ni): ni = None
                
                if date_str not in data_map: data_map[date_str] = {}
                data_map[date_str]["eps"] = eps
                data_map[date_str]["ni"] = ni
                
        # 2. Fetch Dividends (Series)
        divs = ticker.dividends
        if not divs.empty:
            divs.index = pd.to_datetime(divs.index)
            annual_divs = divs.resample('YE').sum()
            
            for date, amount in annual_divs.items():
                date_str = date.strftime("%Y-%m-%d")
                if date_str not in data_map: data_map[date_str] = {}
                data_map[date_str]["div"] = float(amount)
        
        if not data_map:
            print("No data found.")
            return

        count = save_to_db(asset_id, data_map)
        print(f"Saved {count} records for {asset_id}")
        
    except Exception as e:
        print(f"Error for {asset_id}: {e}")



def fetch_hk_history_akshare(asset_id, symbol_code):
    """
    Fetch HK financials using AkShare (deeper history).
    symbol_code: e.g. "00998" (pure digit string)
    """
    print(f"Fetching HK AkShare history for {asset_id} ({symbol_code})...")
    data_map = {}
    
    try:
        # stock_financial_hk_analysis_indicator_em: 
        # indicator="年度" returns Annual Data.
        # Columns: REPORT_DATE, BASIC_EPS, EPS_TTM, NET_PROFIT ... ?
        # Based on test: REPORT_DATE, BASIC_EPS, EPS_TTM
        # Note: NET_PROFIT might be 'HOLDER_PROFIT' (归属母公司股东净利润)?
        # Let's check test output columns again: 
        # 'HOLDER_PROFIT' is present.
        
        df = ak.stock_financial_hk_analysis_indicator_em(symbol=symbol_code, indicator="报告期")
        
        for _, row in df.iterrows():
            date_raw = str(row.get("REPORT_DATE", ""))
            if not date_raw: continue
            
            try:
                dt = pd.to_datetime(date_raw)
                date_str = dt.strftime("%Y-%m-%d")
            except:
                continue
            
            def _parse_val(v):
                try:
                    return float(v)
                except:
                    return None
            
            # Use EPS_TTM if available (AkShare provides it for report periods), else BASIC_EPS
            # If EPS_TTM is valid, use it. BASIC_EPS is for the period (interim).
            ttm = _parse_val(row.get("EPS_TTM"))
            basic = _parse_val(row.get("BASIC_EPS"))
            
            # For DB eps_ttm column:
            # If we have explicit TTM, use it.
            # If we only have Basic, check if it's Annual (Dec 31)? 
            #   If Annual, Basic = TTM.
            #   If Interim, Basic != TTM.
            #   So prioritize EPS_TTM column.
            
            eps_final = ttm if ttm is not None else (basic if dt.month == 12 else None)
            
            ni = _parse_val(row.get("HOLDER_PROFIT")) 
            
            if eps_final is not None or ni is not None:
                if date_str not in data_map: data_map[date_str] = {}
                data_map[date_str]["eps"] = eps_final
                data_map[date_str]["ni"] = ni
            
            # Do NOT overwrite dividends here, as AkShare HK interface might not have dividends or we prefer Yahoo.
            
    except Exception as e:
        print(f"Error fetching HK AkShare for {asset_id}: {e}")
        return

    count = save_to_db(asset_id, data_map)
    print(f"Saved {count} HK AkShare records for {asset_id}")


def main():
    conn = get_connection()
    # Fetch all relevant stocks
    rows = conn.execute("""
        SELECT asset_id, symbol_name, market 
        FROM assets 
        WHERE (market IN ('HK', 'US', 'CN')) 
          AND asset_type = 'EQUITY'
    """).fetchall()
    
    print(f"Found {len(rows)} assets to check/backfill...")
    
    for row in rows:
        asset_id = row[0]
        market = row[2]
        
        try:
            if market == 'CN':
                # Parse pure code 600030 from CN:STOCK:600030
                code = asset_id.split(":")[-1]
                fetch_ashare_history(asset_id, code)
            elif market == 'HK':
                # 1. Yahoo (Dividends + Recent Financials)
                fetch_yfinance_history(asset_id)
                # 2. AkShare (Deep History Financials)
                # Code: HK:STOCK:00998 -> 00998
                code = asset_id.split(":")[-1]
                fetch_hk_history_akshare(asset_id, code)
            else:
                # US
                fetch_yfinance_history(asset_id)
                
        except Exception as e:
            print(f"Global failure for {asset_id}: {e}")
            
    conn.close()


if __name__ == "__main__":
    main()
