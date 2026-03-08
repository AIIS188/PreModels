# PD 项目部署与对接文档

**部署日期**: 2026-03-08  
**部署人员**: 量化助手  
**PD 仓库**: https://github.com/Jisalute/PD  
**原则**: 不修改 PD 仓库，只在本仓库做适配

---

## 📋 目录

- [部署概览](#部署概览)
- [PD 服务部署](#pd 服务部署)
- [API 接口说明](#api 接口说明)
- [数据格式对接](#数据格式对接)
- [使用示例](#使用示例)
- [故障排查](#故障排查)

---

## 部署概览

### 环境信息

| 项目 | 值 |
|------|-----|
| PD 版本 | FastAPI Starter v0.1.0 |
| Python 版本 | 3.10.12 |
| 数据库 | MySQL 8.0 |
| API 地址 | http://127.0.0.1:8007 |
| 部署路径 | `/root/.openclaw/workspace/pd-project` |

### 组件关系

```
┌─────────────────┐      ┌─────────────────┐
│  PreModels v2   │──────│   PD API        │
│  (优化系统)     │      │  (业务系统)     │
│                 │      │                 │
│  api_client.py  │──────│  /api/v1/...    │
└─────────────────┘      └─────────────────┘
         │                        │
         │                        │
         ▼                        ▼
┌─────────────────────────────────────────┐
│           MySQL Database                │
│  - pd_deliveries (报货单)               │
│  - pd_weighbills (磅单)                 │
│  - pd_contracts (合同)                  │
└─────────────────────────────────────────┘
```

---

## PD 服务部署

### 1. 克隆仓库

```bash
cd /root/.openclaw/workspace
git clone https://github.com/Jisalute/PD.git pd-project
```

### 2. 安装依赖

```bash
cd pd-project
python3 -m venv venv
./venv/bin/pip install fastapi uvicorn apscheduler pydantic PyJWT bcrypt \
    requests python-dotenv python-multipart Pillow PyMySQL \
    rapidocr-onnxruntime
```

### 3. 配置数据库

```bash
# 安装 MySQL
apt-get install -y mysql-server mysql-client

# 创建数据库
mysql -u root -e "CREATE DATABASE IF NOT EXISTS pd CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -u root -e "ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '123456'; FLUSH PRIVILEGES;"
```

### 4. 配置环境变量

创建 `.env` 文件：

```env
APP_NAME=PD API
JWT_SECRET=change-me
JWT_ALGORITHM=HS256
DATABASE_URL=mysql+pymysql://root:123456@127.0.0.1:3306/pd?charset=utf8mb4
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DATABASE=pd
PORT=8007
```

### 5. 初始化数据库

```bash
./venv/bin/python database_setup.py
```

### 6. 启动服务

```bash
# 后台运行
./venv/bin/python main.py > /tmp/pd.log 2>&1 &

# 验证
curl http://127.0.0.1:8007/healthz
# 返回：{"status":"ok"}
```

---

## API 接口说明

### 核心接口

| 接口 | 方法 | 用途 | PreModels 使用场景 |
|------|------|------|-------------------|
| `/api/v1/deliveries/` | GET | 查询报货单列表 | 获取在途报单 |
| `/api/v1/deliveries/json` | POST | 创建报货单 | 执行发货计划 |
| `/api/v1/weighbills/` | GET | 查询磅单列表 | 获取已确认到货 |
| `/api/v1/weighbills/create` | POST | 创建磅单 | (PD 内部使用) |
| `/healthz` | GET | 健康检查 | 服务状态监控 |

### 接口详情

#### GET /api/v1/deliveries/

**查询报货单列表**

参数:
- `exact_status`: 状态过滤（待确认/已确认/已完成）
- `exact_contract_no`: 合同编号过滤
- `exact_report_date`: 报货日期过滤
- `page`: 页码（默认 1）
- `page_size`: 每页数量（默认 20，最大 100）

返回:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "contract_no": "HT-2024-001",
      "report_date": "2026-03-08",
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
  "page_size": 20
}
```

#### POST /api/v1/deliveries/json

**创建报货单**

请求体:
```json
{
  "report_date": "2026-03-08",
  "target_factory_name": "R1",
  "product_name": "A",
  "quantity": 100.0,
  "vehicle_no": "京 A12345",
  "driver_name": "张三",
  "driver_phone": "13800138000",
  "status": "待确认"
}
```

返回:
```json
{
  "success": true,
  "message": "报货单创建成功",
  "data": {
    "delivery_id": 1
  }
}
```

#### GET /api/v1/weighbills/

**查询磅单列表（按报单分组）**

参数:
- `exact_weigh_date`: 磅单日期过滤
- `exact_contract_no`: 合同编号过滤
- `page`: 页码
- `page_size`: 每页数量

返回:
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
          "product_name": "A",
          "net_weight": 50.0,
          "weigh_date": "2026-03-08",
          "unit_price": 520.0,
          "total_amount": 26000.0
        }
      ]
    }
  ]
}
```

---

## 数据格式对接

### PreModels → PD 数据映射

| PreModels 字段 | PD 字段 | 说明 |
|---------------|---------|------|
| `cid` | `contract_no` | 合同编号 |
| `warehouse` | `target_factory_name` | 收货方/工厂 |
| `category` | `product_name` | 品种名称 |
| `tons` | `quantity` | 数量（吨） |
| `ship_day` | `report_date` | 发货日期 |
| `truck_id` | `vehicle_no` | 车牌号 |
| `driver_id` | `driver_name` | 司机姓名 |

### api_client.py 适配层

```python
# PreModels/v2/api_client.py

class PDAPIClient:
    """PD API 客户端 - 适配层"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8007"):
        self.base_url = base_url
    
    def get_deliveries(self, ...) -> List[Delivery]:
        """获取报货单（在途）"""
        ...
    
    def get_weighbills(self, ...) -> List[Weighbill]:
        """获取磅单（已确认到货）"""
        ...
    
    def create_delivery(self, delivery: dict) -> dict:
        """创建报货单（执行发货计划）"""
        ...
```

---

## 使用示例

### 1. 基本使用

```python
from api_client import PDAPIClient

# 初始化客户端
api = PDAPIClient(base_url="http://127.0.0.1:8007")

# 健康检查
if not api.health_check():
    print("PD API 不可用！")
    exit(1)

# 获取报货单
deliveries = api.get_deliveries(page=1, page_size=20)
print(f"报货单数量：{len(deliveries)}")

# 获取磅单
weighbills = api.get_weighbills(page=1, page_size=20)
print(f"磅单数量：{len(weighbills)}")
```

### 2. 获取已确认到货

```python
from api_client import get_confirmed_arrivals

# 获取今日到货
today = "2026-03-08"
arrivals = get_confirmed_arrivals(api, today=today)

# 按合同汇总
for contract_no, weight in arrivals.items():
    print(f"合同 {contract_no}: {weight}吨")
```

### 3. 创建报货单（执行发货计划）

```python
# 从优化模型获取发货计划
shipment_plan = {
    "warehouse": "W1",
    "cid": "C1",
    "category": "A",
    "tons": 99.1,
    "ship_day": "2026-03-08"
}

# 转换为 PD API 格式
delivery_data = {
    "report_date": shipment_plan["ship_day"],
    "target_factory_name": shipment_plan["warehouse"],
    "product_name": shipment_plan["category"],
    "quantity": shipment_plan["tons"],
    "vehicle_no": "京 A12345",  # 从车辆调度获取
    "driver_name": "张三",      # 从车辆调度获取
    "driver_phone": "13800138000",
    "status": "待确认"
}

# 创建报货单
result = api.create_delivery(delivery_data)
if result.get("success"):
    print(f"报货单创建成功：{result['data']['delivery_id']}")
else:
    print(f"创建失败：{result.get('error')}")
```

### 4. 集成到 rolling_optimizer.py

```python
# PreModels/v2/rolling_optimizer.py

from api_client import PDAPIClient, get_confirmed_arrivals

class RollingOptimizer:
    def __init__(self, api_base_url: str = "http://127.0.0.1:8007"):
        self.api = PDAPIClient(api_base_url)
    
    def run(self, today: int, H: int = 10):
        # 1. 从 PD API 获取最新磅单
        today_str = self._day_to_date(today)
        confirmed = get_confirmed_arrivals(self.api, today=today_str)
        
        # 2. 更新在途列表
        self.state.in_transit = filter_confirmed_arrivals(
            self.state.in_transit, confirmed
        )
        
        # 3. 运行优化模型
        plan = self.optimize()
        
        # 4. 执行发货计划（创建报货单）
        for shipment in plan.shipments:
            delivery_data = self._convert_to_delivery(shipment)
            self.api.create_delivery(delivery_data)
```

---

## 故障排查

### PD 服务无法启动

```bash
# 查看日志
cat /tmp/pd.log

# 常见错误：
# 1. 数据库连接失败 -> 检查 MySQL 是否运行
# 2. 端口被占用 -> 修改 .env 中的 PORT
# 3. 依赖缺失 -> 重新安装依赖
```

### API 返回 401/403

```bash
# 检查是否需要认证 Token
# 当前 PD API 未强制认证，如需认证请调用:
api.set_token("your_jwt_token")
```

### 数据格式不匹配

```python
# 启用调试日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 查看原始 API 响应
result = api._get("/api/v1/deliveries/")
print(json.dumps(result, indent=2))
```

### 数据库问题

```bash
# 检查数据库连接
mysql -u root -p123456 -e "USE pd; SHOW TABLES;"

# 重置数据库（谨慎操作！）
mysql -u root -p123456 -e "DROP DATABASE pd; CREATE DATABASE pd CHARACTER SET utf8mb4;"
./venv/bin/python database_setup.py
```

---

## 测试脚本

运行完整测试:

```bash
cd /root/.openclaw/workspace/PreModels/v2
python3 test_pd_api.py
```

预期输出:
```
✅ PD API 连接正常
报货单数量：0
磅单数量：0
今日 (2026-03-08) 无到货记录
✅ 所有测试通过！PD API 对接成功！
```

---

## 下一步工作

1. **数据填充**: 在 PD 系统中录入真实合同、报货单、磅单数据
2. **集成测试**: 将 api_client.py 集成到 rolling_optimizer.py
3. **自动化**: 配置定时任务，每日自动同步 PD 数据
4. **监控**: 添加 PD API 健康监控和告警

---

## 联系方式

有问题请联系项目负责人。

**部署完成时间**: 2026-03-08 13:30  
**部署状态**: ✅ 成功
