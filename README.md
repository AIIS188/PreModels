# PreModels v2 - 采购物流调度优化系统

**版本**: v2.3  
**更新日期**: 2026-03-10  
**维护**: AIIS188  
**状态**: 生产就绪

---

## 简介

PreModels v2 是一个智能采购物流调度系统，通过线性规划（LP）优化算法生成每日发货计划，实现：

- **完成合同** - 在合同期内完成约定重量（±5% 冗余）
- **到货均衡** - 平均分配每日到货量，避免集中到货
- **支持混装** - 一车可装多个品类，降低运输成本
- **滚动优化** - 每日根据真实磅单更新计划
- **PD 集成** - 已对接 PD 业务系统，自动获取合同、磅单、报货单数据
- **品类价格** - 合同集成品类明细和价格，支持多品类合同
- **车牌追踪** - 基于车牌号的在途报单管理

---

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
cd /root/.openclaw/workspace/PreModels/v2
pip install pulp requests python-dotenv
```

### 2. 配置 PD API

编辑 `rolling_optimizer.py` 或使用默认配置：

```python
api = PDAPIClient(base_url="http://127.0.0.1:8007")
```

### 3. 测试运行

```bash
# 运行最优化模型综合测试
cd /root/.openclaw/workspace/PreModels/v2
python3 tests/test_optimization_models.py

# 查看测试报告
cat docs/TEST_REPORT_20260310.md
```

### 4. 生产运行

```bash
# 初始化状态（首次运行）
python3 scripts/run_daily_optimization.py --init

# 运行滚动优化
python3 scripts/run_daily_optimization.py --run --today-date 2026-03-10 --H 10

# 查看状态
python3 scripts/run_daily_optimization.py --status
```

---

## 目录结构

```
PreModels/
├── README.md                   # 本文档
├── PROJECT_STRUCTURE.md        # 项目结构说明
├── api/
│   ├── README.md               # API 文档
│   └── main.py                 # API 服务
├── docs/
│   ├── CONTRACT_PRODUCTS_UPDATE_20260310.md  # 合同品类集成
│   ├── DATE_REFACTOR_COMPLETE_20260309.md    # 日期格式重构
│   ├── SYSTEM_CHECK_REPORT_20260310.md       # 系统检查报告
│   └── TEST_REPORT_20260310.md               # 测试报告
├── monitoring/
│   └── health_check.py         # 健康检查
├── scripts/
│   └── run_daily_optimization.py  # 每日优化脚本
└── v2/
    ├── core/
    │   ├── api_client.py           # PD API 客户端
    │   ├── capacity_allocator.py   # 产能分配器
    │   ├── date_utils.py           # 日期工具
    │   ├── state_manager.py        # 状态管理
    │   └── urgency_calculator.py   # 紧急度计算器
    ├── examples/
    │   ├── capacity_api_example.py
    │   ├── generate_report.py
    │   └── init_state.py
    ├── models/
    │   ├── common_utils_v2.py      # 通用工具（Contract 结构）
    │   ├── complex_system_v2.py    # 最优化模型（LP）
    │   └── rolling_optimizer.py    # 滚动优化器
    └── tests/
        ├── test_optimization_models.py  # 综合测试
        ├── test_date_migration.py
        ├── test_h_impact.py
        ├── test_multi_day.py
        ├── test_balance_shipping.py
        ├── test_pd_api.py
        └── test_with_mock_data.py
```

---

## 核心功能

### 1. 合同管理

- 自动从 PD API 加载合同数据
- 支持合同缓存（API 故障时降级）
- **品类明细集成** - 合同包含 `products: [{product_name, unit_price}]`
- **价格锁定** - 合同期内价格不可调整
- **多品类支持** - 一个合同可包含多个品类
- 合同有效期自动计算

```python
contract = Contract(
    cid="HT-2026-001",
    receiver="R1",
    Q=1000.0,
    start_day="2026-03-10",
    end_day="2026-03-20",
    products=[
        {"product_name": "动力煤", "unit_price": 800.0},
        {"product_name": "焦煤", "unit_price": 1200.0},
    ]
)

# 查询价格
price = contract.get_unit_price("动力煤")  # 800.0 元/吨
base_price = contract.get_base_price("动力煤")  # 763.36 元/吨 (不含票)
```

### 2. 在途跟踪

- 自动获取 PD 报货单数据
- **车牌号匹配** - 基于车牌号的在途管理
- 延迟分布预测（可配置）
- 估重画像支持（35 吨上下浮动）
- 在途转已到货自动确认

```python
# 获取已过磅车牌
weighed_trucks = get_weighed_truck_ids(api, "2026-03-10")

# 从在途删除已过磅报单
updated_in_transit = filter_confirmed_arrivals(in_transit, weighed_trucks)
```

### 3. 产能管理

- 仓库发货能力配置
- 产能预测接口预留
- 多日产能规划（H 天窗口）
- 动态产能分配器

### 4. 优化模型

- 线性规划（PuLP + CBC）
- 多目标优化：
  1. 最小化缺口（最高优先级）
  2. 最小化均衡偏差
  3. 最小化过期浪费
  4. 最小化采购成本（可选）
- 稳定性优化（减少计划抖动）

### 5. 执行计划

- 生成每日发货计划（吨）
- 计算建议车数（支持混装）
- 提供混装明细
- 到货诊断曲线

---

## 数据流

```
┌─────────────────┐
│  PD API         │
│  - 合同         │
│  - 报货单       │
│  - 磅单         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  RollingOptimizer
│  - 加载合同     │
│  - 获取磅单     │
│  - 更新在途     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LP Solver      │
│  (PuLP/CBC)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  发货计划       │
│  - 吨数         │
│  - 车数         │
│  - 混装明细     │
└─────────────────┘
```

---

## 输入数据

### 合同数据（从 PD API）

```python
{
    "contract_no": "HT-2026-001",
    "smelter_company": "R1",
    "total_quantity": 1000.0,
    "contract_date": "2026-03-10",
    "end_date": "2026-03-20",
    "products": [
        {"product_name": "动力煤", "unit_price": 800.0},
        {"product_name": "焦煤", "unit_price": 1200.0}
    ]
}
```

### 在途报单（从 PD API）

```python
{
    "order_id": "DL001",
    "cid": "HT-2026-001",
    "warehouse": "W1",
    "category": "A",
    "ship_day": "2026-03-09",
    "weight": 35.0,
    "truck_id": "京 A12345",  # 车牌号唯一标识
    "status": "pending"
}
```

### 产能预测（临时配置）

```python
cap_forecast = {
    ("W1", "A", 69): 200.0,
    ("W1", "B", 69): 50.0,
    ("W2", "A", 69): 150.0,
}
```

---

## 输出结果

### 今日发货计划

```json
{
  "x_today": {
    "W1_HT-2026-001_A_2026-03-10": 61.03,
    "W2_HT-2026-001_B_2026-03-10": 36.96
  },
  "trucks": {
    "W1_HT-2026-001_2026-03-10": 2,
    "W2_HT-2026-001_2026-03-10": 2
  },
  "mixing": {
    "W1_HT-2026-001_2026-03-10": {"A": 61.03},
    "W2_HT-2026-001_2026-03-10": {"B": 36.96}
  }
}
```

---

## 配置参数

### 模型参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `rho_intransit` | 0.9 | 在途置信系数 |
| `alpha_short` | 3000.0 | 缺口惩罚权重 |
| `beta_balance` | 2.0 | 均衡偏差权重 |
| `gamma_waste` | 80.0 | 过期浪费权重 |
| `H` | 10 | 规划窗口（天） |
| `max_daily_ratio` | 1.5 | 每日发货上限（日均的 150%） |
| `stability_weight` | 0.1 | 稳定性权重 |

### 估重画像

临时配置：35 吨上下浮动（32-38 吨范围）

```python
weight_profile = {
    ("W1", "R1", "A"): (35.0, 37.0),
    ("W1", "R1", "B"): (34.0, 36.0),
}
```

### 延迟分布

临时配置：

- 3% 当日到（delay=0）
- 97% 隔日到（delay=1）
- 2% 2 日到（delay=2）

```python
delay_dist = {0: 0.03, 1: 0.97, 2: 0.02}
```

---

## 命令行接口

### scripts/run_daily_optimization.py

```bash
# 初始化状态
python3 scripts/run_daily_optimization.py --init

# 运行优化
python3 scripts/run_daily_optimization.py --run --today-date 2026-03-10 --H 10

# 查看状态
python3 scripts/run_daily_optimization.py --status
```

### tests/test_optimization_models.py

```bash
# 运行综合测试
python3 tests/test_optimization_models.py

# 测试结果：6/6 通过
```

---

## 滚动优化流程

```
每日运行流程:

08:00  加载状态 → 获取磅单 → 更新在途 → 运行模型 → 生成计划
12:00  获取磅单 → 更新在途 → 重算（可选）
16:00  获取磅单 → 更新在途 → 重算（可选）
20:00  最终结算 → 保存状态
```

---

## PD API 对接

### 已对接接口

| 接口 | 方法 | 用途 | 状态 |
|------|------|------|------|
| `/api/v1/contracts/` | GET | 获取合同列表 | 已完成 |
| `/api/v1/deliveries/` | GET | 获取报货单列表 | 已完成 |
| `/api/v1/weighbills/` | GET | 获取磅单列表 | 已完成 |
| `/api/v1/deliveries/json` | POST | 创建报货单 | 已完成 |

### 配置 API 地址

```python
api = PDAPIClient(base_url="http://127.0.0.1:8007")
```

### 合同缓存机制

- API 成功：加载并缓存到 `state/contracts_cache.json`
- API 失败：使用缓存的合同数据
- API 和缓存都失败：抛出异常终止运行

---

## 日志和状态

### 状态文件

- `state/state.json` - 当前状态
- `state/history/state_day*.json` - 历史快照
- `state/logs/*.log` - 执行日志
- `state/plan_day*.json` - 每日计划
- `state/contracts_cache.json` - 合同缓存

### 查看日志

```bash
# 查看最新日志
tail -f state/logs/*.log

# 查看今日计划
cat state/plan_day10.json | python3 -m json.tool
```

---

## 测试

### 最优化模型综合测试

```bash
cd /root/.openclaw/workspace/PreModels/v2
python3 tests/test_optimization_models.py
```

**测试结果**:

```
Contract 结构体 - 通过
在途预测 - 通过
complex_system_v2 最优化模型 - 通过
rolling_optimizer 滚动优化器 - 通过
产能分配器 - 通过
紧急度计算器 - 通过

总计：6/6 测试通过
```

详见：[docs/TEST_REPORT_20260310.md](docs/TEST_REPORT_20260310.md)

### 降级模式测试

```bash
# 无真实 API 时运行（使用缓存和默认配置）
python3 tests/test_optimization_models.py
```

**结果**: 系统可降级运行，无 API 时不报错

---

## 常见问题

### Q: 合同数据加载失败怎么办？

A: 检查以下几点：
1. PD 服务是否运行：`curl http://127.0.0.1:8007/healthz`
2. PD 系统中是否有合同数据
3. 网络连接是否正常
4. 如果有缓存，会使用缓存数据继续运行

### Q: 计划为空怎么办？

A: 检查以下问题：
1. 在途量是否过大（超过 max_daily）
2. 产能是否充足
3. 合同是否已过期
4. 查看日志：`cat state/logs/*.log`

### Q: 如何调整到货均衡性？

A: 修改 `beta_balance` 权重：
```python
beta_balance = 5.0  # 增加均衡优先级
```

### Q: 如何禁用混装？

A: 在 `suggest_trucks_from_tons_plan()` 中设置：
```python
suggest_trucks_from_tons_plan(..., allow_mixing=False)
```

---

## 文档

| 文档 | 说明 |
|------|------|
| [CONTRACT_PRODUCTS_UPDATE_20260310.md](docs/CONTRACT_PRODUCTS_UPDATE_20260310.md) | 合同品类集成文档 |
| [DATE_REFACTOR_COMPLETE_20260309.md](docs/DATE_REFACTOR_COMPLETE_20260309.md) | 日期格式重构完成报告 |
| [SYSTEM_CHECK_REPORT_20260310.md](docs/SYSTEM_CHECK_REPORT_20260310.md) | 系统完整性检查报告 |
| [TEST_REPORT_20260310.md](docs/TEST_REPORT_20260310.md) | 最优化模型测试报告 |

---

## 版本历史

### v2.3 (2026-03-10)

- **合同品类集成** - Contract 新增 `products` 字段（含价格）
- **价格查询方法** - `get_unit_price()`, `get_base_price()`
- **在途更新重构** - 基于车牌号匹配
- **综合测试** - `test_optimization_models.py` (6/6 通过)
- **项目整理** - 删除 20+ 无用文件
- **文档更新** - 新增测试报告和系统检查报告

### v2.2 (2026-03-10)

- **系统完整性检查** - 所有模块验证通过
- **滚动优化器修复** - 日期格式和参数修复
- **降级模式验证** - 无 API 时可正常运行

### v2.1 (2026-03-10)

- **在途管理** - `filter_confirmed_arrivals` 实现
- **车牌号追踪** - 基于车牌的唯一标识

### v2.0 (2026-03-09)

- **日期格式重构** - int → str (YYYY-MM-DD)
- **PD API 完整对接**
- **合同缓存机制**

---

## GitHub

- **PreModels**: https://github.com/AIIS188/PreModels
- **PD**: https://github.com/Jisalute/PD

---

## 联系

**维护**: AIIS188  
**问题反馈**: GitHub Issues  

---

**最后更新**: 2026-03-10 16:15
