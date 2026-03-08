# 合同加载和估重配置优化

**日期**: 2026-03-08  
**修改人**: AIIS188  
**类型**: 重要修复  

---

## 问题描述

### 问题 1: 合同加载逻辑不合理

**原逻辑**:
- API 失败时降级到硬编码的默认合同
- 硬编码合同可能过期，导致模型基于错误数据决策

**风险**:
- 使用过期合同数据
- 模型优化结果不符合实际情况
- 可能导致错误的发货计划

### 问题 2: 估重配置过于简化

**原配置**:
- 所有线路统一使用 (35.0, 35.0)
- 没有上下浮动，不符合实际场景

**问题**:
- 实际运输中估重会有波动
- 不同线路、不同品类的估重有差异

---

## 修复方案

### 1. 合同加载 - 必须成功原则

**新逻辑**:

```
┌─────────────────────────────────────┐
│  1. 尝试从 PD API 加载合同           │
└──────────────┬──────────────────────┘
               │
       ┌───────┴───────┐
       │               │
   ✅ 成功          ❌ 失败
       │               │
       │               ▼
       │      ┌─────────────────┐
       │      │ 2. 尝试加载缓存  │
       │      └───────┬─────────┘
       │              │
       │      ┌───────┴───────┐
       │      │               │
       │  ✅ 有缓存       ❌ 无缓存
       │      │               │
       │      │               ▼
       │      │      ┌─────────────────┐
       │      │      │ 3. 抛出异常     │
       │      │      │ 终止运行        │
       │      │      └─────────────────┘
       │      │
       ▼      ▼
  使用 API 数据  使用缓存数据
```

**代码实现**:

```python
def _load_contracts(self) -> List[Contract]:
    """
    加载合同列表（从 PD API 获取）
    
    重要说明:
    - 合同数据必须从 PD API 成功加载
    - API 失败时，使用缓存的合同数据（上次成功加载的结果）
    - 如果既无 API 响应也无缓存，则抛出异常终止运行
    - 不使用硬编码的默认合同（避免数据过期导致错误决策）
    """
    # 尝试从 PD API 加载
    try:
        pd_contracts = self.api.get_contracts(page=1, page_size=100)
        
        if pd_contracts:
            contracts = self._convert_pd_contracts(pd_contracts)
            self.state_mgr.log(f"从 PD API 加载 {len(contracts)} 个合同")
            # 缓存成功加载的合同
            self._cache_contracts(contracts)
            return contracts
        
        self.state_mgr.log("PD API 未返回合同数据，尝试使用缓存", "WARNING")
        
    except Exception as e:
        self.state_mgr.log(f"PD API 调用失败：{e}", "ERROR")
    
    # API 失败时，尝试使用缓存的合同
    cached_contracts = self._load_cached_contracts()
    if cached_contracts:
        self.state_mgr.log(f"使用缓存的合同 {len(cached_contracts)} 个", "WARNING")
        return cached_contracts
    
    # API 和缓存都不可用，抛出异常
    self.state_mgr.log("无法加载合同数据：API 失败且无缓存，模型无法运行", "ERROR")
    raise RuntimeError(
        "合同数据加载失败：PD API 不可用且无缓存数据。"
        "请先确保 PD 系统中有合同数据，或检查 API 连接。"
    )
```

**新增方法**:

```python
def _cache_contracts(self, contracts: List[Contract]):
    """缓存合同数据到文件（用于 API 失败时的降级）"""
    cache_file = "./state/contracts_cache.json"
    # 保存合同数据到 JSON 文件

def _load_cached_contracts(self) -> Optional[List[Contract]]:
    """从缓存文件加载合同数据"""
    cache_file = "./state/contracts_cache.json"
    # 从 JSON 文件读取合同数据
```

**优势**:
- 保证合同数据始终是真实的（来自 PD API 或最近缓存）
- 避免使用过期硬编码数据
- API 临时故障时仍可运行（使用缓存）
- 完全不可用时明确报错，不产生错误结果

---

### 2. 估重画像 - 35 吨上下浮动

**新配置**:

| 仓库 | 线路 | 品类 | mu (期望) | hi (高估) | 说明 |
|------|------|------|-----------|-----------|------|
| W1 | R1 | A | 35.0 | 37.0 | 基准 |
| W1 | R1 | B | 34.0 | 36.0 | 略低 |
| W1 | R2 | A | 36.0 | 38.0 | 略高 |
| W1 | R2 | B | 35.0 | 37.0 | 基准 |
| W2 | R1 | A | 33.0 | 35.0 | 较低 |
| W2 | R1 | B | 34.0 | 36.0 | 略低 |
| W2 | R2 | A | 35.0 | 37.0 | 基准 |
| W2 | R2 | B | 33.0 | 35.0 | 较低 |
| W3 | R1 | A | 32.0 | 34.0 | 低 |
| W3 | R1 | B | 33.0 | 35.0 | 较低 |
| W3 | R2 | A | 34.0 | 36.0 | 略低 |
| W3 | R2 | B | 32.0 | 34.0 | 低 |

**范围**: 32-38 吨（35 上下浮动 3 吨）

**代码实现**:

```python
def _load_weight_profile(self) -> Dict:
    """
    加载估重画像
    
    临时配置：35 吨上下浮动（32-38 吨范围）
    不同仓库线路略有差异，模拟真实场景
    """
    return {
        # W1 仓库线路（35 上下浮动）
        ("W1", "R1", "A"): (35.0, 37.0),
        ("W1", "R1", "B"): (34.0, 36.0),
        ("W1", "R2", "A"): (36.0, 38.0),
        ("W1", "R2", "B"): (35.0, 37.0),
        # W2 仓库线路（35 上下浮动）
        ("W2", "R1", "A"): (33.0, 35.0),
        ("W2", "R1", "B"): (34.0, 36.0),
        ("W2", "R2", "A"): (35.0, 37.0),
        ("W2", "R2", "B"): (33.0, 35.0),
        # W3 仓库线路（35 上下浮动）
        ("W3", "R1", "A"): (32.0, 34.0),
        ("W3", "R1", "B"): (33.0, 35.0),
        ("W3", "R2", "A"): (34.0, 36.0),
        ("W3", "R2", "B"): (32.0, 34.0),
    }
```

**优势**:
- 更接近真实运输场景
- 不同线路有合理差异
- 为后续从历史数据学习留出空间

---

## 文件变更

### 修改文件

`v2/rolling_optimizer.py`

**变更统计**:
- 新增 142 行
- 删除 54 行
- 净增 88 行

**修改内容**:
1. `_load_contracts()` - 重写合同加载逻辑
2. `_convert_pd_contracts()` - 新增格式转换方法
3. `_cache_contracts()` - 新增缓存方法
4. `_load_cached_contracts()` - 新增缓存加载方法
5. `_load_weight_profile()` - 更新估重配置

---

## 测试验证

### 语法检查

```bash
cd /root/.openclaw/workspace/PreModels/v2
python3 -c "from rolling_optimizer import RollingOptimizer; print('语法检查通过')"
```

**结果**: 通过

### 功能测试场景

#### 场景 1: API 正常

```
1. PD API 返回合同数据
2. 加载并转换合同
3. 缓存合同到文件
4. 返回合同列表
```

**预期**: 成功加载，缓存生成

#### 场景 2: API 临时故障，有缓存

```
1. PD API 调用失败
2. 捕获异常，记录日志
3. 从缓存文件加载合同
4. 返回缓存合同
```

**预期**: 使用缓存，警告日志

#### 场景 3: API 故障，无缓存

```
1. PD API 调用失败
2. 尝试加载缓存，文件不存在
3. 抛出 RuntimeError
4. 模型终止运行
```

**预期**: 抛出异常，错误日志

---

## 缓存文件说明

### 文件格式

`state/contracts_cache.json`

```json
[
  {
    "cid": "HT-2024-001",
    "receiver": "河南金利金铅集团有限公司",
    "Q": 1000.0,
    "start_day": 15,
    "end_day": 25,
    "allowed_categories": ["A", "B"]
  },
  {
    "cid": "HT-2024-002",
    "receiver": "另一个冶炼厂",
    "Q": 500.0,
    "start_day": 10,
    "end_day": 20,
    "allowed_categories": ["A"]
  }
]
```

### 缓存管理

**生成**: 每次 API 成功加载后自动生成

**更新**: API 成功加载时覆盖旧缓存

**删除**: 
- 手动删除：`rm state/contracts_cache.json`
- 清空缓存后，下次运行必须 API 成功

---

## 运行建议

### 首次运行

```bash
# 确保 PD 系统中有合同数据
# 确保 PD API 可访问
cd /root/.openclaw/workspace/PreModels/v2
python3 rolling_optimizer.py --run --today 10
```

**预期**:
- 从 PD API 加载合同
- 生成缓存文件
- 正常运行优化

### 日常运行

```bash
# 常规运行，自动使用 API 或缓存
python3 rolling_optimizer.py --run --today 11
```

**预期**:
- 优先使用 API 数据
- API 故障时使用缓存
- 完全不可用时明确报错

### 缓存清理

```bash
# 清理缓存（强制重新从 API 加载）
rm state/contracts_cache.json
```

**注意**: 清理后如果 API 不可用，模型将无法运行

---

## 错误处理

### 错误 1: 合同数据加载失败

```
RuntimeError: 合同数据加载失败：PD API 不可用且无缓存数据。
请先确保 PD 系统中有合同数据，或检查 API 连接。
```

**解决方法**:
1. 检查 PD 服务是否运行：`curl http://127.0.0.1:8007/healthz`
2. 检查 PD 系统中是否有合同数据
3. 检查网络连接
4. 恢复后重新运行

### 错误 2: PD API 返回空数据

**日志**:
```
WARNING: PD API 未返回合同数据，尝试使用缓存
WARNING: 使用缓存的合同 X 个
```

**说明**: API 正常但无数据，使用缓存继续运行

---

## 后续优化

### 1. 缓存过期策略

当前缓存永久有效，后续可添加过期时间：

```python
# 缓存 24 小时过期
CACHE_TTL_HOURS = 24

def _is_cache_valid(self) -> bool:
    # 检查缓存文件修改时间
    # 超过 TTL 则视为过期
```

### 2. 缓存版本管理

支持多个版本的缓存，便于回滚：

```
state/
  contracts_cache.json        # 当前缓存
  contracts_cache.v1.json     # 历史版本 1
  contracts_cache.v2.json     # 历史版本 2
```

### 3. 估重画像学习

后续从历史磅单数据学习真实估重：

```python
def _learn_weight_profile_from_history(self) -> Dict:
    # 从 PD 历史磅单统计各线路实际估重
    # 替代临时配置
```

---

## 版本历史

### v2.2 (2026-03-08 14:30)

- [x] 合同加载必须成功，不支持硬编码降级
- [x] 新增合同缓存机制
- [x] 估重画像 35 吨上下浮动（32-38 吨）
- [x] 新增缓存管理方法

### v2.1 (2026-03-08 14:20)

- [x] 合同数据对接 PD API
- [x] 估重画像临时配置
- [x] 延迟分布临时配置

### v2.0 (2026-03-08 13:00)

- [x] PD API 客户端完整实现

---

**文档维护**: AIIS188  
**最后更新**: 2026-03-08 14:30
