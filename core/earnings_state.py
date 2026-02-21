from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional
from core.config_loader import load_vera_rules

@dataclass
class EarningsStateInfo:
    code: str       # "E0".."E6"
    label_zh: str
    desc_zh: str

def compute_eps_yoy(eps_series: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
    """
    输入: 按时间升序的 (report_date, eps) 列表
    输出: (report_date, yoy) 列表
    
    逻辑：
    - 假设 eps_series 已经是按日期升序排序
    - 寻找 "去年同期" (大约365天前) 的记录进行对比
    - 或者如果是季度序列，且比较密集，简单的 shift(4) 可能不够严谨，最好是日期对齐
    - 简化起见：我们假设输入的是标准的季度/年度序列 (e.g. Q1, Q2...)
    - 这里尝试严格的日期对齐：找 report_date 一年前的那个数据的 index
    """
    if not eps_series or len(eps_series) < 2:
        return []
    
    # 转换为 dict 方便查找: date_str -> eps
    # 假设 report_date 格式一致 (YYYY-MM-DD or YYYYMMDD)
    # 我们不仅需要精确匹配，通常财报日期相对固定，但也可能差几天。
    # 简化策略：
    # 1. 解析日期
    # 2. 对每个点，寻找 (date - 1 year) 附近的数据点
    
    # 但为了稳健性，如果数据是标准的 quarters，可以直接用 index - 4 (如果是季度数据)
    # 或者我们先做一个简单的 dict lookup 假设日期是标准的 (e.g. *0331, *0630, *0930, *1231)
    
    eps_map = {date: val for date, val in eps_series}
    yoy_list = []
    
    for date, val in eps_series:
        # 尝试构造去年同期的 key
        # 简单处理：YYYY-MM-DD -> (YYYY-1)-MM-DD
        try:
            year = int(date[:4])
            suffix = date[4:]
            prev_year_date = f"{year-1}{suffix}"
            
            prev_val = eps_map.get(prev_year_date)
            if prev_val is not None and prev_val != 0:
                yoy = (val - prev_val) / abs(prev_val)
                yoy_list.append((date, yoy))
            else:
                # 无法计算 YoY
                pass
        except:
            continue
            
    return yoy_list

def determine_earnings_state(
    eps_series: List[Tuple[str, float]],
    rules: Dict[str, Any] | None = None
) -> EarningsStateInfo:
    """
    根据 EPS 序列和 earnigns_state 配置，判断盈利周期 E0–E6。
    - 若有效财报期数 < 4，直接返回 E0（无结构）。
    
    Input: eps_series: list of (report_date, eps_value), sorted by date ascending.
    """
    if rules is None:
        rules = load_vera_rules()
    
    # 获取配置
    erules = rules.get("earnings_state", {})
    thresholds = erules.get("thresholds", {})
    min_trend = erules.get("min_trend_quarters", 2)
    labels = erules.get("labels", {})
    
    # Default E0
    def _return_state(code):
        lbl = labels.get(code, labels.get("E0", {}))
        return EarningsStateInfo(
            code=code,
            label_zh=lbl.get("label_zh", "未知"),
            desc_zh=lbl.get("desc_zh", "无描述")
        )

    if not eps_series or len(eps_series) < 4:
        return _return_state("E0")

    # 1) 计算 YoY 序列
    yoy_series = compute_eps_yoy(eps_series)
    
    # 如果 YoY 数据点太少，也无法判断
    if len(yoy_series) < 3:
        return _return_state("E0")
        
    # 取最近的数据点进行分析
    # yoy_series is [(date, yoy), ...]
    # 我们主要关注最近几个季度的趋势
    # current (latest)
    curr_yoy = yoy_series[-1][1]
    
    # history (reverse order for easier trend check: latest -> oldest)
    yoy_rev = [y for d, y in reversed(yoy_series)]
    
    # Extract thresholds
    g_strong = thresholds.get("growth_strong", 0.15)
    g_mod = thresholds.get("growth_moderate", 0.05)
    d_mild = thresholds.get("decline_mild", -0.05)
    d_deep = thresholds.get("decline_deep", -0.20)
    
    # Helper to check if last N quarters matched a condition
    def check_trend(n, condition_func):
        if len(yoy_rev) < n: return False
        return all(condition_func(y) for y in yoy_rev[:n])
    
    # E5: 亏损/深度下滑
    # 1. 连续大幅下滑 Or 2. EPS 本身为负 (需检查原始 EPS)
    # Check latest EPS value
    curr_eps = eps_series[-1][1]
    
    # E5 Logic:
    # - Latest EPS < 0 (Loss)
    # - OR Latest YoY < decline_deep AND Prev YoY < decline_mild (Deep decline trend)
    if curr_eps < 0:
        return _return_state("E5")
    
    if check_trend(1, lambda y: y < d_deep) or check_trend(2, lambda y: y < d_deep):
         return _return_state("E5")
         
    # E4: 盈利下滑
    # YoY 转负且持续 (e.g. last 2 < 0) OR significant drop below mild
    if check_trend(min_trend, lambda y: y < d_mild):
         return _return_state("E4")
         
    # E6: 盈利修复
    # 从 E4/E5 状态恢复 -> YoY 转正并保持
    # Heuristic: Latest > 0, but Previous was negative OR We look further back?
    # 简单判定：Latest > 0 AND (Avg of prev 2-4 was negative)
    # Better logic: Check if we are "recovering".
    # Condition: Current YoY > 0 AND (Previous YoY < 0 OR Previous EPS < 0)
    # BUT "持续多个季度" -> maybe last 2 qtrs > 0, and before that was bad.
    if len(yoy_rev) >= 3:
        # e.g. + + -
        is_pos_now = check_trend(2, lambda y: y > 0)
        was_bad_before = yoy_rev[2] < 0 
        if is_pos_now and was_bad_before:
            return _return_state("E6")
            
    # E1: 盈利扩张早期
    # High growth for N quarters
    if check_trend(min_trend, lambda y: y > g_strong):
        return _return_state("E1")
        
    # E3: 增长放缓
    # E1/E2 -> Lower growth
    # Condition: Current < Moderate, but Previous was Strong/Moderate
    # e.g. Current in [0, 0.05], Prev > 0.15
    if 0 <= curr_yoy < g_mod:
        if len(yoy_rev) >= 2 and yoy_rev[1] > g_strong:
            return _return_state("E3")
            
    # E2: 盈利稳定高位
    # Moderate growth or fluctuating around a positive mean
    # Or just stable growth in [0.05, 0.15] range
    # Or simply: if not any of above, but positive?
    if check_trend(min_trend, lambda y: y >= d_mild): # Roughly stable or growing
        # Distinction between E1 and E2 is magnitude
        return _return_state("E2")

    # Default fallback
    return _return_state("E0")
