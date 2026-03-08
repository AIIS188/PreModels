#!/usr/bin/env python3
"""
init_state.py

初始化状态（首次运行）

使用方式：
    python init_state.py
"""

from state_manager import StateManager

def main():
    state_mgr = StateManager()
    
    # 初始状态（示例数据，实际应从 PD API 获取）
    delivered_so_far = {
        "C1": 120.0,
        "C2": 520.0,
    }
    
    in_transit_orders = [
        {"order_id": "O1001", "cid": "C1", "receiver": "R1", "warehouse": "W1", "category": "A", "ship_day": 9},
        {"order_id": "O1002", "cid": "C1", "receiver": "R1", "warehouse": "W2", "category": "B", "ship_day": 9},
        {"order_id": "O2001", "cid": "C2", "receiver": "R2", "warehouse": "W1", "category": "A", "ship_day": 9},
        {"order_id": "O2002", "cid": "C2", "receiver": "R2", "warehouse": "W1", "category": "A", "ship_day": 9},
        {"order_id": "O2003", "cid": "C2", "receiver": "R2", "warehouse": "W2", "category": "B", "ship_day": 9},
        {"order_id": "O2004", "cid": "C2", "receiver": "R2", "warehouse": "W2", "category": "B", "ship_day": 9},
        {"order_id": "O2005", "cid": "C2", "receiver": "R2", "warehouse": "W3", "category": "A", "ship_day": 9},
    ]
    
    state = state_mgr.initialize_state(
        delivered_so_far=delivered_so_far,
        in_transit_orders=in_transit_orders,
    )
    
    print("状态初始化完成：")
    print(f"  已到货：{delivered_so_far}")
    print(f"  在途：{len(in_transit_orders)} 单")
    print(f"  状态文件：./state/state.json")

if __name__ == "__main__":
    main()
