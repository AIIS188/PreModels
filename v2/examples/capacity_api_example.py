#!/usr/bin/env python3
"""
capacity_api_example.py

产能预测模型对接示例

展示如何将产能预测模型与滚动优化器对接

产能预测模型输出格式 (新):
{
    "仓库名": {
        "日期 (格式"%Y-%m-%d")": {"品类 1": 重量 (float), "品类 2": 重量},
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
"""

from typing import Dict, List, Optional
import sys
from pathlib import Path

# 添加 v2 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))


# =========================
# 方案 1: 调用内部产能预测函数（推荐）
# =========================

from models.capacity_predictor import predict_capacity, CapacityPredictor


def use_internal_predictor():
    """
    使用内部产能预测模型
    
    不需要对接外部 API，直接调用函数即可
    """
    predictor = CapacityPredictor()
    
    # 预测未来 10 天产能
    forecast = predictor.predict(today="2026-03-11", H=10)
    
    return forecast


# =========================
# 方案 2: 集成到滚动优化器
# =========================

def integrate_with_rolling_optimizer():
    """
    演示如何将产能预测集成到滚动优化器
    
    rolling_optimizer.py 已自动调用内部产能预测模型
    无需额外配置
    """
    from models.rolling_optimizer import RollingOptimizer
    
    optimizer = RollingOptimizer()
    
    # 运行优化时会自动调用产能预测模型
    result = optimizer.run(today_date="2026-03-11", H=10)
    
    return result


# =========================
# 使用示例
# =========================

if __name__ == "__main__":
    import json
    
    print("=" * 80)
    print("产能预测模型对接示例")
    print("=" * 80)
    
    # 示例 1: 调用内部产能预测函数
    print("\n1. 调用内部产能预测函数（推荐）")
    print("-" * 80)
    
    forecast = use_internal_predictor()
    
    print(f"获取到产能预测数据（前 3 天）:")
    for warehouse, dates in forecast.items():
        print(f"\n  {warehouse}:")
        for i, (date_str, categories) in enumerate(dates.items()):
            if i >= 3:
                break
            print(f"    {date_str}: {categories}")
    
    # 示例 2: 集成到滚动优化器
    print("\n2. 集成到滚动优化器")
    print("-" * 80)
    
    print("rolling_optimizer.py 已自动调用内部产能预测模型")
    print("运行优化命令:")
    print("  python rolling_optimizer.py --run --today-date 2026-03-11 --H 10")
    
    # 示例 3: 验证返回格式
    print("\n3. 验证返回格式")
    print("-" * 80)
    
    # 验证格式是否符合要求
    def validate_format(data: Dict) -> bool:
        """
        验证返回数据格式
        
        要求:
        - 是字典
        - 每个值是字典（日期）
        - 日期字典的值是字典（品类）
        - 品类字典的值是数字
        """
        if not isinstance(data, dict):
            return False
        
        for warehouse, dates in data.items():
            if not isinstance(dates, dict):
                return False
            
            for date_str, categories in dates.items():
                if not isinstance(categories, dict):
                    return False
                
                # 验证日期格式
                import re
                if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                    return False
                
                # 验证品类和重量
                for category, weight in categories.items():
                    if not isinstance(weight, (int, float)):
                        return False
        
        return True
    
    is_valid = validate_format(forecast)
    print(f"格式验证：{'✅ 通过' if is_valid else '❌ 失败'}")
    
    # 示例 4: 完整 JSON 格式展示
    print("\n4. 完整 JSON 格式示例（W1 仓库前 2 天）")
    print("-" * 80)
    
    example_output = {
        "W1": {
            date: cats for i, (date, cats) in enumerate(forecast["W1"].items()) if i < 2
        }
    }
    
    print(json.dumps(example_output, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 80)
    print("示例完成")
    print("=" * 80)
