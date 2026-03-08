# PreModels v2 - 采购物流调度优化系统

## 简介

PreModels v2 是一个智能采购物流调度系统，通过优化算法生成每日发货计划，实现：

-  **完成合同** - 在合同期内完成约定重量（±5% 冗余）
-  **到货均衡** - 平均分配每日到货量，避免集中到货
-  **支持混装** - 一车可装多个品类，降低运输成本
-  **滚动优化** - 每日根据真实磅单更新计划

---

##  快速开始

### 1. 安装依赖

```bash
cd /root/.openclaw/workspace/PreModels/v2
pip install pulp
```

### 2. 首次运行

```bash
# 初始化状态
python3 init_state.py

# 运行优化
python3 rolling_optimizer.py --run --today 10

# 查看状态
python3 rolling_optimizer.py --status
```

### 3. 对比测试

```bash
# 运行简单系统和复杂系统对比
python3 runner_compare_v2.py
```

---

##  目录结构

```
PreModels/
├── v2/
│   ├── common_utils_v2.py      # 通用工具
│   ├── simple_system_v2.py     # 简单系统（贪心）
│   ├── complex_system_v2.py    # 复杂系统（LP 优化）
│   ├── runner_compare_v2.py    # 对比测试
│   ├── api_client.py           # PD API 客户端
│   ├── state_manager.py        # 状态管理
│   ├── rolling_optimizer.py    # 滚动优化器
│   └── init_state.py           # 初始化脚本
├── docs/
│   └── TECHNICAL.md            # 技术文档
└── README.md                   # 本文档
```

---

##  输入数据

### 合同数据

```python
Contract(
    cid="C1",                    # 合同 ID
    receiver="R1",               # 收货方
    Q=520.0,                     # 合同总量（吨）
    start_day=9,                 # 到货有效期开始
    end_day=13,                  # 到货有效期结束
    allowed_categories={"A", "B"} # 允许的品类
)
```

### 在途报单

```python
{
    "order_id": "O1001",
    "cid": "C1",
    "receiver": "R1",
    "warehouse": "W1",
    "category": "A",
    "ship_day": 9
}
```

### 产能预测

```python
cap_forecast = {
    ("W1", "A", 10): 220.0,  # 仓库 W1 品类 A day10 的产能
    ("W1", "B", 10): 60.0,
    ...
}
```

---

##  输出结果

### 今日发货计划

```json
{
  "shipments": [
    {
      "warehouse": "W1",
      "cid": "C1",
      "category": "A",
      "tons": 99.1
    }
  ],
  "trucks": [
    {
      "warehouse": "W1",
      "cid": "C1",
      "trucks": 4,
      "mixing": {"A": 99.1}
    }
  ]
}
```

### 到货诊断曲线

```
合同 C1 有效期 [9,13]：
  到货日 11: 91.7 吨
  到货日 12: 5.6 吨
  到货日 13: 3.0 吨
```

---

##  配置参数

### 模型参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `rho_intransit` | 0.9 | 在途置信系数 |
| `max_daily_ratio` | 1.5 | 每日发货上限（日均的 150%） |
| `H` | 10 | 规划窗口（天） |

### 价格参数

```python
# 品类单价（不同品类价格不同）
contract_unit_price_by_category = {
    ("C1", "A"): 520.0,
    ("C1", "B"): 500.0,
}

# 仓库加价（特定仓库 +10 元/吨）
warehouse_const = {
    "W1": 0.0,
    "W2": 10.0,  # 于娇娇/王菲仓
    "W3": 0.0,
}
```

---

##  命令行接口

### rolling_optimizer.py

```bash
# 运行优化
python3 rolling_optimizer.py --run --today 10 --H 10

# 查看状态
python3 rolling_optimizer.py --status

# 重置状态
python3 rolling_optimizer.py --reset
```

### runner_compare_v2.py

```bash
# 运行对比测试
python3 runner_compare_v2.py
```

---

##  滚动优化流程

```
┌─────────────────────────────────────────┐
│  每日运行                                │
├─────────────────────────────────────────┤
│  08:00  │ 加载状态 → 运行模型 → 生成计划 │
│  12:00  │ 获取磅单 → 更新状态 → 重算     │
│  16:00  │ 获取磅单 → 更新状态 → 重算     │
│  20:00  │ 最终结算 → 保存状态            │
└─────────────────────────────────────────┘
```

---

##  对接 PD API

### 待实现接口

```python
# api_client.py 中实现

# 获取磅单
GET /api/v1/weighbills?date=2026-03-08

# 获取报货单
GET /api/v1/deliveries?status=pending

# 创建报货单
POST /api/v1/deliveries
```

### 配置 API 地址

```python
api = PDAPIClient(base_url="http://172.30.147.217:8007")
```

---

##  日志和状态

### 状态文件

- `state/state.json` - 当前状态
- `state/history/state_day*.json` - 历史快照
- `state/logs/*.log` - 执行日志
- `state/plan_day*.json` - 每日计划

### 查看日志

```bash
cat state/logs/20260308.log
```

---

##  常见问题

### Q: 计划为空怎么办？

A: 检查以下问题：
1. 在途量是否过大（超过 max_daily）
2. 产能是否充足
3. 合同是否已过期

### Q: 如何调整到货均衡性？

A: 修改 `beta_balance` 权重：
```python
beta_balance = 5.0  # 增加均衡优先级
```

### Q: 如何禁用混装？

A: 设置 `allow_mixing=False`：
```python
suggest_trucks_from_tons_plan(..., allow_mixing=False)
```

---

##  文档

- [技术文档](docs/TECHNICAL.md) - 算法详解、架构说明
- [优化历史](docs/TECHNICAL.md#优化历史) - 版本变更记录

---

## 📞 联系

有问题请联系项目负责人。
