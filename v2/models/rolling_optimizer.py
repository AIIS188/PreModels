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

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.common_utils_v2 import Contract, default_global_delay_pmf
from models.complex_system_v2 import solve_lp_rolling_H_days
from core.api_client import PDAPIClient
from core.state_manager import StateManager, ModelState
from core.date_utils import DateUtils


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
        api_base_url: str = "http://8.136.35.215:8007",
    ):
        self.state_mgr = StateManager(state_dir)
        self.api = PDAPIClient(api_base_url)
    
    def run(self, today_date: Optional[str] = None, H: int = 10) -> Dict:
        """
        运行滚动优化
        
        参数:
            today_date: 今日（日期字符串）
            H: 规划窗口（天数）
        
        返回:
            优化结果
        
        使用示例:
            # 推荐：使用日期
            optimizer.run(today_date="2026-03-10", H=10)
            
        """

        if today_date:
            date_str = today_date
        else:
            date_str = DateUtils.today()
        
        
        self.state_mgr.log(f"开始滚动优化 (date={date_str}, H={H})")
        
        # 1. 加载合同
        contracts = self._load_contracts()
        
        # 2. 刷新状态（从 PD API 获取最新磅单并更新 state.json）
        #    此步骤会自动：
        #    - 初始化 state（如果不存在）
        #    - 获取今日磅单并累加 delivered_so_far
        #    - 获取已过磅车牌号并更新 in_transit_orders
        #    - 清理过期合同数据
        state = self.state_mgr.refresh_state(
            api=self.api,
            today=date_str,
            contracts=contracts,
            auto_init=True,
        )
        
        # 3. 准备模型输入
        cap_forecast = self._load_cap_forecast(date_str, H)  # 使用日期字符串
        weight_profile = self._load_weight_profile()
        delay_profile = self._load_delay_profile()
        
        # 4. 准备模型输入（仓库和品类从合同和产能预测中提取，不依赖在途报单）
        #    原因：当 in_transit_orders 为空时，需要确保模型仍有变量可求解
        warehouses_from_transit = list(set(o["warehouse"] for o in state.in_transit_orders)) if state.in_transit_orders else []
        categories_from_transit = list(set(o["category"] for o in state.in_transit_orders)) if state.in_transit_orders else []
        
        # 从产能预测中提取仓库和品类（更可靠）
        warehouses_from_cap = list(set(w for (w, k, t) in cap_forecast.keys()))
        categories_from_cap = list(set(k for (w, k, t) in cap_forecast.keys()))
        
        # 合并（优先使用产能预测的，因为在途可能为空）
        warehouses = list(set(warehouses_from_cap + warehouses_from_transit))
        categories = list(set(categories_from_cap + categories_from_transit))
        
        self.state_mgr.log(f"模型输入：warehouses={warehouses}, categories={categories}")
        
        # 5. 重新运行模型（注意：solve_lp_rolling_H_days 使用日期字符串）
        result = solve_lp_rolling_H_days(
            warehouses=warehouses,
            categories=categories,
            today=date_str,  # 使用日期字符串
            H=H,
            contracts=contracts,
            cap_forecast=cap_forecast,
            delivered_so_far=state.delivered_so_far,
            in_transit_orders=state.in_transit_orders,
            weight_profile=weight_profile,
            delay_profile=delay_profile,
            global_delay_pmf=default_global_delay_pmf(),
            x_prev=state.x_prev,  # 用于稳定性优化
            stability_weight=0.1,  # 启用稳定性
        )
        
        x_today, x_horizon, arrival_plan, trucks, mixing = result
        
        # 5. 保存状态和计划（传入 contracts 用于清理过期数据）
        self.state_mgr.update_state(
            delivered_so_far=state.delivered_so_far,
            in_transit_orders=state.in_transit_orders,
            x_prev=x_horizon,  # 保存窗口计划用于明日稳定性
            today=date_str,  # 使用日期字符串
            contracts=contracts,  # 传入合同列表用于清理过期数据
        )
        
        # 保存计划文件
        self._save_plan(x_today, trucks, mixing, date_str)
        
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
        
        重要说明:
        - 合同数据必须从 PD API 成功加载
        - API 失败时，使用缓存的合同数据（上次成功加载的结果）
        - 如果既无 API 响应也无缓存，则抛出异常终止运行
        - 不使用硬编码的默认合同（避免数据过期导致错误决策）
        
        返回:
            合同列表
        
        异常:
            RuntimeError: 当 API 和缓存都不可用时抛出
        """
        # 尝试从 PD API 加载
        try:
            pd_contracts = self.api.get_contracts(page=1, page_size=20)
            
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
    
    def _convert_pd_contracts(self, pd_contracts: List) -> List[Contract]:
        """
        将 PD 合同转换为内部 Contract 格式
        
        参数:
            pd_contracts: PD API 返回的合同列表
        
        返回:
            内部 Contract 格式列表
        """
        contracts = []
        for pc in pd_contracts:
            # 品类明细（价格锁定）
            products = pc.products if pc.products else []
            
            # 计算有效期（日期字符串格式）
            start_day = pc.contract_date
            end_day = pc.end_date
            
            contracts.append(Contract(
                cid=pc.contract_no,
                receiver=pc.smelter_company,
                Q=pc.total_quantity,
                start_day=start_day,
                end_day=end_day,
                products=products,
            ))
        
        return contracts
    
    def _cache_contracts(self, contracts: List[Contract]):
        """
        缓存合同数据到文件（用于 API 失败时的降级）
        
        参数:
            contracts: 要缓存的合同列表
        """
        import json
        cache_file = self.state_mgr.state_dir + "/contracts_cache.json"
        
        try:
            data = [
                {
                    "cid": c.cid,
                    "receiver": c.receiver,
                    "Q": c.Q,
                    "start_day": c.start_day,
                    "end_day": c.end_day,
                    "products": c.products,
                }
                for c in contracts
            ]
            
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.state_mgr.log(f"合同已缓存到 {cache_file}")
        except Exception as e:
            self.state_mgr.log(f"缓存合同失败：{e}", "WARNING")
    
    def _get_categories_from_contracts(self) -> List[str]:
        """
        从合同数据中提取所有品类
        
        返回:
            品类列表，如 ["A", "B"]
        
        实现逻辑:
        1. 优先从已加载的合同对象中获取
        2. 降级：从缓存的合同文件中获取
        3. 最后降级：返回空列表（调用方使用默认品类）
        """
        categories_set = set()
        
        # 方法 1: 尝试从当前状态获取合同（如果已加载）
        try:
            contracts = self._load_contracts()
            for contract in contracts:
                # 从 products 字段获取品类
                if hasattr(contract, 'products') and contract.products:
                    for product in contract.products:
                        if isinstance(product, dict) and 'product_name' in product:
                            categories_set.add(product['product_name'])
                        elif hasattr(product, 'product_name'):
                            categories_set.add(product.product_name)
                
                # 向后兼容：从 allowed_categories 获取
                if hasattr(contract, 'allowed_categories'):
                    categories_set.update(contract.allowed_categories)
            
            if categories_set:
                return sorted(list(categories_set))
        except Exception as e:
            self.state_mgr.log(f"从合同对象获取品类失败：{e}", "WARNING")
        
        # 方法 2: 从缓存文件获取
        try:
            cache_file = Path(self.state_mgr.state_dir) / "contracts_cache.json"
            if cache_file.exists():
                import json
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for contract in data:
                    if 'products' in contract and contract['products']:
                        for product in contract['products']:
                            if isinstance(product, dict) and 'product_name' in product:
                                categories_set.add(product['product_name'])
                
                if categories_set:
                    return sorted(list(categories_set))
        except Exception as e:
            self.state_mgr.log(f"从缓存文件获取品类失败：{e}", "WARNING")
        
        # 方法 3: 返回空列表（调用方使用默认品类）
        return []
    
    def _load_cached_contracts(self) -> Optional[List[Contract]]:
        """
        从缓存文件加载合同数据
        
        返回:
            合同列表，如果缓存不存在则返回 None
        """
        import json
        from pathlib import Path
        cache_file = Path(self.state_mgr.state_dir) / "contracts_cache.json"
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            contracts = [
                Contract(
                    cid=item["cid"],
                    receiver=item["receiver"],
                    Q=item["Q"],
                    start_day=item["start_day"],
                    end_day=item["end_day"],
                    products=item["products"],
                )
                for item in data
            ]
            
            return contracts
        except FileNotFoundError:
            return None
        except Exception as e:
            self.state_mgr.log(f"加载缓存合同失败：{e}", "WARNING")
            return None
    

    
    def _load_cap_forecast(self, today: str, H: int) -> Dict:
        """
        加载产能预测/仓库发货能力评估
        
        使用内部产能预测模型（不依赖外部 API）
        
        产能预测模型返回格式:
        {
            "仓库名": {
                "日期": {"品类 1": 重量， "品类 2": 重量},
                ...
            }
        }
        
        参数:
            today: 今日（日期字符串 "YYYY-MM-DD"）
            H: 规划窗口（天数）
        
        返回:
            cap_forecast[(warehouse, category, date)] = 最大发货量（吨）
        """
        # =====================================================
        # 调用内部产能预测模型
        # =====================================================
        try:
            from models.capacity_predictor import predict_capacity
            
            # 从合同数据中获取真实品类
            categories = self._get_categories_from_contracts()
            if not categories:
                categories = ["A", "B"]  # 降级：默认品类
                self.state_mgr.log(f"未找到合同品类，使用默认品类：{categories}", "WARNING")
            
            self.state_mgr.log(f"合同品类：{categories}")
            
            # 调用产能预测，传入品类列表
            capacity_data = predict_capacity(today=today, H=H, categories=categories)
            
            if capacity_data:
                self.state_mgr.log(f"从内部模型加载产能预测 (today={today}, H={H}, categories={categories})")
                return self._convert_capacity_format_new(capacity_data, today, categories)
        except Exception as e:
            self.state_mgr.log(f"内部产能模型调用失败：{e}，使用默认配置", "WARNING")
        
        # =====================================================
        # 降级：使用默认配置
        # =====================================================
        self.state_mgr.log(f"使用默认产能配置（H={H}）")
        
        # 默认配置：基于仓库和品类的发货能力
        default_capacity = {
            # (warehouse, category): daily_capacity (tons)
            ("W1", "A"): 220.0, ("W1", "B"): 60.0,
            ("W2", "A"): 80.0,  ("W2", "B"): 220.0,
            ("W3", "A"): 120.0, ("W3", "B"): 120.0,
        }
        
        # 生成 H 天的产能预测（使用日期字符串）
        cap_forecast = {}
        for d in range(H):
            date = DateUtils.add_days(today, d)
            for (w, k), base in default_capacity.items():
                # 使用简单波动因子
                factor = 1.05 if (d % 2 == 0) else 0.90
                cap_forecast[(w, k, date)] = float(base) * factor
        
        return cap_forecast
    
    def _load_capacity_from_api(self, today: int, H: int) -> Optional[Dict]:
        """
        从外部产能预测 API 加载产能数据
        
        API 返回格式:
        {
            "w1": [350, 360, 370, ...],  // w1 仓库未来 H 天的产能
            "w2": [200, 210, 220, ...],
            ...
        }
        
        参数:
            today: 今日（day）
            H: 规划窗口（天数）
        
        返回:
            cap_forecast[(warehouse, category, date)] = 最大发货量（吨）
            如果 API 不可用则返回 None
        """
        try:
            # 调用产能预测 API
            # TODO: 替换为真实 API 地址
            import requests
            
            # 示例 API 调用（预留接口）
            # response = requests.post(
            #     "http://capacity-predictor-api/predict",
            #     json={"today": today, "H": H},
            #     timeout=30
            # )
            # response.raise_for_status()
            # capacity_data = response.json()  # {"w1": [350, 360, ...], ...}
            
            # 临时：返回 None 表示使用默认配置
            # 实际对接时取消上面的注释
            return None
            
        except Exception as e:
            self.state_mgr.log(f"产能预测 API 调用失败：{e}", "ERROR")
            return None
    
    def _convert_capacity_format(self, capacity_data: Dict, today: int, H: int, 
                                  categories: List[str]) -> Dict:
        """
        将产能预测 API 的格式转换为模型需要的格式（旧版，兼容总产能格式）
        
        输入格式:
        {
            "w1": [350, 360, 370, ...],  // w1 仓库未来 H 天的总产能
            "w2": [200, 210, 220, ...],
            ...
        }
        
        输出格式:
        {
            ("w1", "A", today): 110.0,  // w1 仓库品类 A 在 today 的产能
            ("w1", "B", today): 240.0,  // w1 仓库品类 B 在 today 的产能
            ...
        }
        
        参数:
            capacity_data: API 返回的产能数据
            today: 今日（day）
            H: 规划窗口（天数）
            categories: 品类列表
        
        返回:
            cap_forecast[(warehouse, category, date)] = 最大发货量（吨）
        """
        cap_forecast = {}
        
        for warehouse, daily_caps in capacity_data.items():
            # 仓库名标准化（转为大写）
            wh = warehouse.upper()
            
            # 遍历 H 天
            for i, total_cap in enumerate(daily_caps[:H]):
                date = DateUtils.add_days(today, i)
                
                # 将总产能分配到各品类
                # 策略：按品类数量平均分配（可优化）
                num_categories = len(categories)
                if num_categories > 0:
                    cap_per_category = total_cap / num_categories
                    
                    for category in categories:
                        cap_forecast[(wh, category, date)] = cap_per_category
        
        return cap_forecast
    
    def _convert_capacity_format_new(self, capacity_data: Dict[str, Dict[str, Dict[str, float]]], 
                                      today: str, categories: List[str]) -> Dict:
        """
        将产能预测模型的新格式转换为模型需要的格式
        
        输入格式 (新):
        {
            "仓库名": {
                "日期": {"品类 1": 重量， "品类 2": 重量},
                ...
            }
        }
        
        示例:
        {
            "W1": {
                "2026-03-11": {"A": 220.0, "B": 60.0},
                "2026-03-12": {"A": 231.0, "B": 63.0},
            },
            "W2": {
                "2026-03-11": {"A": 80.0, "B": 220.0},
                ...
            }
        }
        
        输出格式:
        {
            ("W1", "A", "2026-03-11"): 220.0,
            ("W1", "B", "2026-03-11"): 60.0,
            ("W1", "A", "2026-03-12"): 231.0,
            ...
        }
        
        参数:
            capacity_data: 产能预测模型返回的数据（包含品类信息）
            today: 今日（日期字符串）
            categories: 品类列表
        
        返回:
            cap_forecast[(warehouse, category, date)] = 最大发货量（吨）
        """
        cap_forecast = {}
        
        for warehouse, dates in capacity_data.items():
            # 仓库名标准化（转为大写）
            wh = warehouse.upper()
            
            # 遍历每个日期
            for date_str, categories_cap in dates.items():
                # 遍历每个品类
                for category, capacity in categories_cap.items():
                    cap_forecast[(wh, category, date_str)] = float(capacity)
        
        return cap_forecast
    
    def _load_weight_profile(self) -> Dict:
        """
        加载估重画像
        
        临时配置：以 35 吨为基准，上下浮动（32-38 吨范围）
        后续从历史磅单数据学习各线路实际估重分布
        
        返回:
            weight_profile[(warehouse, receiver, category)] = (mu, hi)
            mu: 期望估重（吨）
            hi: 高估重（吨）
        """
        # 临时配置：35 吨上下浮动，范围 32-38 吨
        # 不同仓库线路略有差异，模拟真实场景
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
        today: str,
    ):
        """保存今日计划到文件"""
        from pathlib import Path
        # 使用日期字符串作为文件名
        plan_file = Path(self.state_mgr.state_dir) / f"plan_{today}.json"
        plan_file.parent.mkdir(parents=True, exist_ok=True)
        
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
    parser.add_argument("--today-date", type=str, default=None, help="今日 (日期字符串，推荐)")
    parser.add_argument("--H", type=int, default=10, help="规划窗口 (天)")
    
    args = parser.parse_args()
    
    optimizer = RollingOptimizer()
    
    if args.run:
        result = optimizer.run(today_date=args.today_date, H=args.H)
        print(json.dumps(result, indent=2, default=str))
    
    elif args.status:
        state = optimizer.state_mgr.load_state()
        if state:
            print(json.dumps({
                "last_run_date": state.last_run_date,
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
