"""
PreModels API Server

提供发货计划查询 API 供前端使用

功能：
1. 获取今日发货计划
2. 获取多日发货计划
3. 获取合同完成进度
4. 获取统计信息
5. 手动触发优化运行

使用方式：
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8001
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import json
import sys

# 添加 v2 目录到路径
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "v2"))

# 设置 state 目录为工作目录
STATE_DIR = BASE_DIR / "v2" / "state"

from rolling_optimizer import RollingOptimizer
from state_manager import StateManager


# =========================
# 数据模型
# =========================

class ShipmentPlan(BaseModel):
    """单条发货计划"""
    warehouse: str = Field(..., description="仓库")
    cid: str = Field(..., description="合同号")
    category: str = Field(..., description="品类")
    tons: float = Field(..., description="吨数")
    trucks: int = Field(0, description="车数")
    receiver: Optional[str] = Field(None, description="收货方")


class DailyPlan(BaseModel):
    """单日发货计划"""
    date: str = Field(..., description="日期描述")
    day: int = Field(..., description="Day 编号")
    total_tons: float = Field(..., description="总吨数")
    total_trucks: int = Field(..., description="总车数")
    avg_load: float = Field(..., description="平均载重（吨/车）")
    shipments: List[ShipmentPlan] = Field(..., description="发货明细")


class ContractProgress(BaseModel):
    """合同完成进度"""
    cid: str = Field(..., description="合同号")
    receiver: str = Field(..., description="收货方")
    total_quantity: float = Field(..., description="合同总量（吨）")
    completed: float = Field(..., description="已完成（吨）")
    progress: float = Field(..., description="完成率（%）")
    remaining: float = Field(..., description="剩余量（吨）")
    status: str = Field(..., description="状态")


class Statistics(BaseModel):
    """统计信息"""
    total_tons: float = Field(..., description="总发货量")
    total_trucks: int = Field(..., description="总车数")
    avg_load: float = Field(..., description="平均载重")
    daily_avg: float = Field(..., description="日均发货")


class OptimizeRequest(BaseModel):
    """优化请求"""
    today: int = Field(..., description="今日 (Day 编号)")
    H: int = Field(10, description="规划窗口（天）")


# =========================
# FastAPI 应用
# =========================

app = FastAPI(
    title="PreModels API",
    description="采购物流调度优化系统 API",
    version="2.2",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# 辅助函数
# =========================

def load_contracts():
    """加载合同信息"""
    cache_file = STATE_DIR / "contracts_cache.json"
    if not cache_file.exists():
        return {}
    
    with open(cache_file, 'r', encoding='utf-8') as f:
        contracts = json.load(f)
        return {c['cid']: c for c in contracts}


def load_plan(day: int):
    """加载指定日的计划"""
    plan_file = STATE_DIR / f"plan_day{day}.json"
    if not plan_file.exists():
        return None
    
    with open(plan_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def calculate_contract_progress(contracts: Dict, shipments: List[Dict]) -> Dict[str, float]:
    """计算合同完成进度"""
    progress = {cid: 0.0 for cid in contracts.keys()}
    
    for shipment in shipments:
        cid = shipment.get('cid')
        if cid in progress:
            progress[cid] += shipment.get('tons', 0)
    
    return progress


def day_to_date(day: int) -> str:
    """将 Day 编号转换为日期字符串"""
    base = datetime(2026, 1, 1)
    from datetime import timedelta
    target = base + timedelta(days=day-1)
    return target.strftime("%Y-%m-%d")


# =========================
# API 接口
# =========================

@app.get("/")
def root():
    """根路径"""
    return {
        "service": "PreModels API",
        "version": "2.2",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "ok"}


@app.get("/api/v1/plan/today", response_model=DailyPlan)
def get_today_plan(today: Optional[int] = None):
    """
    获取今日发货计划
    
    参数:
        today: 今日 (Day 编号)，不传则使用最新状态中的日期
    """
    # 如果没有指定 today，从状态文件读取
    if today is None:
        state_file = STATE_DIR / "state.json"
        if state_file.exists():
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
                today = state.get('last_run_day', 10)
        else:
            today = 10
    
    # 加载计划
    plan = load_plan(today)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Day {today} 的计划不存在")
    
    # 加载合同信息
    contracts = load_contracts()
    
    # 构建发货明细
    shipments = []
    for shipment in plan.get('shipments', []):
        cid = shipment['cid']
        contract = contracts.get(cid, {})
        
        # 查找对应的车数
        truck_count = 0
        for truck in plan.get('trucks', []):
            if truck['warehouse'] == shipment['warehouse'] and truck['cid'] == cid:
                truck_count = truck['trucks']
                break
        
        shipments.append(ShipmentPlan(
            warehouse=shipment['warehouse'],
            cid=cid,
            category=shipment['category'],
            tons=shipment['tons'],
            trucks=truck_count,
            receiver=contract.get('receiver'),
        ))
    
    # 计算总计
    total_tons = sum(s.tons for s in shipments)
    total_trucks = sum(s.trucks for s in shipments)
    avg_load = total_tons / total_trucks if total_trucks > 0 else 0
    
    return DailyPlan(
        date=f"Day {today} ({day_to_date(today)})",
        day=today,
        total_tons=total_tons,
        total_trucks=total_trucks,
        avg_load=avg_load,
        shipments=shipments,
    )


@app.get("/api/v1/plan/{day}", response_model=DailyPlan)
def get_plan_by_day(day: int):
    """
    获取指定日的发货计划
    
    参数:
        day: Day 编号
    """
    plan = load_plan(day)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Day {day} 的计划不存在")
    
    # 加载合同信息
    contracts = load_contracts()
    
    # 构建发货明细
    shipments = []
    for shipment in plan.get('shipments', []):
        cid = shipment['cid']
        contract = contracts.get(cid, {})
        
        # 查找对应的车数
        truck_count = 0
        for truck in plan.get('trucks', []):
            if truck['warehouse'] == shipment['warehouse'] and truck['cid'] == cid:
                truck_count = truck['trucks']
                break
        
        shipments.append(ShipmentPlan(
            warehouse=shipment['warehouse'],
            cid=cid,
            category=shipment['category'],
            tons=shipment['tons'],
            trucks=truck_count,
            receiver=contract.get('receiver'),
        ))
    
    total_tons = sum(s.tons for s in shipments)
    total_trucks = sum(s.trucks for s in shipments)
    avg_load = total_tons / total_trucks if total_trucks > 0 else 0
    
    return DailyPlan(
        date=f"Day {day} ({day_to_date(day)})",
        day=day,
        total_tons=total_tons,
        total_trucks=total_trucks,
        avg_load=avg_load,
        shipments=shipments,
    )


@app.get("/api/v1/plan/range")
def get_plan_range(
    start_day: int = Query(..., description="起始日"),
    end_day: int = Query(..., description="结束日")
):
    """
    获取指定日期范围的发货计划
    
    参数:
        start_day: 起始日
        end_day: 结束日
    """
    plans = []
    for day in range(start_day, end_day + 1):
        plan = load_plan(day)
        if plan:
            plans.append({
                'day': day,
                'date': day_to_date(day),
                'total_tons': sum(s['tons'] for s in plan.get('shipments', [])),
                'shipments_count': len(plan.get('shipments', [])),
            })
    
    return {
        'start_day': start_day,
        'end_day': end_day,
        'plans': plans,
    }


@app.get("/api/v1/contracts/progress", response_model=List[ContractProgress])
def get_contract_progress():
    """
    获取合同完成进度
    
    扫描所有历史计划，计算累计完成量
    """
    contracts = load_contracts()
    if not contracts:
        raise HTTPException(status_code=404, detail="合同数据不存在")
    
    # 扫描所有计划文件
    progress = {cid: 0.0 for cid in contracts.keys()}
    
    for plan_file in STATE_DIR.glob("plan_day*.json"):
        with open(plan_file, 'r', encoding='utf-8') as f:
            plan = json.load(f)
            for shipment in plan.get('shipments', []):
                cid = shipment['cid']
                if cid in progress:
                    progress[cid] += shipment['tons']
    
    # 构建返回结果
    result = []
    for cid, completed in progress.items():
        contract = contracts[cid]
        total = contract['Q']
        pct = (completed / total) * 100 if total > 0 else 0
        remaining = total - completed
        
        # 判断状态
        if pct >= 100:
            status = "已完成"
        elif pct >= 90:
            status = "即将完成"
        elif pct >= 50:
            status = "进行中"
        else:
            status = "刚开始"
        
        result.append(ContractProgress(
            cid=cid,
            receiver=contract.get('receiver', ''),
            total_quantity=total,
            completed=completed,
            progress=pct,
            remaining=remaining,
            status=status,
        ))
    
    return result


@app.get("/api/v1/statistics")
def get_statistics():
    """
    获取统计信息
    
    扫描所有历史计划，计算总体统计
    """
    total_tons = 0
    total_trucks = 0
    days_count = 0
    daily_totals = []
    
    for plan_file in STATE_DIR.glob("plan_day*.json"):
        with open(plan_file, 'r', encoding='utf-8') as f:
            plan = json.load(f)
            day_tons = sum(s['tons'] for s in plan.get('shipments', []))
            day_trucks = sum(t['trucks'] for t in plan.get('trucks', []))
            
            total_tons += day_tons
            total_trucks += day_trucks
            daily_totals.append(day_tons)
            days_count += 1
    
    avg_load = total_tons / total_trucks if total_trucks > 0 else 0
    daily_avg = total_tons / days_count if days_count > 0 else 0
    
    return Statistics(
        total_tons=total_tons,
        total_trucks=total_trucks,
        avg_load=avg_load,
        daily_avg=daily_avg,
    )


@app.post("/api/v1/optimize")
def run_optimize(request: OptimizeRequest):
    """
    手动触发优化运行
    
    参数:
        today: 今日 (Day 编号)
        H: 规划窗口（天）
    
    返回:
        优化结果
    """
    try:
        optimizer = RollingOptimizer(
            state_dir="./state",
            api_base_url="http://127.0.0.1:8007",
        )
        
        result = optimizer.run(today=request.today, H=request.H)
        
        return {
            "success": True,
            "message": "优化成功",
            "data": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"优化失败：{str(e)}")


@app.get("/api/v1/status")
def get_status():
    """
    获取系统状态
    
    返回当前状态文件信息
    """
    state_file = STATE_DIR / "state.json"
    if not state_file.exists():
        return {
            "status": "no_state",
            "message": "状态文件不存在，需要先运行优化"
        }
    
    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)
    
    return {
        "status": "ok",
        "last_run_day": state.get('last_run_day'),
        "last_updated": state.get('last_updated'),
        "delivered_so_far": state.get('delivered_so_far', {}),
        "in_transit_count": len(state.get('in_transit_orders', [])),
    }


# =========================
# 启动
# =========================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
