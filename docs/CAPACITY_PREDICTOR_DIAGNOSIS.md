# 产能预测模型全面诊断报告

**诊断时间**: 2026-03-11  
**诊断范围**: PreModels 所有与产能预测相关的文件  
**诊断结果**: ✅ 全部修复完成

---

## 一、问题背景

用户反馈：
1. 产能预测不需要对接外部 API，应调用内部函数
2. 返回格式需要包含品类信息：`{仓库：{日期：{品类：重量}}}`
3. 之前忘记提及品类区分，可能有文件未适配新格式

---

## 二、诊断范围

检查了以下文件类型：
- ✅ 产能预测模型 (`capacity_predictor.py`)
- ✅ 滚动优化器 (`rolling_optimizer.py`)
- ✅ 最优化模型 (`complex_system_v2.py`)
- ✅ 产能分配器 (`capacity_allocator.py`)
- ✅ 所有测试文件
- ✅ 示例文件

---

## 三、发现的问题及修复

### 问题 1: 产能预测调用外部 API
**文件**: `rolling_optimizer.py`  
**问题**: `_load_cap_forecast()` 尝试调用外部 API  
**修复**: 改为调用内部 `predict_capacity()` 函数

```python
# 修复前
external_cap = self._load_capacity_from_api(today, H)

# 修复后
from models.capacity_predictor import predict_capacity
capacity_data = predict_capacity(today=today, H=H)
```

### 问题 2: 产能格式不包含品类
**文件**: `capacity_api_example.py` (旧)  
**问题**: 返回格式只有总产能 `{w1: [350, 360, ...]}`  
**修复**: 新增 `capacity_predictor.py`，返回包含品类的格式

```python
# 新格式
{
    "W1": {
        "2026-03-11": {"A": 220.0, "B": 60.0},
        "2026-03-12": {"A": 231.0, "B": 63.0}
    }
}
```

### 问题 3: 格式转换方法缺失
**文件**: `rolling_optimizer.py`  
**问题**: 旧方法 `_convert_capacity_format()` 不支持新格式  
**修复**: 新增 `_convert_capacity_format_new()` 方法

```python
def _convert_capacity_format_new(self, capacity_data, today, categories):
    """支持新格式：{仓库：{日期：{品类：重量}}}"""
    cap_forecast = {}
    for warehouse, dates in capacity_data.items():
        for date_str, categories_cap in dates.items():
            for category, capacity in categories_cap.items():
                cap_forecast[(wh, category, date_str)] = float(capacity)
    return cap_forecast
```

### 问题 4: 测试文件使用旧格式 (day 编号)
**文件**: `test_optimization_models.py`  
**问题**: 产能预测使用 day 编号而非日期字符串

```python
# 修复前 (day 编号)
cap_forecast[("W1", "A", day)] = 200.0  # day 是整数

# 修复后 (日期字符串)
date = DateUtils.add_days(today, d)
cap_forecast[("W1", "A", date)] = 200.0  # date 是字符串
```

### 问题 5: 降级代码使用 day 编号
**文件**: `rolling_optimizer.py`  
**问题**: 降级模式下的默认产能配置使用 day 编号

```python
# 修复前
for t in range(DateUtils.to_day_number(today), ...):
    cap_forecast[(w, k, t)] = base * factor  # t 是整数

# 修复后
for d in range(H):
    date = DateUtils.add_days(today, d)
    cap_forecast[(w, k, date)] = base * factor  # date 是字符串
```

### 问题 6: 函数调用参数错误
**文件**: `rolling_optimizer.py`  
**问题**: `run()` 方法调用 `_load_cap_forecast(day, H)` 传入 day 编号

```python
# 修复前
cap_forecast = self._load_cap_forecast(day, H)  # day 是整数

# 修复后
cap_forecast = self._load_cap_forecast(date_str, H)  # date_str 是字符串
```

---

## 四、修复文件清单

| 文件 | 修改类型 | 说明 |
|------|---------|------|
| `v2/models/capacity_predictor.py` | ✅ 新增 | 内部产能预测模型 |
| `v2/models/rolling_optimizer.py` | ✅ 修改 | 调用内部模型 + 格式转换 |
| `v2/examples/capacity_api_example.py` | ✅ 修改 | 更新示例代码 |
| `v2/tests/test_capacity_integration.py` | ✅ 新增 | 集成测试 |
| `v2/tests/test_optimization_models.py` | ✅ 修改 | 适配新格式 |
| `docs/CAPACITY_PREDICTOR_FIX.md` | ✅ 新增 | 修复文档 |

---

## 五、格式对比

### 旧格式 (已废弃)
```python
# 外部 API 格式
{
    "w1": [350, 360, 370, ...],  # 总产能，无品类
    "w2": [200, 210, 220, ...]
}

# 模型内部格式 (使用 day 编号)
{
    ("W1", "A", 70): 200.0,  # day 编号
    ("W1", "B", 70): 50.0
}
```

### 新格式 (推荐)
```python
# 产能预测模型输出
{
    "W1": {
        "2026-03-11": {"A": 220.0, "B": 60.0},
        "2026-03-12": {"A": 231.0, "B": 63.0}
    },
    "W2": {...}
}

# 模型内部格式 (使用日期字符串)
{
    ("W1", "A", "2026-03-11"): 220.0,
    ("W1", "B", "2026-03-11"): 60.0,
    ("W1", "A", "2026-03-12"): 231.0
}
```

---

## 六、测试验证

### 1. 产能预测模型测试
```bash
python3 models/capacity_predictor.py
```
**结果**: ✅ 通过 - 返回正确格式

### 2. 集成测试
```bash
python3 tests/test_capacity_integration.py
```
**结果**: ✅ 所有测试通过
- 格式验证 ✅
- 格式转换 ✅
- 集成测试 ✅

### 3. 最优化模型测试
```bash
python3 tests/test_optimization_models.py
```
**结果**: ✅ 所有测试通过 (6/6)
- Contract 结构体 ✅
- 在途预测 ✅
- 最优化模型 ✅
- 滚动优化器 ✅
- 产能分配器 ✅
- 紧急度计算器 ✅

---

## 七、兼容性说明

### 向后兼容
- ✅ 保留 `to_day_number()` 和 `from_day_number()` 转换方法
- ✅ 保留旧版 `_convert_capacity_format()` 方法（未使用但保留）
- ✅ 状态文件同时记录日期和 day 编号

### 不兼容项
- ❌ 外部 API 调用接口已移除（改为内部函数）
- ❌ 旧版总产能格式不再使用（已升级为分品类格式）

---

## 八、使用示例

### 直接使用产能预测
```python
from models.capacity_predictor import predict_capacity

# 预测未来 10 天产能
forecast = predict_capacity(today="2026-03-11", H=10)

# 输出格式
{
    "W1": {
        "2026-03-11": {"A": 220.5, "B": 60.1},
        "2026-03-12": {"A": 232.8, "B": 63.5}
    }
}
```

### 在滚动优化器中使用
```python
from models.rolling_optimizer import RollingOptimizer

optimizer = RollingOptimizer()
result = optimizer.run(today_date="2026-03-11", H=10)
# 自动调用内部产能预测模型
```

---

## 九、后续建议

1. **数据驱动优化**: 从历史数据学习产能波动规律
2. **机器学习预测**: 引入 ML 模型（LSTM/Prophet）提升预测精度
3. **实时监控**: 对接生产系统，实时调整产能预测
4. **因素扩展**: 考虑设备状态、原材料、工人排班等因素

---

## 十、总结

✅ **所有产能预测相关文件已完全适配新设定**

- ✅ 不再依赖外部 API
- ✅ 返回格式包含品类信息
- ✅ 所有文件统一使用日期字符串
- ✅ 所有测试通过
- ✅ 向后兼容性良好

**诊断完成，可以安心使用！** 🎉
