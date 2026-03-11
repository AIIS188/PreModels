#!/usr/bin/env python3
"""
capacity_predictor.py

产能预测模型

功能：
1. 预测各仓库未来 H 天的产能（按品类）
2. 返回格式：
{
    "仓库名": {
        "日期": {"品类 1": 重量， "品类 2": 重量},
        ...
    }
}

使用方式：
    predictor = CapacityPredictor()
    forecast = predictor.predict(today="2026-03-11", H=10)
"""

from typing import Dict, List
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.date_utils import DateUtils


class CapacityPredictor:
    """
    产能预测模型
    
    基于历史数据、设备状态、原材料供应等因素
    预测各仓库未来 H 天的产能（分品类）
    
    支持动态品类配置：
        predictor = CapacityPredictor(categories=["A", "B", "C"])
    """
    
    def __init__(self, categories: List[str] = None):
        """
        初始化预测模型
        
        参数:
            categories: 品类列表，None 则使用默认 ["A", "B"]
        """
        self.categories = categories or ["A", "B"]
        
        # 仓库基础产能配置（吨/天）
        # 注意：这里只配置基础品类，其他品类会动态分配
        self.base_capacity = {
            "W1": {"A": 220.0, "B": 60.0},   # W1 仓库
            "W2": {"A": 80.0, "B": 220.0},   # W2 仓库
            "W3": {"A": 120.0, "B": 120.0},  # W3 仓库
        }
        
        # 产能波动因子（模拟设备维护、原材料供应等影响）
        self.capacity_factors = {
            "weekday": 1.0,      # 工作日
            "weekend": 0.85,     # 周末产能略降
            "maintenance": 0.7,  # 维护日
        }
    
    def predict(self, today: str, H: int = 10, categories: List[str] = None) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        预测产能
        
        参数:
            today: 今日（日期字符串 "YYYY-MM-DD"）
            H: 预测天数
            categories: 品类列表，None 则使用初始化时的配置
        
        返回:
            {
                "仓库名": {
                    "日期": {"品类 1": 重量， "品类 2": 重量},
                    ...
                }
            }
        
        示例:
            {
                "W1": {
                    "2026-03-11": {"A": 220.0, "B": 60.0, "C": 100.0},
                    "2026-03-12": {"A": 231.0, "B": 63.0, "C": 105.0},
                    ...
                },
                "W2": {
                    "2026-03-11": {"A": 80.0, "B": 220.0, "C": 90.0},
                    ...
                }
            }
        """
        # 使用传入的品类或默认品类
        use_categories = categories or self.categories
        
        result = {}
        
        for warehouse in self.base_capacity.keys():
            result[warehouse] = {}
            
            for t in range(H):
                # 计算日期
                date = DateUtils.add_days(today, t)
                date_str = date if isinstance(date, str) else DateUtils.from_day_number(date)
                
                # 计算产能波动因子
                factor = self._calculate_capacity_factor(date, warehouse)
                
                # 预测各品类产能
                # 策略：基础品类使用配置的产能，其他品类平均分配
                warehouse_caps = self.base_capacity[warehouse]
                base_categories = list(warehouse_caps.keys())
                new_categories = [c for c in use_categories if c not in base_categories]
                
                # 计算总产能
                total_base_cap = sum(warehouse_caps.values())
                
                # 如果有新品类，将总产能重新分配
                if new_categories:
                    # 所有品类平均分配总产能
                    cap_per_category = total_base_cap / len(use_categories)
                    result[warehouse][date_str] = {
                        category: cap_per_category * factor
                        for category in use_categories
                    }
                else:
                    # 只有基础品类，直接使用配置
                    result[warehouse][date_str] = {
                        category: base * factor 
                        for category, base in warehouse_caps.items()
                    }
        
        return result
    
    def _calculate_capacity_factor(self, date, warehouse: str) -> float:
        """
        计算产能波动因子
        
        考虑因素：
        1. 工作日/周末
        2. 设备维护计划
        3. 原材料供应
        4. 季节性因素
        
        参数:
            date: 日期
            warehouse: 仓库名
        
        返回:
            产能因子（0.0-1.5）
        """
        # 基础因子
        factor = 1.0
        
        # 1. 工作日/周末
        try:
            if isinstance(date, str):
                dt = datetime.strptime(date, "%Y-%m-%d")
            else:
                dt = DateUtils.to_datetime(date)
            
            if dt.weekday() >= 5:  # 周末
                factor *= 0.85
        except:
            pass
        
        # 2. 设备维护（示例：每月 15 号）
        try:
            if isinstance(date, str):
                dt = datetime.strptime(date, "%Y-%m-%d")
            else:
                dt = DateUtils.to_datetime(date)
            
            if dt.day == 15:
                factor *= 0.7
        except:
            pass
        
        # 3. 仓库特定因子（模拟不同仓库的效率差异）
        warehouse_factors = {
            "W1": 1.05,  # W1 效率略高
            "W2": 0.95,  # W2 效率略低
            "W3": 1.0,   # W3 标准
        }
        factor *= warehouse_factors.get(warehouse, 1.0)
        
        # 4. 随机波动（±5%）
        import random
        random.seed(hash(str(date) + warehouse) % 1000)
        factor *= (0.95 + random.random() * 0.1)
        
        return factor
    
    def predict_total(self, today: str, H: int = 10) -> Dict[str, List[float]]:
        """
        预测总产能（不分类别）
        
        参数:
            today: 今日
            H: 预测天数
        
        返回:
            {
                "W1": [350, 360, 370, ...],
                "W2": [200, 210, 220, ...],
                ...
            }
        """
        detailed = self.predict(today, H)
        
        result = {}
        for warehouse, dates in detailed.items():
            result[warehouse] = []
            for date, categories in dates.items():
                total = sum(categories.values())
                result[warehouse].append(total)
        
        return result


# =========================
# 兼容旧版 API 格式
# =========================

def predict_capacity(today: str, H: int = 10, categories: List[str] = None) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    产能预测函数（主接口）
    
    参数:
        today: 今日（日期字符串 "YYYY-MM-DD"）
        H: 预测天数
        categories: 品类列表，None 则使用默认 ["A", "B"]
    
    返回:
        {
            "仓库名": {
                "日期": {"品类": 重量},
                ...
            }
        }
    """
    predictor = CapacityPredictor(categories=categories)
    return predictor.predict(today, H, categories=categories)


def predict_capacity_total(today: str, H: int = 10) -> Dict[str, List[float]]:
    """
    产能预测函数（总产能，兼容旧版）
    
    参数:
        today: 今日
        H: 预测天数
    
    返回:
        {
            "W1": [350, 360, 370, ...],
            "W2": [200, 210, 220, ...],
        }
    """
    predictor = CapacityPredictor()
    return predictor.predict_total(today, H)


# =========================
# 使用示例
# =========================

if __name__ == "__main__":
    import json
    
    print("=" * 80)
    print("产能预测模型示例")
    print("=" * 80)
    
    # 示例 1: 详细预测（分品类）
    print("\n1. 详细产能预测（分品类）")
    print("-" * 80)
    
    predictor = CapacityPredictor()
    forecast = predictor.predict(today="2026-03-11", H=5)
    
    print(json.dumps(forecast, indent=2, ensure_ascii=False))
    
    # 示例 2: 总产能预测（兼容旧版）
    print("\n2. 总产能预测（兼容旧版格式）")
    print("-" * 80)
    
    total_forecast = predictor.predict_total(today="2026-03-11", H=5)
    
    print(json.dumps(total_forecast, indent=2, ensure_ascii=False))
    
    # 示例 3: 在 rolling_optimizer 中使用
    print("\n3. 在 rolling_optimizer 中使用")
    print("-" * 80)
    
    from rolling_optimizer import RollingOptimizer
    
    optimizer = RollingOptimizer()
    
    # 获取产能预测
    capacity_data = predict_capacity(today="2026-03-11", H=10)
    
    # 转换为模型需要的格式
    categories = ["A", "B"]
    cap_forecast = optimizer._convert_capacity_format_new(
        capacity_data,
        today="2026-03-11",
        categories=categories
    )
    
    print(f"转换后的格式（前 5 条）:")
    for i, (key, value) in enumerate(cap_forecast.items()):
        if i >= 5:
            break
        print(f"  {key}: {value:.1f} 吨")
    
    print("\n" + "=" * 80)
    print("示例完成")
    print("=" * 80)
