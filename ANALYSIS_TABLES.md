# VERA 分析快照表说明

## ✅ 新增的核心分析表

### 4. 分析快照表 (analysis_snapshot)
**用途**：核心表，原 `vera_snapshot` 的升级版，存储完整的分析结果

| 字段 | 类型 | 说明 |
|------|------|------|
| snapshot_id | TEXT (PK) | UUID 唯一标识 |
| asset_id | TEXT (FK) | 资产代码 |
| as_of_date | DATE | 评估日期 |
| risk_level | TEXT | 风险等级（High/Medium/Low） |
| valuation_anchor | TEXT | 选用的估值锚（PE/PB/PS） |
| valuation_status | TEXT | 估值状态（Undervalued/Fair/Overvalued） |
| payout_score | INTEGER | 价值兑现分（-2 到 +2） |
| is_value_trap | BOOLEAN | 是否触发价值陷阱 |
| created_at | DATETIME | 创建时间 |

**外键**：asset_id → assets(asset_id) ON DELETE CASCADE

**关键特性**：
- 使用 UUID 作为主键，便于分布式系统和跨系统引用
- 包含风险评估、估值分析、价值陷阱判断等核心决策信息
- 每次分析生成一个快照，可追溯历史决策

### 5. 指标明细表 (metric_details)
**用途**：存储快照相关的所有指标，支持历史分位数

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER (PK) | 自增主键 |
| snapshot_id | TEXT (FK) | 关联的快照 ID |
| metric_key | TEXT | 指标名称（如 max_drawdown, pe_ratio） |
| value | REAL | 指标绝对值 |
| percentile | REAL | 历史分位数（0.0 - 1.0） |

**外键**：snapshot_id → analysis_snapshot(snapshot_id) ON DELETE CASCADE

**关键特性**：
- 支持任意指标的存储（灵活扩展）
- **percentile 字段**：记录该指标在历史数据中的分位数
  - 0.0 = 历史最低
  - 0.5 = 中位数
  - 1.0 = 历史最高
- 用于判断当前指标是否处于极端值

### 6. 决策日志表 (decision_log)
**用途**：记录基于快照做出的投资决策，用于复盘

| 字段 | 类型 | 说明 |
|------|------|------|
| decision_id | INTEGER (PK) | 自增主键 |
| snapshot_id | TEXT (FK) | 关联的快照 ID（必须） |
| action | TEXT | 操作（Buy/Sell/Hold） |
| context_note | TEXT | 当时的想法记录 |
| created_at | DATETIME | 决策时间 |

**外键**：snapshot_id → analysis_snapshot(snapshot_id) ON DELETE CASCADE

**关键特性**：
- 每个决策必须关联到具体的快照
- 支持复盘：可以查看当时的分析结果和决策依据
- context_note 记录主观判断，用于总结经验教训

## 表关系图

```
assets (资产表)
  ├─→ price_history (价格历史表)
  ├─→ financial_history (财务历史表)
  └─→ analysis_snapshot (分析快照表)
        ├─→ metric_details (指标明细表)
        └─→ decision_log (决策日志表)
```

## 数据库表总览（更新）

当前数据库包含 **10 张表**：

### 旧表（待弃用）
1. `vera_price_cache` - 价格缓存（旧）
2. `vera_snapshot` - 快照记录（旧）
3. `vera_risk_metrics` - 风险指标（旧）

### 新表（VERA 核心）
4. ✅ `assets` - 资产表
5. ✅ `price_history` - 价格历史表
6. ✅ `financial_history` - 财务历史表
7. ✅ `analysis_snapshot` - 分析快照表（新）
8. ✅ `metric_details` - 指标明细表（新）
9. ✅ `decision_log` - 决策日志表（新）

### 系统表
10. `sqlite_sequence` - SQLite 自增序列表

## 使用示例

### 创建一个分析快照
```python
import uuid
from datetime import date

snapshot_id = str(uuid.uuid4())

# 1. 创建快照
cursor.execute("""
    INSERT INTO analysis_snapshot 
    (snapshot_id, asset_id, as_of_date, risk_level, valuation_anchor, 
     valuation_status, payout_score, is_value_trap)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (snapshot_id, "TSLA", date.today(), "Medium", "PE", 
      "Overvalued", -1, False))

# 2. 添加指标明细
cursor.execute("""
    INSERT INTO metric_details 
    (snapshot_id, metric_key, value, percentile)
    VALUES (?, ?, ?, ?)
""", (snapshot_id, "max_drawdown", -0.35, 0.72))

# 3. 记录决策
cursor.execute("""
    INSERT INTO decision_log 
    (snapshot_id, action, context_note)
    VALUES (?, ?, ?)
""", (snapshot_id, "Hold", "估值偏高但增长强劲，继续观察"))
```

## 下一步工作

1. **更新 snapshot_builder**：使用新的 `analysis_snapshot` 表
2. **实现百分位计算**：为每个指标计算历史分位数
3. **实现估值分析**：基于财务数据计算 PE/PB/PS
4. **实现风险评级**：基于多个指标综合评估风险等级
5. **逐步弃用旧表**：将旧的 `vera_*` 表标记为废弃
