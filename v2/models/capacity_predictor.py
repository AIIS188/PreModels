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
    """
    
    def __init__(self):
        """初始化预测模型"""
        # 仓库基础产能配置（吨/天）
        self.base_capacity = {
            "W1": {"A": 220.0, "B": 60.0},   # W1 仓库：A 品类 220 吨，B 品类 60 吨
            "W2": {"A": 80.0, "B": 220.0},   # W2 仓库：A 品类 80 吨，B 品类 220 吨
            "W3": {"A": 120.0, "B": 120.0},  # W3 仓库：A 品类 120 吨，B 品类 120 吨
        }
        
        # 产能波动因子（模拟设备维护、原材料供应等影响）
        self.capacity_factors = {
            "weekday": 1.0,      # 工作日
            "weekend": 0.85,     # 周末产能略降
            "maintenance": 0.7,  # 维护日
        }
    
    def predict(self, today: str, H: int = 10) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        预测产能
        
        参数:
            today: 今日（日期字符串 "YYYY-MM-DD"）
            H: 预测天数
        
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
                    "2026-03-11": {"A": 220.0, "B": 60.0},
                    "2026-03-12": {"A": 231.0, "B": 63.0},
                    ...
                },
                "W2": {
                    "2026-03-11": {"A": 80.0, "B": 220.0},
                    ...
                }
            }
        """
        result = {}
        
        for warehouse, categories in self.base_capacity.items():
            result[warehouse] = {}
            
            for t in range(H):
                # 计算日期
                date = DateUtils.add_days(today, t)
                date_str = date if isinstance(date, str) else DateUtils.from_day_number(date)
                
                # 计算产能波动因子
                factor = self._calculate_capacity_factor(date, warehouse)
                
                # 预测各品类产能
                result[warehouse][date_str] = {
                    category: base * factor 
                    for category, base in categories.items()
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

def predict_capacity(today: str, H: int = 10) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    产能预测函数（主接口）
    
    参数:
        today: 今日（日期字符串 "YYYY-MM-DD"）
        H: 预测天数
    
    返回:
        {
            "仓库名": {
                "日期": {"品类": 重量},
                ...
            }
        }
    """
    predictor = CapacityPredictor()
    return predictor.predict(today, H)


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
