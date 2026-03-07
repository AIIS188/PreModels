"""
rolling_optimizer.py

滚动优化器

功能：
1. 整合 API 客户端和状态管理器
2. 实现滚动优化流程
3. 支持每日多次运行

使用方式：
    python rolling_optimizer.py --run          # 运行优化
    python rolling_optimizer.py --status       # 查看状态
    python rolling_optimizer.py --reset        # 重置状态
"""

from __future__ import annotations
from typing import Dict, List, Optional
import argparse
import json
import sys

from common_utils_v2 import Contract, default_global_delay_pmf
from complex_system_v2 import solve_lp_rolling_H_days
from api_client import PDAPIClient, get_confirmed_arrivals, filter_confirmed_arrivals
from state_manager import StateManager, ModelState


# =========================
# 滚动优化器
# =========================

class RollingOptimizer:
    """
    滚动优化器
    
    流程：
    1. 加载状态
    2. 获取最新磅单（真实到货）
    3. 更新已到货量和在途列表
    4. 重新运行模型
    5. 保存状态和计划
    """
    
    def __init__(
        self,
        state_dir: str = "./state",
        api_base_url: str = "http://localhost:8000",
    ):
        self.state_mgr = StateManager(state_dir)
        self.api = PDAPIClient(api_base_url)
    
    def run(self, today: int, H: int = 10) -> Dict:
        """
        运行滚动优化
        
        参数:
            today: 今日（day）
            H: 规划窗口（天数）
        
        返回:
            优化结果
        """
        self.state_mgr.log(f"开始滚动优化 (day={today})")
        
        # 1. 加载状态
        state = self.state_mgr.load_state()
        if state is None:
            self.state_mgr.log("状态不存在，需要先初始化", "ERROR")
            raise RuntimeError("状态不存在，请先调用 initialize_state()")
        
        # 2. 获取最新磅单（真实到货）
        today_arrivals = get_confirmed_arrivals(self.api, today)
        self.state_mgr.log(f"获取今日到货：{today_arrivals}")
        
        # 3. 更新已到货量和在途列表
        updated_delivered = state.delivered_so_far.copy()
        for cid, tons in today_arrivals.items():
            updated_delivered[cid] = updated_delivered.get(cid, 0.0) + tons
        
        updated_in_transit = filter_confirmed_arrivals(
            state.in_transit_orders,
            today_arrivals,
        )
        self.state_mgr.log(f"更新后在途：{len(updated_in_transit)} 单")
        
        # 4. 准备模型输入
        contracts = self._load_contracts()
        cap_forecast = self._load_cap_forecast(today, H)
        weight_profile = self._load_weight_profile()
        delay_profile = self._load_delay_profile()
        
        # 5. 重新运行模型
        result = solve_lp_rolling_H_days(
            warehouses=list(set(o["warehouse"] for o in updated_in_transit)),
            categories=list(set(o["category"] for o in updated_in_transit)),
            today=today,
            H=H,
            contracts=contracts,
            cap_forecast=cap_forecast,
            delivered_so_far=updated_delivered,
            in_transit_orders=updated_in_transit,
            weight_profile=weight_profile,
            delay_profile=delay_profile,
            global_delay_pmf=default_global_delay_pmf(),
            x_prev=state.x_prev,  # 用于稳定性优化
            stability_weight=0.1,  # 启用稳定性
        )
        
        x_today, x_horizon, arrival_plan, trucks, mixing = result
        
        # 6. 保存状态和计划
        self.state_mgr.update_state(
            delivered_so_far=updated_delivered,
            in_transit_orders=updated_in_transit,
            x_prev=x_horizon,  # 保存窗口计划用于明日稳定性
            today=today,
        )
        
        self._save_plan(x_today, trucks, mixing, today)
        
        self.state_mgr.log(f"优化完成，今日计划：{len(x_today)} 条记录")
        
        # 转换为可序列化格式
        return {
            "x_today": {f"{k[0]}_{k[1]}_{k[2]}_{k[3]}": v for k, v in x_today.items()},
            "trucks": {f"{k[0]}_{k[1]}_{k[2]}": v for k, v in trucks.items()},
            "mixing": {f"{k[0]}_{k[1]}_{k[2]}": v for k, v in mixing.items()},
            "arrival_plan": {f"{k[0]}_{k[1]}": v for k, v in arrival_plan.items()},
        }
    
    def _load_contracts(self) -> List[Contract]:
        """加载合同列表（从文件或 API）"""
        # TODO: 从 PD API 获取
        # 临时硬编码
        return [
            Contract(cid="C1", receiver="R1", Q=520.0, start_day=9, end_day=13, allowed_categories={"A", "B"}),
            Contract(cid="C2", receiver="R2", Q=900.0, start_day=8, end_day=20, allowed_categories={"A", "B"}),
        ]
    
    def _load_cap_forecast(self, today: int, H: int) -> Dict:
        """加载产能预测（从文件或 API）"""
        # TODO: 从产能系统获取
        # 临时硬编码
        cap_today = {
            ("W1", "A"): 220.0, ("W1", "B"): 60.0,
            ("W2", "A"): 80.0,  ("W2", "B"): 220.0,
            ("W3", "A"): 120.0, ("W3", "B"): 120.0,
        }
        
        cap_forecast = {}
        for t in range(today, today + H):
            for (w, k), base in cap_today.items():
                factor = 1.05 if (t % 2 == 0) else 0.90
                cap_forecast[(w, k, t)] = float(base) * factor
        
        return cap_forecast
    
    def _load_weight_profile(self) -> Dict:
        """加载估重画像（从历史数据学习）"""
        # TODO: 从历史磅单数据学习
        return {
            ("W1", "R1", "A"): (32.0, 35.0), ("W1", "R1", "B"): (30.0, 35.0),
            ("W2", "R1", "A"): (31.0, 35.0), ("W2", "R1", "B"): (33.0, 35.0),
            ("W3", "R1", "A"): (29.0, 35.0), ("W3", "R1", "B"): (28.0, 35.0),
            ("W1", "R2", "A"): (33.0, 35.0), ("W1", "R2", "B"): (32.0, 35.0),
            ("W2", "R2", "A"): (30.0, 35.0), ("W2", "R2", "B"): (31.0, 35.0),
            ("W3", "R2", "A"): (28.0, 35.0), ("W3", "R2", "B"): (29.0, 35.0),
        }
    
    def _load_delay_profile(self) -> Dict:
        """加载延迟分布（从历史数据学习）"""
        # TODO: 从历史磅单数据学习
        return {
            ("W1", "R1"): {0: 0.03, 1: 0.90, 2: 0.04, 3: 0.03},
            ("W2", "R1"): {0: 0.02, 1: 0.92, 2: 0.04, 3: 0.02},
            ("W3", "R1"): {0: 0.05, 1: 0.85, 2: 0.06, 3: 0.04},
            ("W1", "R2"): {0: 0.02, 1: 0.90, 2: 0.05, 3: 0.03},
            ("W2", "R2"): {0: 0.03, 1: 0.88, 2: 0.06, 3: 0.03},
            ("W3", "R2"): {0: 0.04, 1: 0.86, 2: 0.06, 3: 0.04},
        }
    
    def _save_plan(
        self,
        x_today: Dict,
        trucks: Dict,
        mixing: Dict,
        today: int,
    ):
        """保存今日计划到文件"""
        plan_file = f"./state/plan_day{today}.json"
        
        # 转换为可序列化格式
        plan_data = {
            "today": today,
            "shipments": [
                {
                    "warehouse": w,
                    "cid": cid,
                    "category": k,
                    "tons": tons,
                }
                for (w, cid, k, t), tons in x_today.items()
            ],
            "trucks": [
                {
                    "warehouse": w,
                    "cid": cid,
                    "trucks": count,
                    "mixing": mixing.get((w, cid, t), {}),
                }
                for (w, cid, t), count in trucks.items()
            ],
        }
        
        with open(plan_file, 'w', encoding='utf-8') as f:
            json.dump(plan_data, f, indent=2, ensure_ascii=False)


# =========================
# 命令行接口
# =========================

def main():
    parser = argparse.ArgumentParser(description="滚动优化器")
    parser.add_argument("--run", action="store_true", help="运行优化")
    parser.add_argument("--status", action="store_true", help="查看状态")
    parser.add_argument("--reset", action="store_true", help="重置状态")
    parser.add_argument("--today", type=int, default=10, help="今日 (day)")
    parser.add_argument("--H", type=int, default=10, help="规划窗口 (天)")
    
    args = parser.parse_args()
    
    optimizer = RollingOptimizer()
    
    if args.run:
        result = optimizer.run(today=args.today, H=args.H)
        print(json.dumps(result, indent=2, default=str))
    
    elif args.status:
        state = optimizer.state_mgr.load_state()
        if state:
            print(json.dumps({
                "last_run_day": state.last_run_day,
                "last_updated": state.last_updated,
                "delivered_so_far": state.delivered_so_far,
                "in_transit_count": len(state.in_transit_orders),
            }, indent=2))
        else:
            print("状态不存在")
    
    elif args.reset:
        import shutil
        if input("确认重置状态？(y/N): ").lower() == 'y':
            shutil.rmtree("./state", ignore_errors=True)
            print("状态已重置")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
