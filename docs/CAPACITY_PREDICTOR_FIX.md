# 产能预测模型修复说明

## 问题描述

用户反馈产能预测模型接口有问题：
1. 不需要对接外部 API，而是调用内部函数做预测
2. 返回格式需要包含品类信息
3. 需要修改最优化函数中的 cap 格式

## 修改内容

### 1. 新增产能预测模型 (`models/capacity_predictor.py`)

**文件位置**: `/root/.openclaw/workspace/PreModels/v2/models/capacity_predictor.py`

**核心功能**:
- 预测各仓库未来 H 天的产能（按品类）
- 不依赖外部 API，直接调用内部函数
- 返回格式包含品类信息

**返回格式**:
```json
{
  "仓库名": {
    "日期 (格式"%Y-%m-%d")": {
      "品类 1": 重量 (float),
      "品类 2": 重量 (float)
    }
  }
}
```

**示例**:
```json
{
  "W1": {
    "2026-03-11": {
      "A": 220.0,
      "B": 60.0
    },
    "2026-03-12": {
      "A": 231.0,
      "B": 63.0
    }
  },
  "W2": {
    "2026-03-11": {
      "A": 80.0,
      "B": 220.0
    }
  }
}
```

**使用方式**:
```python
from models.capacity_predictor import predict_capacity, CapacityPredictor

# 方式 1: 使用类
predictor = CapacityPredictor()
forecast = predictor.predict(today="2026-03-11", H=10)

# 方式 2: 使用函数
forecast = predict_capacity(today="2026-03-11", H=10)
```

### 2. 修改滚动优化器 (`models/rolling_optimizer.py`)

**修改内容**:

#### 2.1 更新 `_load_cap_forecast` 方法

- 从调用外部 API 改为调用内部产能预测模型
- 使用新的返回格式（包含品类信息）

```python
def _load_cap_forecast(self, today: str, H: int) -> Dict:
    # 调用内部产能预测模型
    from models.capacity_predictor import predict_capacity
    
    capacity_data = predict_capacity(today=today, H=H)
    
    if capacity_data:
        # 转换为模型需要的格式
        categories = ["A", "B"]
        return self._convert_capacity_format_new(capacity_data, today, categories)
```

#### 2.2 新增 `_convert_capacity_format_new` 方法

- 支持新的产能预测格式（包含品类信息）
- 将嵌套字典转换为模型需要的元组键格式

**输入格式**:
```python
{
    "W1": {
        "2026-03-11": {"A": 220.0, "B": 60.0},
        "2026-03-12": {"A": 231.0, "B": 63.0},
    }
}
```

**输出格式**:
```python
{
    ("W1", "A", "2026-03-11"): 220.0,
    ("W1", "B", "2026-03-11"): 60.0,
    ("W1", "A", "2026-03-12"): 231.0,
    ...
}
```

### 3. 更新示例文件 (`examples/capacity_api_example.py`)

**修改内容**:
- 移除外部 API 调用示例
- 添加内部产能预测模型使用示例
- 添加格式验证示例

**使用方式**:
```bash
cd /root/.openclaw/workspace/PreModels/v2
python3 examples/capacity_api_example.py
```

### 4. 新增集成测试 (`tests/test_capacity_integration.py`)

**测试内容**:
1. 产能预测模型返回格式验证
2. 产能格式转换验证
3. 滚动优化器集成验证

**运行测试**:
```bash
cd /root/.openclaw/workspace/PreModels/v2
python3 tests/test_capacity_integration.py
```

**测试结果**:
```
格式验证：✅ 通过
格式转换：✅ 通过
集成测试：✅ 通过

🎉 所有测试通过！
```

## 验证步骤

### 1. 测试产能预测模型

```bash
cd /root/.openclaw/workspace/PreModels/v2
python3 models/capacity_predictor.py
```

**预期输出**:
```
1. 详细产能预测（分品类）
{
  "W1": {
    "2026-03-11": {"A": 220.0, "B": 60.0},
    "2026-03-12": {"A": 231.0, "B": 63.0},
    ...
  },
  ...
}
```

### 2. 测试示例文件

```bash
python3 examples/capacity_api_example.py
```

**预期输出**:
```
1. 调用内部产能预测函数（推荐）
获取到产能预测数据（前 3 天）:
  W1:
    2026-03-11: {'A': 220.5, 'B': 60.1}
    2026-03-12: {'A': 232.8, 'B': 63.5}
    ...

格式验证：✅ 通过
```

### 3. 运行集成测试

```bash
python3 tests/test_capacity_integration.py
```

**预期输出**:
```
测试总结
格式验证：✅ 通过
格式转换：✅ 通过
集成测试：✅ 通过

🎉 所有测试通过！
```

### 4. 运行滚动优化器（完整流程）

```bash
python3 models/rolling_optimizer.py --run --today-date 2026-03-11 --H 10
```

**注意**: 需要确保状态已初始化，合同数据已加载。

## 技术细节

### 产能预测模型

**基础产能配置**:
```python
base_capacity = {
    "W1": {"A": 220.0, "B": 60.0},   # W1 仓库
    "W2": {"A": 80.0, "B": 220.0},   # W2 仓库
    "W3": {"A": 120.0, "B": 120.0},  # W3 仓库
}
```

**产能波动因子**:
- 工作日：1.0
- 周末：0.85
- 维护日（每月 15 号）：0.7
- 仓库效率因子：W1=1.05, W2=0.95, W3=1.0
- 随机波动：±5%

### 格式转换逻辑

```python
def _convert_capacity_format_new(self, capacity_data, today, categories):
    cap_forecast = {}
    
    for warehouse, dates in capacity_data.items():
        wh = warehouse.upper()  # 仓库名标准化
        
        for date_str, categories_cap in dates.items():
            for category, capacity in categories_cap.items():
                cap_forecast[(wh, category, date_str)] = float(capacity)
    
    return cap_forecast
```

## 兼容性说明

### 旧版格式（已废弃）

```json
{
    "w1": [350, 360, 370, ...],
    "w2": [200, 210, 220, ...]
}
```

### 新版格式（推荐）

```json
{
    "仓库名": {
        "日期": {"品类 1": 重量， "品类 2": 重量}
    }
}
```

**优势**:
1. 包含品类信息，更精确
2. 使用日期字符串，更直观
3. 嵌套结构，更易读

## 后续优化建议

1. **数据驱动**: 从历史磅单数据学习各仓库实际产能分布
2. **因素扩展**: 考虑设备状态、原材料供应、工人排班等因素
3. **机器学习**: 使用 ML 模型预测产能（如 LSTM、Prophet）
4. **实时监控**: 对接生产系统，实时调整产能预测

## 修改文件清单

1. ✅ `/root/.openclaw/workspace/PreModels/v2/models/capacity_predictor.py` (新增)
2. ✅ `/root/.openclaw/workspace/PreModels/v2/models/rolling_optimizer.py` (修改)
3. ✅ `/root/.openclaw/workspace/PreModels/v2/examples/capacity_api_example.py` (修改)
4. ✅ `/root/.openclaw/workspace/PreModels/v2/tests/test_capacity_integration.py` (新增)
5. ✅ `/root/.openclaw/workspace/PreModels/docs/CAPACITY_PREDICTOR_FIX.md` (本文档)

## 完成时间

2026-03-11

## 测试状态

✅ 所有测试通过
