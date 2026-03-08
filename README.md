# PreModels v2 - 采购物流调度优化系统

**版本**: v2.2  
**更新日期**: 2026-03-08  
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

### 3. 测试运行（使用模拟数据）

```bash
# 运行模拟数据测试
python3 test_with_mock_data.py --today 10

# 查看测试报告
cat state/test_report_day10.json | python3 -m json.tool
```

### 4. 生产运行

```bash
# 初始化状态（首次运行）
python3 init_state.py

# 运行滚动优化
python3 rolling_optimizer.py --run --today 10 --H 10

# 查看状态
python3 rolling_optimizer.py --status

# 查看今日计划
cat state/plan_day10.json | python3 -m json.tool
```

---

## 目录结构

```
PreModels/
├── v2/
│   ├── common_utils_v2.py      # 通用工具（合同、延迟分布等）
│   ├── simple_system_v2.py     # 简单系统（贪心算法）
│   ├── complex_system_v2.py    # 复杂系统（LP 优化）
│   ├── rolling_optimizer.py    # 滚动优化器（主程序）
│   ├── api_client.py           # PD API 客户端（已对接）
│   ├── state_manager.py        # 状态管理（持久化）
│   ├── init_state.py           # 初始化脚本
│   ├── test_with_mock_data.py  # 模拟数据测试
│   └── test_pd_api.py          # PD API 接口测试
├── docs/
│   ├── PD_API_INTEGRATION.md   # PD API 对接文档
│   ├── PD_DEPLOYMENT.md        # PD 服务部署指南
│   ├── PD_API_DEMO.md          # PD API 接口演示
│   ├── EXTERNAL_DATA_INTEGRATION_STATUS.md  # 外部数据对接状态
│   ├── DATA_INTEGRATION_UPDATE_20260308.md  # 数据对接更新日志
│   ├── CONTRACT_LOADING_FIX_20260308.md     # 合同加载优化文档
│   └── TECHNICAL.md            # 技术文档（算法详解）
└── README.md                   # 本文档
```

---

## 核心功能

### 1. 合同管理

- 自动从 PD API 加载合同数据
- 支持合同缓存（API 故障时降级）
- 合同有效期自动计算
- 多品类支持

### 2. 在途跟踪

- 自动获取 PD 报货单数据
- 延迟分布预测（ configurable）
- 估重画像支持（35 吨上下浮动）
- 在途转已到货自动确认

### 3. 产能管理

- 仓库发货能力配置
- 产能预测接口预留
- 多日产能规划（H 天窗口）

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
    "total_quantity": 520.0,
    "contract_date": "2026-03-01",
    "end_date": "2026-03-20",
    "products": [
        {"product_name": "A", "unit_price": 520.0},
        {"product_name": "B", "unit_price": 500.0}
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
    "ship_day": 9,
    "weight": 35.0,
    "status": "pending"
}
```

### 产能预测（临时配置）

```python
cap_forecast = {
    ("W1", "A", 10): 220.0,
    ("W1", "B", 10): 60.0,
    ("W2", "A", 10): 80.0,
    ("W2", "B", 10): 220.0,
    ("W3", "A", 10): 120.0,
    ("W3", "B", 10): 120.0,
}
```

---

## 输出结果

### 今日发货计划

```json
{
  "x_today": {
    "W1_HT-2026-002_A_10": 61.03,
    "W2_HT-2026-001_A_10": 36.96
  },
  "trucks": {
    "W1_HT-2026-002_10": 2,
    "W2_HT-2026-001_10": 2
  },
  "mixing": {
    "W1_HT-2026-002_10": {"A": 61.03},
    "W2_HT-2026-001_10": {"A": 36.96}
  }
}
```

### 发货计划详情

```json
{
  "shipments": [
    {
      "warehouse": "W1",
      "cid": "HT-2026-002",
      "category": "A",
      "tons": 61.03
    }
  ],
  "trucks": [
    {
      "warehouse": "W1",
      "cid": "HT-2026-002",
      "trucks": 2,
      "mixing": {"A": 61.03}
    }
  ]
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
    # ... 所有线路
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

### rolling_optimizer.py

```bash
# 运行优化
python3 rolling_optimizer.py --run --today 10 --H 10

# 查看状态
python3 rolling_optimizer.py --status

# 重置状态
python3 rolling_optimizer.py --reset
```

### test_with_mock_data.py

```bash
# 使用模拟数据测试
python3 test_with_mock_data.py --today 10 --H 10

# 查看测试报告
cat state/test_report_day10.json | python3 -m json.tool
```

### test_pd_api.py

```bash
# 测试 PD API 接口
python3 test_pd_api.py
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
- `state/test_report_day*.json` - 测试报告

### 查看日志

```bash
# 查看最新日志
tail -f state/logs/*.log

# 查看今日计划
cat state/plan_day10.json | python3 -m json.tool

# 查看测试报告
cat state/test_report_day10.json | python3 -m json.tool
```

---

## 测试

### 模拟数据测试

```bash
cd /root/.openclaw/workspace/PreModels/v2
python3 test_with_mock_data.py --today 10
```

**测试结果示例**:

```
测试结果:
  - 今日计划：2 条
  - 建议车数：2 条
  - 混装明细：2 条
  - 到货计划：0 条

测试通过！
```

### PD API 测试

```bash
python3 test_pd_api.py
```

**测试结果**:

```
1. 健康检查 ✅
2. 获取报货单 ✅
3. 获取磅单 ✅
4. 获取合同 ✅
5. 获取已确认到货 ✅

所有测试通过！
```

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

### Q: 产能预测如何对接？

A: 产能预测接口已预留，见 `rolling_optimizer.py::_load_cap_forecast()`。
后续可对接仓库发货能力评估系统或产能预测 API。

---

## 文档

| 文档 | 说明 |
|------|------|
| [PD_API_INTEGRATION.md](docs/PD_API_INTEGRATION.md) | PD API 接口对接文档 |
| [PD_DEPLOYMENT.md](docs/PD_DEPLOYMENT.md) | PD 服务部署指南 |
| [PD_API_DEMO.md](docs/PD_API_DEMO.md) | PD API 接口演示 |
| [EXTERNAL_DATA_INTEGRATION_STATUS.md](docs/EXTERNAL_DATA_INTEGRATION_STATUS.md) | 外部数据对接状态 |
| [DATA_INTEGRATION_UPDATE_20260308.md](docs/DATA_INTEGRATION_UPDATE_20260308.md) | 数据对接更新日志 |
| [CONTRACT_LOADING_FIX_20260308.md](docs/CONTRACT_LOADING_FIX_20260308.md) | 合同加载优化文档 |
| [TECHNICAL.md](docs/TECHNICAL.md) | 技术文档（算法详解） |

---

## 版本历史

### v2.2 (2026-03-08)

- [x] 合同加载必须成功，支持缓存降级
- [x] 估重画像 35 吨上下浮动（32-38 吨）
- [x] 延迟分布统一配置（3%/97%/2%）
- [x] 产能预测预留接口
- [x] 模拟数据测试脚本
- [x] 完整文档更新

### v2.1 (2026-03-08)

- [x] PD API 完整对接
- [x] 合同数据自动加载
- [x] 磅单/报货单接口集成

### v2.0 (2026-03-08)

- [x] PD 项目部署
- [x] API 客户端实现
- [x] 接口文档编写

### v1.0 (2026-03-07)

- [x] 基础滚动优化器
- [x] LP 模型实现
- [x] 对比测试工具

---

## GitHub

- **PreModels**: https://github.com/AIIS188/PreModels
- **PD**: https://github.com/Jisalute/PD

---

## 联系

**维护**: AIIS188  
**问题反馈**: GitHub Issues  

---

**最后更新**: 2026-03-08 14:40
