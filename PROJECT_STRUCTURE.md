# PreModels v2 项目结构

**版本**: v2.2  
**更新日期**: 2026-03-08  

---

## 目录结构

```
PreModels/
├── README.md                      # 项目说明
├── PROJECT_STRUCTURE.md           # 项目结构说明
│
├── api/                           # FastAPI 服务
│   ├── main.py                    # API 主程序
│   └── README.md                  # API 文档
│
├── v2/                            # 核心优化系统
│   ├── core/                      # 核心模块
│   │   ├── api_client.py          # PD API 客户端
│   │   ├── capacity_allocator.py  # 产能动态分配器
│   │   ├── urgency_calculator.py  # 合同紧急度计算器
│   │   └── state_manager.py       # 状态管理器
│   │
│   ├── models/                    # 优化模型
│   │   ├── rolling_optimizer.py   # 滚动优化器
│   │   ├── complex_system_v2.py   # LP 优化模型
│   │   └── common_utils_v2.py     # 通用工具
│   │
│   ├── tests/                     # 测试脚本
│   │   ├── test_pd_api.py         # PD API 测试
│   │   ├── test_with_mock_data.py # 模拟数据测试
│   │   ├── test_multi_day.py      # 多日测试
│   │   ├── test_balance_shipping.py # 均衡性测试
│   │   └── test_h_impact.py       # H 值影响测试
│   │
│   └── examples/                  # 示例代码
│       ├── generate_report.py     # 报告生成示例
│       └── capacity_api_example.py # 产能 API 示例
│
├── scripts/                       # 运维脚本
│   ├── run_daily_optimization.py  # 每日自动优化
│   └── crontab_config.txt         # Crontab 配置
│
├── monitoring/                    # 监控告警
│   └── health_check.py            # 健康检查脚本
│
└── docs/                          # 文档
    ├── PD_API_INTEGRATION.md      # PD API 对接文档
    ├── CAPACITY_INTEGRATION.md    # 产能预测集成
    ├── CAPACITY_ALLOCATION_OPTIMIZATION.md # 产能分配优化
    ├── API_DEMO_20260308.md       # API 演示
    ├── FINAL_TEST_REPORT_20260308.md # 最终测试报告
    ├── PRODUCTION_READINESS_ASSESSMENT.md # 上线评估
    └── SETUP_COMPLETE_20260308.md # 配置完成报告
```

---

## 核心文件说明

### API 服务

| 文件 | 说明 | 用途 |
|------|------|------|
| `api/main.py` | FastAPI 主程序 | 提供 REST API 给前端 |

### 核心模块

| 文件 | 说明 | 用途 |
|------|------|------|
| `v2/core/api_client.py` | PD API 客户端 | 对接 PD 业务系统 |
| `v2/core/capacity_allocator.py` | 产能分配器 | 动态分配产能 |
| `v2/core/urgency_calculator.py` | 紧急度计算器 | 计算合同紧急度 |
| `v2/core/state_manager.py` | 状态管理器 | 持久化模型状态 |

### 优化模型

| 文件 | 说明 | 用途 |
|------|------|------|
| `v2/models/rolling_optimizer.py` | 滚动优化器 | 协调优化流程 |
| `v2/models/complex_system_v2.py` | LP 优化模型 | 线性规划求解 |
| `v2/models/common_utils_v2.py` | 通用工具 | 工具函数 |

### 运维脚本

| 文件 | 说明 | 用途 |
|------|------|------|
| `scripts/run_daily_optimization.py` | 每日优化 | 定时任务脚本 |
| `monitoring/health_check.py` | 健康检查 | 服务监控 |

---

## 文件分类

### 生产文件 (必须)

```
api/main.py
v2/core/*.py
v2/models/*.py
scripts/run_daily_optimization.py
monitoring/health_check.py
```

### 测试文件 (可选)

```
v2/tests/*.py
```

### 示例文件 (可选)

```
v2/examples/*.py
```

### 文档文件 (参考)

```
docs/*.md
```

---

## 清理建议

### 可以删除

- `v2/simple_system_v2.py` - 旧版简单系统
- `v2/runner_compare_v2.py` - 旧版对比测试
- `v2/init_state.py` - 初始化脚本 (已集成到优化器)

### 保留

- 所有核心生产文件
- 测试文件 (用于回归测试)
- 监控和定时任务脚本

---

## 运行方式

### 生产运行

```bash
# 定时任务自动运行 (crontab)
0 8 * * 1-5 cd /root/.openclaw/workspace/PreModels/scripts && python3 run_daily_optimization.py --today auto

# 健康检查 (每 5 分钟)
*/5 * * * * cd /root/.openclaw/workspace/PreModels/monitoring && python3 health_check.py
```

### 测试运行

```bash
# 运行所有测试
cd /root/.openclaw/workspace/PreModels/v2/tests
python3 -m pytest .

# 运行单个测试
python3 test_pd_api.py
```

### API 服务

```bash
# 启动 API 服务
cd /root/.openclaw/workspace/PreModels/api
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001
```

---

**维护**: AIIS188  
**最后更新**: 2026-03-08
