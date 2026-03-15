"""
test_expired_contract_cleanup.py

测试过期合同清理逻辑

验证：
1. update_state() 正确清理过期合同的 delivered_so_far
2. update_state() 正确清理过期合同的 in_transit_orders
3. end_day 当天不算过期，次日才算过期
"""

import sys
from pathlib import Path
# 添加 v2 目录到路径（支持直接运行和 PYTHONPATH 运行）
v2_dir = Path(__file__).parent.parent
if str(v2_dir) not in sys.path:
    sys.path.insert(0, str(v2_dir))

from core.state_manager import StateManager, ModelState
from models.common_utils_v2 import Contract
from core.date_utils import DateUtils
import shutil
import os

def test_cleanup_logic():
    """测试过期合同清理逻辑"""
    
    # 准备测试环境
    test_state_dir = "./test_state_cleanup"
    shutil.rmtree(test_state_dir, ignore_errors=True)
    
    state_mgr = StateManager(test_state_dir)
    
    # 创建测试合同
    today = "2026-03-15"
    contracts = [
        Contract(
            cid="HT-001",
            receiver="R1",
            Q=1000.0,
            start_day="2026-03-01",
            end_day="2026-03-14",  # 已过期（昨天结束）
            products=[{"product_name": "A", "unit_price": 800.0}],
        ),
        Contract(
            cid="HT-002",
            receiver="R1",
            Q=500.0,
            start_day="2026-03-10",
            end_day="2026-03-15",  # 今天结束（不算过期）
            products=[{"product_name": "A", "unit_price": 800.0}],
        ),
        Contract(
            cid="HT-003",
            receiver="R1",
            Q=800.0,
            start_day="2026-03-12",
            end_day="2026-03-20",  # 未过期
            products=[{"product_name": "A", "unit_price": 800.0}],
        ),
    ]
    
    # 模拟状态数据（包含过期合同）
    delivered_so_far = {
        "HT-001": 500.0,  # 过期合同，应被清理
        "HT-002": 300.0,  # 今天结束，应保留
        "HT-003": 200.0,  # 未过期，应保留
        "HT-OLD": 100.0,  # 不在合同列表中，应被清理
    }
    
    in_transit_orders = [
        {"order_id": "O1", "cid": "HT-001", "warehouse": "W1", "category": "A", "ship_day": "2026-03-13"},  # 过期，应清理
        {"order_id": "O2", "cid": "HT-002", "warehouse": "W1", "category": "A", "ship_day": "2026-03-14"},  # 保留
        {"order_id": "O3", "cid": "HT-003", "warehouse": "W2", "category": "A", "ship_day": "2026-03-14"},  # 保留
        {"order_id": "O4", "cid": "HT-OLD", "warehouse": "W1", "category": "A", "ship_day": "2026-03-13"},  # 不在合同列表，应清理
    ]
    
    # 调用 update_state（传入 contracts）
    state = state_mgr.update_state(
        delivered_so_far=delivered_so_far,
        in_transit_orders=in_transit_orders,
        x_prev=None,
        today=today,
        contracts=contracts,
    )
    
    # 验证结果
    print("=" * 60)
    print("测试：过期合同清理逻辑")
    print("=" * 60)
    
    # 检查 delivered_so_far
    print(f"\n原始 delivered_so_far: {len(delivered_so_far)} 条")
    print(f"  - HT-001 (过期): 500.0")
    print(f"  - HT-002 (今天结束): 300.0")
    print(f"  - HT-003 (未过期): 200.0")
    print(f"  - HT-OLD (不在合同列表): 100.0")
    
    print(f"\n清理后 delivered_so_far: {len(state.delivered_so_far)} 条")
    for cid, tons in state.delivered_so_far.items():
        print(f"  - {cid}: {tons}")
    
    assert "HT-001" not in state.delivered_so_far, "❌ HT-001 (过期合同) 应被清理"
    assert "HT-002" in state.delivered_so_far, "❌ HT-002 (今天结束) 应保留"
    assert "HT-003" in state.delivered_so_far, "❌ HT-003 (未过期) 应保留"
    assert "HT-OLD" not in state.delivered_so_far, "❌ HT-OLD (不在合同列表) 应被清理"
    assert state.delivered_so_far["HT-002"] == 300.0, "❌ HT-002 数据应保持不变"
    assert state.delivered_so_far["HT-003"] == 200.0, "❌ HT-003 数据应保持不变"
    
    # 检查 in_transit_orders
    print(f"\n原始 in_transit_orders: {len(in_transit_orders)} 条")
    print(f"清理后 in_transit_orders: {len(state.in_transit_orders)} 条")
    for order in state.in_transit_orders:
        print(f"  - {order['order_id']} ({order['cid']})")
    
    order_cids = {o["cid"] for o in state.in_transit_orders}
    assert "HT-001" not in order_cids, "❌ HT-001 (过期合同) 的在途报单应被清理"
    assert "HT-002" in order_cids, "❌ HT-002 (今天结束) 的在途报单应保留"
    assert "HT-003" in order_cids, "❌ HT-003 (未过期) 的在途报单应保留"
    assert "HT-OLD" not in order_cids, "❌ HT-OLD (不在合同列表) 的在途报单应被清理"
    
    # 验证日志
    print("\n✅ 所有测试通过！")
    print("=" * 60)
    
    # 清理测试环境
    shutil.rmtree(test_state_dir, ignore_errors=True)
    
    return True


def test_backward_compatibility():
    """测试向后兼容性（不传 contracts 参数）"""
    
    test_state_dir = "./test_state_compat"
    shutil.rmtree(test_state_dir, ignore_errors=True)
    
    state_mgr = StateManager(test_state_dir)
    
    delivered_so_far = {"HT-001": 500.0, "HT-002": 300.0}
    in_transit_orders = [{"order_id": "O1", "cid": "HT-001"}]
    
    # 不传 contracts 参数（旧版调用方式）
    state = state_mgr.update_state(
        delivered_so_far=delivered_so_far,
        in_transit_orders=in_transit_orders,
        x_prev=None,
        today="2026-03-15",
        contracts=None,  # 显式传入 None
    )
    
    print("\n" + "=" * 60)
    print("测试：向后兼容性（不传 contracts）")
    print("=" * 60)
    
    # 应该保留所有数据（不清理）
    assert state.delivered_so_far == delivered_so_far, "❌ 不传 contracts 时应保留所有数据"
    assert state.in_transit_orders == in_transit_orders, "❌ 不传 contracts 时应保留所有在途报单"
    
    print("✅ 向后兼容性测试通过！")
    print("=" * 60)
    
    shutil.rmtree(test_state_dir, ignore_errors=True)
    
    return True


if __name__ == "__main__":
    test_cleanup_logic()
    test_backward_compatibility()
    print("\n🎉 所有测试完成！")
