"""
轨迹解析模块
解析GPX和CSV格式的轨迹文件
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Callable
import gpxpy
import pandas as pd
from dateutil import parser as date_parser
from .models import TrackPoint


def parse_gpx(
    gpx_path: str,
    on_progress: Optional[Callable[[int, int, str], None]] = None
) -> List[TrackPoint]:
    """
    解析GPX文件
    
    Args:
        gpx_path: GPX文件路径
        on_progress: 进度回调函数 (done, total, message)，可选
        
    Returns:
        轨迹点列表（按时间排序）
        
    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件格式错误或无有效轨迹点
    """
    path = Path(gpx_path)
    if not path.exists():
        raise FileNotFoundError(f"GPX文件不存在: {gpx_path}")
    
    if on_progress:
        on_progress(0, 0, "开始解析GPX文件...")
    
    try:
        with open(gpx_path, 'r', encoding='utf-8') as f:
            gpx = gpxpy.parse(f)
    except Exception as e:
        raise ValueError(f"GPX文件格式错误: {e}")
    
    track_points = []
    total_segments = sum(len(track.segments) for track in gpx.tracks)
    processed_segments = 0
    
    for track in gpx.tracks:
        for segment in track.segments:
            processed_segments += 1
            if on_progress:
                on_progress(processed_segments, total_segments, 
                          f"解析第 {processed_segments}/{total_segments} 个轨迹段...")
            
            for point in segment.points:
                if point.time and point.latitude is not None and point.longitude is not None:
                    # 将时间转换为naive datetime（去除时区信息，统一为UTC）
                    if point.time.tzinfo is not None:
                        t_utc = point.time.astimezone(timezone.utc).replace(tzinfo=None)
                    else:
                        # 假设已经是UTC
                        t_utc = point.time
                    
                    track_points.append(TrackPoint(
                        t_utc=t_utc,
                        lat=point.latitude,
                        lon=point.longitude
                    ))
    
    if on_progress:
        on_progress(total_segments, total_segments, "排序轨迹点...")
    
    # 按时间排序
    track_points.sort(key=lambda p: p.t_utc)
    
    # 基础校验
    if not track_points:
        raise ValueError("GPX文件中没有找到有效的轨迹点（需要包含时间、经纬度信息）")
    
    # 检查时间是否递增（允许相同时间）
    for i in range(1, len(track_points)):
        if track_points[i].t_utc < track_points[i-1].t_utc:
            # 时间不递增，重新排序已经修复，但仍然记录警告
            pass
    
    if on_progress:
        on_progress(len(track_points), len(track_points), 
                   f"解析完成：共 {len(track_points)} 个轨迹点")
    
    return track_points


def parse_csv(
    csv_path: str,
    col_map: dict = None,
    time_is_utc: bool = True,
    tz_offset: float = 0,
    time_format: str = 'auto',
    on_progress: Optional[Callable[[int, int, str], None]] = None
) -> List[TrackPoint]:
    """
    解析CSV文件
    
    Args:
        csv_path: CSV文件路径
        col_map: 列名映射，例如 {'time': 'timestamp', 'lat': 'latitude', 'lon': 'longitude'}
                  如果为None，则使用默认列名：time, lat, lon
                  支持"一生足迹"app格式：{'time': 'dataTime', 'lat': 'latitude', 'lon': 'longitude'}
        time_is_utc: 时间列是否为UTC，如果False则根据tz_offset转换
        tz_offset: 时区偏移（小时），例如+8表示东八区
        time_format: 时间格式，'auto'=自动检测，'timestamp'=Unix时间戳（秒），'iso'=ISO格式字符串
        on_progress: 进度回调函数 (done, total, message)，可选
        
    Returns:
        轨迹点列表（按时间排序）
        
    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件格式错误或缺少必需列
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV文件不存在: {csv_path}")
    
    if col_map is None:
        col_map = {'time': 'time', 'lat': 'lat', 'lon': 'lon'}
    
    if on_progress:
        on_progress(0, 0, "开始读取CSV文件...")
    
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        raise ValueError(f"CSV文件格式错误: {e}")
    
    # 检查必需的列
    required_cols = [col_map['time'], col_map['lat'], col_map['lon']]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        available_cols = list(df.columns)
        raise ValueError(
            f"CSV文件缺少必需的列: {missing_cols}\n"
            f"可用的列: {available_cols}\n"
            f"提示：对于'一生足迹'app导出的CSV，请使用列映射: "
            f"{{'time': 'dataTime', 'lat': 'latitude', 'lon': 'longitude'}}"
        )
    
    # 自动检测时间格式
    if time_format == 'auto':
        sample_time = str(df[col_map['time']].iloc[0])
        # 如果是纯数字且长度为10位，可能是Unix时间戳
        if sample_time.isdigit() and len(sample_time) == 10:
            time_format = 'timestamp'
        else:
            time_format = 'iso'
    
    track_points = []
    total_rows = len(df)
    
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        if on_progress and idx % 10000 == 0:
            on_progress(idx, total_rows, f"解析第 {idx}/{total_rows} 行...")
        
        try:
            # 解析时间
            time_value = row[col_map['time']]
            
            if time_format == 'timestamp':
                # Unix时间戳（秒）
                timestamp = int(time_value)
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)
            else:
                # ISO格式或其他字符串格式
                time_str = str(time_value)
                dt = date_parser.parse(time_str)
                
                # 如果解析出的时间有时区信息，转换为UTC
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                elif not time_is_utc:
                    # 如果没有时区信息且不是UTC，根据tz_offset转换
                    from datetime import timedelta
                    tz = timezone(timedelta(hours=tz_offset))
                    dt = dt.replace(tzinfo=tz)
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            
            lat = float(row[col_map['lat']])
            lon = float(row[col_map['lon']])
            
            track_points.append(TrackPoint(
                t_utc=dt,
                lat=lat,
                lon=lon
            ))
        except Exception as e:
            # 跳过无效行
            continue
    
    if on_progress:
        on_progress(total_rows, total_rows, "排序轨迹点...")
    
    # 按时间排序
    track_points.sort(key=lambda p: p.t_utc)
    
    # 基础校验
    if not track_points:
        raise ValueError("CSV文件中没有找到有效的轨迹点")
    
    # 检查时间是否递增（允许相同时间）
    non_increasing_count = 0
    for i in range(1, len(track_points)):
        if track_points[i].t_utc < track_points[i-1].t_utc:
            non_increasing_count += 1
    
    if non_increasing_count > 0:
        # 时间不递增，但排序已经修复，只是记录警告
        pass
    
    if on_progress:
        on_progress(len(track_points), len(track_points),
                   f"解析完成：共 {len(track_points)} 个轨迹点")
    
    return track_points

