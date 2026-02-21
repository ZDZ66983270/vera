# VERA 新表结构说明

## ✅ 已创建的新表

### 1. 资产表 (assets)
**用途**：存储资产基本信息

| 字段 | 类型 | 说明 |
|------|------|------|
| asset_id | TEXT (PK) | 标的代码（如 AAPL, 00700.HK） |
| symbol_name | TEXT | 名称 |
| market | TEXT | 市场（US/HK/CN） |
| industry | TEXT | 行业（用于估值锚定） |
| created_at | DATETIME | 创建时间 |

### 2. 价格历史表 (price_history)
**用途**：存储日线级别的价格数据

| 字段 | 类型 | 说明 |
|------|------|------|
| asset_id | TEXT (PK) | 资产代码 |
| trade_date | DATE (PK) | 交易日期 |
| open | REAL | 开盘价 |
| high | REAL | 最高价 |
| low | REAL | 最低价 |
| close | REAL | 收盘价 |
| adj_close | REAL | **复权收盘价**（核心计算字段，计算收益率基于此字段） |
| volume | REAL | 成交量 |

**外键**：asset_id → assets(asset_id) ON DELETE CASCADE

### 3. 财务历史表 (financial_history)
**用途**：存储财务指标数据，用于估值计算

| 字段 | 类型 | 说明 |
|------|------|------|
| asset_id | TEXT (PK) | 资产代码 |
| report_date | DATE (PK) | 报告日期 |
| eps_ttm | REAL | 用于计算 PE |
| bps | REAL | 用于计算 PB |
| revenue_ttm | REAL | 用于计算 PS |
| net_profit_ttm | REAL | 用于计算利润率 |
| dividend_amount | REAL | 年度分红总额 |
| buyback_amount | REAL | 年度回购总额 |

**外键**：asset_id → assets(asset_id) ON DELETE CASCADE

## 数据库表总览

当前数据库包含 **7 张表**：

### 核心表（MVP）
1. ✅ `vera_price_cache` - 价格缓存（旧）
2. ✅ `vera_snapshot` - 快照记录
3. ✅ `vera_risk_metrics` - 风险指标事实表

### 新增表（Phase 2）
4. ✅ `assets` - 资产表
5. ✅ `price_history` - 价格历史表
6. ✅ `financial_history` - 财务历史表

### 系统表
7. `sqlite_sequence` - SQLite 自增序列表

## 表关系图

```
assets (资产表)
  ├─→ price_history (价格历史表)
  └─→ financial_history (财务历史表)

vera_snapshot (快照表)
  └─→ vera_risk_metrics (风险指标表)
```

## 下一步工作

1. **数据迁移**：考虑将 `vera_price_cache` 的数据迁移到 `price_history`
2. **数据获取**：实现从 yfinance 获取数据并填充到新表
3. **资产管理**：实现资产的添加、查询功能
4. **财务数据**：实现财务指标的获取和存储
