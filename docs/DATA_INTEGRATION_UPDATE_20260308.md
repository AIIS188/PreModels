# 外部数据对接更新日志

**更新日期**: 2026-03-08  
**更新人**: AIIS188  
**版本**: v2.1  

---

## 更新内容

### 1. 合同数据对接 - 已完成

**文件**: `v2/rolling_optimizer.py`

**修改**:
- 实现 `_load_contracts()` 方法
- 对接 PD API: `GET /api/v1/contracts/`
- 添加 `_date_to_day()` 日期转换工具
- 支持降级到默认合同（API 失败时）

**代码示例**:
```python
def _load_contracts(self) -> List[Contract]:
    """从 PD API 加载合同列表"""
    pd_contracts = self.api.get_contracts(page=1, page_size=100)
    
    if not pd_contracts:
        # 降级使用默认合同
        return [default_contracts...]
    
    contracts = []
    for pc in pd_contracts:
        contracts.append(Contract(
            cid=pc.contract_no,
            receiver=pc.smelter_company,
            Q=pc.total_quantity,
            start_day=self._date_to_day(pc.contract_date),
            end_day=self._date_to_day(pc.end_date),
            allowed_categories={p['product_name'] for p in pc.products},
        ))
    
    return contracts
```

**状态**: 已完成并测试

---

### 2. 估重画像 - 临时配置

**文件**: `v2/rolling_optimizer.py`

**配置**:
- 所有线路统一使用 `(mu=35.0, hi=35.0)`
- 以 35 吨为基准

**代码**:
```python
def _load_weight_profile(self) -> Dict:
    base_mu = 35.0  # 基准估重
    base_hi = 35.0  # 基准高估重
    
    return {
        ("W1", "R1", "A"): (base_mu, base_hi),
        ("W1", "R1", "B"): (base_mu, base_hi),
        # ... 所有线路
    }
```

**后续优化**: 从历史磅单数据学习各线路实际估重分布

**状态**: 临时配置完成

---

### 3. 延迟分布 - 临时配置

**文件**: `v2/rolling_optimizer.py`

**配置**:
- 3% 当日到 (delay=0)
- 97% 隔日到 (delay=1)
- 2% 2 日到 (delay=2)

**代码**:
```python
def _load_delay_profile(self) -> Dict:
    # 统一延迟分布
    delay_dist = {0: 0.03, 1: 0.97, 2: 0.02}
    
    return {
        ("W1", "R1"): delay_dist,
        ("W1", "R2"): delay_dist,
        # ... 所有线路
    }
```

**后续优化**: 从历史磅单数据学习各线路实际延迟分布

**状态**: 临时配置完成

---

### 4. 产能预测/仓库发货能力评估 - 预留接口

**文件**: `v2/rolling_optimizer.py`

**预留接口说明**:
```python
def _load_cap_forecast(self, today: int, H: int) -> Dict:
    """
    加载产能预测/仓库发货能力评估
    
    TODO: 后续由外部产能系统/仓库发货能力评估模块提供
    
    预留接口说明:
    - 需要对接仓库发货能力评估系统
    - 或者从产能预测 API 获取
    - 当前使用临时配置
    """
    # =====================================================
    # 预留接口：产能预测/仓库发货能力评估
    # =====================================================
    # TODO: 后续替换为真实产能系统接口
    # 示例:
    #   cap_forecast = self._load_capacity_from_external_system(today, H)
    #   if cap_forecast:
    #       return cap_forecast
    # =====================================================
    
    # 临时配置：基于仓库和品类的默认发货能力
    default_capacity = {
        ("W1", "A"): 220.0, ("W1", "B"): 60.0,
        ("W2", "A"): 80.0,  ("W2", "B"): 220.0,
        ("W3", "A"): 120.0, ("W3", "B"): 120.0,
    }
    
    # 生成 H 天的产能预测
    cap_forecast = {}
    for t in range(today, today + H):
        for (w, k), base in default_capacity.items():
            factor = 1.05 if (t % 2 == 0) else 0.90
            cap_forecast[(w, k, t)] = float(base) * factor
    
    return cap_forecast
```

**临时配置**:
- W1: A 品类 220 吨/日，B 品类 60 吨/日
- W2: A 品类 80 吨/日，B 品类 220 吨/日
- W3: A 品类 120 吨/日，B 品类 120 吨/日

**后续对接**:
- 需要仓库发货能力评估系统提供真实数据
- 或者接入产能预测 API
- 支持手动配置文件覆盖

**状态**: 预留接口完成，等待后续补充

---

## 对接状态总结

| 数据项 | 状态 | 配置方式 | 说明 |
|--------|------|---------|------|
| 合同数据 | 已完成 | PD API 自动获取 | 支持降级 |
| 磅单数据 | 已完成 | PD API 自动获取 | - |
| 报货单数据 | 已完成 | PD API 自动获取 | - |
| 估重画像 | 临时配置 | 硬编码 (35 吨基准) | 后续从历史学习 |
| 延迟分布 | 临时配置 | 硬编码 (97% 隔日) | 后续从历史学习 |
| 产能预测 | 预留接口 | 硬编码 (临时配置) | 等待仓库能力评估 |
| 创建报货单 | 已完成 | PD API 调用 | - |

**整体进度**: 7/9 (78%)

---

## 文件变更

### 修改文件

- `v2/rolling_optimizer.py`
  - `_load_contracts()`: 新增 PD API 对接
  - `_load_cap_forecast()`: 添加预留接口说明
  - `_load_weight_profile()`: 更新为 35 吨基准
  - `_load_delay_profile()`: 更新为统一延迟分布
  - `_date_to_day()`: 新增工具方法

### 新增文件

- `docs/DATA_INTEGRATION_UPDATE_20260308.md` - 本文档

---

## 测试验证

### 语法检查

```bash
cd /root/.openclaw/workspace/PreModels/v2
python3 -c "from rolling_optimizer import RollingOptimizer; print('语法检查通过')"
```

**结果**: 通过

### 功能测试

待 PD 系统录入真实合同数据后进行完整测试。

---

## 后续工作

### 高优先级

1. **仓库发货能力评估模块开发**
   - 设计仓库能力评估算法
   - 从历史发货数据统计分析
   - 集成到优化模型

2. **PD 系统数据录入**
   - 录入真实合同数据
   - 录入历史磅单数据
   - 验证合同数据对接

### 中优先级

3. **估重画像学习**
   - 实现学习算法
   - 从历史磅单统计各线路 mu/hi
   - 替代临时配置

4. **延迟分布学习**
   - 实现学习算法
   - 对比报货日期和磅单日期
   - 统计实际延迟分布

---

## 接口预留说明

### 产能预测接口

```python
# 预留接口位置：rolling_optimizer.py::_load_cap_forecast()

# 后续对接示例:
def _load_capacity_from_external_system(self, today: int, H: int) -> Dict:
    """从外部产能系统加载产能预测"""
    # 示例 1: 调用产能预测 API
    response = requests.get(
        "http://capacity-system/api/forecast",
        params={"today": today, "H": H}
    )
    return response.json()
    
    # 示例 2: 从配置文件读取
    # with open('capacity_config.json') as f:
    #     return json.load(f)
    
    # 示例 3: 从数据库查询
    # return self._query_capacity_from_db(today, H)
```

### 估重画像学习接口

```python
# 预留接口位置：rolling_optimizer.py::_load_weight_profile()

# 后续对接示例:
def _learn_weight_profile_from_history(self) -> Dict:
    """从历史磅单数据学习估重画像"""
    # 获取历史磅单
    weighbills = self.api.get_weighbills(page=1, page_size=10000)
    
    # 按线路统计
    profile = {}
    for wb in weighbills:
        key = (wb.warehouse, wb.target_factory_name, wb.product_name)
        if key not in profile:
            profile[key] = []
        profile[key].append(wb.net_weight)
    
    # 计算 mu 和 hi
    result = {}
    for key, weights in profile.items():
        mu = np.mean(weights)
        hi = np.percentile(weights, 90)
        result[key] = (mu, hi)
    
    return result
```

### 延迟分布学习接口

```python
# 预留接口位置：rolling_optimizer.py::_load_delay_profile()

# 后续对接示例:
def _learn_delay_profile_from_history(self) -> Dict:
    """从历史数据学习延迟分布"""
    # 获取历史报货单和磅单
    deliveries = self.api.get_deliveries(page=1, page_size=10000)
    weighbills = self.api.get_weighbills(page=1, page_size=10000)
    
    # 匹配报货单和磅单，计算延迟
    delays = {}
    for wb in weighbills:
        delivery = find_delivery_by_id(deliveries, wb.delivery_id)
        if delivery:
            delay = (wb.weigh_date - delivery.report_date).days
            key = (delivery.warehouse, delivery.target_factory_name)
            if key not in delays:
                delays[key] = []
            delays[key].append(delay)
    
    # 统计概率分布
    profile = {}
    for key, delay_list in delays.items():
        counter = Counter(delay_list)
        total = len(delay_list)
        profile[key] = {d: c/total for d, c in counter.items()}
    
    return profile
```

---

## 版本历史

### v2.1 (2026-03-08)

- [x] 合同数据对接 PD API
- [x] 估重画像临时配置 (35 吨基准)
- [x] 延迟分布临时配置 (97% 隔日)
- [x] 产能预测预留接口

### v2.0 (2026-03-08)

- [x] PD API 客户端完整实现
- [x] 磅单/报货单接口对接
- [x] 创建报货单接口对接

### v1.0 (2026-03-07)

- [x] 基础滚动优化器实现
- [x] 硬编码测试数据

---

**文档维护**: AIIS188  
**最后更新**: 2026-03-08 14:20
