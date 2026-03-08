# PD API 接口对接文档

**版本**: v2.0  
**更新日期**: 2026-03-08  
**PD 仓库**: https://github.com/Jisalute/PD  
**PreModels 仓库**: https://github.com/AIIS188/PreModels  

---

## 📋 目录

- [概述](#概述)
- [核心接口详解](#核心接口详解)
- [数据格式映射](#数据格式映射)
- [使用示例](#使用示例)
- [错误处理](#错误处理)
- [API 参考](#api 参考)

---

## 概述

### 接口架构

```
┌─────────────────────────────────────────────────────┐
│              PreModels v2                           │
│  (量化优化系统)                                     │
│                                                     │
│  ┌───────────────────────────────────────┐         │
│  │  api_client.py (适配层)               │         │
│  │                                       │         │
│  │  - PDAPIClient 类                     │         │
│  │  - 数据格式转换                       │         │
│  │  - 错误处理和重试                     │         │
│  └───────────────────────────────────────┘         │
└─────────────────┬───────────────────────────────────┘
                  │ HTTP/JSON
                  │ http://127.0.0.1:8007
                  ▼
┌─────────────────────────────────────────────────────┐
│              PD API                                 │
│  (业务系统)                                         │
│                                                     │
│  /api/v1/deliveries/    - 报货单管理               │
│  /api/v1/weighbills/    - 磅单管理                 │
│  /api/v1/contracts/     - 合同管理                 │
│  /api/v1/balances/      - 磅单结余                 │
└─────────────────────────────────────────────────────┘
```

### 接口列表

| 类别 | 接口 | 方法 | PreModels 使用场景 |
|------|------|------|-------------------|
| **健康检查** | `/healthz` | GET | 服务状态监控 |
| **报货单** | `/api/v1/deliveries/` | GET | 获取在途报单 |
| **报货单** | `/api/v1/deliveries/{id}` | GET | 查询报单详情 |
| **报货单** | `/api/v1/deliveries/json` | POST | 创建报货单（执行发货） |
| **报货单** | `/api/v1/deliveries/{id}` | PUT | 更新报货单 |
| **磅单** | `/api/v1/weighbills/` | GET | 获取已确认到货 |
| **磅单** | `/api/v1/weighbills/delivery/{id}` | GET | 查询报单的磅单 |
| **磅单** | `/api/v1/weighbills/{id}` | GET | 查询磅单详情 |
| **合同** | `/api/v1/contracts/` | GET | 获取合同信息 |
| **合同** | `/api/v1/contracts/id/{id}` | GET | 查询合同详情 |
| **结余** | `/api/v1/balances/` | GET | 查询磅单结余 |

---

## 核心接口详解

### 1. 健康检查

```http
GET /healthz
```

**响应**:
```json
{"status": "ok"}
```

**使用场景**: 服务启动时检查 PD API 可用性

---

### 2. 获取报货单列表

```http
GET /api/v1/deliveries/
```

**查询参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `exact_status` | string | 否 | 状态过滤：待确认/已确认/已完成 |
| `exact_contract_no` | string | 否 | 合同编号过滤 |
| `exact_report_date` | string | 否 | 报货日期过滤 (YYYY-MM-DD) |
| `exact_factory_name` | string | 否 | 目标工厂过滤 |
| `page` | integer | 否 | 页码（默认 1） |
| `page_size` | integer | 否 | 每页数量（默认 20，最大 100） |

**响应格式**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "report_date": "2026-03-08",
      "contract_no": "HT-2024-001",
      "warehouse": "W1",
      "target_factory_name": "R1",
      "product_name": "A",
      "products": ["A", "B"],
      "quantity": 100.0,
      "vehicle_no": "京 A12345",
      "driver_name": "张三",
      "driver_phone": "13800138000",
      "driver_id_card": "110101199001011234",
      "has_delivery_order": "有",
      "upload_status": "已上传",
      "shipper": "李四",
      "reporter_id": 1,
      "reporter_name": "李四",
      "payee": "王五",
      "service_fee": 100.0,
      "contract_unit_price": 520.0,
      "total_amount": 52100.0,
      "status": "待确认"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

**PreModels 使用场景**: 
- 获取在途报单列表
- 更新优化模型的在途状态

---

### 3. 创建报货单

```http
POST /api/v1/deliveries/json
```

**请求体**:
```json
{
  "report_date": "2026-03-08",
  "target_factory_name": "R1",
  "product_name": "A",
  "products": "A,B,C",
  "quantity": 100.0,
  "vehicle_no": "京 A12345",
  "driver_name": "张三",
  "driver_phone": "13800138000",
  "driver_id_card": "110101199001011234",
  "has_delivery_order": "无",
  "status": "待确认",
  "contract_no": "HT-2024-001",
  "reporter_id": 1,
  "reporter_name": "李四"
}
```

**响应格式**:
```json
{
  "success": true,
  "message": "报货单创建成功",
  "data": {
    "delivery_id": 1,
    "existing_orders": []
  }
}
```

**字段说明**:
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `report_date` | string | 是 | 报货日期 (YYYY-MM-DD) |
| `target_factory_name` | string | 是 | 目标工厂名称 |
| `product_name` | string | 是 | 主品种名称 |
| `products` | string | 否 | 品种列表（逗号分隔，最多 4 个） |
| `quantity` | float | 是 | 数量（吨） |
| `vehicle_no` | string | 是 | 车牌号 |
| `driver_name` | string | 是 | 司机姓名 |
| `driver_phone` | string | 是 | 司机电话 |
| `driver_id_card` | string | 否 | 身份证号 |
| `has_delivery_order` | string | 否 | 是否有联单：有/无（默认无） |
| `status` | string | 否 | 状态：待确认/已确认/已完成（默认待确认） |
| `contract_no` | string | 否 | 合同编号 |
| `reporter_id` | integer | 否 | 报单人 ID |
| `reporter_name` | string | 否 | 报单人姓名 |

**PreModels 使用场景**: 
- 执行优化模型生成的发货计划
- 创建报货单到 PD 系统

---

### 4. 获取磅单列表

```http
GET /api/v1/weighbills/
```

**查询参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `exact_weigh_date` | string | 否 | 磅单日期过滤 (YYYY-MM-DD) |
| `exact_contract_no` | string | 否 | 合同编号过滤 |
| `page` | integer | 否 | 页码（默认 1） |
| `page_size` | integer | 否 | 每页数量（默认 20，最大 100） |

**响应格式**:
```json
{
  "success": true,
  "data": [
    {
      "delivery_id": 1,
      "contract_no": "HT-2024-001",
      "report_date": "2026-03-08",
      "target_factory_name": "R1",
      "driver_phone": "13800138000",
      "driver_name": "张三",
      "vehicle_no": "京 A12345",
      "has_delivery_order": "有",
      "shipper": "李四",
      "reporter_name": "李四",
      "payee": "王五",
      "warehouse": "W1",
      "service_fee": 100.0,
      "total_weighbills": 2,
      "uploaded_weighbills": 2,
      "weighbills": [
        {
          "id": 1,
          "delivery_id": 1,
          "weigh_date": "2026-03-08",
          "weigh_ticket_no": "WP20260308001",
          "contract_no": "HT-2024-001",
          "vehicle_no": "京 A12345",
          "product_name": "A",
          "gross_weight": 50.5,
          "tare_weight": 15.2,
          "net_weight": 35.3,
          "unit_price": 520.0,
          "total_amount": 18356.0,
          "delivery_time": "10:30",
          "upload_status": "已上传",
          "warehouse": "W1",
          "payee": "王五"
        }
      ]
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

**注意**: PD API 返回的磅单是按报单分组的，需要展开处理。

**PreModels 使用场景**: 
- 获取已确认的到货数据
- 更新优化模型的已到货状态
- 计算合同完成进度

---

### 5. 获取合同列表

```http
GET /api/v1/contracts/
```

**查询参数**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `exact_contract_no` | string | 否 | 合同编号过滤 |
| `exact_smelter_company` | string | 否 | 冶炼厂过滤 |
| `exact_status` | string | 否 | 状态过滤 |
| `page` | integer | 否 | 页码 |
| `page_size` | integer | 否 | 每页数量 |

**响应格式**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "contract_no": "HT-2024-001",
      "contract_date": "2024-01-15",
      "end_date": "2024-01-20",
      "smelter_company": "河南金利金铅集团有限公司",
      "total_quantity": 1000.0,
      "truck_count": 40,
      "arrival_payment_ratio": 0.9,
      "final_payment_ratio": 0.1,
      "status": "生效中",
      "products": [
        {"product_name": "A", "unit_price": 520.0},
        {"product_name": "B", "unit_price": 500.0}
      ]
    }
  ]
}
```

---

## 数据格式映射

### PreModels ↔ PD 字段映射

| PreModels 字段 | PD 字段 | 类型 | 转换说明 |
|---------------|---------|------|---------|
| `cid` | `contract_no` | string | 合同编号 |
| `warehouse` | `warehouse` / `target_factory_name` | string | 仓库/目标工厂 |
| `category` | `product_name` | string | 品种名称 |
| `tons` / `weight` | `quantity` / `net_weight` | float | 数量/重量（吨） |
| `ship_day` | `report_date` / `weigh_date` | string | 日期转换：day ↔ YYYY-MM-DD |
| `truck_id` | `vehicle_no` | string | 车牌号 |
| `driver_id` | `driver_name` / `payee` | string | 司机/收款人 |
| `order_id` | `id` | int | 报单 ID（前缀 DL） |
| `bill_id` | `id` | int | 磅单 ID（前缀 WB） |

### 日期转换

```python
# day 编号 ↔ YYYY-MM-DD
# 基准日：2026-01-01

def day_to_date(day: int) -> str:
    """将 day 编号转换为日期字符串"""
    from datetime import datetime, timedelta
    base = datetime(2026, 1, 1)
    target = base + timedelta(days=day-1)
    return target.strftime("%Y-%m-%d")

def date_to_day(date_str: str) -> int:
    """将日期字符串转换为 day 编号"""
    from datetime import datetime
    base = datetime(2026, 1, 1)
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return (dt - base).days + 1
```

### 状态转换

| PD 状态 | PreModels 状态 | 说明 |
|--------|---------------|------|
| `待确认` | `pending` | 待确认 |
| `已确认` | `weighed` | 已过磅 |
| `已完成` | `weighed` | 已完成 |
| `已取消` | `cancelled` | 已取消 |

---

## 使用示例

### 1. 初始化客户端

```python
from api_client import PDAPIClient

# 初始化
api = PDAPIClient(base_url="http://127.0.0.1:8007")

# 健康检查
if not api.health_check():
    print("PD API 不可用！")
    exit(1)

print("✅ PD API 连接正常")
```

### 2. 获取在途报单

```python
# 获取所有待确认的报单
deliveries = api.get_deliveries(
    exact_status="待确认",
    page=1,
    page_size=100
)

print(f"在途报单数量：{len(deliveries)}")

# 转换为 PreModels 格式
from api_client import PDAPIClient

in_transit = []
for d in deliveries:
    pm_delivery = PDAPIClient.convert_to_pre_models_delivery(d)
    in_transit.append(pm_delivery)
```

### 3. 获取已确认到货

```python
from api_client import get_confirmed_arrivals

# 获取今日到货
today = "2026-03-08"
arrivals = get_confirmed_arrivals(api, today=today)

# 按合同汇总
for contract_no, weight in arrivals.items():
    print(f"合同 {contract_no}: {weight}吨")
```

### 4. 执行发货计划

```python
# 从优化模型获取发货计划
shipment_plan = {
    "warehouse": "W1",
    "cid": "C1",
    "category": "A",
    "tons": 99.1,
    "ship_day": 10  # day 编号
}

# 转换为 PD API 格式
from api_client import PDAPIClient

delivery_data = {
    "report_date": PDAPIClient._day_to_date(shipment_plan["ship_day"]),
    "target_factory_name": shipment_plan["warehouse"],
    "product_name": shipment_plan["category"],
    "quantity": shipment_plan["tons"],
    "vehicle_no": "京 A12345",  # 从车辆调度获取
    "driver_name": "张三",      # 从车辆调度获取
    "driver_phone": "13800138000",
    "status": "待确认",
    "contract_no": shipment_plan["cid"]
}

# 创建报货单
result = api.create_delivery(delivery_data)

if result.get("success"):
    delivery_id = result["data"]["delivery_id"]
    print(f"✅ 报货单创建成功：{delivery_id}")
else:
    print(f"❌ 创建失败：{result.get('error')}")
```

### 5. 集成到 rolling_optimizer.py

```python
from api_client import PDAPIClient, get_confirmed_arrivals

class RollingOptimizer:
    def __init__(self, api_base_url: str = "http://127.0.0.1:8007"):
        self.api = PDAPIClient(api_base_url)
    
    def run_optimization(self, today: int, H: int = 10):
        """运行滚动优化"""
        
        # 1. 日期转换
        today_str = self._day_to_date(today)
        
        # 2. 从 PD API 获取最新磅单
        confirmed = get_confirmed_arrivals(self.api, today=today_str)
        print(f"今日到货：{confirmed}")
        
        # 3. 获取在途报单
        in_transit_pd = self.api.get_deliveries(exact_status="待确认")
        in_transit = [
            PDAPIClient.convert_to_pre_models_delivery(d)
            for d in in_transit_pd
        ]
        
        # 4. 更新状态
        self.state.update_arrivals(confirmed)
        self.state.update_in_transit(in_transit)
        
        # 5. 运行优化模型
        plan = self.optimize(today, H)
        
        # 6. 执行发货计划
        for shipment in plan.shipments:
            self._execute_shipment(shipment)
        
        return plan
    
    def _execute_shipment(self, shipment):
        """执行单个发货计划"""
        delivery_data = {
            "report_date": self._day_to_date(shipment.ship_day),
            "target_factory_name": shipment.warehouse,
            "product_name": shipment.category,
            "quantity": shipment.weight,
            "vehicle_no": self._get_truck(shipment),
            "driver_name": self._get_driver(shipment),
            "driver_phone": self._get_driver_phone(shipment),
            "status": "待确认",
            "contract_no": shipment.cid
        }
        
        result = self.api.create_delivery(delivery_data)
        if result.get("success"):
            print(f"✅ 发货计划执行成功：{result['data']['delivery_id']}")
        else:
            print(f"❌ 发货计划执行失败：{result.get('error')}")
```

---

## 错误处理

### 常见错误码

| HTTP 状态码 | 说明 | 处理建议 |
|-----------|------|---------|
| 200 | 成功 | - |
| 400 | 请求参数错误 | 检查参数格式和必填字段 |
| 401 | 未授权 | 检查 Token 是否有效 |
| 403 | 禁止访问 | 检查用户权限 |
| 404 | 资源不存在 | 检查 ID 是否正确 |
| 409 | 冲突（重复创建） | 检查是否已存在 |
| 500 | 服务器内部错误 | 联系 PD 系统管理员 |

### 错误处理示例

```python
def safe_get_deliveries(api: PDAPIClient, **kwargs):
    """安全获取报货单（带重试）"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = api.get_deliveries(**kwargs)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed: {e}")
            if attempt == max_retries - 1:
                logger.error("Max retries reached, returning empty list")
                return []
    return []
```

---

## API 参考

### PDAPIClient 类方法

```python
class PDAPIClient:
    # 初始化
    __init__(base_url: str = "http://127.0.0.1:8007")
    set_token(token: str)
    health_check() -> bool
    
    # 磅单接口
    get_weighbills(...) -> List[WeighbillData]
    get_weighbills_by_delivery(delivery_id: int) -> List[WeighbillData]
    get_weighbill(weighbill_id: int) -> Optional[WeighbillData]
    get_weighbills_today(today: str, cid: str = None) -> List[WeighbillData]
    
    # 报货单接口
    get_deliveries(...) -> List[DeliveryData]
    get_delivery(delivery_id: int) -> Optional[DeliveryData]
    create_delivery(delivery: Dict) -> Dict
    update_delivery(delivery_id: int, updates: Dict) -> Dict
    
    # 合同接口
    get_contracts(...) -> List[ContractData]
    get_contract(contract_id: int) -> Optional[ContractData]
    
    # 结余接口
    get_balances(...) -> List[Dict]
    
    # 数据转换
    convert_to_pre_models_weighbill(pd_wb: WeighbillData) -> Weighbill
    convert_to_pre_models_delivery(pd_d: DeliveryData) -> Delivery
```

### 辅助函数

```python
# 获取已确认到货
get_confirmed_arrivals(api, today, cid) -> Dict[str, float]

# 过滤在途列表
filter_confirmed_arrivals(in_transit, confirmed) -> List[Dict]
```

---

## 测试

运行测试脚本:

```bash
cd /root/.openclaw/workspace/PreModels/v2
python3 api_client.py
```

预期输出:
```
============================================================
PD API 客户端测试
============================================================

1. 健康检查
   ✅ PD API 连接正常

2. 获取报货单
   报货单数量：0

3. 获取磅单
   磅单数量：0

4. 获取合同
   合同数量：0

5. 获取已确认到货
   今日 (2026-03-08) 无到货记录

============================================================
✅ 所有测试通过！
============================================================
```

---

## 更新日志

### v2.0 (2026-03-08)
- ✅ 完整实现所有核心接口
- ✅ 添加数据格式转换工具
- ✅ 添加错误处理和重试机制
- ✅ 完善文档和示例

### v1.0 (2026-03-08)
- ✅ 初始版本
- ✅ 实现基础接口调用

---

## 联系方式

有问题请联系项目负责人。

**文档维护**: 量化助手  
**最后更新**: 2026-03-08 13:45
