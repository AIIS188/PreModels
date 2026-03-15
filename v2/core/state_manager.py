"""
state_manager.py

状态管理器

功能：
1. 持久化模型状态（已到货、在途、历史计划）
2. 支持滚动优化时恢复状态
3. 记录执行日志
"""

from __future__ import annotations
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import json
import os
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.date_utils import DateUtils


# =========================
# 数据结构
# =========================

@dataclass
class ModelState:
    """模型状态"""
    # 已到货量（从磅单确认）
    delivered_so_far: Dict[str, float]  # {cid: tons}
    
    # 在途报单
    in_transit_orders: List[Dict]  # [{order_id, cid, warehouse, category, weight, ship_day, ...}]
    
    # 历史计划（用于稳定性优化）
    x_prev: Optional[Dict]  # {(w, cid, k, t): tons}
    
    # 最后更新时间
    last_updated: str  # ISO 格式时间戳
    
    # 最后运行日期 (日期字符串)
    last_run_date: Optional[str]  # "2026-03-10"
    


# =========================
# 状态管理器
# =========================

class StateManager:
    """
    状态管理器
    
    文件存储：
    - state.json: 当前状态
    - history/: 历史状态（每日快照）
    - logs/: 执行日志
    """
    
    def __init__(self, state_dir: str = "./state"):
        self.state_dir = state_dir
        self.state_file = os.path.join(state_dir, "state.json")
        self.history_dir = os.path.join(state_dir, "history")
        self.logs_dir = os.path.join(state_dir, "logs")
        
        # 确保目录存在
        os.makedirs(self.history_dir, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)
    
    def load_state(self) -> Optional[ModelState]:
        """
        加载当前状态
        
        返回:
            ModelState 或 None（如果不存在）
        """
        if not os.path.exists(self.state_file):
            return None
        
        with open(self.state_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return ModelState(**data)
    
    def save_state(self, state: ModelState):
        """
        保存当前状态
        
        参数:
            state: 模型状态
        """
        # 转换为字典，处理 tuple 键
        state_dict = asdict(state)
        
        # 将 tuple 键转换为字符串
        if state_dict.get('x_prev'):
            state_dict['x_prev'] = {
                f"{k[0]}_{k[1]}_{k[2]}_{k[3]}" if isinstance(k, tuple) else k: v
                for k, v in state_dict['x_prev'].items()
            }
        
        # 保存到 state.json
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(state_dict, f, indent=2, ensure_ascii=False)
        
        # 保存到历史快照（按日期）
        if state.last_run_date is not None:
            # 从日期提取 day 编号用于文件名（仅用于文件命名）
            today_day = DateUtils.to_day_number(state.last_run_date)
            history_file = os.path.join(
                self.history_dir,
                f"state_day{today_day}.json"
            )
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(state_dict, f, indent=2, ensure_ascii=False)
    
    def log(self, message: str, level: str = "INFO"):
        """
        记录执行日志
        
        参数:
            message: 日志内容
            level: 日志级别（INFO/WARNING/ERROR）
        """
        timestamp = datetime.now().isoformat()
        log_line = f"[{timestamp}] [{level}] {message}\n"
        
        # 写入今日日志
        today = datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(self.logs_dir, f"{today}.log")
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(log_line)
    
    def initialize_state(
        self,
        delivered_so_far: Dict[str, float] = {},
        in_transit_orders: List[Dict] = [],
        today: Optional[str] = None,
    ) -> ModelState:
        """
        初始化状态（首次运行）
        
        参数:
            delivered_so_far: 已到货量
            in_transit_orders: 在途报单
            today: 今日日期（可选，默认今天）
        
        返回:
            初始化的 ModelState
        """
        from core.date_utils import DateUtils
        
        if today is None:
            today = DateUtils.today()

        
        state = ModelState(
            delivered_so_far=delivered_so_far,
            in_transit_orders=in_transit_orders,
            x_prev=None,
            last_updated=datetime.now().isoformat(),
            last_run_date=today,
        )
        self.save_state(state)
        self.log(f"状态初始化完成 (date={today})")
        return state
    
    def update_state(
        self,
        delivered_so_far: Dict[str, float],
        in_transit_orders: List[Dict],
        x_prev: Optional[Dict],
        today: str,  # 改为日期字符串
        contracts: Optional[List] = None,  # 新增：合同列表（用于清理过期数据）
    ) -> ModelState:
        """
        更新状态（滚动优化）
        
        参数:
            delivered_so_far: 更新后的已到货量
            in_transit_orders: 更新后的在途报单
            x_prev: 今日计划（用于明日稳定性优化）
            today: 今日（日期字符串，如 "2026-03-10"）
            contracts: 合同列表（用于清理过期合同数据，可选）
        
        返回:
            更新后的 ModelState
        
        清理逻辑：
        - end_day >= today 的合同视为有效（end_day 当天不算过期）
        - end_day < today 的合同视为过期，从 delivered_so_far 和 in_transit_orders 中移除
        """
        # 清理过期合同数据（如果提供了合同列表）
        if contracts is not None:
            # 构建有效合同 ID 集合（end_day >= today 视为有效）
            # diff_days(today, end_day) >= 0 表示 end_day >= today
            valid_cid_set = {
                c.cid for c in contracts
                if DateUtils.diff_days(today, c.end_day) >= 0
            }
            
            # 清理 delivered_so_far：只保留有效合同的数据
            cleaned_delivered = {
                cid: tons
                for cid, tons in delivered_so_far.items()
                if cid in valid_cid_set
            }
            
            # 清理 in_transit_orders：只保留有效合同的报单
            cleaned_in_transit = [
                order for order in in_transit_orders
                if order.get('cid') in valid_cid_set
            ]
            
            # 记录清理日志
            removed_delivered = len(delivered_so_far) - len(cleaned_delivered)
            removed_orders = len(in_transit_orders) - len(cleaned_in_transit)
            if removed_delivered > 0 or removed_orders > 0:
                self.log(f"清理过期合同数据：delivered_so_far 移除{removed_delivered}条，in_transit 移除{removed_orders}条", "INFO")
        else:
            # 未提供合同列表，使用原始数据（向后兼容）
            cleaned_delivered = delivered_so_far
            cleaned_in_transit = in_transit_orders
        
        state = ModelState(
            delivered_so_far=cleaned_delivered,
            in_transit_orders=cleaned_in_transit,
            x_prev=x_prev,
            last_updated=datetime.now().isoformat(),
            last_run_date=today,  # 日期字符串
        )
        self.save_state(state)
        self.log(f"状态更新完成 (date={today})")
        return state

        
    def get_x_prev_for_date(self, target_date: str) -> Optional[Dict]:
        """
        获取指定日期的历史计划（用于稳定性优化）
        
        参数:
            target_date: 目标日期（字符串，如 "2026-03-10"）
        
        返回:
            历史计划或 None
        """
        # 从历史快照中查找（使用 day 编号的文件名）
        target_day = DateUtils.to_day_number(target_date)
        history_file = os.path.join(
            self.history_dir,
            f"state_day{target_day - 1}.json"  # 前一天的计划
        )
        
        if not os.path.exists(history_file):
            return None
        
        with open(history_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data.get("x_prev")
    
    def get_x_prev_for_day(self, target_day: int) -> Optional[Dict]:
        """
        获取指定 day 编号的历史计划（兼容旧版）
        
        参数:
            target_day: 目标 day 编号
        
        返回:
            历史计划或 None
        """
        # 从历史快照中查找
        history_file = os.path.join(
            self.history_dir,
            f"state_day{target_day - 1}.json"  # 前一天的计划
        )
        
        if not os.path.exists(history_file):
            return None
        
        with open(history_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data.get("x_prev")
    
    def refresh_state(
        self,
        api,  # PDAPIClient 实例
        today: str,
        contracts: Optional[List] = None,
        auto_init: bool = True,
    ) -> ModelState:
        """
        刷新状态（从 PD API 获取最新磅单并更新）
        
        功能：
        1. 加载现有状态（如果不存在且 auto_init=True 则初始化）
        2. 从 PD API 获取今日磅单（已确认到货）
        3. 更新 delivered_so_far（累加今日到货）
        4. 从 PD API 获取已过磅车牌号
        5. 更新 in_transit_orders（移除已过磅报单）
        6. 调用 update_state() 保存（含清理过期合同）
        
        参数:
            api: PDAPIClient 实例（用于获取磅单和车牌号）
            today: 今日日期（字符串，如 "2026-03-10"）
            contracts: 合同列表（用于清理过期合同和初始化新合同，可选）
            auto_init: 是否自动初始化（如果 state 不存在）
        
        返回:
            更新后的 ModelState
        
        说明：
        - 此方法负责数据获取和处理
        - 保存逻辑委托给 update_state()（避免重复）
        - 如果 contracts 为 None，则跳过清理和初始化逻辑
        """
        from core.api_client import get_confirmed_arrivals, get_weighed_truck_ids, filter_confirmed_arrivals, get_in_transit_orders
        
        self.log(f"开始刷新状态 (date={today})")
        
        # 1. 加载现有状态（或初始化）
        state = self.load_state()
        if state is None:
            if auto_init:
                self.log("未找到现有状态，初始化新状态", "WARNING")
                state = self.initialize_state(today=today)
            else:
                self.log("无法刷新状态：当前状态不存在且 auto_init=False", "ERROR")
                raise ValueError("当前状态不存在")
        
        # 2. 如果提供了合同列表，初始化新合同的 delivered_so_far
        if contracts is not None:
            for contract in contracts:
                if contract.cid not in state.delivered_so_far:
                    state.delivered_so_far[contract.cid] = 0.0
                    self.log(f"初始化新合同 {contract.cid} 的 delivered_so_far=0.0")
        
        # 3. 获取今日磅单（已确认到货）并累加
        today_arrivals = get_confirmed_arrivals(api, today)
        self.log(f"获取今日 ({today}) 到货：{today_arrivals}")
        
        for cid, tons in today_arrivals.items():
            old_val = state.delivered_so_far.get(cid, 0.0)
            state.delivered_so_far[cid] = old_val + tons
            if tons > 0:
                self.log(f"合同 {cid} 累加今日到货 {tons} 吨 (累计：{state.delivered_so_far[cid]})")
        
        # 4. 获取所有在途报单（从 PD API 获取全部待确认状态的报货单）
        fresh_in_transit = get_in_transit_orders(api, today)
        self.log(f"从 PD API 获取在途报单：{len(fresh_in_transit)} 单")
        
        # 5. 获取今日已过磅车牌号
        weighed_trucks = get_weighed_truck_ids(api, today)
        self.log(f"今日已过磅车辆：{len(weighed_trucks)} 辆")
        
        # 6. 从在途列表中移除已过磅的报单
        filtered_in_transit = filter_confirmed_arrivals(
            fresh_in_transit,
            weighed_trucks,
        )
        removed_count = len(fresh_in_transit) - len(filtered_in_transit)
        if removed_count > 0:
            self.log(f"移除已过磅报单：{removed_count} 单")
        self.log(f"过滤后在途：{len(filtered_in_transit)} 单")
        
        # 7. 更新在途列表（以 PD API 为准，完全替换）
        #    策略：PD API 是权威数据源，包含所有待确认状态的报货单
        state.in_transit_orders = filtered_in_transit
        self.log(f"更新后在途：{len(state.in_transit_orders)} 单")
        
        # 8. 调用 update_state() 保存（含清理过期合同）
        updated_state = self.update_state(
            delivered_so_far=state.delivered_so_far,
            in_transit_orders=state.in_transit_orders,
            x_prev=state.x_prev,
            today=today,
            contracts=contracts,
        )
        
        self.log(f"状态刷新完成 (date={today}, delivered={len(updated_state.delivered_so_far)}, in_transit={len(updated_state.in_transit_orders)})")
        
        return updated_state


# =========================
# 使用示例
# =========================

if __name__ == "__main__":
    # 示例：初始化状态
    state_mgr = StateManager()
    
    # 首次运行
    state = state_mgr.initialize_state(
        delivered_so_far={"C1": 120.0, "C2": 520.0},
        in_transit_orders=[
            {"order_id": "O1001", "cid": "C1", "warehouse": "W1", "category": "A", "ship_day": 9},
        ],
    )
    
    # 滚动优化
    state = state_mgr.update_state(
        delivered_so_far={"C1": 150.0, "C2": 550.0},
        in_transit_orders=[...],  # 更新后的在途
        x_prev={("W1", "C1", "A", 10): 100.0},  # 今日计划
        today=10,
    )
    
    # 获取历史计划
    x_prev = state_mgr.get_x_prev_for_day(11)
