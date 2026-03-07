# PreModels v2 技术文档

## 📋 目录

- [系统概述](#系统概述)
- [核心算法](#核心算法)
- [数据流](#数据流)
- [模块说明](#模块说明)
- [优化历史](#优化历史)

---

## 系统概述

PreModels v2 是一个**大宗货物采购物流调度优化系统**，通过线性规划（LP）和贪心算法，优化每日发货计划，实现：

1. **完成合同** - 在合同期内完成约定重量（允许±5% 冗余）
2. **到货均衡** - 尽可能平均分配每日到货量
3. **支持混装** - 一车可装多个品类，按总重换算车数
4. **成本控制** - 考虑品类单价和仓库加价

---

## 核心算法

### 1. 简单系统（Baseline）

**算法**：贪心分配

**流程**：
```
1. 计算每个合同的当日目标吨数
   target = (Q - delivered - 0.9*future_intransit) / T_remain

2. 合同排序：临期优先（end_day 近优先）

3. 仓库排序：准时概率高优先，其次产能大优先

4. 贪心分配：从优先级高的 (warehouse, category) 开始
```

**优点**：快速、可解释性强
**缺点**：不考虑未来产能，可能局部最优

### 2. 复杂系统（Rolling Horizon LP）

**算法**：滚动时域线性规划

**决策变量**：
```
x[w,cid,k,t] = 从仓库 w 发往合同 cid 品类 k 在 t 日的吨数
```

**目标函数**（多目标加权）：
```
Minimize:
  α_short × 缺口总和          (α=3000，最高优先级)
  + β_balance × 均衡偏差      (β=2)
  + γ_waste × 过期浪费        (γ=80)
  + η_cost × 采购成本         (η=0~1，可选)
  + stability × 计划抖动      (可选)
```

**约束条件**：
1. **产能约束**：`sum_c x[w,cid,k,t] <= cap_forecast[w,k,t]`
2. **合同完成**：`delivered + intransit + new >= 0.95 * Q`
3. **超发限制**：`delivered + intransit + new <= 1.05 * Q`
4. **发货上限**：`sum x[w,cid,k,today] <= q_star * 1.5`（防止集中发货）
5. **品类限制**：`k in allowed_categories`

**滚动优化**：
- 规划窗口：[today, today+H-1]（H=10 天）
- 每日重算：根据最新磅单更新状态

---

## 数据流

```
┌─────────────────┐
│  合同数据       │  Q, start_day, end_day, allowed_categories
└────────┬────────┘
         │
┌────────▼────────┐
│  在途报单       │  order_id, warehouse, category, ship_day
└────────┬────────┘
         │
┌────────▼────────┐
│  在途预测       │  按延迟分布分摊到未来到货日
└────────┬────────┘
         │
┌────────▼────────┐
│  模型优化       │  LP 求解器 (pulp/CBC)
└────────┬────────┘
         │
┌────────▼────────┐
│  发货计划       │  x_today[(w,cid,k,t)] = 吨
└────────┬────────┘
         │
┌────────▼────────┐
│  车数换算       │  支持混装：按 lane 聚合后换算
└────────┬────────┘
         │
┌────────▼────────┐
│  执行发货       │  创建报货单 → PD API
└─────────────────┘
```

---

## 模块说明

### common_utils_v2.py

**功能**：通用工具函数

**核心函数**：
- `predict_intransit_arrivals_expected()` - 在途预测（按延迟分布分摊）
- `suggest_trucks_from_tons_plan()` - 车数换算（支持混装）
- `get_mixing_details()` - 混装明细
- `calc_purchase_price_per_ton()` - 采购价计算

### simple_system_v2.py

**功能**：简单系统（贪心算法）

**输入**：
- 合同列表、在途报单、已到货量
- 当日产能 cap_today

**输出**：
- `x_today[(w,cid,k,today)]` - 今日发货计划（吨）
- `truck_suggest[(w,cid,today)]` - 建议车数
- `mixing_details[(w,cid,today)]` - 混装明细

### complex_system_v2.py

**功能**：复杂系统（LP 优化）

**输入**：
- 合同列表、在途报单、已到货量
- 多日产能预测 cap_forecast
- 权重参数（alpha_short, beta_balance, ...）

**输出**：
- `x_today_plan` - 今日执行计划
- `x_horizon_plan` - 窗口计划（用于明日稳定性）
- `arrival_plan` - 到货诊断曲线
- `truck_suggest_today` - 建议车数
- `mixing_details_today` - 混装明细

### rolling_optimizer.py

**功能**：滚动优化器

**流程**：
1. 加载状态（`state_manager.py`）
2. 获取最新磅单（`api_client.py`）
3. 更新已到货量和在途列表
4. 重新运行模型
5. 保存状态和计划

**运行方式**：
```bash
python3 rolling_optimizer.py --run --today 10
```

### api_client.py

**功能**：PD API 客户端（预留接口）

**待实现接口**：
- `GET /api/v1/weighbills` - 获取磅单列表
- `GET /api/v1/deliveries` - 获取报货单列表
- `POST /api/v1/deliveries` - 创建报货单

### state_manager.py

**功能**：状态持久化

**存储内容**：
- `state.json` - 当前状态
- `history/state_day*.json` - 历史快照
- `logs/*.log` - 执行日志
- `plan_day*.json` - 每日计划

---

## 优化历史

### 2026-03-08

#### 1. 混装支持
- **问题**：原模型按品类单独换算车数，无法拼车
- **解决**：按 lane(warehouse, cid, day) 聚合后换算
- **效果**：减少总车数约 15-20%

#### 2. 合同总重逻辑
- **问题**：原模型按品类分开计算需求
- **解决**：合同只认总重，品类自由分配
- **效果**：更灵活，符合业务实际

#### 3. 在途期望修复
- **问题**：在途期望包含了今天到达的量
- **解决**：只计算 today+1 及以后到达的
- **效果**：今日发货目标更合理

#### 4. 到货上限约束
- **问题**：原约束限制"在途 + 新增"，导致在途大时无法发货
- **解决**：改为限制每日发货量
- **效果**：C1 到货 Std 从 149.9 降至 14.5（-90%）

#### 5. 品类单价支持
- **新增**：`contract_unit_price_by_category[(cid, category)]`
- **兼容**：保留旧版 `contract_unit_price[cid]`

---

## 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `rho_intransit` | 0.9 | 在途置信系数 |
| `alpha_short` | 3000.0 | 缺口惩罚权重 |
| `beta_balance` | 2.0 | 均衡偏差权重 |
| `gamma_waste` | 80.0 | 过期浪费权重 |
| `max_daily_ratio` | 1.5 | 每日发货上限（日均的倍数） |
| `invoice_factor` | 1.048 | 票点（13% 专票） |

---

## 待优化方向

1. **延迟分布学习**：从历史磅单数据学习实际延迟分布
2. **估重画像学习**：从历史数据学习各 lane 的 mu/hi
3. **产能预测**：接入真实产能系统
4. **多目标调权**：根据业务反馈调整权重
5. **求解器优化**：大规模场景下的性能优化
