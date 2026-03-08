# 日期格式重构计划

**日期**: 2026-03-08  
**状态**: 计划中  

---

## 一、当前问题

### 使用 day 编号的问题

```python
# 当前方式
today = 10  # Day 10
start_day = 9
end_day = 13
```

**问题**:
1. ❌ 不直观，需要计算才知道是哪天
2. ❌ 依赖基准日 (2026-01-01)
3. ❌ 与 PD API 对接时需要转换
4. ❌ 日志和记录不清晰

---

## 二、重构方案

### 使用日期字符串

```python
# 新方式
today = "2026-03-10"  # 直接日期
start_date = "2026-03-09"
end_date = "2026-03-13"
```

**优势**:
1. ✅ 直观清晰
2. ✅ 无需基准日
3. ✅ 与 PD API 格式一致
4. ✅ 日志易读

---

## 三、修改范围

### 核心文件

| 文件 | 修改点 | 工作量 |
|------|--------|--------|
| `v2/models/rolling_optimizer.py` | run(today) → run(today_date) | 2 小时 |
| `v2/models/complex_system_v2.py` | day 参数 → date 参数 | 4 小时 |
| `v2/core/state_manager.py` | 日期存储格式 | 1 小时 |
| `v2/core/api_client.py` | 日期转换函数 | 1 小时 |

### 测试文件

| 文件 | 修改点 | 工作量 |
|------|--------|--------|
| `v2/tests/*.py` | 测试用例日期格式 | 2 小时 |

### 脚本

| 文件 | 修改点 | 工作量 |
|------|--------|--------|
| `scripts/run_daily_optimization.py` | 自动获取日期 | 1 小时 |

---

## 四、日期处理工具

### 新增工具类

```python
# v2/core/date_utils.py

class DateUtils:
    """日期工具类"""
    
    @staticmethod
    def today() -> str:
        """获取今日日期"""
        return datetime.now().strftime("%Y-%m-%d")
    
    @staticmethod
    def add_days(date_str: str, days: int) -> str:
        """日期加减"""
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        result = dt + timedelta(days=days)
        return result.strftime("%Y-%m-%d")
    
    @staticmethod
    def diff_days(date1: str, date2: str) -> int:
        """计算日期差"""
        d1 = datetime.strptime(date1, "%Y-%m-%d")
        d2 = datetime.strptime(date2, "%Y-%m-%d")
        return (d2 - d1).days
    
    @staticmethod
    def to_day_number(date_str: str, base: str = "2026-01-01") -> int:
        """日期转 day 编号 (兼容旧版)"""
        base_dt = datetime.strptime(base, "%Y-%m-%d")
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return (dt - base_dt).days + 1
    
    @staticmethod
    def from_day_number(day: int, base: str = "2026-01-01") -> str:
        """day 编号转日期 (兼容旧版)"""
        base_dt = datetime.strptime(base, "%Y-%m-%d")
        result = base_dt + timedelta(days=day-1)
        return result.strftime("%Y-%m-%d")
```

---

## 五、过渡方案

### 兼容旧版 day 编号

```python
# 过渡期支持两种格式
def run(self, today=None, today_date=None, H=10):
    """
    运行优化
    
    参数:
        today: Day 编号 (旧版，兼容)
        today_date: 日期字符串 (新版，推荐)
        H: 规划窗口
    """
    # 优先使用 today_date
    if today_date:
        date_str = today_date
    elif today:
        date_str = DateUtils.from_day_number(today)
    else:
        date_str = DateUtils.today()
    
    # 后续逻辑使用 date_str
```

---

## 六、实施步骤

### 阶段 1: 新增日期工具 (1 小时)

- [ ] 创建 `v2/core/date_utils.py`
- [ ] 实现日期转换函数
- [ ] 编写单元测试

### 阶段 2: 修改核心逻辑 (6 小时)

- [ ] 修改 `rolling_optimizer.py`
- [ ] 修改 `complex_system_v2.py`
- [ ] 修改 `state_manager.py`
- [ ] 修改 `api_client.py`

### 阶段 3: 修改脚本 (1 小时)

- [ ] 修改 `run_daily_optimization.py`
- [ ] 修改 `health_check.py`

### 阶段 4: 修改测试 (2 小时)

- [ ] 修改所有测试用例
- [ ] 运行回归测试

### 阶段 5: 文档更新 (1 小时)

- [ ] 更新 README
- [ ] 更新 API 文档
- [ ] 更新示例代码

---

## 七、示例对比

### 优化前

```python
optimizer = RollingOptimizer()
result = optimizer.run(today=10, H=10)

# 结果
{
    "day": 10,
    "shipments": [...]
}
```

### 优化后

```python
optimizer = RollingOptimizer()
result = optimizer.run(today_date="2026-03-10", H=10)

# 结果
{
    "date": "2026-03-10",
    "shipments": [...]
}
```

---

## 八、数据迁移

### 状态文件迁移

```python
# 旧版 state.json
{
    "last_run_day": 10,
    "delivered_so_far": {...}
}

# 新版 state.json
{
    "last_run_date": "2026-03-10",
    "delivered_so_far": {...}
}
```

### 自动迁移脚本

```python
def migrate_state_file():
    """迁移状态文件"""
    state_file = "v2/state/state.json"
    
    with open(state_file, 'r') as f:
        state = json.load(f)
    
    # 转换 day → date
    if 'last_run_day' in state:
        state['last_run_date'] = DateUtils.from_day_number(state['last_run_day'])
        del state['last_run_day']
    
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)
```

---

## 九、时间估算

| 阶段 | 工作量 | 完成时间 |
|------|--------|---------|
| 日期工具 | 1 小时 | Day 1 |
| 核心逻辑 | 6 小时 | Day 1-2 |
| 脚本修改 | 1 小时 | Day 2 |
| 测试修改 | 2 小时 | Day 2 |
| 文档更新 | 1 小时 | Day 2 |
| **总计** | **11 小时** | **2 天** |

---

## 十、风险与缓解

### 风险

1. **兼容性问题** - 旧版 day 编号可能还有地方使用
2. **测试遗漏** - 可能有测试用例未更新
3. **数据丢失** - 状态文件迁移可能出错

### 缓解措施

1. **保留兼容层** - 过渡期支持两种格式
2. **完整测试** - 运行所有测试用例
3. **备份数据** - 迁移前备份状态文件

---

**计划人**: AIIS188  
**计划时间**: 2026-03-08  
**状态**: 待批准
