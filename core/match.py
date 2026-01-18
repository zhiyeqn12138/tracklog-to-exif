"""
匹配算法模块
根据时间将照片与轨迹点进行匹配
"""
import bisect
import math
from datetime import datetime, timedelta
from typing import List, Optional, Callable
from pathlib import Path
from .models import PhotoItem, TrackPoint, MatchItem, MATCH_STATUS_MATCHED, MATCH_STATUS_TOO_FAR


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    使用Haversine公式计算两个GPS坐标之间的距离（米）
    
    Args:
        lat1, lon1: 第一个点的纬度和经度
        lat2, lon2: 第二个点的纬度和经度
        
    Returns:
        距离（米）
    """
    # 地球平均半径（公里）
    R = 6371.0
    
    # 转换为弧度
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    # Haversine公式
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    distance_km = R * c
    # 转换为米
    distance_m = distance_km * 1000
    return distance_m


def match_photos_to_track(
    photos: List[PhotoItem],
    track_points: List[TrackPoint],
    photo_tz_offset: float = 8.0,
    camera_offset_sec: float = 0.0,
    max_error_sec: float = 120.0,
    method: str = 'interp',
    max_distance_m: Optional[float] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None
) -> List[MatchItem]:
    """
    将照片与轨迹点进行时间匹配
    
    Args:
        photos: 待处理照片列表
        track_points: 轨迹点列表（已按时间排序）
        photo_tz_offset: 照片时区偏移（小时），默认+8（东八区）
        camera_offset_sec: 相机时间偏移（秒），默认0
        max_error_sec: 最大允许误差（秒），默认120
        method: 匹配模式，'nearest' 或 'interp'（默认插值）
        max_distance_m: 插值模式下，两点间最大距离（米），None表示不限制
        on_progress: 进度回调函数 (done, total, message)，可选
        
    Returns:
        匹配结果列表
        
    Raises:
        ValueError: 轨迹点列表为空或参数无效
    """
    if not track_points:
        raise ValueError("轨迹点列表为空，无法进行匹配")
    
    if method not in ('nearest', 'interp'):
        raise ValueError(f"无效的匹配模式: {method}，必须是 'nearest' 或 'interp'")
    
    # 提取时间列表用于二分查找
    track_times = [p.t_utc for p in track_points]
    
    match_results = []
    total = len(photos)
    
    if on_progress:
        on_progress(0, total, "开始匹配照片与轨迹...")
    
    for idx, photo in enumerate(photos, 1):
        if on_progress and idx % 100 == 0:
            on_progress(idx, total, f"匹配第 {idx}/{total} 张照片...")
        
        if photo.status != 'need_process' or photo.datetime_utc is None:
            # 不是待处理照片，直接标记
            match_results.append(MatchItem(
                photo_path=photo.path,
                lat=None,
                lon=None,
                error_sec=None,
                method=None,
                status=photo.status,
                reason=None
            ))
            continue
        
        # 将照片时间转换为UTC
        # EXIF时间通常是本地时间，需要根据时区转换
        photo_dt_utc = _convert_photo_time_to_utc(
            photo.datetime_utc,
            photo_tz_offset,
            camera_offset_sec
        )
        
        # 使用二分查找找到最近的点
        idx = bisect.bisect_left(track_times, photo_dt_utc)
        
        # 确定相邻的两个轨迹点
        if idx == 0:
            # 照片时间早于所有轨迹点
            nearest_point = track_points[0]
            error_sec = abs((photo_dt_utc - nearest_point.t_utc).total_seconds())
            
            if error_sec > max_error_sec:
                match_results.append(MatchItem(
                    photo_path=photo.path,
                    lat=None,
                    lon=None,
                    error_sec=error_sec,
                    method=None,
                    status='too_far',
                    reason=f"照片时间早于轨迹起点，误差{error_sec:.1f}秒"
                ))
            else:
                lat, lon = nearest_point.lat, nearest_point.lon
                match_results.append(MatchItem(
                    photo_path=photo.path,
                    lat=lat,
                    lon=lon,
                    error_sec=error_sec,
                    method='nearest',
                    status='matched',
                    reason=None
                ))
                
        elif idx >= len(track_points):
            # 照片时间晚于所有轨迹点
            nearest_point = track_points[-1]
            error_sec = abs((photo_dt_utc - nearest_point.t_utc).total_seconds())
            
            if error_sec > max_error_sec:
                match_results.append(MatchItem(
                    photo_path=photo.path,
                    lat=None,
                    lon=None,
                    error_sec=error_sec,
                    method=None,
                    status='too_far',
                    reason=f"照片时间晚于轨迹终点，误差{error_sec:.1f}秒"
                ))
            else:
                lat, lon = nearest_point.lat, nearest_point.lon
                match_results.append(MatchItem(
                    photo_path=photo.path,
                    lat=lat,
                    lon=lon,
                    error_sec=error_sec,
                    method='nearest',
                    status='matched',
                    reason=None
                ))
        else:
            # 照片时间在两个轨迹点之间
            point_before = track_points[idx - 1]
            point_after = track_points[idx]
            
            if method == 'nearest':
                # 最近点模式
                error_before = abs((photo_dt_utc - point_before.t_utc).total_seconds())
                error_after = abs((photo_dt_utc - point_after.t_utc).total_seconds())
                
                if error_before < error_after:
                    nearest_point = point_before
                    error_sec = error_before
                else:
                    nearest_point = point_after
                    error_sec = error_after
                
                if error_sec > max_error_sec:
                    match_results.append(MatchItem(
                        photo_path=photo.path,
                        lat=None,
                        lon=None,
                        error_sec=error_sec,
                        method=None,
                        status='too_far',
                        reason=f"最近点误差{error_sec:.1f}秒超过阈值"
                    ))
                else:
                    lat, lon = nearest_point.lat, nearest_point.lon
                    match_results.append(MatchItem(
                        photo_path=photo.path,
                        lat=lat,
                        lon=lon,
                        error_sec=error_sec,
                        method='nearest',
                        status='matched',
                        reason=None
                    ))
            else:
                # 插值模式（默认）
                t_before = point_before.t_utc
                t_after = point_after.t_utc
                total_span = (t_after - t_before).total_seconds()
                
                # 检查两点间距离（如果启用了距离过滤）
                if max_distance_m is not None:
                    distance_m = calculate_distance(
                        point_before.lat, point_before.lon,
                        point_after.lat, point_after.lon
                    )
                    
                    if distance_m > max_distance_m:
                        # 两点距离过大，降级为最近点模式
                        error_before = abs((photo_dt_utc - point_before.t_utc).total_seconds())
                        error_after = abs((photo_dt_utc - point_after.t_utc).total_seconds())
                        
                        if error_before < error_after:
                            nearest_point = point_before
                            error_sec = error_before
                        else:
                            nearest_point = point_after
                            error_sec = error_after
                        
                        if error_sec > max_error_sec:
                            match_results.append(MatchItem(
                                photo_path=photo.path,
                                lat=None,
                                lon=None,
                                error_sec=error_sec,
                                method=None,
                                status='too_far',
                                reason=f"两点距离{distance_m:.0f}米过大，降级为最近点模式，误差{error_sec:.1f}秒超过阈值"
                            ))
                        else:
                            lat, lon = nearest_point.lat, nearest_point.lon
                            match_results.append(MatchItem(
                                photo_path=photo.path,
                                lat=lat,
                                lon=lon,
                                error_sec=error_sec,
                                method='nearest',
                                status=MATCH_STATUS_MATCHED,
                                reason=f"两点距离{distance_m:.0f}米过大，降级为最近点模式"
                            ))
                        
                        if on_progress:
                            on_progress(i + 1, total, f'匹配: {Path(photo.path).name}')
                        continue
                
                # 进行线性插值计算经纬度
                if total_span == 0:
                    # 两个点时间相同，直接使用前一个点
                    lat, lon = point_before.lat, point_before.lon
                    error_sec = abs((photo_dt_utc - t_before).total_seconds())
                else:
                    ratio = (photo_dt_utc - t_before).total_seconds() / total_span
                    lat = point_before.lat + (point_after.lat - point_before.lat) * ratio
                    lon = point_before.lon + (point_after.lon - point_before.lon) * ratio
                    
                    # 误差取两个相邻点的平均误差
                    error_before = abs((photo_dt_utc - t_before).total_seconds())
                    error_after = abs((photo_dt_utc - t_after).total_seconds())
                    error_sec = min(error_before, error_after)
                
                if error_sec > max_error_sec:
                    match_results.append(MatchItem(
                        photo_path=photo.path,
                        lat=None,
                        lon=None,
                        error_sec=error_sec,
                        method=None,
                        status='too_far',
                        reason=f"插值误差{error_sec:.1f}秒超过阈值"
                    ))
                else:
                    match_results.append(MatchItem(
                        photo_path=photo.path,
                        lat=lat,
                        lon=lon,
                        error_sec=error_sec,
                        method='interp',
                        status=MATCH_STATUS_MATCHED,
                        reason=None
                    ))
    
    if on_progress:
        matched_count = sum(1 for m in match_results if m.status == MATCH_STATUS_MATCHED)
        on_progress(total, total, f"匹配完成：{matched_count}/{total} 张照片匹配成功")
    
    return match_results


def _convert_photo_time_to_utc(
    photo_dt: datetime,
    tz_offset: float,
    camera_offset_sec: float
) -> datetime:
    """
    将照片时间转换为UTC时间
    
    Args:
        photo_dt: 照片EXIF时间（naive datetime，本地时间）
        tz_offset: 时区偏移（小时）
        camera_offset_sec: 相机时间偏移（秒）
        
    Returns:
        UTC时间（naive datetime）
    """
    from datetime import timezone, timedelta
    
    # 将本地时间转换为UTC
    tz = timezone(timedelta(hours=tz_offset))
    photo_dt_tz = photo_dt.replace(tzinfo=tz)
    photo_dt_utc = photo_dt_tz.astimezone(timezone.utc)
    
    # 应用相机偏移
    if camera_offset_sec != 0:
        photo_dt_utc = photo_dt_utc + timedelta(seconds=camera_offset_sec)
    
    # 返回naive datetime（与轨迹点时间格式一致）
    return photo_dt_utc.replace(tzinfo=None)

