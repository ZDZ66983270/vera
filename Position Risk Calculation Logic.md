# Position Risk 计算逻辑详解

> **版本历史**
> - **v1.0**: 基于 progress（回撤进度）的位置计算
> - **v2.0** (2024-12-24): 引入二值化逻辑 + 滞回防抖 + 统一 Quadrant 计算

---

## 🆕 v2.0 升级摘要

### **核心改进**

**问题**：v1.0 中 Position 和 Path 使用三值 (HIGH/MID/LOW)，导致象限判断不稳定，且前端可能重复推导。

**解决方案**：
1. ✅ **二值化** - Position/Path 只有 HIGH/LOW 两种状态
2. ✅ **滞回机制** - 边界切换需要满足不同阈值，防抖动
3. ✅ **后端权威** - Quadrant 只由后端计算，前端不再推导
4. ✅ **验证规则** - 5条展示一致性规则确保语义正确

### **新增模块**

- [`analysis/risk_quadrant.py`](#新增模块-risk_quadrantpy) - 二值化逻辑与 Quadrant 计算
- 新增字段：`pos_bin`, `path_bin`, `path_state`

[跳转到 v2.0 详细说明 ↓](#v20-二值化逻辑与-quadrant-重构)

---

## 概述 (v1.0)

Position Risk (当前位置/行为风险) 是 VERA 风险矩阵系统的核心维度之一，用于判断**资产当前价格在历史回撤路径中的位置**，并据此评估潜在的行为偏差风险（如 FOMO、恐慌抛售等）。

---

## 核心数据来源

### **`progress` (回撤进度)**

Position Risk 基于 **状态机确认的回撤进度** (`confirmed_progress`)，这个值来自 `StateMachine` 的输出。

- **progress = 0.0**: 当前在历史高点（Peak）
- **progress = 1.0**: 当前在回撤底部（Trough）
- **progress = 0.5**: 回撤进度 50%（从高点到低点的中间）

---

## 计算流程

### **Step 1: 获取确认进度**

```python
# analysis/risk_matrix.py L101
progress = _get_confirmed_progress(self.risk_metrics)
```

**数据来源**:
```python
# L24-36
def _get_confirmed_progress(risk_metrics: Dict[str, Any]) -> Optional[float]:
    """
    Use state-machine confirmed progress as the ONLY position progress source.
    """
    rs = risk_metrics.get("risk_state") or {}
    p = rs.get("progress")
    if p is None:
        return None
    try:
        p = float(p)
        return max(0.0, min(1.0, p))  # 限制在 [0, 1] 区间
    except Exception:
        return None
```

---

### **Step 2: 判定位置区域 (Zone)**

```python
# L103-115
if progress is None:
    zone = "Unknown"
elif progress <= 0.05:
    zone = "Peak"     # 阶段高点（±5%）
elif progress >= 0.95:
    zone = "Trough"   # 阶段低点（±5%）
elif progress < 0.33:
    zone = "Upper"    # 上部区域
elif progress < 0.66:
    zone = "Middle"   # 中部区域
else:
    zone = "Lower"    # 下部区域
```

#### **Zone 映射表**

| Progress 范围 | Zone | 位置描述 | 风险含义 | Quadrant 倾向 |
|--------------|------|---------|---------|--------------|
| **0.00 - 0.05** | Peak | 阶段高点（非回撤中） | FOMO 风险区（追涨） | Q1/Q2 (高位) |
| **0.05 - 0.33** | Upper | 上部区域（初期回撤） | 调整初期，警惕转向 | Q1/Q2 (高位) |
| **0.33 - 0.66** | Middle | 中部区域（中度回撤） | 博弈区，方向不明 | Q3/Q4 (过渡) |
| **0.66 - 0.95** | Lower | 下部区域（深度回撤） | 接近底部，修复预期 | Q3/Q4 (低位) |
| **0.95 - 1.00** | Trough | 阶段低点（回撤底部） | 恐慌抛售风险区 | Q3/Q4 (低位) |

---

### **Step 3: UI 显示控制 (Guardrails)**

```python
# L117-122
show_pct = True
if progress is None:
    show_pct = False
elif progress <= 0.05 or progress >= 0.95:
    show_pct = False  # Peak/Trough 不显示具体百分比
```

**设计理念**:
- **Peak/Trough**: 显示语义化标签（如"阶段高点"），不显示具体数字
  - **原因**: 避免用户误解为"距离高点 5%" 等错误解读
- **其他区域**: 显示具体进度百分比（如"回撤阶段：45.2%"）
  - **原因**: 明确告知用户当前在回撤路径中的相对位置

---

### **Step 4: 生成显示标签**

```python
# L132-139
def _position_label(self, zone: str, show_pct: bool, progress: Optional[float]) -> str:
    if not show_pct:
        if zone == "Peak":
            return "当前位置：阶段高点（非回撤中）"
        if zone == "Trough":
            return "当前位置：阶段低点（回撤底部）"
        return "当前位置：—"
    return f"回撤阶段：{round(progress * 100, 1)}%"
```

#### **标签示例**

| Progress | Zone | show_pct | Label 输出 |
|----------|------|----------|-----------|
| 0.02 | Peak | False | "当前位置：阶段高点（非回撤中）" |
| 0.25 | Upper | True | "回撤阶段：25.0%" |
| 0.50 | Middle | True | "回撤阶段：50.0%" |
| 0.75 | Lower | True | "回撤阶段：75.0%" |
| 0.98 | Trough | False | "当前位置：阶段低点（回撤底部）" |

---

### **Step 5: 返回 Position Card**

```python
# L124-130
return {
    "progress": progress,                           # 原始进度值 (0~1)
    "progress_pct": round(progress * 100, 1) if (show_pct and progress is not None) else None,
    "zone": zone,                                   # Zone 标识
    "show_progress_pct": show_pct,                  # UI 控制标志
    "label": self._position_label(zone, show_pct, progress),
}
```

---

## 与 Quadrant 系统的交互 (v1.0)

Position Zone 与 **Path Risk Level** 结合，映射到 **Risk Quadrant**：

```python
# v1.0 - 已废弃 (保留用于对比)
def get_quadrant(pos_zone: str, path_zone: str) -> str:
    """
    ⚠️ v1.0 逻辑：使用三值 (HIGH/MID/LOW)
    问题：MID 导致判断模糊
    """
    is_pos_high = (pos_zone in ["Peak", "Upper"])   # HIGH position
    is_path_high = (path_zone == "HIGH")
    
    if is_pos_high and not is_path_high: return "Q1"  # 追涨区
    if is_pos_high and is_path_high:     return "Q2"  # 极危险
    if not is_pos_high and is_path_high: return "Q3"  # 恐慌区
    return "Q4"  # 相对稳态
```

### **Quadrant → Behavior Flags 映射**

```python
# L210-247
if quadrant == "Q1":
    flags.append({"code": "FOMO_RISK", "title": "追涨风险 (FOMO)"})
elif quadrant == "Q2":
    flags.append({"code": "OVERCONFIDENCE_RISK", "title": "情绪坍塌风险"})
elif quadrant == "Q3":
    flags.append({"code": "PANIC_SELL_RISK", "title": "杀跌风险 (PANIC)"})
elif quadrant == "Q4":
    flags.append({"code": "FALSE_SECURITY_RISK", "title": "相对稳态"})
```

---

## v2.0 二值化逻辑与 Quadrant 重构

### **问题诊断**

v1.0 存在的核心问题：
1. **三值模糊**: Position 和 Path 使用 HIGH/MID/LOW 三值，导致边界不清晰
2. **前端推导**: UI 可能根据 percentile/state 自行计算 Quadrant，造成不一致
3. **MID 干扰**: MID 状态在象限判断中引入不确定性

---

### **新增模块: risk_quadrant.py**

#### **核心数据结构**

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class PositionRiskResult:
    """Position Risk 计算结果 (v2.0)"""
    price_percentile: Optional[float]    # 0..1 价格分位
    pos_bin: str                          # "HIGH" | "LOW" (二值化)
    path_bin: str                         # "HIGH" | "LOW" (二值化)
    risk_quadrant: str                    # "Q1".."Q4"
    notes: Dict[str, Any]                 # 解释信息（如 hysteresis, dd_state）
```

---

#### **1. Position 二值化（带滞回防抖）**

```python
def _bin_position(price_percentile: Optional[float],
                  *,
                  enter_high: float = 0.62,
                  exit_high: float = 0.58,
                  last_pos_bin: Optional[str] = None) -> str:
    """
    二值化位置（带滞回，防抖）
    
    滞回逻辑：
    - 从 LOW → HIGH：需要超过 62%
    - 从 HIGH → LOW：需要低于 58%
    - 无历史时：用 60% 作为稳健阈值
    """
    if price_percentile is None:
        return "LOW"

    if last_pos_bin == "HIGH":
        return "HIGH" if price_percentile >= exit_high else "LOW"
    if last_pos_bin == "LOW":
        return "HIGH" if price_percentile >= enter_high else "LOW"

    # 没有历史时用稳健阈值
    return "HIGH" if price_percentile >= 0.60 else "LOW"
```

**滞回优势**：
- 防止在 60% 附近频繁切换（抖动）
- 需要明确的趋势才触发状态变化
- 更稳定的 Quadrant 输出

---

####  **2. Path 二值化（基于 D-state）**

```python
def _bin_path_from_dd_state(dd_state: Optional[str]) -> str:
    """
    二值化路径（结构）
    
    规则：
    - D0/D1/D2：结构相对稳（LOW）
    - D3/D4/D5：结构脆弱（HIGH）
    """
    if not dd_state:
        return "LOW"
    s = dd_state.strip().upper()
    return "HIGH" if s in {"D3", "D4", "D5"} else "LOW"
```

**映射表**：

| D-state | 结构状态 | path_bin |
|---------|---------|----------|
| D0 | 未形成完整回撤结构 | LOW |
| D1 | 正常波动期 | LOW |
| D2 | 结构中性 | LOW |
| D3 | 博弈区 | **HIGH** |
| D4 | 敏感阶段 | **HIGH** |
| D5 | 脆弱阶段 | **HIGH** |

---

#### **3. Quadrant 映射（冻结标准）**

```python
def _quadrant_from_bins(pos_bin: str, path_bin: str) -> str:
    """
    2x2 Quadrant 定义（冻结为 v2.0 标准）
    
    映射规则：
    - HIGH + LOW  → Q1 (追涨区)
    - HIGH + HIGH → Q2 (泡沫区)
    - LOW  + HIGH → Q3 (恐慌区)
    - LOW  + LOW  → Q4 (稳态区)
    """
    if pos_bin == "HIGH" and path_bin == "LOW":
        return "Q1"
    if pos_bin == "HIGH" and path_bin == "HIGH":
        return "Q2"
    if pos_bin == "LOW" and path_bin == "HIGH":
        return "Q3"
    return "Q4"
```

**2×2 矩阵**：

|  | path_bin=LOW | path_bin=HIGH |
|--|--------------|---------------|
| **pos_bin=HIGH** | Q1 (追涨区) | Q2 (泡沫区) |
| **pos_bin=LOW** | Q4 (稳态区) | Q3 (恐慌区) |

---

#### **4. 统一计算入口**

```python
def compute_position_risk(price_percentile: Optional[float],
                          dd_state: Optional[str],
                          *,
                          last_pos_bin: Optional[str] = None) -> PositionRiskResult:
    """
    统一计算 Position Risk 与 Quadrant (v2.0)
    
    使用示例：
    >>> result = compute_position_risk(0.65, "D2")
    >>> result.pos_bin        # "HIGH"
    >>> result.path_bin       # "LOW"
    >>> result.risk_quadrant  # "Q1"
    """
    pos_bin = _bin_position(price_percentile, last_pos_bin=last_pos_bin)
    path_bin = _bin_path_from_dd_state(dd_state)
    quad = _quadrant_from_bins(pos_bin, path_bin)

    return PositionRiskResult(
        price_percentile=price_percentile,
        pos_bin=pos_bin,
        path_bin=path_bin,
        risk_quadrant=quad,
        notes={
            "dd_state": dd_state,
            "hysteresis": {"enter_high": 0.62, "exit_high": 0.58}
        }
    )
```

---

### **集成到 build_risk_card()**

```python
# analysis/risk_matrix.py
def build_risk_card(...):
    from analysis.risk_quadrant import compute_position_risk
    
    # 获取数据
    price_percentile = risk_metrics.get("price_percentile")  # 0..1
    dd_state = (risk_metrics.get("risk_state") or {}).get("state")  # D0-D5
    
    # 🔧 NEW: 使用二值化逻辑计算
    pos_risk = compute_position_risk(price_percentile, dd_state)
    quadrant = pos_risk.risk_quadrant  # 直接使用，不再推导
    
    card_data = {
        ...
        "price_percentile": pos_risk.price_percentile,
        "pos_bin": pos_risk.pos_bin,       # NEW: HIGH/LOW
        "path_bin": pos_risk.path_bin,     # NEW: HIGH/LOW
        "path_state": dd_state,            # NEW: D0-D5
        "risk_quadrant": quadrant,         # Q1-Q4 (来自二值化)
        ...
    }
```

---

### **新增字段说明**

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `pos_bin` | `"HIGH"` \| `"LOW"` | Position 二值化结果 | `"HIGH"` |
| `path_bin` | `"HIGH"` \| `"LOW"` | Path 二值化结果 | `"LOW"` |
| `path_state` | `D0-D5` | D-state (确认后) | `"D2"` |
| `risk_quadrant` | `Q1-Q4` | 来自二值化计算 | `"Q1"` |

---

### **v1.0 vs v2.0 对比**

| 维度 | v1.0 | v2.0 |
|------|------|------|
| **Position** | HIGH/MID/LOW | **HIGH/LOW** (二值化) |
| **Path** | HIGH/MID/LOW | **HIGH/LOW** (D3-D5=HIGH) |
| **滞回** | ❌ 无 | ✅ 62%/58% 双阈值 |
| **计算位置** | 前端可能推导 | **后端权威** |
| **MID 状态** | 存在，导致模糊 | ✅ 删除，清晰二值 |
| **验证规则** | ❌ 无 | ✅ 5条展示规则 |

---

## 展示一致性验证规则

### **规则 R1: Quadrant 只能来自后端**
- ✅ 前端只读取 `risk_quadrant` 字段
- ❌ 禁止前端根据 percentile/state 推导

### **规则 R2: 百分比与风险等级不得矛盾**
- ❌ 错误：`path_risk_level="HIGH"` 但显示 "0% 回撤"
- ✅ 正确：使用语义标签或确保百分比口径一致

### **规则 R3: D0 不得触发"高风险措辞"**
- ❌ 禁止：D0 显示 "Bubble"/"Panic"/"二次探底"
- ✅ 允许：D0 显示 "Neutral"/"Insufficient Evidence"

### **规则 R4: Path 与 Position 不得互相越权**
- Position 不得出现：二次探底、修复失败
- Path 不得出现：贵/便宜/估值偏离（归 Value）

### **规则 R5: 缺失值不得用 0 代替**
- ❌ 错误：`price_percentile=0.0` 表示缺失
- ✅ 正确：`price_percentile=None` 或显示 `N/A`

---

## 代码位置索引 (v2.0)

| 功能 | 文件 | 说明 |
|------|------|------|
| `compute_position_risk()` | `analysis/risk_quadrant.py` | v2.0 统一入口 |
| `_bin_position()` | `analysis/risk_quadrant.py` | Position 二值化 + 滞回 |
| `_bin_path_from_dd_state()` | `analysis/risk_quadrant.py` | Path 二值化 (D3-D5=HIGH) |
| `_quadrant_from_bins()` | `analysis/risk_quadrant.py` | 2×2 Quadrant 映射 |
| `validate_risk_card_display()` | `analysis/risk_quadrant.py` | 5条验证规则 |
| `build_risk_card()` | `analysis/risk_matrix.py` | 集成调用点 |

---

## 实际应用示例 (v2.0)

### **案例 1: TSLA 边界防抖**

```python
# Scenario 1: 初始状态
price_percentile = 0.61
dd_state = "D2"
last_pos_bin = None

result = compute_position_risk(0.61, "D2")
# pos_bin = "HIGH" (>= 0.60)
# path_bin = "LOW" (D2)
# risk_quadrant = "Q1"

# Scenario 2: 小幅回调至 59%（滞回保护）
result2 = compute_position_risk(0.59, "D2", last_pos_bin="HIGH")
# pos_bin = "HIGH" (仍维持，因为 >= exit_high=0.58)
# risk_quadrant = "Q1" (不变)

# Scenario 3: 明确下跌至 57%
result3 = compute_position_risk(0.57, "D2", last_pos_bin="HIGH")
# pos_bin = "LOW" (< exit_high=0.58)
# risk_quadrant = "Q4" (切换)
```

**解读**：滞回机制避免在 60% 附近频繁切换 Quadrant。

---

### **案例 2: 深度回撤中的 SPX**

```python
price_percentile = 0.22  # 低位
dd_state = "D4"          # 敏感阶段

result = compute_position_risk(0.22, "D4")
# pos_bin = "LOW"
# path_bin = "HIGH" (D4)
# risk_quadrant = "Q3" (恐慌区)
# behavior_flag = "PANIC_SELL_RISK"
```

**解读**：价格低位 + 结构脆弱，典型的 Q3 恐慌区，易错误离场。

---

## 总结

Position Risk v2.0 通过 **二值化 + 滞回机制**，将象限判断从模糊的"三值博弈"升级为**清晰的逻辑分支**，同时通过后端统一计算确保前端展示的一致性。

**v2.0 核心价值**:
1. ✅ **稳定性**: 滞回机制避免边界抖动
2. ✅ **清晰性**: 二值化消除 MID 模糊地带
3. ✅ **权威性**: 后端统一计算，前端不推导
4. ✅ **可验证性**: 5条规则确保展示语义正确
5. ✅ **行为导向**: Quadrant 直接映射 Behavior Flags
