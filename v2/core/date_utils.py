"""
date_utils.py

日期工具类

功能:
1. 日期格式化
2. 日期计算
3. day 编号与日期互转 (兼容旧版)
4. 自动获取今日日期

使用方式:
    from core.date_utils import DateUtils
    
    # 获取今日
    today = DateUtils.today()  # "2026-03-10"
    
    # 日期计算
    tomorrow = DateUtils.add_days(today, 1)  # "2026-03-11"
    
    # 计算天数差
    days = DateUtils.diff_days("2026-03-10", "2026-03-15")  # 5
    
    # day 编号与日期互转 (兼容旧版)
    day = DateUtils.to_day_number("2026-03-10")  # 70
    date = DateUtils.from_day_number(70)  # "2026-03-10"
"""

from datetime import datetime, timedelta
from typing import Optional


class DateUtils:
    """日期工具类"""
    
    # 默认基准日 (用于 day 编号转换)
    DEFAULT_BASE = "2026-01-01"
    
    # 日期格式
    DATE_FORMAT = "%Y-%m-%d"
    
    @classmethod
    def today(cls) -> str:
        """
        获取今日日期
        
        返回:
            日期字符串 "2026-03-10"
        """
        return datetime.now().strftime(cls.DATE_FORMAT)
    
    @classmethod
    def now(cls) -> str:
        """
        获取当前时间戳
        
        返回:
            ISO 格式时间戳 "2026-03-10T14:30:00"
        """
        return datetime.now().isoformat(timespec='seconds')
    
    @classmethod
    def add_days(cls, date_str: str, days: int) -> str:
        """
        日期加减
        
        参数:
            date_str: 日期字符串 "2026-03-10"
            days: 天数 (正数=未来，负数=过去)
        
        返回:
            日期字符串 "2026-03-15"
        """
        dt = datetime.strptime(date_str, cls.DATE_FORMAT)
        result = dt + timedelta(days=days)
        return result.strftime(cls.DATE_FORMAT)
    
    @classmethod
    def diff_days(cls, date1: str, date2: str) -> int:
        """
        计算两个日期之间的天数差
        
        参数:
            date1: 日期字符串 "2026-03-10"
            date2: 日期字符串 "2026-03-15"
        
        返回:
            天数差 5
        """
        d1 = datetime.strptime(date1, cls.DATE_FORMAT)
        d2 = datetime.strptime(date2, cls.DATE_FORMAT)
        return (d2 - d1).days
    
    @classmethod
    def to_day_number(cls, date_str: str, base: Optional[str] = None) -> int:
        """
        日期转 day 编号 (兼容旧版)
        
        参数:
            date_str: 日期字符串 "2026-03-10"
            base: 基准日期，默认 "2026-01-01"
        
        返回:
            day 编号 70
        """
        base_date = base or cls.DEFAULT_BASE
        base_dt = datetime.strptime(base_date, cls.DATE_FORMAT)
        dt = datetime.strptime(date_str, cls.DATE_FORMAT)
        return (dt - base_dt).days + 1
    
    @classmethod
    def from_day_number(cls, day: int, base: Optional[str] = None) -> str:
        """
        day 编号转日期 (兼容旧版)
        
        参数:
            day: day 编号 70
            base: 基准日期，默认 "2026-01-01"
        
        返回:
            日期字符串 "2026-03-10"
        """
        base_date = base or cls.DEFAULT_BASE
        base_dt = datetime.strptime(base_date, cls.DATE_FORMAT)
        result = base_dt + timedelta(days=day-1)
        return result.strftime(cls.DATE_FORMAT)
    
    @classmethod
    def parse(cls, date_str: str, fmt: Optional[str] = None) -> datetime:
        """
        解析日期字符串
        
        参数:
            date_str: 日期字符串
            fmt: 格式，默认 "%Y-%m-%d"
        
        返回:
            datetime 对象
        """
        fmt = fmt or cls.DATE_FORMAT
        return datetime.strptime(date_str, fmt)
    
    @classmethod
    def format(cls, dt: datetime, fmt: Optional[str] = None) -> str:
        """
        格式化 datetime 对象
        
        参数:
            dt: datetime 对象
            fmt: 格式，默认 "%Y-%m-%d"
        
        返回:
            日期字符串
        """
        fmt = fmt or cls.DATE_FORMAT
        return dt.strftime(fmt)
    
    @classmethod
    def is_valid(cls, date_str: str) -> bool:
        """
        验证日期字符串是否有效
        
        参数:
            date_str: 日期字符串
        
        返回:
            True/False
        """
        try:
            datetime.strptime(date_str, cls.DATE_FORMAT)
            return True
        except ValueError:
            return False
    
    @classmethod
    def start_of_day(cls, date_str: str) -> str:
        """
        获取日期开始时间
        
        参数:
            date_str: 日期字符串
        
        返回:
            "2026-03-10 00:00:00"
        """
        return f"{date_str} 00:00:00"
    
    @classmethod
    def end_of_day(cls, date_str: str) -> str:
        """
        获取日期结束时间
        
        参数:
            date_str: 日期字符串
        
        返回:
            "2026-03-10 23:59:59"
        """
        return f"{date_str} 23:59:59"


# =========================
# 使用示例
# =========================

if __name__ == "__main__":
    print("=" * 60)
    print("日期工具类示例")
    print("=" * 60)
    
    # 1. 获取今日
    today = DateUtils.today()
    print(f"\n1. 今日日期：{today}")
    
    # 2. 日期计算
    tomorrow = DateUtils.add_days(today, 1)
    yesterday = DateUtils.add_days(today, -1)
    print(f"\n2. 日期计算:")
    print(f"   昨日：{yesterday}")
    print(f"   今日：{today}")
    print(f"   明日：{tomorrow}")
    
    # 3. 计算天数差
    future = DateUtils.add_days(today, 10)
    days = DateUtils.diff_days(today, future)
    print(f"\n3. 天数差:")
    print(f"   {today} 到 {future}: {days} 天")
    
    # 4. day 编号与日期互转
    day = DateUtils.to_day_number(today)
    date = DateUtils.from_day_number(day)
    print(f"\n4. day 编号与日期互转:")
    print(f"   日期 {today} → day 编号 {day}")
    print(f"   day 编号 {day} → 日期 {date}")
    
    # 5. 验证日期
    valid = DateUtils.is_valid("2026-03-10")
    invalid = DateUtils.is_valid("2026-13-40")
    print(f"\n5. 日期验证:")
    print(f"   '2026-03-10' 有效：{valid}")
    print(f"   '2026-13-40' 有效：{invalid}")
    
    print("\n" + "=" * 60)
