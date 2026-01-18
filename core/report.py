"""
报告导出模块
生成CSV格式的处理报告
"""
import csv
from pathlib import Path
from typing import List
from .models import PhotoItem, MatchItem
from .models import (
    PHOTO_STATUS_ALREADY_GPS,
    PHOTO_STATUS_NO_TIME,
    MATCH_STATUS_MATCHED,
    MATCH_STATUS_UNMATCHED,
    MATCH_STATUS_TOO_FAR,
    MATCH_STATUS_WRITE_FAILED
)


def generate_report(
    already_gps: List[PhotoItem],
    need_process: List[PhotoItem],
    no_time: List[PhotoItem],
    match_results: List[MatchItem],
    report_path: str
) -> dict:
    """
    生成处理报告CSV文件
    
    Args:
        already_gps: 已有GPS的照片列表
        need_process: 待处理照片列表
        no_time: 无时间照片列表
        match_results: 匹配结果列表
        report_path: 报告文件路径
        
    Returns:
        摘要字典
    """
    report_file = Path(report_path)
    report_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 构建匹配结果字典（以照片路径为key）
    match_dict = {m.photo_path: m for m in match_results}
    
    with open(report_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # 写入表头
        writer.writerow([
            'path', 'filename', 'status', 'error_sec', 'lat', 'lon', 'method', 'note'
        ])
        
        # 写入已有GPS的照片
        for photo in already_gps:
            writer.writerow([
                photo.path,
                Path(photo.path).name,
                'already_gps',
                '',
                '',
                '',
                '',
                '照片已包含GPS信息'
            ])
        
        # 写入待处理照片的匹配结果
        for photo in need_process:
            match_item = match_dict.get(photo.path)
            if match_item:
                writer.writerow([
                    photo.path,
                    Path(photo.path).name,
                    match_item.status,
                    f'{match_item.error_sec:.2f}' if match_item.error_sec else '',
                    f'{match_item.lat:.6f}' if match_item.lat else '',
                    f'{match_item.lon:.6f}' if match_item.lon else '',
                    match_item.method or '',
                    match_item.reason or ''
                ])
            else:
                writer.writerow([
                    photo.path,
                    Path(photo.path).name,
                    'unmatched',
                    '',
                    '',
                    '',
                    '',
                    '未找到匹配结果'
                ])
        
        # 写入无时间照片
        for photo in no_time:
            writer.writerow([
                photo.path,
                Path(photo.path).name,
                'no_time',
                '',
                '',
                '',
                '',
                '照片无可用拍摄时间'
            ])
    
    # 计算摘要
    matched_count = sum(1 for m in match_results if m.status == MATCH_STATUS_MATCHED)
    unmatched_count = sum(1 for m in match_results if m.status in [MATCH_STATUS_UNMATCHED, MATCH_STATUS_TOO_FAR])
    write_failed_count = sum(1 for m in match_results if m.status == MATCH_STATUS_WRITE_FAILED)
    
    summary = {
        'total': len(already_gps) + len(need_process) + len(no_time),
        'already_gps': len(already_gps),
        'need_process': len(need_process),
        'no_time': len(no_time),
        'matched': matched_count,
        'unmatched': unmatched_count,
        'write_failed': write_failed_count
    }
    
    return summary

