"""
VERA Recent Cycle Engine (近期周期风险引擎)
-------------------------------------------
负责评估 1年期（约252个交易日）内的回撤周期状态 (R-State)。
R-State 分类基于两个维度的交叉：
  1. 幅度维度 (amp_key)：回撤/年波动率 → sigma 分桶 (A0~A4)
  2. 时间维度 (dur_key)：回撤持续交易日 → 时间分桶 (T0~T2)
分类规则从 vera_rules.yaml 中的 state_matrix 读取。

此模块仅负责计算，不操作数据库和 UI。
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from core.config_loader import load_vera_rules


@dataclass
class RecentCycleInfo:
    state: str                      # R-State code, e.g. "R0_NORMAL"
    state_label_zh: str             # 中文标签
    off_high_1y: float              # 当前价格距1Y高点的回撤幅度 (负数)
    max_dd_1y: float                # 1Y内最大回撤 (负数)
    dd_days: int                    # 回撤持续的交易日数
    dd_sigma: float                 # 回撤幅度 / 年波动率 (sigma倍数)
    amp_key: str                    # 幅度分桶 key, e.g. "A1_SHALLOW"
    dur_key: str                    # 时间分桶 key, e.g. "T1_INTERMEDIATE"
    peak_1y: float                  # 1Y内最高价
    peak_date: pd.Timestamp         # 1Y最高价对应日期
    valley_1y: float                # 1Y内最低价（从峰后计算）
    valley_date: pd.Timestamp       # 1Y最低价对应日期
    recovery_pct: float             # 从谷底到当前的修复比例 [0, 1]
    recovery_days: int              # 从谷底到当前的交易日数


class RecentCycleEngine:
    def __init__(self):
        self.rules = load_vera_rules()

    def evaluate(self, close: pd.Series, vol_1y: float) -> RecentCycleInfo:
        """
        评估近 1 年回撤周期状态 (R-State)
        """
        if close.empty or len(close) < 20:
            return self._default_r0(close)

        cfg = self.rules.get("risk_overlay", {}).get("drawdown", {}).get("recent_cycle", {})

        # 1. 取 1Y 窗口
        last_date = close.index[-1]
        start_date = last_date - pd.Timedelta(days=365)
        window = close.loc[start_date:]

        if window.empty or len(window) < 2:
            return self._default_r0(close)

        # 2. 找 1Y 最高点（峰值）
        peak_idx = window.idxmax()
        peak_price = float(window.loc[peak_idx])
        current_price = float(close.iloc[-1])

        # 3. 计算当前距峰值回撤
        off_high_1y = (current_price / peak_price) - 1.0

        # 4. 从峰值以后找谷底
        post_peak = window.loc[peak_idx:]
        if post_peak.empty:
            valley_idx = peak_idx
            valley_price = peak_price
        else:
            valley_idx = post_peak.idxmin()
            valley_price = float(post_peak.loc[valley_idx])

        # 5. 1Y 最大回撤（从峰到谷）
        curr_dd = (valley_price / peak_price) - 1.0 if peak_price > 0 else 0.0
        max_dd_cycle = min(curr_dd, off_high_1y)

        # 6. 回撤持续天数（峰值到谷底的交易日数）
        dd_days = max(0, len(window.loc[peak_idx:valley_idx]) - 1)

        # 7. 修复比例（谷底到当前）
        if peak_price > valley_price:
            recovery_pct = max(0.0, min(1.0, (current_price - valley_price) / (peak_price - valley_price)))
        else:
            recovery_pct = 1.0

        # 8. 从谷底到当前的交易日数
        recovery_days = max(0, len(close.loc[valley_idx:]) - 1)

        # 9. 计算 dd_sigma = |off_high_1y| / vol_1y
        vol = vol_1y if vol_1y and vol_1y > 0.01 else 0.01
        dd_sigma = abs(off_high_1y) / vol

        # 10. 分桶
        amp_key = self._match_band(dd_sigma, cfg.get("amp_sigma_bands", []))
        dur_key = self._match_band(dd_days, cfg.get("duration_bands", []))

        # 11. 查 state_matrix
        state_matrix = cfg.get("state_matrix", [])
        matched = False
        chosen = {"state": "R0_NORMAL", "label_zh": "正常波动期"}

        for rule in state_matrix:
            amp_in = rule.get("amp_in", [])
            dur_in = rule.get("dur_in", [])
            if amp_key in amp_in and dur_key in dur_in:
                chosen = {"state": rule.get("state"), "label_zh": rule.get("label_zh", "")}
                matched = True

        # 12. 兜底：超高 sigma (>= 3.0) 必须至少是 R3
        if not matched or (dd_sigma >= 3.0 and chosen["state"] in ["R0_NORMAL", "R1_PULLBACK"]):
            chosen = {"state": "R3_DEEP_BEAR", "label_zh": "深度调整"}

        return RecentCycleInfo(
            state=chosen["state"],
            state_label_zh=chosen["label_zh"],
            off_high_1y=off_high_1y,
            max_dd_1y=max_dd_cycle,
            dd_days=dd_days,
            dd_sigma=dd_sigma,
            amp_key=amp_key,
            dur_key=dur_key,
            peak_1y=peak_price,
            peak_date=peak_idx,
            valley_1y=valley_price,
            valley_date=valley_idx,
            recovery_pct=recovery_pct,
            recovery_days=recovery_days,
        )

    def _default_r0(self, close: pd.Series) -> RecentCycleInfo:
        """数据不足时返回 R0 默认状态"""
        last_price = float(close.iloc[-1]) if not close.empty else 0.0
        last_date = close.index[-1] if not close.empty else pd.Timestamp.utcnow()
        return RecentCycleInfo(
            state="R0_NORMAL",
            state_label_zh="正常波动期",
            off_high_1y=0.0,
            max_dd_1y=0.0,
            dd_days=0,
            dd_sigma=0.0,
            amp_key="A0_FLAT",
            dur_key="T0_BRIEF",
            peak_1y=last_price,
            peak_date=last_date,
            valley_1y=last_price,
            valley_date=last_date,
            recovery_pct=1.0,
            recovery_days=0,
        )

    @staticmethod
    def _match_band(value, bands: list) -> str:
        """根据 value 匹配 bands 列表中的分桶，返回对应 key"""
        if not bands:
            return "UNKNOWN"
        for band in bands:
            rg = band.get("range")
            if rg and len(rg) >= 2:
                lo, hi = rg[0], rg[-1]
                if lo <= value < hi:
                    return band.get("key", "UNKNOWN")
        # 超出最大范围时返回最后一个桶
        return bands[-1].get("key", "UNKNOWN")
