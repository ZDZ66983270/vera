"""
VERA 系统全局排序规则配置
所有涉及资产排序的地方都应引用此配置，确保一致性
"""

# 市场排序优先级 (Market Priority)
# 数字越小优先级越高
MARKET_PRIORITY = {
    'HK': 0,  # 港股优先
    'US': 1,  # 美股次之
    'CN': 2,  # A股第三
}

# 资产类型排序优先级 (Asset Type Priority)
# 数字越小优先级越高
ASSET_TYPE_PRIORITY = {
    'EQUITY': 0,  # 个股优先
    'STOCK': 0,   # 个股（别名）
    'ETF': 1,     # ETF次之
    'INDEX': 2,   # 指数最后
}

def get_market_priority(market: str) -> int:
    """获取市场排序优先级"""
    return MARKET_PRIORITY.get(market.upper() if market else '', 999)

def get_asset_type_priority(asset_type: str) -> int:
    """获取资产类型排序优先级"""
    return ASSET_TYPE_PRIORITY.get(asset_type.upper() if asset_type else '', 999)

def get_sort_key(asset_id: str, market: str = None, asset_type: str = None) -> tuple:
    """
    生成统一的排序键
    
    Args:
        asset_id: 资产ID（典范ID）
        market: 市场代码（可选，会从asset_id推断）
        asset_type: 资产类型（可选，会从asset_id推断）
    
    Returns:
        排序键元组 (market_priority, type_priority, numeric_flag, code_value)
    """
    import re
    
    # 推断市场
    if not market:
        if asset_id.startswith('HK:'):
            market = 'HK'
        elif asset_id.startswith('US:'):
            market = 'US'
        elif asset_id.startswith('CN:'):
            market = 'CN'
        else:
            market = 'OTHER'
    
    # 推断类型
    if not asset_type:
        if ':INDEX:' in asset_id:
            asset_type = 'INDEX'
        elif ':ETF:' in asset_id:
            asset_type = 'ETF'
        elif ':STOCK:' in asset_id:
            asset_type = 'EQUITY'
        else:
            asset_type = 'EQUITY'  # 默认
    
    m_priority = get_market_priority(market)
    t_priority = get_asset_type_priority(asset_type)
    
    # 提取数字代码进行排序
    digits = re.findall(r'\d+', asset_id)
    if digits:
        code_part = digits[-1]
        # 港股代码补齐5位
        if market == 'HK':
            code_part = code_part.zfill(5)
        try:
            return (m_priority, t_priority, 0, int(code_part))
        except:
            pass
    
    # 字母排序
    return (m_priority, t_priority, 1, asset_id.upper())


# SQL ORDER BY 子句生成器
def get_sql_order_clause(
    market_col: str = 'market',
    type_col: str = 'asset_type',
    id_col: str = 'asset_id'
) -> str:
    """
    生成标准的 SQL ORDER BY 子句
    
    Args:
        market_col: 市场字段名
        type_col: 类型字段名
        id_col: ID字段名
    
    Returns:
        SQL ORDER BY 子句（不含 ORDER BY 关键字）
    """
    market_case = f"""
    CASE {market_col}
        WHEN 'HK' THEN 0
        WHEN 'US' THEN 1
        WHEN 'CN' THEN 2
        ELSE 999
    END
    """
    
    type_case = f"""
    CASE {type_col}
        WHEN 'EQUITY' THEN 0
        WHEN 'STOCK' THEN 0
        WHEN 'ETF' THEN 1
        WHEN 'INDEX' THEN 2
        ELSE 999
    END
    """
    
    return f"{market_case} ASC, {type_case} ASC, {id_col} ASC"
