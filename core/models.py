"""
数据模型定义
统一全链路使用的数据结构
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from pathlib import Path


# 状态常量定义
PHOTO_STATUS_ALREADY_GPS = 'already_gps'
PHOTO_STATUS_NEED_PROCESS = 'need_process'
PHOTO_STATUS_NO_TIME = 'no_time'

MATCH_STATUS_MATCHED = 'matched'
MATCH_STATUS_UNMATCHED = 'unmatched'
MATCH_STATUS_TOO_FAR = 'too_far'
MATCH_STATUS_ALREADY_GPS = 'already_gps'
MATCH_STATUS_NO_TIME = 'no_time'
MATCH_STATUS_WRITE_FAILED = 'write_failed'

MATCH_METHOD_NEAREST = 'nearest'
MATCH_METHOD_INTERP = 'interp'


@dataclass
class PhotoItem:
    """照片项"""
    path: str
    has_gps: bool
    datetime_utc: Optional[datetime]
    status: str  # 'already_gps' | 'need_process' | 'no_time'
    
    def __post_init__(self):
        """数据验证"""
        # 验证路径
        if not self.path:
            raise ValueError("照片路径不能为空")
        
        # 验证状态
        valid_statuses = {PHOTO_STATUS_ALREADY_GPS, PHOTO_STATUS_NEED_PROCESS, PHOTO_STATUS_NO_TIME}
        if self.status not in valid_statuses:
            raise ValueError(f"无效的状态值: {self.status}，必须是 {valid_statuses} 之一")
        
        # 验证逻辑一致性
        if self.status == PHOTO_STATUS_ALREADY_GPS and not self.has_gps:
            raise ValueError("状态为 already_gps 但 has_gps 为 False")
        if self.status == PHOTO_STATUS_NEED_PROCESS and (self.has_gps or self.datetime_utc is None):
            raise ValueError("状态为 need_process 但 has_gps=True 或 datetime_utc=None")
        if self.status == PHOTO_STATUS_NO_TIME and self.datetime_utc is not None:
            raise ValueError("状态为 no_time 但 datetime_utc 不为 None")
    
    def __repr__(self) -> str:
        """便于调试的字符串表示"""
        filename = Path(self.path).name
        dt_str = self.datetime_utc.strftime("%Y-%m-%d %H:%M:%S") if self.datetime_utc else "None"
        return (f"PhotoItem(path='{filename}', has_gps={self.has_gps}, "
                f"datetime_utc={dt_str}, status='{self.status}')")


@dataclass
class TrackPoint:
    """轨迹点"""
    t_utc: datetime
    lat: float
    lon: float
    
    def __post_init__(self):
        """数据验证"""
        # 验证经纬度范围
        if not (-90.0 <= self.lat <= 90.0):
            raise ValueError(f"纬度超出有效范围 [-90, 90]: {self.lat}")
        if not (-180.0 <= self.lon <= 180.0):
            raise ValueError(f"经度超出有效范围 [-180, 180]: {self.lon}")
        
        # 验证时间
        if not isinstance(self.t_utc, datetime):
            raise ValueError(f"时间必须是 datetime 对象: {type(self.t_utc)}")
    
    def __repr__(self) -> str:
        """便于调试的字符串表示"""
        dt_str = self.t_utc.strftime("%Y-%m-%d %H:%M:%S")
        return (f"TrackPoint(t_utc={dt_str}, lat={self.lat:.6f}, "
                f"lon={self.lon:.6f})")
    
    def __lt__(self, other: 'TrackPoint') -> bool:
        """支持排序"""
        if not isinstance(other, TrackPoint):
            return NotImplemented
        return self.t_utc < other.t_utc


@dataclass
class MatchItem:
    """匹配结果项"""
    photo_path: str
    lat: Optional[float]
    lon: Optional[float]
    error_sec: Optional[float]  # 误差秒数
    method: Optional[str]  # 'nearest' | 'interp'
    status: str  # 'matched' | 'unmatched' | 'too_far' | 'already_gps' | 'no_time' | 'write_failed'
    reason: Optional[str]  # 状态原因说明
    
    def __post_init__(self):
        """数据验证"""
        # 验证路径
        if not self.photo_path:
            raise ValueError("照片路径不能为空")
        
        # 验证状态
        valid_statuses = {
            MATCH_STATUS_MATCHED, MATCH_STATUS_UNMATCHED, MATCH_STATUS_TOO_FAR,
            MATCH_STATUS_ALREADY_GPS, MATCH_STATUS_NO_TIME, MATCH_STATUS_WRITE_FAILED
        }
        if self.status not in valid_statuses:
            raise ValueError(f"无效的状态值: {self.status}，必须是 {valid_statuses} 之一")
        
        # 验证匹配方法
        if self.method is not None:
            valid_methods = {MATCH_METHOD_NEAREST, MATCH_METHOD_INTERP}
            if self.method not in valid_methods:
                raise ValueError(f"无效的匹配方法: {self.method}，必须是 {valid_methods} 之一")
        
        # 验证逻辑一致性
        if self.status == MATCH_STATUS_MATCHED:
            if self.lat is None or self.lon is None:
                raise ValueError("状态为 matched 但 lat 或 lon 为 None")
            if self.method is None:
                raise ValueError("状态为 matched 但 method 为 None")
            # 验证经纬度范围
            if not (-90.0 <= self.lat <= 90.0):
                raise ValueError(f"纬度超出有效范围 [-90, 90]: {self.lat}")
            if not (-180.0 <= self.lon <= 180.0):
                raise ValueError(f"经度超出有效范围 [-180, 180]: {self.lon}")
        elif self.status in {MATCH_STATUS_UNMATCHED, MATCH_STATUS_TOO_FAR}:
            # unmatched 和 too_far 可以有坐标（用于显示），但不强制要求
            if self.lat is not None and not (-90.0 <= self.lat <= 90.0):
                raise ValueError(f"纬度超出有效范围 [-90, 90]: {self.lat}")
            if self.lon is not None and not (-180.0 <= self.lon <= 180.0):
                raise ValueError(f"经度超出有效范围 [-180, 180]: {self.lon}")
    
    def __repr__(self) -> str:
        """便于调试的字符串表示"""
        filename = Path(self.photo_path).name
        lat_str = f"{self.lat:.6f}" if self.lat is not None else "None"
        lon_str = f"{self.lon:.6f}" if self.lon is not None else "None"
        error_str = f"{self.error_sec:.2f}s" if self.error_sec is not None else "None"
        return (f"MatchItem(photo='{filename}', status='{self.status}', "
                f"lat={lat_str}, lon={lon_str}, error={error_str}, "
                f"method={self.method}, reason={self.reason})")

