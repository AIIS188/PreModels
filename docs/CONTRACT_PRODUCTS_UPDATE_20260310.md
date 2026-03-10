# 合同品类明细集成完成报告

**日期**: 2026-03-10  
**版本**: v2.1 - 品类价格集成  
**提交**: `待提交`

---

## ✅ 更新目标

将 PD API 的品类价格数据直接集成到 PreModels 内部的 `Contract` 结构中，实现：
1. 合同自包含价格信息，不依赖外部实时查询
2. 结算时直接用合同价，避免争议
3. 历史合同价格可追溯

---

## 📝 修改内容

### 1. `Contract` 结构体修改

**文件**: `v2/models/common_utils_v2.py`

```python
# 修改前
@dataclass(frozen=True)
class Contract:
    cid: str
    receiver: str
    Q: float
    start_day: str
    end_day: str
    allowed_categories: Set[str]  # 只有品类名称

# 修改后
@dataclass(frozen=True)
class Contract:
    cid: str
    receiver: str
    Q: float
    start_day: str
    end_day: str
    products: List[Dict]  # 品类明细 [{product_name, unit_price}]
    
    @property
    def allowed_categories(self) -> Set[str]:
        """向后兼容：从 products 提取品类名称集合"""
        return {p["product_name"] for p in self.products}
    
    def get_unit_price(self, product_name: str) -> Optional[float]:
        """获取指定品类的合同单价（元/吨）"""
        ...
    
    def get_base_price(self, product_name: str, invoice_factor: float = 1.048) -> Optional[float]:
        """获取指定品类的基础价（不含票）"""
        ...
```

### 2. 关键约束

- ✅ 一个合同可包含多个品类（如 `[{"动力煤": 800}, {"焦煤": 1200}]`）
- ✅ 合同期内价格锁定，不可调整
- ✅ 同一收货方只能有 1 个活跃合同（业务约束）

### 3. 向后兼容

- `allowed_categories` 作为 `@property` 保留，旧代码无需修改
- 自动从 `products` 提取品类名称集合

---

## 🔧 相关修改

### Rolling Optimizer

**文件**: `v2/models/rolling_optimizer.py`

1. **`_convert_pd_contracts`**: 直接使用 PD API 的 `products` 字段
2. **`_cache_contracts`**: 缓存 `products` 而非 `allowed_categories`
3. **`_load_cached_contracts`**: 从缓存加载 `products`

```python
# 转换 PD 合同
def _convert_pd_contracts(self, pd_contracts: List) -> List[Contract]:
    contracts = []
    for pc in pd_contracts:
        products = pc.products if pc.products else []
        start_day = pc.contract_date  # 使用日期字符串
        end_day = pc.end_date
        
        contracts.append(Contract(
            cid=pc.contract_no,
            receiver=pc.smelter_company,
            Q=pc.total_quantity,
            start_day=start_day,
            end_day=end_day,
            products=products,  # 直接集成品类价格
        ))
    
    return contracts
```

### 测试文件

更新所有测试用例使用新的 `products` 格式：

- ✅ `tests/test_date_migration.py`
- ✅ `tests/test_h_impact.py`
- ✅ `tests/test_multi_day.py`
- ✅ `tests/test_balance_shipping.py`

---

## ✅ 测试验证

### 1. 基础功能测试

```bash
cd /root/.openclaw/workspace/PreModels/v2
python3 tests/test_date_migration.py
```

**结果**: 所有测试通过 ✅

### 2. 新产品结构测试

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

# 测试价格查询
contract.get_unit_price("动力煤")  # 800.0
contract.get_base_price("动力煤")  # 763.36 (不含票)

# 测试向后兼容
contract.allowed_categories  # {"动力煤", "焦煤"}
```

**结果**: 所有功能正常 ✅

---

## 🎯 优势

### 1. 数据一致性
- ✅ 合同价格直接从 PD API 同步，避免人工录入错误
- ✅ 价格锁定在合同创建时，合同期内不可变

### 2. 计算便捷性
- ✅ 无需跨系统查询价格
- ✅ 结算时直接用 `contract.get_unit_price(category)`

### 3. 历史追溯
- ✅ 历史合同价格完整保存
- ✅ 支持价格变动分析

### 4. 向后兼容
- ✅ 旧代码无需修改（`allowed_categories` 作为 property 保留）
- ✅ 渐进式迁移，不影响现有功能

---

## 📋 修改文件清单

1. ✅ `v2/models/common_utils_v2.py` - Contract 结构体增强
2. ✅ `v2/models/rolling_optimizer.py` - 合同转换和缓存逻辑更新
3. ✅ `v2/tests/test_date_migration.py` - 测试用例更新
4. ✅ `v2/tests/test_h_impact.py` - 测试用例更新
5. ✅ `v2/tests/test_multi_day.py` - 测试用例更新
6. ✅ `v2/tests/test_balance_shipping.py` - 测试用例更新

---

## 🚀 下一步

1. ✅ 已完成：核心模型更新
2. ✅ 已完成：测试验证通过
3. ⏳ 可选：更新其他使用 Contract 的模块
4. ⏳ 生产环境验证（对接真实 PD API）

---

## 📞 使用示例

### 创建合同（从 PD API）

```python
from core.api_client import PDAPIClient
from models.common_utils_v2 import Contract

api = PDAPIClient()
pd_contracts = api.get_contracts()

# 转换为内部格式
contracts = []
for pc in pd_contracts:
    contract = Contract(
        cid=pc.contract_no,
        receiver=pc.smelter_company,
        Q=pc.total_quantity,
        start_day=pc.contract_date,
        end_day=pc.end_date,
        products=pc.products,  # 品类明细（含价格）
    )
    contracts.append(contract)
```

### 查询合同价格

```python
# 获取某品类的合同单价
price = contract.get_unit_price("动力煤")  # 800.0 元/吨

# 获取基础价（不含票）
base_price = contract.get_base_price("动力煤")  # 763.36 元/吨

# 检查品类是否允许
if "动力煤" in contract.allowed_categories:
    print("允许发运动力煤")
```

---

**更新完成！** 🎉
