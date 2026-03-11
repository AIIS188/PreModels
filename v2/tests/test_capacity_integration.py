#!/usr/bin/env python3
"""
test_capacity_integration.py

产能预测模型集成测试

验证:
1. 产能预测模型返回格式正确
2. rolling_optimizer 能正确调用产能预测
3. 格式转换正确
"""

import sys
import json
from pathlib import Path

# 添加 v2 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.capacity_predictor import predict_capacity, CapacityPredictor
from models.rolling_optimizer import RollingOptimizer
from core.date_utils import DateUtils


def test_capacity_predictor_format():
    """测试产能预测模型返回格式"""
    print("=" * 80)
    print("测试 1: 产能预测模型返回格式")
    print("=" * 80)
    
    predictor = CapacityPredictor()
    forecast = predictor.predict(today="2026-03-11", H=5)
    
    # 验证格式
    assert isinstance(forecast, dict), "返回必须是字典"
    
    for warehouse, dates in forecast.items():
        assert isinstance(dates, dict), f"{warehouse} 的值必须是字典"
        
        for date_str, categories in dates.items():
            # 验证日期格式 (YYYY-MM-DD)
            import re
            assert re.match(r'^\d{4}-\d{2}-\d{2}$', date_str), f"日期格式错误：{date_str}"
            
            # 验证品类和重量
            assert isinstance(categories, dict), f"{date_str} 的值必须是字典"
            for category, weight in categories.items():
                assert isinstance(weight, (int, float)), f"重量必须是数字：{weight}"
    
    print("✅ 格式验证通过")
    print(f"\n示例输出:")
    print(json.dumps({
        "W1": {
            date: cats for i, (date, cats) in enumerate(forecast["W1"].items()) if i < 2
        }
    }, indent=2, ensure_ascii=False))
    
    return True


def test_capacity_format_conversion():
    """测试产能格式转换"""
    print("\n" + "=" * 80)
    print("测试 2: 产能格式转换")
    print("=" * 80)
    
    predictor = CapacityPredictor()
    capacity_data = predictor.predict(today="2026-03-11", H=3)
    
    optimizer = RollingOptimizer()
    categories = ["A", "B"]
    
    # 转换为模型需要的格式
    cap_forecast = optimizer._convert_capacity_format_new(
        capacity_data,
        today="2026-03-11",
        categories=categories
    )
    
    # 验证转换结果
    assert isinstance(cap_forecast, dict), "转换结果必须是字典"
    
    # 检查键格式：(warehouse, category, date)
    for key, value in cap_forecast.items():
        assert isinstance(key, tuple), f"键必须是元组：{key}"
        assert len(key) == 3, f"键必须是 3 元组：{key}"
        
        warehouse, category, date = key
        assert isinstance(warehouse, str), f"仓库必须是字符串：{warehouse}"
        assert isinstance(category, str), f"品类必须是字符串：{category}"
        assert isinstance(date, str), f"日期必须是字符串：{date}"
        assert isinstance(value, float), f"产能必须是浮点数：{value}"
    
    print("✅ 格式转换验证通过")
    print(f"\n转换结果示例（前 5 条）:")
    for i, (key, value) in enumerate(cap_forecast.items()):
        if i >= 5:
            break
        print(f"  {key}: {value:.1f} 吨")
    
    return True


def test_rolling_optimizer_integration():
    """测试滚动优化器集成（模拟）"""
    print("\n" + "=" * 80)
    print("测试 3: 滚动优化器集成（模拟）")
    print("=" * 80)
    
    # 注意：这个测试需要完整的环境（合同、状态等）
    # 这里只测试产能加载部分
    
    optimizer = RollingOptimizer()
    
    # 测试 _load_cap_forecast 方法
    try:
        cap_forecast = optimizer._load_cap_forecast(today="2026-03-11", H=5)
        
        assert isinstance(cap_forecast, dict), "产能预测必须是字典"
        
        # 检查键格式
        for key, value in cap_forecast.items():
            assert isinstance(key, tuple), f"键必须是元组：{key}"
            assert len(key) == 3, f"键必须是 3 元组：{key}"
        
        print("✅ 滚动优化器集成验证通过")
        print(f"加载了 {len(cap_forecast)} 条产能记录")
        
        return True
        
    except Exception as e:
        print(f"⚠️  部分验证失败（可能需要完整环境）: {e}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("产能预测模型集成测试")
    print("=" * 80 + "\n")
    
    results = []
    
    # 测试 1: 格式验证
    results.append(("格式验证", test_capacity_predictor_format()))
    
    # 测试 2: 格式转换
    results.append(("格式转换", test_capacity_format_conversion()))
    
    # 测试 3: 集成测试
    results.append(("集成测试", test_rolling_optimizer_integration()))
    
    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(r for _, r in results)
    
    if all_passed:
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠️  部分测试失败，请检查")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
