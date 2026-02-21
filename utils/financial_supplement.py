"""
财务数据补充工具
在 CSV 导入后自动调用 yfinance 补充财务数据
"""
import yfinance as yf
from db.connection import get_connection

def convert_to_yahoo_symbol(canonical_id: str) -> str:
    """
    将典范 ID 转换为 Yahoo Finance 格式
    
    Examples:
        HK:STOCK:00700 -> 0700.HK
        US:STOCK:TSLA -> TSLA
        CN:STOCK:600036 -> 600036.SS
    """
    if not canonical_id or ':' not in canonical_id:
        return canonical_id
    
    parts = canonical_id.split(':')
    if len(parts) != 3:
        return canonical_id
    
    market, asset_type, code = parts
    
    if market == 'HK':
        # 港股：补齐4位，加 .HK 后缀
        return f"{code.zfill(4)}.HK"
    elif market == 'US':
        # 美股：直接使用代码
        return code
    elif market == 'CN':
        # A股：加 .SS 后缀（上海）或 .SZ（深圳）
        # 简单规则：60开头上海，00/30开头深圳
        if code.startswith('60'):
            return f"{code}.SS"
        else:
            return f"{code}.SZ"
    elif market == 'WORLD':
        # 全球市场（如加密货币）：直接使用代码
        return code
    
    return canonical_id


def fetch_and_save_financials(canonical_id: str, verbose: bool = True) -> tuple[bool, str]:
    """
    为指定资产获取并保存财务数据
    
    Args:
        canonical_id: 典范ID（如 HK:STOCK:00005）
        verbose: 是否打印详细信息
    
    Returns:
        (成功标志, 消息)
    """
    try:
        yahoo_symbol = convert_to_yahoo_symbol(canonical_id)
        
        if verbose:
            print(f"  正在获取 {canonical_id} ({yahoo_symbol}) 的财务数据...")
        
        ticker = yf.Ticker(yahoo_symbol)
        info = ticker.info
        
        # 提取关键指标
        eps = info.get('trailingEps')
        pe = info.get('trailingPE')
        pb = info.get('priceToBook')
        ps = info.get('priceToSalesTrailing12Months')
        dividend_yield = info.get('dividendYield')
        
        # 检查是否有有效数据
        if not any([eps, pe, pb, ps, dividend_yield]):
            return False, f"Yahoo Finance 未返回 {canonical_id} 的财务数据"
        
        # 更新 vera_price_cache 的最新记录
        conn = get_connection()
        cursor = conn.cursor()
        
        # 获取最新交易日
        latest_date = cursor.execute(
            "SELECT MAX(trade_date) FROM vera_price_cache WHERE symbol = ?",
            (canonical_id,)
        ).fetchone()[0]
        
        if not latest_date:
            conn.close()
            return False, f"{canonical_id} 在 vera_price_cache 中无记录"
        
        # 更新财务字段
        cursor.execute("""
            UPDATE vera_price_cache 
            SET pe = COALESCE(?, pe),
                pb = COALESCE(?, pb),
                ps = COALESCE(?, ps),
                eps = COALESCE(?, eps),
                dividend_yield = COALESCE(?, dividend_yield)
            WHERE symbol = ? AND trade_date = ?
        """, (pe, pb, ps, eps, dividend_yield, canonical_id, latest_date))
        
        updated = cursor.rowcount
        conn.commit()
        conn.close()
        
        if updated > 0:
            metrics = []
            if pe: metrics.append(f"PE={pe:.2f}")
            if pb: metrics.append(f"PB={pb:.2f}")
            if eps: metrics.append(f"EPS={eps:.2f}")
            
            return True, f"✓ 成功更新 {canonical_id}: {', '.join(metrics)}"
        else:
            return False, f"未能更新 {canonical_id}（可能已有数据）"
            
    except Exception as e:
        return False, f"获取 {canonical_id} 失败: {str(e)}"


def batch_supplement_financials(canonical_ids: list[str], verbose: bool = True) -> dict:
    """
    批量补充财务数据
    
    Args:
        canonical_ids: 典范ID列表
        verbose: 是否打印详细信息
    
    Returns:
        统计信息字典
    """
    stats = {
        'total': len(canonical_ids),
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'messages': []
    }
    
    if verbose:
        print(f"\n📊 开始补充财务数据（共 {stats['total']} 个资产）...")
    
    for canonical_id in canonical_ids:
        # 检查是否已有财务数据
        conn = get_connection()
        has_financials = conn.execute(
            "SELECT COUNT(*) FROM vera_price_cache WHERE symbol = ? AND pe IS NOT NULL",
            (canonical_id,)
        ).fetchone()[0] > 0
        conn.close()
        
        if has_financials:
            stats['skipped'] += 1
            if verbose:
                print(f"  ⊘ 跳过 {canonical_id}（已有财务数据）")
            continue
        
        success, message = fetch_and_save_financials(canonical_id, verbose=False)
        
        if success:
            stats['success'] += 1
            if verbose:
                print(f"  {message}")
        else:
            stats['failed'] += 1
            if verbose:
                print(f"  ✗ {message}")
        
        stats['messages'].append(message)
    
    if verbose:
        print(f"\n📈 补充完成: 成功 {stats['success']}, 失败 {stats['failed']}, 跳过 {stats['skipped']}")
    
    return stats
