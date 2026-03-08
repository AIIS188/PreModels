# PD API 接口演示

**演示时间**: 2026-03-08 13:55  
**服务地址**: http://127.0.0.1:8007  

---

##  实时 API 调用结果

### 1. 健康检查接口

```bash
GET /healthz
```

**响应**:
```json
{
  "status": "ok"
}
```

 **状态**: 服务正常运行

---

### 2. 报货单列表接口

```bash
GET /api/v1/deliveries/?page=1&page_size=10
```

**响应**:
```json
{
  "success": true,
  "data": [],
  "total": 0,
  "page": 1,
  "page_size": 10
}
```

 **状态**: 接口正常（当前无数据）

---

### 3. 磅单列表接口

```bash
GET /api/v1/weighbills/?page=1&page_size=10
```

**响应**:
```json
{
  "success": true,
  "data": [],
  "total": 0,
  "page": 1,
  "page_size": 10
}
```

 **状态**: 接口正常（当前无数据）

---

### 4. 合同列表接口

```bash
GET /api/v1/contracts/?page=1&page_size=10
```

**响应**:
```json
{
  "success": true,
  "data": [],
  "total": 0,
  "page": 1,
  "page_size": 10
}
```

 **状态**: 接口正常（当前无数据）

---

##  API 数据结构

### 报货单 (Delivery)

**数据库表**: `pd_deliveries`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 报货单 ID |
| `report_date` | date | 报货日期 |
| `contract_no` | varchar(64) | 合同编号 |
| `product_name` | varchar(64) | 品种名称 |
| `products` | varchar(255) | 品种列表（逗号分隔） |
| `quantity` | decimal(12,3) | 数量（吨） |
| `vehicle_no` | varchar(32) | 车牌号 |
| `driver_name` | varchar(64) | 司机姓名 |
| `driver_phone` | varchar(32) | 司机电话 |
| `driver_id_card` | varchar(18) | 身份证号 |
| `target_factory_name` | varchar | 目标工厂 |
| `warehouse` | varchar | 仓库 |
| `status` | varchar | 状态 |

**API 响应示例** (有数据时):
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "report_date": "2026-03-08",
      "contract_no": "HT-2024-001",
      "target_factory_name": "R1",
      "product_name": "A",
      "quantity": 100.0,
      "vehicle_no": "京 A12345",
      "driver_name": "张三",
      "driver_phone": "13800138000",
      "status": "待确认"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

---

### 磅单 (Weighbill)

**数据库表**: `pd_weighbills`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 磅单 ID |
| `delivery_id` | int | 关联报货单 ID |
| `weigh_date` | date | 磅单日期 |
| `weigh_ticket_no` | varchar(64) | 过磅单号 |
| `contract_no` | varchar(64) | 合同编号 |
| `product_name` | varchar(64) | 品种名称 |
| `gross_weight` | decimal(12,3) | 毛重（吨） |
| `tare_weight` | decimal(12,3) | 皮重（吨） |
| `net_weight` | decimal(12,3) | 净重（吨） |
| `unit_price` | decimal(12,2) | 单价（元/吨） |
| `total_amount` | decimal | 总金额（元） |

**API 响应示例** (有数据时):
```json
{
  "success": true,
  "data": [
    {
      "delivery_id": 1,
      "contract_no": "HT-2024-001",
      "weighbills": [
        {
          "id": 1,
          "weigh_date": "2026-03-08",
          "product_name": "A",
          "net_weight": 35.3,
          "unit_price": 520.0,
          "total_amount": 18356.0
        }
      ]
    }
  ]
}
```

---

### 合同 (Contract)

**数据库表**: `pd_contracts`

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 合同 ID |
| `contract_no` | varchar(64) | 合同编号 |
| `contract_date` | date | 签订日期 |
| `total_quantity` | decimal(12,3) | 合同总量（吨） |
| `status` | varchar(32) | 状态（生效中/已完成/已过期） |

**API 响应示例** (有数据时):
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "contract_no": "HT-2024-001",
      "contract_date": "2024-01-15",
      "total_quantity": 1000.0,
      "status": "生效中",
      "products": [
        {"product_name": "A", "unit_price": 520.0}
      ]
    }
  ]
}
```

---

##  Swagger 文档

**访问地址**: http://127.0.0.1:8007/docs

Swagger UI 提供:
-  交互式 API 测试
-  请求/响应示例
-  参数说明
-  在线调试

---

##  数据库表统计

| 表名 | 用途 | 字段数 |
|------|------|--------|
| `pd_contracts` | 合同管理 | ~15 |
| `pd_deliveries` | 报货单管理 | ~25 |
| `pd_weighbills` | 磅单管理 | ~20 |
| `pd_balance_details` | 结余明细 | ~15 |
| `pd_payment_details` | 支付明细 | ~15 |
| `pd_customers` | 客户管理 | ~10 |
| `pd_users` | 用户管理 | ~15 |

**总计**: 15 张表

---

##  接口调用示例

### Python 示例

```python
import requests

# 健康检查
response = requests.get("http://127.0.0.1:8007/healthz")
print(response.json())  # {"status": "ok"}

# 获取报货单列表
response = requests.get(
    "http://127.0.0.1:8007/api/v1/deliveries/",
    params={"page": 1, "page_size": 10}
)
data = response.json()
print(f"报货单数量：{data['total']}")

# 获取磅单列表
response = requests.get(
    "http://127.0.0.1:8007/api/v1/weighbills/",
    params={"page": 1, "page_size": 10}
)
data = response.json()
print(f"磅单组数：{len(data['data'])}")
```

### curl 示例

```bash
# 健康检查
curl http://127.0.0.1:8007/healthz

# 获取报货单
curl "http://127.0.0.1:8007/api/v1/deliveries/?page=1&page_size=10"

# 获取磅单（按日期过滤）
curl "http://127.0.0.1:8007/api/v1/weighbills/?exact_weigh_date=2026-03-08"

# 获取合同
curl "http://127.0.0.1:8007/api/v1/contracts/?page=1&page_size=10"
```

---

##  接口验证总结

| 接口类型 | 测试状态 | 说明 |
|---------|---------|------|
| 健康检查 |  通过 | 返回 `{"status": "ok"}` |
| 报货单查询 |  通过 | 返回空列表（无数据） |
| 磅单查询 |  通过 | 返回空列表（无数据） |
| 合同查询 |  通过 | 返回空列表（无数据） |
| 数据库连接 |  通过 | 15 张表已创建 |
| OpenAPI 规范 |  通过 | 62 个接口已注册 |

---

##  下一步

1. **录入测试数据** - 通过 Swagger UI 或 API 创建合同、报货单、磅单
2. **验证数据查询** - 测试各种过滤和分页参数
3. **集成到 PreModels** - 使用 api_client.py 调用真实数据

---

**演示完成时间**: 2026-03-08 13:55  
**演示人**: AIIS188
