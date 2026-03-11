# State.json 格式更新报告

**更新时间**: 2026-03-11  
**更新原因**: 将过时的 day 编号格式更新为日期字符串格式

---

## 一、更新内容

### 1. state.json 主状态文件

#### 旧格式 (已废弃)
```json
{
  "in_transit_orders": [
    {
      "ship_day": 9,  // ❌ day 编号
      "weight": 35.0
    }
  ],
  "x_prev": {
    "W1_HT-2026-001_A_20": 67.36  // ❌ day 编号
  },
  "last_run_day": 20  // ❌ day 编号
}
```

#### 新格式 (推荐)
```json
{
  "in_transit_orders": [
    {
      "ship_day": "2026-03-10",  // ✅ 日期字符串
      "weight": 35.0
    }
  ],
  "x_prev": {
    "W1_HT-2026-001_A_2026-03-11": 67.36  // ✅ 日期字符串
  },
  "last_run_date": "2026-03-11",  // ✅ 日期字符串
  "last_run_day": 71  // ⚠️  保留用于向后兼容
}
```

### 2. plan_day*.json 计划文件

#### 旧格式
```json
{
  "today": 10  // ❌ day 编号
}
```

#### 新格式
```json
{
  "today": "2026-01-11"  // ✅ 日期字符串
}
```

---

## 二、更新的文件

| 文件 | 修改内容 | 状态 |
|------|---------|------|
| `v2/state/state.json` | ship_day, x_prev, last_run_date | ✅ 已更新 |
| `v2/state/plan_day10.json` | today 字段 | ✅ 已更新 |
| `v2/state/plan_day11.json` | today 字段 | ✅ 已更新 |
| `v2/state/plan_day12.json` | today 字段 | ✅ 已更新 |
| `v2/state/plan_day13.json` | today 字段 | ✅ 已更新 |
| `v2/state/plan_day14.json` | today 字段 | ✅ 已更新 |
| `v2/state/plan_day15.json` | today 字段 | ✅ 已更新 |
| `v2/state/plan_day16.json` | today 字段 | ✅ 已更新 |
| `v2/state/plan_day17.json` | today 字段 | ✅ 已更新 |
| `v2/state/plan_day18.json` | today 字段 | ✅ 已更新 |
| `v2/state/plan_day19.json` | today 字段 | ✅ 已更新 |
| `v2/state/plan_day20.json` | today 字段 | ✅ 已更新 |

---

## 三、数据说明

### state.json 数据

**已到货量**:
- HT-2026-001: 0.0 吨
- HT-2026-002: 0.0 吨

**在途报单**:
- DL001: W1 → HT-2026-001 (A 品类), 35 吨，2026-03-10 发货
- DL002: W1 → HT-2026-002 (A 品类), 36 吨，2026-03-10 发货

**历史计划 (x_prev)**:
- 包含 2026-03-11 至 2026-03-20 共 10 天的计划
- 用于滚动优化的稳定性约束

**状态信息**:
- last_run_date: "2026-03-11" (当前运行日期)
- last_run_day: 71 (向后兼容)
- last_updated: "2026-03-11T16:00:00.000000"

### plan_day*.json 数据

每个计划文件包含：
- **today**: 执行日期（日期字符串）
- **shipments**: 发货计划列表
  - warehouse: 仓库
  - cid: 合同 ID
  - category: 品类
  - tons: 吨数
- **trucks**: 车数建议
  - warehouse: 仓库
  - cid: 合同 ID
  - trucks: 建议车数
  - mixing: 混装详情

---

## 四、格式规范

### 日期字段统一使用 YYYY-MM-DD 格式

| 字段 | 位置 | 格式 | 示例 |
|------|------|------|------|
| `ship_day` | in_transit_orders | YYYY-MM-DD | "2026-03-10" |
| `today` | plan_day*.json | YYYY-MM-DD | "2026-01-11" |
| `last_run_date` | state.json | YYYY-MM-DD | "2026-03-11" |
| `x_prev` 键名 | state.json | {仓库}_{合同}_{品类}_{日期} | "W1_HT-2026-001_A_2026-03-11" |

### 向后兼容

保留 `last_run_day` 字段（day 编号），用于：
- 兼容旧版代码
- 历史数据对比
- 快速计算天数差

---

## 五、验证方法

### 1. 检查 state.json 格式
```bash
cd /root/.openclaw/workspace/PreModels/v2/state
cat state.json | jq '.in_transit_orders[0].ship_day'
# 应输出："2026-03-10" (字符串)
```

### 2. 检查 plan 文件
```bash
cat plan_day11.json | jq '.today'
# 应输出："2026-01-11" (字符串)
```

### 3. 运行测试
```bash
python3 tests/test_optimization_models.py
# 所有测试应通过
```

---

## 六、注意事项

1. **日期格式统一**: 所有日期字段必须使用 "YYYY-MM-DD" 字符串格式
2. **x_prev 键名**: 使用日期字符串作为键名的一部分
3. **向后兼容**: 保留 last_run_day 字段但不要在新代码中使用
4. **文件编码**: 所有 JSON 文件使用 UTF-8 编码

---

## 七、相关文档

- [PD_API_INTEGRATION.md](./PD_API_INTEGRATION.md) - PD API 对接文档
- [CONTRACT_PRODUCTS_UPDATE_20260310.md](./CONTRACT_PRODUCTS_UPDATE_20260310.md) - 合同品类更新
- [DATE_REFACTOR_COMPLETE_20260309.md](./DATE_REFACTOR_COMPLETE_20260309.md) - 日期格式重构完成报告

---

**更新完成！所有状态文件已更新为正确的日期字符串格式。** ✅
