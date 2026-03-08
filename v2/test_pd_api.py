#!/usr/bin/env python3
"""
test_pd_api.py

测试 PD API 对接脚本

功能：
1. 测试 PD API 连接
2. 测试获取磅单/报货单
3. 测试创建报货单
4. 验证数据格式
"""

import sys
import json
from api_client import PDAPIClient, get_confirmed_arrivals


def test_health_check(api: PDAPIClient):
    """测试健康检查"""
    print("=" * 60)
    print("测试 1: 健康检查")
    print("=" * 60)
    
    if api.health_check():
        print("✅ PD API 连接正常")
        return True
    else:
        print("❌ PD API 连接失败")
        return False


def test_get_deliveries(api: PDAPIClient):
    """测试获取报货单"""
    print("\n" + "=" * 60)
    print("测试 2: 获取报货单")
    print("=" * 60)
    
    deliveries = api.get_deliveries(page=1, page_size=20)
    print(f"报货单数量：{len(deliveries)}")
    
    if deliveries:
        print("\n示例数据:")
        for d in deliveries[:3]:
            print(f"  - ID: {d.id}, 合同：{d.contract_no}, 品种：{d.product_name}, 数量：{d.quantity}吨")
    else:
        print("（暂无报货单数据）")
    
    return True


def test_get_weighbills(api: PDAPIClient):
    """测试获取磅单"""
    print("\n" + "=" * 60)
    print("测试 3: 获取磅单")
    print("=" * 60)
    
    weighbills = api.get_weighbills(page=1, page_size=20)
    print(f"磅单数量：{len(weighbills)}")
    
    if weighbills:
        print("\n示例数据:")
        for wb in weighbills[:3]:
            print(f"  - ID: {wb.id}, 合同：{wb.contract_no}, 品种：{wb.product_name}, 净重：{wb.net_weight}吨")
    else:
        print("（暂无磅单数据）")
    
    return True


def test_get_confirmed_arrivals(api: PDAPIClient):
    """测试获取已确认到货"""
    print("\n" + "=" * 60)
    print("测试 4: 获取已确认到货")
    print("=" * 60)
    
    today = "2026-03-08"
    arrivals = get_confirmed_arrivals(api, today=today)
    
    if arrivals:
        print(f"今日到货汇总:")
        for contract_no, weight in arrivals.items():
            print(f"  - 合同 {contract_no}: {weight}吨")
    else:
        print(f"今日 ({today}) 无到货记录")
    
    return True


def test_create_delivery(api: PDAPIClient):
    """测试创建报货单"""
    print("\n" + "=" * 60)
    print("测试 5: 创建报货单（示例）")
    print("=" * 60)
    
    # 示例数据（不实际创建，仅展示格式）
    sample_delivery = {
        "report_date": "2026-03-08",
        "target_factory_name": "R1",
        "product_name": "A",
        "quantity": 100.0,
        "vehicle_no": "京 A12345",
        "driver_name": "张三",
        "driver_phone": "13800138000",
        "status": "待确认"
    }
    
    print("报货单数据格式:")
    print(json.dumps(sample_delivery, indent=2, ensure_ascii=False))
    print("\n（测试模式：不实际创建）")
    
    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("PD API 对接测试")
    print("=" * 60)
    
    # 初始化 API 客户端
    api = PDAPIClient(base_url="http://127.0.0.1:8007")
    
    # 运行测试
    tests = [
        test_health_check,
        test_get_deliveries,
        test_get_weighbills,
        test_get_confirmed_arrivals,
        test_create_delivery,
    ]
    
    results = []
    for test in tests:
        try:
            result = test(api)
            results.append(result)
        except Exception as e:
            print(f"\n❌ 测试失败：{e}")
            results.append(False)
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"通过：{passed}/{total}")
    
    if passed == total:
        print("\n✅ 所有测试通过！PD API 对接成功！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
