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
        """
        加载合同列表（从 PD API 获取）
        
        已对接 PD API: GET /api/v1/contracts/
        
        返回:
            合同列表
        """
        try:
            pd_contracts = self.api.get_contracts(page=1, page_size=100)
            
            if not pd_contracts:
                self.state_mgr.log("警告：PD API 未返回合同数据，使用默认合同", "WARNING")
                return [
                    Contract(cid="C1", receiver="R1", Q=520.0, start_day=9, end_day=13, allowed_categories={"A", "B"}),
                    Contract(cid="C2", receiver="R2", Q=900.0, start_day=8, end_day=20, allowed_categories={"A", "B"}),
                ]
            
            contracts = []
            for pc in pd_contracts:
                # 从 PD 合同转换为内部 Contract 格式
                # 提取允许的品类（从产品明细）
                allowed_categories = set()
                for prod in pc.products:
                    allowed_categories.add(prod.get("product_name", ""))
                
                # 计算有效期（从日期转换为 day 编号）
                start_day = self._date_to_day(pc.contract_date)
                end_day = self._date_to_day(pc.end_date)
                
                contracts.append(Contract(
                    cid=pc.contract_no,
                    receiver=pc.smelter_company,
                    Q=pc.total_quantity,
                    start_day=start_day,
                    end_day=end_day,
                    allowed_categories=allowed_categories,
                ))
            
            self.state_mgr.log(f"从 PD API 加载 {len(contracts)} 个合同")
            return contracts
            
        except Exception as e:
            self.state_mgr.log(f"加载合同失败：{e}", "ERROR")
            # 降级使用默认合同
            return [
                Contract(cid="C1", receiver="R1", Q=520.0, start_day=9, end_day=13, allowed_categories={"A", "B"}),
                Contract(cid="C2", receiver="R2", Q=900.0, start_day=8, end_day=20, allowed_categories={"A", "B"}),
            ]
    
    def _date_to_day(self, date_str: str) -> int:
        """将日期字符串转换为 day 编号（从 2026-01-01 开始）"""
        from datetime import datetime
        if not date_str:
            return 0
        try:
            base = datetime(2026, 1, 1)
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return (dt - base).days + 1
        except Exception:
            return 0
    
    def _load_cap_forecast(self, today: int, H: int) -> Dict:
        """
        加载产能预测/仓库发货能力评估
        
        TODO: 后续由外部产能系统/仓库发货能力评估模块提供
        
        预留接口说明:
        - 需要对接仓库发货能力评估系统
        - 或者从产能预测 API 获取
        - 当前使用临时配置
        
        参数:
            today: 今日（day）
            H: 规划窗口（天数）
        
        返回:
            cap_forecast[(warehouse, category, day)] = 最大发货量（吨）
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
        # 后续会根据实际仓库发货能力评估结果动态调整
        default_capacity = {
            # (warehouse, category): daily_capacity (tons)
            ("W1", "A"): 220.0, ("W1", "B"): 60.0,
            ("W2", "A"): 80.0,  ("W2", "B"): 220.0,
            ("W3", "A"): 120.0, ("W3", "B"): 120.0,
        }
        
        self.state_mgr.log(f"使用默认产能配置（预留接口待对接）")
        
        # 生成 H 天的产能预测
        cap_forecast = {}
        for t in range(today, today + H):
            for (w, k), base in default_capacity.items():
                # 临时使用简单波动因子（后续替换为真实预测）
                factor = 1.05 if (t % 2 == 0) else 0.90
                cap_forecast[(w, k, t)] = float(base) * factor
        
        return cap_forecast
    
    def _load_weight_profile(self) -> Dict:
        """
        加载估重画像
        
        临时配置：以 35 吨为基准，上下浮动
        后续从历史磅单数据学习各线路实际估重分布
        
        返回:
            weight_profile[(warehouse, receiver, category)] = (mu, hi)
            mu: 期望估重（吨）
            hi: 高估重（吨）
        """
        # 临时配置：以 35 吨为基准，各线路略有差异
        # 后续会根据实际历史数据学习调整
        base_mu = 35.0  # 基准估重
        base_hi = 35.0  # 基准高估重
        
        return {
            # W1 仓库线路
            ("W1", "R1", "A"): (base_mu, base_hi),
            ("W1", "R1", "B"): (base_mu, base_hi),
            ("W1", "R2", "A"): (base_mu, base_hi),
            ("W1", "R2", "B"): (base_mu, base_hi),
            # W2 仓库线路
            ("W2", "R1", "A"): (base_mu, base_hi),
            ("W2", "R1", "B"): (base_mu, base_hi),
            ("W2", "R2", "A"): (base_mu, base_hi),
            ("W2", "R2", "B"): (base_mu, base_hi),
            # W3 仓库线路
            ("W3", "R1", "A"): (base_mu, base_hi),
            ("W3", "R1", "B"): (base_mu, base_hi),
            ("W3", "R2", "A"): (base_mu, base_hi),
            ("W3", "R2", "B"): (base_mu, base_hi),
        }
    
    def _load_delay_profile(self) -> Dict:
        """
        加载延迟分布
        
        临时配置：
        - 3% 当日到（delay=0）
        - 97% 隔日到（delay=1）
        - 2% 2 日到（delay=2）
        
        后续从历史磅单数据学习各线路实际延迟分布
        
        返回:
            delay_profile[(warehouse, receiver)] = {delay_days: probability}
        """
        # 统一延迟分布配置
        # 0: 当日到，1: 隔日到，2: 2 日到
        delay_dist = {0: 0.03, 1: 0.97, 2: 0.02}
        
        # 所有线路使用相同的延迟分布
        return {
            # W1 仓库线路
            ("W1", "R1"): delay_dist,
            ("W1", "R2"): delay_dist,
            # W2 仓库线路
            ("W2", "R1"): delay_dist,
            ("W2", "R2"): delay_dist,
            # W3 仓库线路
            ("W3", "R1"): delay_dist,
            ("W3", "R2"): delay_dist,
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
