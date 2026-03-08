# 产能预测模型集成文档

**版本**: v1.0  
**日期**: 2026-03-08  
**维护**: AIIS188  

---

## 一、产能预测数据格式

### API 返回格式

```json
{
  "w1": [350, 360, 370, 380, 390, ...],
  "w2": [200, 210, 220, 230, 240, ...],
  "w3": [150, 160, 170, 180, 190, ...]
}
```

**说明**:
- **键**: 仓库名（w1, w2, w3...）
- **值**: 数组，表示未来每日的总产能（吨）
- **数组索引**: 
  - 索引 0 = today（今日）
  - 索引 1 = today+1（明日）
  - 索引 i = today+i

**示例**:
```json
{
  "w1": [350, 360, 370],  // w1: 今日 350 吨，明日 360 吨，后日 370 吨
  "w2": [200, 210, 220],
  "w3": [150, 160, 170]
}
```

---

## 二、数据格式转换

### 输入格式（产能预测 API）

```json
{
  "w1": [350, 360, 370, ...],
  "w2": [200, 210, 220, ...]
}
```

### 输出格式（模型需要）

```python
{
    ("W1", "A", 10): 175.0,  # w1 仓库品类 A 在 Day10 的产能
    ("W1", "B", 10): 175.0,  # w1 仓库品类 B 在 Day10 的产能
    ("W1", "A", 11): 180.0,
    ("W1", "B", 11): 180.0,
    ("W2", "A", 10): 100.0,
    ("W2", "B", 10): 100.0,
    ...
}
```

### 转换逻辑

```python
def _convert_capacity_format(capacity_data, today, H, categories):
    """
    将产能预测 API 格式转换为模型格式
    
    策略：按品类数量平均分配总产能
    """
    cap_forecast = {}
    
    for warehouse, daily_caps in capacity_data.items():
        wh = warehouse.upper()  # 转为大写
        
        for i, total_cap in enumerate(daily_caps[:H]):
            day = today + i
            
            # 平均分配到各品类
            num_categories = len(categories)
            cap_per_category = total_cap / num_categories
            
            for category in categories:
                cap_forecast[(wh, category, day)] = cap_per_category
    
    return cap_forecast
```

---

## 三、集成方式

### 方式 1: HTTP API 调用（推荐）

**架构**:
```
滚动优化器 → HTTP POST → 产能预测 API → JSON 响应 → 格式转换 → LP 模型
```

**实现代码**:

```python
# 在 rolling_optimizer.py 中

def _load_capacity_from_api(self, today: int, H: int) -> Optional[Dict]:
    """从外部产能预测 API 加载产能数据"""
    try:
        import requests
        
        # 调用产能预测 API
        response = requests.post(
            "http://capacity-predictor:8002/predict",
            json={
                "today": today,
                "H": H,
            },
            timeout=30
        )
        response.raise_for_status()
        
        # 获取产能预测数据
        capacity_data = response.json()
        # 格式：{"w1": [350, 360, ...], "w2": [...], ...}
        
        # 获取品类列表
        categories = self._get_categories()  # 从合同或配置获取
        
        # 转换为模型需要的格式
        return self._convert_capacity_format(
            capacity_data, today, H, categories
        )
        
    except Exception as e:
        self.state_mgr.log(f"产能预测 API 调用失败：{e}", "ERROR")
        return None  # 返回 None 使用默认配置
```

**产能预测 API 实现示例** (FastAPI):

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class PredictRequest(BaseModel):
    today: int
    H: int

@app.post("/predict")
async def predict(request: PredictRequest):
    # 调用产能预测模型
    prediction = capacity_model.predict(
        today=request.today,
        horizon=request.H
    )
    
    # 返回格式: {"w1": [350, 360, ...], ...}
    return prediction
```

---

### 方式 2: 文件共享

**架构**:
```
产能预测模型 → JSON 文件 ← 滚动优化器
```

**实现代码**:

```python
# 在 rolling_optimizer.py 中

def _load_capacity_from_file(self, file_path: str, H: int) -> Optional[Dict]:
    """从 JSON 文件读取产能预测"""
    import json
    from pathlib import Path
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            capacity_data = json.load(f)
        
        # 获取品类列表
        categories = self._get_categories()
        
        # 转换格式
        return self._convert_capacity_format(
            capacity_data, self.today, H, categories
        )
        
    except Exception as e:
        self.state_mgr.log(f"读取产能文件失败：{e}", "ERROR")
        return None
```

**文件格式示例** (`capacity_forecast.json`):

```json
{
  "w1": [350, 360, 370, 380, 390, 400, 350, 360, 370, 380],
  "w2": [200, 210, 220, 230, 240, 250, 200, 210, 220, 230],
  "w3": [150, 160, 170, 180, 190, 200, 150, 160, 170, 180]
}
```

---

### 方式 3: 数据库共享

**架构**:
```
产能预测模型 → 数据库 ← 滚动优化器
```

**数据库表结构**:

```sql
CREATE TABLE capacity_forecast (
    id INT PRIMARY KEY AUTO_INCREMENT,
    warehouse VARCHAR(10) NOT NULL,  -- 仓库名
    forecast_date INT NOT NULL,      -- 预测日期 (day 编号)
    total_capacity DECIMAL(10,2) NOT NULL,  -- 总产能
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_warehouse_date (warehouse, forecast_date)
);
```

**实现代码**:

```python
# 在 rolling_optimizer.py 中

def _load_capacity_from_db(self, today: int, H: int) -> Optional[Dict]:
    """从数据库读取产能预测"""
    import pymysql
    
    try:
        conn = pymysql.connect(
            host='localhost',
            user='root',
            password='password',
            database='capacity_db'
        )
        
        with conn.cursor() as cursor:
            # 查询未来 H 天的产能
            sql = """
                SELECT warehouse, forecast_date, total_capacity
                FROM capacity_forecast
                WHERE forecast_date BETWEEN %s AND %s
                ORDER BY warehouse, forecast_date
            """
            cursor.execute(sql, (today, today + H - 1))
            rows = cursor.fetchall()
        
        # 转换为字典格式
        capacity_data = {}
        for warehouse, date, cap in rows:
            if warehouse not in capacity_data:
                capacity_data[warehouse] = {}
            capacity_data[warehouse][date] = cap
        
        # 转换为数组格式
        result = {}
        for warehouse, date_caps in capacity_data.items():
            caps = [date_caps.get(today + i, 0) for i in range(H)]
            result[warehouse] = caps
        
        # 获取品类列表并转换格式
        categories = self._get_categories()
        return self._convert_capacity_format(result, today, H, categories)
        
    except Exception as e:
        self.state_mgr.log(f"数据库读取失败：{e}", "ERROR")
        return None
```

---

## 四、完整集成示例

### 修改 rolling_optimizer.py

```python
class RollingOptimizer:
    def __init__(
        self,
        state_dir: str = "./state",
        api_base_url: str = "http://127.0.0.1:8007",
        capacity_api_url: str = "http://capacity-predictor:8002",  # 新增
    ):
        self.state_mgr = StateManager(state_dir)
        self.api = PDAPIClient(api_base_url)
        self.capacity_api_url = capacity_api_url  # 新增
    
    def _load_cap_forecast(self, today: int, H: int) -> Dict:
        """加载产能预测"""
        
        # 1. 尝试从外部 API 获取
        capacity = self._load_capacity_from_api(today, H)
        if capacity:
            self.state_mgr.log(f"从外部 API 加载产能预测 (H={H})")
            return capacity
        
        # 2. 降级到默认配置
        self.state_mgr.log(f"使用默认产能配置 (H={H})")
        return self._get_default_capacity(today, H)
    
    def _load_capacity_from_api(self, today: int, H: int) -> Optional[Dict]:
        """从外部产能预测 API 加载"""
        if not self.capacity_api_url:
            return None
        
        try:
            import requests
            
            response = requests.post(
                f"{self.capacity_api_url}/predict",
                json={"today": today, "H": H},
                timeout=30
            )
            response.raise_for_status()
            
            capacity_data = response.json()
            
            # 获取品类列表
            categories = self._get_categories()
            
            # 转换格式
            return self._convert_capacity_format(
                capacity_data, today, H, categories
            )
            
        except Exception as e:
            self.state_mgr.log(f"产能 API 失败：{e}", "WARNING")
            return None
    
    def _get_categories(self) -> List[str]:
        """获取品类列表"""
        # 从合同或配置获取
        return ["A", "B"]
    
    def _convert_capacity_format(self, capacity_data: Dict, today: int, 
                                  H: int, categories: List[str]) -> Dict:
        """转换产能格式"""
        cap_forecast = {}
        
        for warehouse, daily_caps in capacity_data.items():
            wh = warehouse.upper()
            
            for i, total_cap in enumerate(daily_caps[:H]):
                day = today + i
                
                # 平均分配到各品类
                num_categories = len(categories)
                cap_per_category = total_cap / num_categories
                
                for category in categories:
                    cap_forecast[(wh, category, day)] = cap_per_category
        
        return cap_forecast
```

---

## 五、测试验证

### 测试脚本

```bash
cd /root/.openclaw/workspace/PreModels/v2
python3 capacity_api_example.py
```

### 预期输出

```
================================================================================
产能预测 API 对接示例
================================================================================

1. 调用外部产能预测 API
--------------------------------------------------------------------------------
获取到产能预测数据:
  w1: [350, 360, 370, 380, 390, ...]
  w2: [200, 210, 220, 230, 240, ...]
  w3: [150, 160, 170, 180, 190, ...]

2. 从文件读取产能预测
--------------------------------------------------------------------------------
创建示例文件：capacity_forecast_example.json
内容：{...}

3. 格式转换示例
--------------------------------------------------------------------------------
输入格式 (API):
  {"w1": [350, 360, 370], "w2": [200, 210, 220]}

输出格式 (模型):
  ("W1", "A", 10): 175.0 吨
  ("W1", "B", 10): 175.0 吨
  ("W1", "A", 11): 180.0 吨
  ("W1", "B", 11): 180.0 吨
  ("W2", "A", 10): 100.0 吨
  ("W2", "B", 10): 100.0 吨
  ...

================================================================================
示例完成
================================================================================
```

---

## 六、配置说明

### 环境变量

```bash
# 产能预测 API 地址
export CAPACITY_API_URL="http://capacity-predictor:8002"

# 或者在代码中配置
capacity_api_url = "http://capacity-predictor:8002"
```

### 配置文件

```json
// config.json
{
  "capacity": {
    "api_url": "http://capacity-predictor:8002",
    "timeout": 30,
    "fallback": "default"  // default|file|db
  }
}
```

---

## 七、降级策略

### 多级降级

```
1. 外部 API (优先)
   ↓ 失败
2. 本地文件
   ↓ 失败
3. 默认配置 (保底)
```

### 实现

```python
def _load_cap_forecast(self, today: int, H: int) -> Dict:
    # 1. 外部 API
    capacity = self._load_capacity_from_api(today, H)
    if capacity:
        return capacity
    
    # 2. 本地文件
    capacity = self._load_capacity_from_file("./capacity.json", H)
    if capacity:
        return capacity
    
    # 3. 默认配置
    return self._get_default_capacity(today, H)
```

---

## 八、监控与日志

### 日志记录

```python
self.state_mgr.log(f"加载产能预测：H={H}, 来源=API")
self.state_mgr.log(f"加载产能预测：H={H}, 来源=文件（降级）")
self.state_mgr.log(f"加载产能预测：H={H}, 来源=默认（降级）")
```

### 监控指标

- API 调用成功率
- API 响应时间
- 降级触发次数
- 产能预测准确率

---

## 九、下一步工作

1. **实现产能预测 API**
   - 开发产能预测模型
   - 部署 FastAPI 服务
   - 提供预测接口

2. **集成测试**
   - 单元测试
   - 集成测试
   - 性能测试

3. **生产部署**
   - 配置管理
   - 监控告警
   - 日志收集

---

**文档维护**: AIIS188  
**最后更新**: 2026-03-08 17:00
