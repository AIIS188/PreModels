# PreModels API 文档

**版本**: v2.2  
**服务地址**: http://127.0.0.1:8001  
**Swagger 文档**: http://127.0.0.1:8001/docs  
**ReDoc 文档**: http://127.0.0.1:8001/redoc  

---

## 快速开始

### 启动服务

```bash
cd /root/.openclaw/workspace/PreModels/api
python3 -m uvicorn main:app --host 0.0.0.0 --port 8001
```

### 后台运行

```bash
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8001 > /tmp/api.log 2>&1 &
```

### 检查服务状态

```bash
curl http://127.0.0.1:8001/health
# 返回：{"status": "ok"}
```

---

## API 接口

### 1. 获取今日发货计划

**接口**: `GET /api/v1/plan/today`

**参数**:
- `today` (可选): 今日 (Day 编号)，不传则使用最新状态

**响应示例**:
```json
{
  "date": "Day 10 (2026-01-10)",
  "day": 10,
  "total_tons": 98.03,
  "total_trucks": 4,
  "avg_load": 24.51,
  "shipments": [
    {
      "warehouse": "W1",
      "cid": "HT-2026-001",
      "category": "A",
      "tons": 37.00,
      "trucks": 2,
      "receiver": "R1"
    },
    {
      "warehouse": "W1",
      "cid": "HT-2026-002",
      "category": "A",
      "tons": 61.03,
      "trucks": 2,
      "receiver": "R2"
    }
  ]
}
```

**使用示例**:
```bash
# 获取今日计划
curl http://127.0.0.1:8001/api/v1/plan/today

# 获取指定日计划
curl "http://127.0.0.1:8001/api/v1/plan/today?today=10"
```

---

### 2. 获取指定日发货计划

**接口**: `GET /api/v1/plan/{day}`

**参数**:
- `day`: Day 编号

**响应示例**: 同上

**使用示例**:
```bash
curl http://127.0.0.1:8001/api/v1/plan/10
```

---

### 3. 获取日期范围计划

**接口**: `GET /api/v1/plan/range`

**参数**:
- `start_day`: 起始日
- `end_day`: 结束日

**响应示例**:
```json
{
  "start_day": 10,
  "end_day": 15,
  "plans": [
    {
      "day": 10,
      "date": "2026-01-10",
      "total_tons": 98.03,
      "shipments_count": 2
    },
    ...
  ]
}
```

**使用示例**:
```bash
curl "http://127.0.0.1:8001/api/v1/plan/range?start_day=10&end_day=15"
```

---

### 4. 获取合同完成进度

**接口**: `GET /api/v1/contracts/progress`

**参数**: 无

**响应示例**:
```json
[
  {
    "cid": "HT-2026-001",
    "receiver": "R1",
    "total_quantity": 520.0,
    "completed": 555.70,
    "progress": 106.87,
    "remaining": -35.70,
    "status": "已完成"
  },
  {
    "cid": "HT-2026-002",
    "receiver": "R2",
    "total_quantity": 900.0,
    "completed": 916.03,
    "progress": 101.78,
    "remaining": -16.03,
    "status": "已完成"
  }
]
```

**使用示例**:
```bash
curl http://127.0.0.1:8001/api/v1/contracts/progress
```

---

### 5. 获取统计信息

**接口**: `GET /api/v1/statistics`

**参数**: 无

**响应示例**:
```json
{
  "total_tons": 1471.73,
  "total_trucks": 60,
  "avg_load": 24.53,
  "daily_avg": 98.12
}
```

**使用示例**:
```bash
curl http://127.0.0.1:8001/api/v1/statistics
```

---

### 6. 获取系统状态

**接口**: `GET /api/v1/status`

**参数**: 无

**响应示例**:
```json
{
  "status": "ok",
  "last_run_day": 24,
  "last_updated": "2026-03-08T15:01:18.403914",
  "delivered_so_far": {
    "HT-2026-001": 0.0,
    "HT-2026-002": 0.0
  },
  "in_transit_count": 2
}
```

**使用示例**:
```bash
curl http://127.0.0.1:8001/api/v1/status
```

---

### 7. 手动触发优化

**接口**: `POST /api/v1/optimize`

**请求体**:
```json
{
  "today": 10,
  "H": 10
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "优化成功",
  "data": {
    "x_today": {...},
    "trucks": {...},
    ...
  }
}
```

**使用示例**:
```bash
curl -X POST http://127.0.0.1:8001/api/v1/optimize \
  -H "Content-Type: application/json" \
  -d '{"today": 10, "H": 10}'
```

---

### 8. 健康检查

**接口**: `GET /health`

**响应**:
```json
{"status": "ok"}
```

**使用示例**:
```bash
curl http://127.0.0.1:8001/health
```

---

### 9. 根路径

**接口**: `GET /`

**响应**:
```json
{
  "service": "PreModels API",
  "version": "2.2",
  "status": "running",
  "docs": "/docs"
}
```

**使用示例**:
```bash
curl http://127.0.0.1:8001/
```

---

## 前端集成示例

### JavaScript/TypeScript

```typescript
// 获取今日发货计划
async function getTodayPlan() {
  const response = await fetch('http://127.0.0.1:8001/api/v1/plan/today');
  const data = await response.json();
  return data;
}

// 获取合同进度
async function getContractProgress() {
  const response = await fetch('http://127.0.0.1:8001/api/v1/contracts/progress');
  const data = await response.json();
  return data;
}

// 获取统计信息
async function getStatistics() {
  const response = await fetch('http://127.0.0.1:8001/api/v1/statistics');
  const data = await response.json();
  return data;
}

// 使用示例
const plan = await getTodayPlan();
console.log(`今日计划：${plan.total_tons} 吨，${plan.total_trucks} 车`);

plan.shipments.forEach(shipment => {
  console.log(`${shipment.warehouse} -> ${shipment.cid}: ${shipment.tons} 吨`);
});
```

### Vue.js

```vue
<template>
  <div>
    <h2>今日发货计划</h2>
    <div v-if="plan">
      <p>总吨数：{{ plan.total_tons }} 吨</p>
      <p>总车数：{{ plan.total_trucks }} 车</p>
      <p>平均载重：{{ plan.avg_load }} 吨/车</p>
      
      <table>
        <tr>
          <th>仓库</th>
          <th>合同号</th>
          <th>品类</th>
          <th>吨数</th>
          <th>车数</th>
          <th>收货方</th>
        </tr>
        <tr v-for="shipment in plan.shipments" :key="shipment.cid">
          <td>{{ shipment.warehouse }}</td>
          <td>{{ shipment.cid }}</td>
          <td>{{ shipment.category }}</td>
          <td>{{ shipment.tons }}</td>
          <td>{{ shipment.trucks }}</td>
          <td>{{ shipment.receiver }}</td>
        </tr>
      </table>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      plan: null
    }
  },
  async mounted() {
    const response = await fetch('http://127.0.0.1:8001/api/v1/plan/today');
    this.plan = await response.json();
  }
}
</script>
```

### React

```jsx
import React, { useState, useEffect } from 'react';

function ShippingPlan() {
  const [plan, setPlan] = useState(null);
  
  useEffect(() => {
    fetch('http://127.0.0.1:8001/api/v1/plan/today')
      .then(res => res.json())
      .then(data => setPlan(data));
  }, []);
  
  if (!plan) return <div>加载中...</div>;
  
  return (
    <div>
      <h2>今日发货计划</h2>
      <p>总吨数：{plan.total_tons} 吨</p>
      <p>总车数：{plan.total_trucks} 车</p>
      
      <table>
        <thead>
          <tr>
            <th>仓库</th>
            <th>合同号</th>
            <th>品类</th>
            <th>吨数</th>
            <th>收货方</th>
          </tr>
        </thead>
        <tbody>
          {plan.shipments.map((s, i) => (
            <tr key={i}>
              <td>{s.warehouse}</td>
              <td>{s.cid}</td>
              <td>{s.category}</td>
              <td>{s.tons}</td>
              <td>{s.receiver}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

---

## 数据模型

### ShipmentPlan (发货计划)

| 字段 | 类型 | 说明 |
|------|------|------|
| warehouse | string | 仓库 |
| cid | string | 合同号 |
| category | string | 品类 |
| tons | float | 吨数 |
| trucks | int | 车数 |
| receiver | string | 收货方 |

### DailyPlan (单日计划)

| 字段 | 类型 | 说明 |
|------|------|------|
| date | string | 日期描述 |
| day | int | Day 编号 |
| total_tons | float | 总吨数 |
| total_trucks | int | 总车数 |
| avg_load | float | 平均载重 |
| shipments | array | 发货明细 |

### ContractProgress (合同进度)

| 字段 | 类型 | 说明 |
|------|------|------|
| cid | string | 合同号 |
| receiver | string | 收货方 |
| total_quantity | float | 合同总量 |
| completed | float | 已完成 |
| progress | float | 完成率 (%) |
| remaining | float | 剩余量 |
| status | string | 状态 |

### Statistics (统计信息)

| 字段 | 类型 | 说明 |
|------|------|------|
| total_tons | float | 总发货量 |
| total_trucks | int | 总车数 |
| avg_load | float | 平均载重 |
| daily_avg | float | 日均发货 |

---

## 错误处理

### 404 Not Found

```json
{
  "detail": "Day 10 的计划不存在"
}
```

### 500 Internal Server Error

```json
{
  "detail": "优化失败：错误信息"
}
```

---

## 部署

### 开发环境

```bash
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

### 生产环境

```bash
# 使用 gunicorn + uvicorn workers
pip install gunicorn

gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8001
```

### Systemd 服务

创建 `/etc/systemd/system/premodels-api.service`:

```ini
[Unit]
Description=PreModels API Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/root/.openclaw/workspace/PreModels/api
ExecStart=/usr/bin/python3 -m uvicorn main:app --host 0.0.0.0 --port 8001
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务:

```bash
sudo systemctl daemon-reload
sudo systemctl enable premodels-api
sudo systemctl start premodels-api
```

---

## Swagger UI

访问 http://127.0.0.1:8001/docs 查看交互式 API 文档。

支持：
- 在线测试所有接口
- 查看请求/响应格式
- 下载 OpenAPI 规范

---

## ReDoc

访问 http://127.0.0.1:8001/redoc 查看更美观的 API 文档。

---

**文档维护**: AIIS188  
**最后更新**: 2026-03-08 15:50
