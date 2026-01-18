"""
处理流水线模块
将扫描、匹配、写入、报告串联起来
"""
from typing import Callable, Optional, List
from pathlib import Path
from .models import PhotoItem, TrackPoint, MatchItem
from .models import MATCH_STATUS_MATCHED, MATCH_STATUS_UNMATCHED, MATCH_STATUS_TOO_FAR
from .scan import scan_photos
from .track import parse_gpx, parse_csv
from .match import match_photos_to_track
from .exif_io import write_gps_to_copy, write_gps_inplace
from .report import generate_report as create_report


def process_pipeline(
    folder_path: str,
    track_path: str,
    track_type: str,  # 'gpx' or 'csv'
    output_dir: str = 'output',
    output_mode: str = 'copy',  # 'copy' or 'overwrite'
    generate_report: bool = True,  # 是否生成报告
    recursive: bool = False,
    photo_tz_offset: float = 8.0,
    camera_offset_sec: float = 0.0,
    max_error_sec: float = 120.0,
    match_method: str = 'interp',
    max_distance_m: Optional[float] = None,  # 插值模式下两点间最大距离（米）
    csv_col_map: Optional[dict] = None,
    csv_time_is_utc: bool = True,
    csv_tz_offset: float = 0.0,
    on_progress: Optional[Callable[[str, int, int, str], None]] = None
) -> dict:
    """
    执行完整的处理流水线
    
    Args:
        folder_path: 照片文件夹路径
        track_path: 轨迹文件路径
        track_type: 轨迹类型 'gpx' 或 'csv'
        output_dir: 输出目录（copy模式时使用）
        output_mode: 输出模式 'copy'（创建副本）或 'overwrite'（覆盖原文件）
        generate_report: 是否生成CSV报告
        recursive: 是否递归扫描子目录
        photo_tz_offset: 照片时区偏移（小时）
        camera_offset_sec: 相机时间偏移（秒）
        max_error_sec: 最大允许误差（秒）
        match_method: 匹配模式 'nearest' 或 'interp'
        csv_col_map: CSV列名映射（仅CSV需要）
        csv_time_is_utc: CSV时间是否为UTC（仅CSV需要）
        csv_tz_offset: CSV时区偏移（仅CSV需要）
        on_progress: 进度回调函数 (phase, done, total, message)
        
    Returns:
        处理结果摘要字典
    """
    # 阶段1：扫描照片
    if on_progress:
        on_progress('scanning', 0, 0, '开始扫描照片...')
    
    already_gps, need_process, no_time = scan_photos(folder_path, recursive)
    
    total_photos = len(already_gps) + len(need_process) + len(no_time)
    if on_progress:
        on_progress('scanning', total_photos, total_photos, f'扫描完成：共{total_photos}张照片')
    
    # 阶段2：解析轨迹
    if on_progress:
        on_progress('parsing_track', 0, 0, f'开始解析轨迹文件: {track_path}')
    
    if track_type.lower() == 'gpx':
        track_points = parse_gpx(track_path)
    elif track_type.lower() == 'csv':
        track_points = parse_csv(
            track_path,
            col_map=csv_col_map,
            time_is_utc=csv_time_is_utc,
            tz_offset=csv_tz_offset,
            time_format='auto'  # 自动检测时间格式
        )
    else:
        raise ValueError(f"不支持的轨迹类型: {track_type}")
    
    if on_progress:
        on_progress('parsing_track', len(track_points), len(track_points), 
                   f'轨迹解析完成：共{len(track_points)}个轨迹点')
    
    # 阶段3：匹配
    if on_progress:
        on_progress('matching', 0, len(need_process), '开始匹配照片与轨迹...')
    
    match_results = match_photos_to_track(
        need_process,
        track_points,
        photo_tz_offset,
        camera_offset_sec,
        max_error_sec,
        match_method,
        max_distance_m
    )
    
    if on_progress:
        matched_count = sum(1 for m in match_results if m.status == MATCH_STATUS_MATCHED)
        on_progress('matching', len(need_process), len(need_process),
                   f'匹配完成：{matched_count}/{len(need_process)}张照片匹配成功')
    
    # 阶段4：写入和报告
    if on_progress:
        on_progress('writing', 0, len(match_results), '开始写入GPS信息...')
    
    # 根据输出模式选择不同的写入方式
    if output_mode == 'copy':
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        # overwrite模式：输出路径设为照片所在目录
        output_path = Path(folder_path)
    
    write_success = 0
    write_failed = 0
    
    for i, match_item in enumerate(match_results):
        if match_item.status == MATCH_STATUS_MATCHED and match_item.lat is not None and match_item.lon is not None:
            src_path = Path(match_item.photo_path)
            
            try:
                if output_mode == 'copy':
                    # 创建副本模式：生成输出路径（扁平输出，MVP不保持目录结构）
                    dst_path = output_path / src_path.name
                    if write_gps_to_copy(str(src_path), str(dst_path), match_item.lat, match_item.lon):
                        write_success += 1
                    else:
                        write_failed += 1
                else:
                    # 覆盖模式：直接修改原文件
                    if write_gps_inplace(str(src_path), match_item.lat, match_item.lon):
                        write_success += 1
                    else:
                        write_failed += 1
            except Exception:
                write_failed += 1
        
        if on_progress:
            on_progress('writing', i + 1, len(match_results), 
                      f'正在处理: {Path(match_item.photo_path).name}')
    
    # 生成报告（可选）
    report_path = None
    
    if generate_report:
        if on_progress:
            on_progress('reporting', 0, 0, '正在生成报告...')
        
        report_path = output_path / 'report.csv'
        summary = create_report(
            already_gps,
            need_process,
            no_time,
            match_results,
            str(report_path)
        )
        
        if on_progress:
            on_progress('reporting', 1, 1, f'报告已生成: {report_path}')
    else:
        if on_progress:
            on_progress('reporting', 0, 0, '已跳过报告生成')
    
    # 返回摘要
    return {
        'total': total_photos,
        'already_gps': len(already_gps),
        'need_process': len(need_process),
        'no_time': len(no_time),
        'matched': sum(1 for m in match_results if m.status == MATCH_STATUS_MATCHED),
        'unmatched': sum(1 for m in match_results if m.status in [MATCH_STATUS_UNMATCHED, MATCH_STATUS_TOO_FAR]),
        'write_success': write_success,
        'write_failed': write_failed,
        'output_dir': str(output_path),
        'report_path': str(report_path) if report_path else None
    }

