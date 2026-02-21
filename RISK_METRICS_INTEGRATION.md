# VERA 风险指标表集成完成

## ✅ 已完成

### 1. 数据库表结构
成功添加 `vera_risk_metrics` 表到 `db/schema.sql`：

```sql
CREATE TABLE IF NOT EXISTS vera_risk_metrics (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id        INTEGER NOT NULL,
    metric_name        TEXT NOT NULL,     -- max_drawdown / volatility
    metric_value       REAL NOT NULL,
    window             INTEGER,           -- 252 / 60 / 5 等
    parameters         TEXT,              -- JSON 字符串
    unit               TEXT,              -- %, days, ratio
    computed_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id)
        REFERENCES vera_snapshot(id)
        ON DELETE CASCADE
);
```

### 2. 引擎更新
更新了 `engine/snapshot_builder.py` 中的 `save_snapshot()` 函数：
- 保存快照记录到 `vera_snapshot`
- 获取 `snapshot_id`
- 将 `max_drawdown` 和 `annual_volatility` 指标保存到 `vera_risk_metrics`

### 3. 数据库验证
当前数据库包含的表：
- ✅ `vera_price_cache` - 价格缓存
- ✅ `vera_snapshot` - 快照记录
- ✅ `vera_risk_metrics` - 风险指标（新增）

## 下一步升级路径

按照原计划，接下来可以添加：
1. ❌ 市场开闭逻辑
2. ❌ 百分位计算
3. ❌ 行为标志
4. ❌ UI
5. ❌ AI 集成
