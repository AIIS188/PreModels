#!/usr/bin/env python3
"""
test_date_migration.py

日期格式重构完整性测试

验证所有修改后的日期格式是否正确工作
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.date_utils import DateUtils
from models.common_utils_v2 import (
    Contract, 
    predict_intransit_arrivals_expected,
    intransit_total_expected_in_valid_window,
    suggest_trucks_from_tons_plan,
)
from models.complex_system_v2 import solve_lp_rolling_H_days


def test_contract_with_date():
    """测试 Contract 结构体使用日期字符串"""
    print("=" * 60)
    print("测试 1: Contract 结构体日期格式")
    print("=" * 60)
    
    contract = Contract(
        cid="HT-2026-001",
        receiver="R1",
        Q=1000.0,
        start_day="2026-03-10",
        end_day="2026-03-20",
        products=[{"product_name": "A", "unit_price": 800.0}, {"product_name": "B", "unit_price": 1200.0}]
    )
    
    print(f"合同 ID: {contract.cid}")
    print(f"有效期：{contract.start_day} 至 {contract.end_day}")
    print(f"合同总量：{contract.Q} 吨")
    
    # 验证日期格式
    assert len(contract.start_day) == 10, "start_day 格式错误"
    assert len(contract.end_day) == 10, "end_day 格式错误"
    assert contract.start_day.count('-') == 2, "start_day 格式错误"
    assert contract.end_day.count('-') == 2, "end_day 格式错误"
    
    # 验证日期计算
    days = DateUtils.diff_days(contract.start_day, contract.end_day)
    print(f"合同期限：{days} 天")
    assert days == 10, "合同期限计算错误"
    
    print("✅ Contract 日期格式测试通过\n")


def test_intransit_with_date():
    """测试在途预测使用日期字符串"""
    print("=" * 60)
    print("测试 2: 在途预测日期格式")
    print("=" * 60)
    
    contracts = [
        Contract(
            cid="HT-2026-001",
            receiver="R1",
            Q=1000.0,
            start_day="2026-03-10",
            end_day="2026-03-20",
            products=[{"product_name": "A", "unit_price": 800.0}]
        )
    ]
    
    in_transit_orders = [
        {
            "warehouse": "WH1",
            "ship_day": "2026-03-09",  # 日期字符串
            "category": "A",
            "receiver": "R1",
            "cid": "HT-2026-001",
            "tons": 100.0
        }
    ]
    
    pred_mu, pred_hi = predict_intransit_arrivals_expected(
        contracts=contracts,
        in_transit_orders=in_transit_orders,
        weight_profile={("WH1", "R1", "A"): (32.0, 35.0)},
        delay_profile=None,
        global_delay_pmf=None
    )
    
    print(f"在途预测结果：")
    for (cid, date), tons in pred_mu.items():
        print(f"  合同 {cid} 在 {date}: {tons:.2f} 吨 (期望)")
        # 验证日期格式
        assert len(date) == 10, f"日期格式错误：{date}"
        assert date.count('-') == 2, f"日期格式错误：{date}"
    
    # 测试有效期内的在途总量
    total = intransit_total_expected_in_valid_window(
        cid="HT-2026-001",
        pred_mu=pred_mu,
        day_from="2026-03-10",
        day_to="2026-03-20"
    )
    print(f"\n有效期内 (2026-03-10 至 2026-03-20) 在途总量：{total:.2f} 吨")
    
    print("✅ 在途预测日期格式测试通过\n")


def test_truck_suggest_with_date():
    """测试车数建议使用日期字符串"""
    print("=" * 60)
    print("测试 3: 车数建议日期格式")
    print("=" * 60)
    
    contracts = [
        Contract(
            cid="HT-2026-001",
            receiver="R1",
            Q=1000.0,
            start_day="2026-03-10",
            end_day="2026-03-20",
            products=[{"product_name": "A", "unit_price": 800.0}]
        )
    ]
    
    # 吨计划使用日期字符串
    tons_plan = {
        ("WH1", "HT-2026-001", "A", "2026-03-10"): 100.0,
        ("WH1", "HT-2026-001", "A", "2026-03-11"): 150.0,
    }
    
    weight_profile = {
        ("WH1", "R1", "A"): (32.0, 35.0)
    }
    
    truck_suggest = suggest_trucks_from_tons_plan(
        tons_plan=tons_plan,
        contracts=contracts,
        weight_profile=weight_profile,
        allow_mixing=True
    )
    
    print(f"车数建议：")
    for (w, cid, date), trucks in truck_suggest.items():
        print(f"  仓库 {w} 合同 {cid} 在 {date}: {trucks} 车")
        # 验证日期格式
        assert len(date) == 10, f"日期格式错误：{date}"
        assert date.count('-') == 2, f"日期格式错误：{date}"
    
    print("✅ 车数建议日期格式测试通过\n")


def test_rolling_optimizer_with_date():
    """测试滚动优化器使用日期字符串"""
    print("=" * 60)
    print("测试 4: 滚动优化器日期格式")
    print("=" * 60)
    
    warehouses = ["WH1", "WH2"]
    categories = ["A", "B"]
    today = "2026-03-09"
    H = 5
    
    contracts = [
        Contract(
            cid="HT-2026-001",
            receiver="R1",
            Q=1000.0,
            start_day="2026-03-10",
            end_day="2026-03-20",
            products=[{"product_name": "A", "unit_price": 800.0}, {"product_name": "B", "unit_price": 1200.0}]
        )
    ]
    
    cap_forecast = {
        ("WH1", "A", "2026-03-09"): 200.0,
        ("WH1", "A", "2026-03-10"): 200.0,
        ("WH1", "B", "2026-03-09"): 150.0,
        ("WH2", "A", "2026-03-09"): 180.0,
    }
    
    delivered_so_far = {
        "HT-2026-001": 300.0
    }
    
    in_transit_orders = [
        {
            "warehouse": "WH1",
            "ship_day": "2026-03-08",
            "category": "A",
            "receiver": "R1",
            "cid": "HT-2026-001",
            "tons": 100.0
        }
    ]
    
    weight_profile = {
        ("WH1", "R1", "A"): (32.0, 35.0),
        ("WH1", "R1", "B"): (30.0, 33.0),
        ("WH2", "R1", "A"): (31.0, 34.0),
    }
    
    try:
        x_today_plan, x_horizon_plan, arrival_plan, truck_suggest, mixing_details = \
            solve_lp_rolling_H_days(
                warehouses=warehouses,
                categories=categories,
                today=today,
                H=H,
                contracts=contracts,
                cap_forecast=cap_forecast,
                delivered_so_far=delivered_so_far,
                in_transit_orders=in_transit_orders,
                weight_profile=weight_profile,
            )
        
        print(f"优化结果：")
        print(f"  今日计划：{len(x_today_plan)} 条记录")
        print(f"  窗口计划：{len(x_horizon_plan)} 条记录")
        print(f"  到货计划：{len(arrival_plan)} 条记录")
        print(f"  车数建议：{len(truck_suggest)} 条记录")
        
        # 验证日期格式
        for key in list(x_today_plan.keys())[:1]:
            w, cid, k, date = key
            print(f"\n  示例计划：{w} -> {cid} ({k}) 在 {date}: {x_today_plan[key]:.2f} 吨")
            assert len(date) == 10, f"日期格式错误：{date}"
            assert date == today, f"今日计划日期错误：{date} != {today}"
        
        for (cid, date), tons in list(arrival_plan.items())[:1]:
            print(f"  示例到货：{cid} 在 {date}: {tons:.2f} 吨")
            assert len(date) == 10, f"日期格式错误：{date}"
        
        print("\n✅ 滚动优化器日期格式测试通过\n")
        
    except Exception as e:
        print(f"❌ 滚动优化器测试失败：{e}")
        import traceback
        traceback.print_exc()
        raise


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("🚀 日期格式重构完整性测试")
    print("=" * 60 + "\n")
    
    test_contract_with_date()
    test_intransit_with_date()
    test_truck_suggest_with_date()
    test_rolling_optimizer_with_date()
    
    print("=" * 60)
    print("🎉 所有测试通过！日期格式重构完成！")
    print("=" * 60)
    print("\n✅ 修改总结:")
    print("  1. Contract.start_day/end_day: int -> str (YYYY-MM-DD)")
    print("  2. CapForecast: (w,k,day) -> (w,k,date)")
    print("  3. 所有日期运算：使用 DateUtils.add_days/diff_days")
    print("  4. API 客户端：weigh_day/ship_day 改为日期字符串")
    print("  5. 向后兼容：保留 day 编号转换功能")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
