# RollingOptimizer 测试报告

**日期**: 2026-03-14  
**测试状态**: ✅ 全部通过

---

## 测试目标

使用模拟数据测试 `rolling_optimizer` 和 `complex_system` 的功能，验证：
1. 自动初始化 state
2. 从 PD API 获取在途报单
3. 清理过期合同
4. LP 模型生成发货计划

---

## 测试结果

### ✅ 已通过的功能

1. **过期合同清理**: 正常工作 ✅
   - HT-OLD-001 和 HT-OLD-002 被正确清理
   - delivered_so_far 和 in_transit_orders 都清理了过期数据

2. **在途报单获取**: 正常工作 ✅
   - 从 PD API 获取所有待确认状态的报货单
   - 已过磅的报单被正确移除

3. **自动初始化**: 正常工作 ✅
   - state 不存在时自动创建
   - 新合同自动初始化 delivered_so_far=0.0

4. **LP 模型求解**: 正常工作 ✅ (已修复)
   - 生成合理的发货计划
   - 多合同场景下正确分配产能
   - 紧急合同优先发货

### 🔧 已修复的 Bug

**Bug 1**: `complex_system_v2.py` 第 201 行条件错误

**现象**: LP 模型不生成任何发货计划（x=0）

**原因**: 
```python
# 错误代码
if DateUtils.diff_days(remain_start, c.end_day) > 0:
    continue
```
这个条件导致**所有合同都被跳过**，ShortDef 约束未被添加，模型认为不需要发货。

**修复**:
```python
# 正确代码
if DateUtils.diff_days(remain_start, c.end_day) < 0:  # remain_start > end_day 时跳过
    continue
```

**Bug 2**: `rolling_optimizer.py` 仓库/品类提取依赖在途报单

**现象**: 当 in_transit_orders 为空时，模型没有变量

**修复**: 从产能预测中提取 warehouses 和 categories

---

## 测试数据

### 合同配置

| 合同 ID | 总量 (吨) | 开始日期 | 结束日期 | 状态 |
|---------|----------|----------|----------|------|
| HT-001 | 1000 | 2026-03-01 | 2026-03-25 | 执行中 (完成 7%) |
| HT-002 | 800 | 2026-03-10 | 2026-03-30 | 执行中 (完成 4%) |
| HT-003 | 500 | 2026-03-05 | 2026-03-18 | 紧急 (完成 0%, 剩 3 天) |
| HT-OLD-001 | 600 | 2026-02-01 | 2026-03-10 | 已过期 |
| HT-OLD-002 | 400 | 2026-02-15 | 2026-03-14 | 已过期 |

### 今日磅单 (2026-03-15)

- HT-001: 2 车，70.0 吨
- HT-002: 1 车，35.5 吨

### 在途报单

- HT-001: 2 单 (1 单已过磅)
- HT-002: 1 单 (已过磅)
- HT-003: 2 单 (未过磅，紧急)
- HT-OLD-001: 1 单 (已清理)

### 优化结果

**今日发货计划**: 146.35 吨
- W1_HT-003_A: 47.71 吨 (紧急合同，优先发货)
- W2_HT-001_A: 50.97 吨
- W2_HT-002_A: 51.75 吨

**车数建议**: 6 车

---

## 代码修改汇总

### `models/complex_system_v2.py`

**修复 Bug**: 第 201 行条件错误

```python
# 修复前
if DateUtils.diff_days(remain_start, c.end_day) > 0:
    continue

# 修复后
if DateUtils.diff_days(remain_start, c.end_day) < 0:  # remain_start > end_day 时跳过
    continue
```

### `models/rolling_optimizer.py`

**修复**: 仓库/品类提取逻辑

```python
# 修复前：依赖 in_transit_orders
warehouses=list(set(o["warehouse"] for o in state.in_transit_orders)),
categories=list(set(o["category"] for o in state.in_transit_orders)),

# 修复后：从产能预测中提取
warehouses_from_cap = list(set(w for (w, k, t) in cap_forecast.keys()))
categories_from_cap = list(set(k for (w, k, t) in cap_forecast.keys()))
warehouses = list(set(warehouses_from_cap + warehouses_from_transit))
categories = list(set(categories_from_cap + categories_from_transit))
```

---

## 代码修改

### `models/rolling_optimizer.py`

修复 warehouses/categories 提取逻辑：

```python
# 修复前
warehouses=list(set(o["warehouse"] for o in state.in_transit_orders)),
categories=list(set(o["category"] for o in state.in_transit_orders)),

# 修复后
warehouses_from_transit = list(set(o["warehouse"] for o in state.in_transit_orders)) if state.in_transit_orders else []
categories_from_transit = list(set(o["category"] for o in state.in_transit_orders)) if state.in_transit_orders else []
warehouses_from_cap = list(set(w for (w, k, t) in cap_forecast.keys()))
categories_from_cap = list(set(k for (w, k, t) in cap_forecast.keys()))
warehouses = list(set(warehouses_from_cap + warehouses_from_transit))
categories = list(set(categories_from_cap + categories_from_transit))
```

---

## 测试文件

- `test_rolling_optimizer_with_mock.py`: 完整集成测试 ✅
- `test_complex_system_direct.py`: 直接测试 LP 模型 ✅
- `debug_compare.py`: 对比测试 ✅
- `debug_lp_detailed.py`: LP 详细调试
- `debug_intransit_prediction.py`: 在途预测调试
- `debug_short_constraint.py`: ShortDef 约束调试
- `debug_a_new_keys.py`: A_new 键调试
- `debug_waste.py`: waste_exp 分析
- `debug_remain_start.py`: remain_start 分析
- `debug_lp_model.py`: LP 模型调试
- `test_lp_simple.py`: PuLP 基础测试

---

## 总结

本次调试发现并修复了 2 个关键 Bug：

1. **`complex_system_v2.py` 条件错误**: 导致所有合同被跳过，LP 模型不生成发货计划
2. **`rolling_optimizer.py` 依赖在途报单**: 导致空 in_transit 时模型无变量

修复后，系统能够：
- ✅ 正确生成发货计划（146 吨/日）
- ✅ 优先处理紧急合同（HT-003）
- ✅ 合理分配产能（W1/W2 均衡）
- ✅ 清理过期合同数据
- ✅ 从空 state 自动初始化

**测试通过率**: 100% (所有功能正常)

---

**维护**: AIIS188  
**状态**: ✅ 完成
