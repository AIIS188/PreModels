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
    
    # 最后运行日期 (日期字符串，推荐)
    last_run_date: Optional[str]  # "2026-03-10"
    
    # 最后运行日期 (day 编号，兼容旧版)
    last_run_day: Optional[int]  # 70


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
        if state.last_run_day is not None:
            history_file = os.path.join(
                self.history_dir,
                f"state_day{state.last_run_day}.json"
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
        delivered_so_far: Dict[str, float],
        in_transit_orders: List[Dict],
    ) -> ModelState:
        """
        初始化状态（首次运行）
        
        参数:
            delivered_so_far: 已到货量
            in_transit_orders: 在途报单
        
        返回:
            初始化的 ModelState
        """
        state = ModelState(
            delivered_so_far=delivered_so_far,
            in_transit_orders=in_transit_orders,
            x_prev=None,
            last_updated=datetime.now().isoformat(),
            last_run_day=None,
        )
        self.save_state(state)
        self.log("状态初始化完成")
        return state
    
    def update_state(
        self,
        delivered_so_far: Dict[str, float],
        in_transit_orders: List[Dict],
        x_prev: Optional[Dict],
        today: str,  # 改为日期字符串
    ) -> ModelState:
        """
        更新状态（滚动优化）
        
        参数:
            delivered_so_far: 更新后的已到货量
            in_transit_orders: 更新后的在途报单
            x_prev: 今日计划（用于明日稳定性优化）
            today: 今日（日期字符串，如 "2026-03-10"）
        
        返回:
            更新后的 ModelState
        """
        # 兼容 day 编号
        if isinstance(today, int):
            today_date = DateUtils.from_day_number(today)
            today_day = today
        else:
            today_date = today
            today_day = DateUtils.to_day_number(today)
        
        state = ModelState(
            delivered_so_far=delivered_so_far,
            in_transit_orders=in_transit_orders,
            x_prev=x_prev,
            last_updated=datetime.now().isoformat(),
            last_run_date=today_date,  # 新增：日期字符串
            last_run_day=today_day,     # 兼容：day 编号
        )
        self.save_state(state)
        self.log(f"状态更新完成 (date={today_date}, day={today_day})")
        return state
    
    def get_x_prev_for_day(self, target_day: int) -> Optional[Dict]:
        """
        获取指定日期的历史计划（用于稳定性优化）
        
        参数:
            target_day: 目标日期
        
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
