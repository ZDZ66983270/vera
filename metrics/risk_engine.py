"""
VERA Risk Engine (核心风险计算引擎)
----------------------------------
本模块负责 VERA 系统中最核心的风险量化逻辑。
主要功能与关键点：
1. 风险指标计算：基于价格序列计算最大回撤 (MDD)、年化波动率、极端跌幅等基础指标。
2. D-State 状态机：实现 10 年长期维度的风险结构识别 (D0-D6)，核心逻辑基于「历史坑深」与「修复进度」。
3. R-State 集成：结合 RecentCycleEngine (1Y 维度) 对路径风险进行动态修正。
4. 高级分析集成：调用 risk_metrics 模块，提供跌速分位、重大回撤频率等深度量化解析。
5. 三层分离准则：作为引擎层，仅负责计算与状态转换，不直接操作数据库或处理 UI 样式。

权限声明：本文件头注释描述了核心意图，修改需经用户批准。
"""
from metrics.drawdown import max_drawdown, current_drawdown, recovery_time, max_drawdown_details, recovery_details, recovery_progress
from metrics.volatility import annual_volatility
from metrics.tail_risk import worst_n_day_drop
from metrics.recent_cycle_engine import RecentCycleEngine, RecentCycleInfo
import pandas as pd

class RiskEngine:
    @staticmethod
    def calculate_risk_metrics(prices: pd.Series):
        """
        风险计算引擎 (重构版：返回标准化 3 层结构 + Recent Cycle Gating)
        """
        if prices.empty:
            return {}
            
        if not isinstance(prices, pd.Series):
            raise ValueError("RiskEngine requires a pandas Series with DatetimeIndex")

        returns = prices.pct_change().dropna()
        mdd, mdd_amount, peak_date, valley_date, peak_price, valley_price = max_drawdown_details(prices)
        rec_days, rec_end_date = recovery_details(prices)
        rec_progress = recovery_progress(prices)
        
        vol_long = annual_volatility(returns)
        returns_1y = returns.iloc[-252:] if len(returns) > 252 else returns
        vol_1y = annual_volatility(returns_1y)
        
        # --- 修正 Current Drawdown 计算 (N=5 保护) ---
        peak_10y = prices.max()
        peak_date_10y = prices.idxmax()
        current_price = prices.iloc[-1]
        
        # 如果最高价出现在最近 5 个交易日内，判定回撤为 0
        days_since_peak = (prices.index[-1] - peak_date_10y).days # Simplified check
        # More robust: check number of trading bars
        bars_since_peak = len(prices[peak_date_10y:]) - 1
        
        if bars_since_peak <= 5:
            curr_dd = 0.0
            curr_dd_days = 0
            curr_peak_date = prices.index[-1].strftime("%Y-%m-%d") # Mark current as peak
        else:
            curr_dd = (current_price / peak_10y) - 1
            curr_dd_days = bars_since_peak
            curr_peak_date = peak_date_10y.strftime("%Y-%m-%d")

        # DD Strength
        dd_strength = abs(curr_dd) / abs(mdd) if mdd != 0 else 0.0

        mdd_days = int((valley_date - peak_date).days) if (peak_date and valley_date) else 0

        # State Calculation (Primary & Overlay)
        # 1. 计算各周期基础指标
        risk_state_data = RiskEngine.calculate_path_risk_state(
            prices, mdd, curr_dd, dd_strength, 
            mdd_duration_days=mdd_days,
            mdd_peak_date=peak_date,
            mdd_valley_date=valley_date,
            mdd_peak_price=peak_price,
            mdd_valley_price=valley_price
        )
        
        # 2. Recent Cycle Analysis (Gating)
        recent_engine = RecentCycleEngine()
        recent_info = recent_engine.evaluate(prices, vol_1y)
        
        # 3. Apply Gating Logic
        base_d_state = risk_state_data.get("state", "D0")
        final_d_state = RiskEngine.apply_recent_cycle_gate(base_d_state, recent_info)
        
        # 4. Update state content if changed
        if final_d_state != base_d_state:
            from core.config_loader import load_vera_rules
            rules = load_vera_rules()
            label_defs = rules.get("d_state", {}).get("labels", {})
            risk_state_data["state"] = final_d_state
            risk_state_data["desc"] = label_defs.get(final_d_state, {}).get("label_zh", "")
            risk_state_data["is_gated"] = True # Mark as gated
            risk_state_data["original_state"] = base_d_state
        
        # 5. Inject Recent Cycle Info into display structure
        from metrics import risk_metrics
        stats = risk_metrics.compute_bucket_aware_stats(prices, recent_info.max_dd_1y)
        max_30d_dd = risk_metrics.compute_short_window_crash(prices)
        narrative = risk_metrics.generate_risk_narrative(prices, recent_info.max_dd_1y)

        risk_state_data["recent_cycle"] = {
            "state": recent_info.state,
            "label": recent_info.state_label_zh,
            "off_high_1y": float(recent_info.off_high_1y),
            "max_dd_1y": float(recent_info.max_dd_1y),
            "dd_days": int(recent_info.dd_days),
            "dd_sigma": float(recent_info.dd_sigma),
            "recovery_pct": float(recent_info.recovery_pct),
            "peak_price": float(recent_info.peak_1y),
            "valley_price": float(recent_info.valley_1y),
            "valley_date": recent_info.valley_date.strftime("%Y-%m-%d") if pd.notnull(recent_info.valley_date) else None,
            "peak_date": recent_info.peak_date.strftime("%Y-%m-%d") if pd.notnull(recent_info.peak_date) else None,
            "recovery_days": int(recent_info.recovery_days),
            "heavy_dd_count_10y": int(stats['heavy_dd_count_10y']) if stats else 0,
            "heavy_dd_avg_duration_10y": int(stats['total_avg_dur']) if stats else 0,
            "dd_slope_pct_10y": float(stats['percentile']) if stats else 0.0,
            "dd_rank_in_bucket": int(stats['rank']) if stats else 0,
            "max_30d_dd_1y": float(max_30d_dd),
            "risk_narrative": narrative
        }

        metrics = {
            "max_drawdown": mdd,
            "max_drawdown_amount": mdd_amount,
            "mdd_peak_price": peak_price,
            "mdd_valley_price": valley_price,
            "mdd_peak_date": peak_date.strftime("%Y-%m-%d") if peak_date else None,
            "mdd_valley_date": valley_date.strftime("%Y-%m-%d") if valley_date else None,
            "mdd_duration_days": int((valley_date - peak_date).days) if (peak_date and valley_date) else 0,
            
            "current_peak_price": peak_10y,
            "current_peak_date": curr_peak_date,
            "current_drawdown": curr_dd,
            "current_drawdown_days": curr_dd_days,
            "dd_strength_vs_max": dd_strength,
            
            "annual_volatility": vol_long,
            "volatility_1y": vol_1y,
            "volatility_10y": vol_long,
            "volatility_period": f"{prices.index[0].strftime('%Y/%m')} - {prices.index[-1].strftime('%Y/%m')}",
            
            "recovery_time": rec_days,
            "recovery_end_date": rec_end_date.strftime("%Y-%m-%d") if rec_end_date else None,
            "recovery_progress": rec_progress,
            "worst_5d_drop": worst_n_day_drop(prices, window=5),
            
            "risk_state": risk_state_data,
            "price_percentile": prices.rank(pct=True).iloc[-1]
        }

        # Severity Bucket
        from core.config_loader import load_vera_rules
        rules = load_vera_rules()
        drules = rules.get("risk_overlay", {}).get("drawdown", {})
        warn_dd = drules.get("current_dd_warn", -0.10)
        severe_dd = drules.get("current_dd_severe", -0.25)

        if abs(curr_dd) < abs(warn_dd): metrics["dd_severity_bucket"] = "MILD"
        elif abs(curr_dd) < abs(severe_dd): metrics["dd_severity_bucket"] = "MODERATE"
        else: metrics["dd_severity_bucket"] = "SEVERE"
        
        return metrics

    @staticmethod
    def calculate_path_risk_state(prices: pd.Series, mdd_total=None, current_dd_val=None, strength_val=None, mdd_duration_days=0, mdd_peak_date=None, mdd_valley_date=None, mdd_peak_price=None, mdd_valley_price=None):
        """
        还原版：单层路径风险状态机 (D0-D6)
        """
        if prices.empty: return None
            
        peak_10y = prices.max()
        peak_date_10y = prices.idxmax()
        post_peak = prices[peak_date_10y:]
        trough_10y = post_peak.min() if not post_peak.empty else prices.iloc[-1]
        current_price = prices.iloc[-1]
        
        # 核心指标
        c_dd = current_dd_val if current_dd_val is not None else (current_price/peak_10y - 1)
        max_dd_cycle = (trough_10y/peak_10y - 1) if peak_10y != 0 else 0
        
        # Recovery Rate (Progress from MDD Valley to MDD Peak)
        # Use provided MDD prices if available, otherwise fallback to global 10Y max/min
        p_ref = mdd_peak_price if mdd_peak_price is not None else peak_10y
        v_ref = mdd_valley_price if mdd_valley_price is not None else trough_10y
        
        if p_ref > v_ref:
            recovery = (current_price - v_ref) / (p_ref - v_ref)
        else:
            recovery = 1.0
            
        # Clamp to [0, 1]
        recovery = max(0.0, min(1.0, recovery))

        # 修复耗时计算 (Recovery Time)
        rec_days = 0
        if mdd_valley_date is not None:
            post_v = prices[mdd_valley_date:]
            if recovery >= 1.0 and p_ref > 0:
                # 寻找首次回到峰值的日期
                rec_hit = post_v[post_v >= p_ref]
                if not rec_hit.empty:
                    rec_date = rec_hit.index[0]
                    rec_days = len(prices[mdd_valley_date:rec_date]) - 1
                else:
                    # 兜底：如果没找到，就用至今的天数
                    rec_days = len(post_v) - 1
            else:
                # 尚未完全修复，计算从底部至今的天数
                rec_days = len(post_v) - 1
        
        c_strength = strength_val if strength_val is not None else (abs(c_dd) / abs(mdd_total) if mdd_total else 0)

        # 加载翻译
        from core.config_loader import load_vera_rules
        rules = load_vera_rules()
        label_defs = rules.get("d_state", {}).get("labels", {})
        
        # 判定状态 (还原至原版逻辑)
        state_code = "D2"
        if c_dd > -0.05 and max_dd_cycle > -0.15: state_code = "D0"
        elif max_dd_cycle > -0.15: state_code = "D1"
        elif recovery >= 0.95: state_code = "D6"
        elif recovery >= 0.3: state_code = "D5"
        elif recovery > 0.0: state_code = "D4"
        elif c_dd <= -0.35: state_code = "D3"
        else: state_code = "D2"

        res = {
            "state": state_code,
            "desc": label_defs.get(state_code, {}).get("label_zh", ""),
            "has_new_high": current_price >= (peak_10y * 0.999),
            "drawdown": {
                "max_dd_10y_pct": float(mdd_total) if mdd_total is not None else 0.0,
                "mdd_duration_days": int(mdd_duration_days),
                "mdd_peak_date": str(mdd_peak_date.date()) if hasattr(mdd_peak_date, 'date') else str(mdd_peak_date),
                "mdd_valley_date": str(mdd_valley_date.date()) if hasattr(mdd_valley_date, 'date') else str(mdd_valley_date),
                "current_dd_pct": float(c_dd),
                "current_dd_days": int(len(prices[peak_date_10y:]) - 1),
                "dd_strength_vs_max": float(c_strength),
                "recovery_pct": float(recovery),
                "recovery_days": int(rec_days)
            },
            "raw_metrics": {
                "recovery": float(recovery),
                "recovery_days": int(rec_days),
                "current_dd": float(c_dd),
                "max_dd_cycle": float(max_dd_cycle)
            }
        }
        return res
        return res

    @staticmethod
    def apply_recent_cycle_gate(base_d_state: str, recent: RecentCycleInfo) -> str:
        """
        输入：10Y D-State + 1Y R-State
        输出：修正后的 D-State（用于最终展示和 PermissionEngine）
        """
        # 1. 若近期状态较温和 (R0/R1)，则不做修正
        # R0_NORMAL, R1_PULLBACK
        if recent.state in ["R0_NORMAL", "R1_PULLBACK"]:
            return base_d_state

        # 2. R2 及以上视为“结构性回调或更严重”
        # 阈值：当前回撤绝对值 >= 25%
        if abs(recent.off_high_1y) < 0.25:
            # 回撤幅度不算非常大 (<25%)，只是压制 D6 完全修复 -> D4 早期反弹 (或 D2)
            # 这里的逻辑是：如果整体看是 D6 (接近历史新高)，但最近跌了快 20%，肯定不能叫“完全修复”
            if base_d_state == "D6":
                return "D4" # 退回到早期反弹/震荡区
            # 如果是 D5 (修复中段)，近期跌了 20%，可能也就是回到 D2 结构性回调
            if base_d_state == "D5":
                return "D2"
            return base_d_state

        # 3. 回撤幅度较大 (>= 25%)，强制回退
        # 即使长期看修复率很高（腾讯 case），也不能显示 D5
        
        # 阈值：>= 35% 深度回撤 -> D3
        if abs(recent.off_high_1y) >= 0.35:
            return "D3"
        
        # 阈值：25% - 35% -> D2 (结构受压)
        # 这里可以使用特殊的 D2_STRUCTURAL_PULLBACK 状态码，如果下游支持
        return "D2"
