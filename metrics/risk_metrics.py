"""
VERA Advanced Risk Metrics Utility (风险巡检核心逻辑)
----------------------------------
本模块实现 VERA 开发总纲中要求的高级风险分析指标。核心目标是为当前风险状态提供基于历史
"同类项"的量化背景。

分析逻辑演进：
1. 历史事件识别 (Event Identification)：
   - 扫描过去 10 年价格序列，识别完整的"峰值到谷底 (Peak-to-Trough)"回撤事件。
   - 记录要素：深度 (Depth)、跌速 (Slope = abs(深度)/持续天数)。
2. 深度分档 (Bucketing)：
   - 根据历史深度将事件划分为：A 档 (重度 ≥30%)、B 档 (中度 20-30%)、C 档 (轻度 <20%)。
3. 显著性降噪 (Noise Filtering)：
   - 引入 -10% 常态波动阈值。若当前回撤深度未达 10%，则判定为随机噪点，隐藏对标话术。
4. 同级对标 (Bucket-Aware Benchmarking)：
   - 仅在相同深度的历史事件集中对比跌速，确保"苹果对比苹果"。
   - 话术：样本 <5 时展示排名 (Rank)，样本 ≥5 时展示百分位 (Percentile)。
"""
import numpy as np
import pandas as pd
from core.config_loader import load_vera_rules


def identify_drawdown_events(prices: pd.Series):
    """
    识别 10 年内所有的回撤事件 (Peak -> trough)。
    返回事件列表，每个事件包含: depth, duration, slope, peak_date, valley_date
    """
    if prices.empty:
        return []

    cummax = prices.cummax()
    drawdowns = (prices / cummax) - 1

    # 标记回撤区间：drawdown < 0 为 in_dd=1
    in_dd = (drawdowns < 0).astype(int)
    dd_id = (in_dd.diff().fillna(0) > 0).cumsum()

    active_groups = in_dd * dd_id
    events = []

    for _, group in prices.groupby(active_groups):
        if len(group) < 1:
            continue
        start_idx = group.index[0]
        end_idx = group.index[-1]
        valley_date = group.idxmin()
        peak_date = cummax[:start_idx].idxmax() if not cummax[:start_idx].empty else start_idx

        peak_price = float(cummax.loc[start_idx])
        valley_price = float(group.loc[valley_date])

        depth = (valley_price / peak_price) - 1 if peak_price > 0 else 0.0
        duration = len(group)
        slope = abs(depth) / duration if duration > 0 else 0.0

        if depth < -0.01:  # 过滤微小噪点
            events.append({
                "depth": depth,
                "duration": duration,
                "slope": slope,
                "peak_date": peak_date,
                "valley_date": valley_date,
            })

    return events


def get_bucket_label(depth: float, buckets_cfg: dict):
    """
    根据深度返回桶 ID 和 标签
    """
    # 按 threshold 从大到小排序（即从最严重到最轻）
    sorted_buckets = sorted(buckets_cfg.items(), key=lambda x: abs(x[1]["threshold"]), reverse=True)
    for b_id, b_info in sorted_buckets:
        if depth <= b_info["threshold"]:
            return b_id, b_info["label"], b_info["threshold"]
    # 默认返回最轻的桶
    b_id, b_info = sorted_buckets[-1]
    return b_id, b_info["label"], b_info["threshold"]


def compute_bucket_aware_stats(prices: pd.Series, provided_depth: float = None):
    """
    执行分档对标分析。
    provided_depth: 外界传入的当前最大回撤深度 (e.g., -0.272)。若不传则自动识别。
    """
    rules = load_vera_rules()
    cfg = rules.get("risk_analytics", {})
    buckets_cfg = cfg.get("dd_buckets", {})

    if prices.empty:
        return None

    events = identify_drawdown_events(prices)

    # 当前深度
    curr_depth = provided_depth
    if curr_depth is None:
        last_date = prices.index[-1]
        one_year_ago = last_date - pd.Timedelta(days=365)
        recent_events = [e for e in events if e["valley_date"] >= one_year_ago]
        curr_event = min(recent_events, key=lambda x: x["depth"]) if recent_events else None
        curr_depth = curr_event["depth"] if curr_event else -0.25

    # 分桶
    b_id, b_label, b_thresh = get_bucket_label(curr_depth, buckets_cfg)

    # 找同桶历史事件
    same_bucket_events = []
    for e in events:
        e_bid, _, _ = get_bucket_label(e["depth"], buckets_cfg)
        if e_bid == b_id:
            same_bucket_events.append(e)

    # 10年重大回撤统计（深度 >= 25%）
    heavy_dd_events = [e for e in events if e["depth"] <= -0.25]
    heavy_dd_count_10y = len(heavy_dd_events)
    total_avg_dur = int(np.mean([e["duration"] for e in heavy_dd_events])) if heavy_dd_events else 0

    if not same_bucket_events:
        return {
            "bucket_id": b_id,
            "bucket_label": b_label,
            "bucket_threshold": b_thresh,
            "count": 0,
            "rank": 0,
            "percentile": 0.0,
            "curr_slope": 0.0,
            "curr_depth": float(curr_depth),
            "heavy_dd_count_10y": heavy_dd_count_10y,
            "total_avg_dur": total_avg_dur,
        }

    # 跌速排名
    all_slopes = sorted([e["slope"] for e in same_bucket_events])
    # 当前跌速：用 provided_depth / 最近一次同桶事件的 duration
    curr_event_match = min(same_bucket_events, key=lambda x: abs(x["depth"] - curr_depth)) if same_bucket_events else None
    curr_slope = curr_event_match["slope"] if curr_event_match else 0.0

    count = len(all_slopes)
    rank = sum(1 for s in all_slopes if s < curr_slope) + 1
    percentile = float(np.mean([s <= curr_slope for s in all_slopes])) * 100 if count >= 1 else 0.0

    return {
        "bucket_id": b_id,
        "bucket_label": b_label,
        "bucket_threshold": b_thresh,
        "count": count,
        "rank": int(rank),
        "percentile": float(percentile),
        "curr_slope": float(curr_slope),
        "curr_depth": float(curr_depth),
        "heavy_dd_count_10y": heavy_dd_count_10y,
        "total_avg_dur": total_avg_dur,
    }


def generate_risk_narrative(prices: pd.Series, provided_depth: float = None) -> str:
    """
    根据分档逻辑生成叙事文案。
    """
    stats = compute_bucket_aware_stats(prices, provided_depth)

    if not stats:
        return "暂无充足历史回撤样本进行对标。"

    narrative = (
        f"过去 10 年共有 {stats['heavy_dd_count_10y']} 次 ≥25% 大回撤，"
        f"平均持续 {stats['total_avg_dur']} 天。"
    )

    curr_depth = stats.get("curr_depth", 0)
    if abs(curr_depth) < 0.1:
        return narrative  # 深度不足 10%，不输出对标话术

    b_label = stats.get("bucket_label", "")
    b_thresh = stats.get("bucket_threshold", 0)
    count = stats.get("count", 0)

    if count >= 5:
        narrative += (
            f"与历史同级（≥{abs(b_thresh) * 100:.0f}%）{b_label}"
            f"相比，本轮跌速处于第 {stats['percentile']:.0f} 分位。"
        )
    elif count > 0:
        narrative += (
            f"与过去 10 年内 {count} 次类似深度回撤相比，"
            f"本轮跌速排第 {stats['rank']} 位。"
        )

    return narrative


def compute_short_window_crash(prices: pd.Series, window_days: int = 30) -> float:
    """
    (保留兼容) 30日崩盘深度
    """
    if prices.empty:
        return 0.0

    last_date = prices.index[-1]
    one_year_ago = last_date - pd.Timedelta(days=365)
    prices_1y = prices.loc[one_year_ago:] if len(prices) > 2 else prices

    roll_max = prices_1y.rolling(window=window_days, min_periods=1).max()
    crash = (prices_1y / roll_max) - 1

    return float(crash.min())
