import requests
import re

def get_stock_name(symbol):
    """
    Fetch stock name from smartbox.gtimg.cn
    Strategy:
    1. Clean symbol: 
       - If 6 digits + suffix (e.g. 600309.SH), strip suffix.
       - Else use as is (e.g. TSLA, AAPL).
    2. Query API
    3. Parse first result
    """
    
    # 0. Pre-clean: Remove prefixes if present
    clean_sym = symbol
    suffix = None
    if ":" in symbol:
        clean_sym = symbol.split(":")[-1]
    
    # 0. Manual Overrides (Fast Path) - Updated for VERA
    MANUAL_OVERRIDES = {
        "HSI": "恒生指数",
        "HSTECH": "恒生科技指数",
        "HSCE": "国企指数",
        "000300": "沪深300",
        "600536": "中国软件",
        "601919": "中远海控",
        "600030": "中信证券",
        "601998": "中信银行",
        "00700": "腾讯控股",
        "00005": "汇丰控股",
        "00998": "中信银行 (00998)",
        "01919": "中远海控 (01919)",
        "09988": "阿里巴巴",
        "02800": "盈富基金",
        "03033": "南方恒生科技",
        "SPX": "标普500",
        "NDX": "纳斯达克100",
        "DJI": "道琼斯工业"
    }
    
    # Check if this asset (or its cleaned form) is in overrides
    if symbol in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[symbol]
    if clean_sym in MANUAL_OVERRIDES:
        return MANUAL_OVERRIDES[clean_sym]
        
    # Re-assign query_key after stripping
    query_key = clean_sym
    
    # Regex for CN stock code
    match_cn = re.match(r'^(\d{6})\.(SH|SZ|SS)$', symbol, re.IGNORECASE)
    # Regex for HK stock code (e.g. 00700.HK)
    match_hk = re.match(r'^(\d{5})\.(HK)$', symbol, re.IGNORECASE)
    
    if match_cn:
        query_key = match_cn.group(1)
        suffix = match_cn.group(2).upper() # SH, SZ, SS
    elif match_hk:
        query_key = match_hk.group(1)
        suffix = "HK"
        
    url = f"http://smartbox.gtimg.cn/s3/?q={query_key}&t=all"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            content = response.text
            start = content.find('"')
            end = content.rfind('"')
            if start != -1 and end != -1:
                inner = content[start+1:end]
                if inner == "N":
                    return symbol 
                
                results = inner.split('^')
                target_name = None
                
                # Logic to select best match
                for res in results:
                    parts = res.split('~')
                    if len(parts) < 3: continue
                    
                    market = parts[0] # sh, sz, hk, us
                    code = parts[1]
                    name_raw = parts[2]
                    
                    # 1. If we have a suffix, enforce market match
                    if suffix:
                        if suffix in ["SH", "SS"] and market == "sh":
                            target_name = name_raw
                            break # Found
                        if suffix == "SZ" and market == "sz":
                            target_name = name_raw
                            break # Found
                        if suffix == "HK" and market == "hk":
                            target_name = name_raw
                            break
                    else:
                        # No suffix: prioritize market based on symbol format
                        # If symbol is purely letters (e.g. GLD, AAPL), prefer 'us' bucket
                        is_alpha_only = query_key.isalpha()
                        
                        target_res = None
                        
                        # First pass: try to find exact market match if possible
                        if is_alpha_only:
                             for r in results:
                                 p = r.split('~')
                                 if len(p) >= 3 and p[0] == 'us':
                                     target_res = p
                                     break
                        
                        # Fallback to first result if no specific match found
                        if not target_res:
                            parts = results[0].split('~')
                            if len(parts) >= 3:
                                target_res = parts
                                
                        if target_res:
                            target_name = target_res[2]
                            break
                
                # If parsed successfully
                if target_name:
                    if "\\u" in target_name:
                         return target_name.encode('utf-8').decode('unicode_escape')
                    return target_name

    except Exception as e:
        print(f"Error fetching name for {symbol}: {e}")
        
    return symbol # Fallback

if __name__ == "__main__":
    print(f"TSLA -> {get_stock_name('TSLA')}")
    print(f"600309.SH -> {get_stock_name('600309.SH')}")
    print(f"000001.SZ -> {get_stock_name('000001.SZ')} (Should be PingAn Bank)")
    print(f"000001.SH -> {get_stock_name('000001.SH')} (Should be ShangZheng Index)")
