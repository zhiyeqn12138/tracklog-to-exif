"""
UI状态管理模块
维护全局应用状态
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from pathlib import Path
from core.models import PhotoItem, MatchItem
from core.config import config_manager


@dataclass
class AppState:
    """应用全局状态"""
    # 文件路径
    folder_path: Optional[str] = None
    track_path: Optional[str] = None
    track_type: Optional[str] = None  # 'gpx' or 'csv'
    
    # 参数设置
    photo_tz_offset: float = 8.0
    camera_offset_sec: float = 0.0
    max_error_sec: float = 120.0
    match_method: str = 'interp'  # 'nearest' or 'interp'
    max_distance_m: Optional[float] = None  # 插值模式下两点间最大距离（米），None表示不限制
    recursive: bool = False
    
    # CSV列映射（默认为"一生足迹"格式）
    csv_col_map: Dict[str, str] = field(default_factory=lambda: {
        'time': 'dataTime',
        'lat': 'latitude',
        'lon': 'longitude'
    })
    csv_time_is_utc: bool = True
    csv_tz_offset: float = 0.0
    
    # 扫描结果
    already_gps: List[PhotoItem] = field(default_factory=list)
    need_process: List[PhotoItem] = field(default_factory=list)
    no_time: List[PhotoItem] = field(default_factory=list)
    
    # 匹配结果
    match_results: List[MatchItem] = field(default_factory=list)
    
    # 输出设置
    output_dir: str = 'output'
    output_mode: str = 'copy'  # 'copy' 或 'overwrite'
    generate_report: bool = True  # 是否生成报告
    report_path: Optional[str] = None
    
    # 任务进度
    task_phase: Optional[str] = None  # 'scanning' | 'parsing_track' | 'matching' | 'writing' | 'reporting'
    task_progress: float = 0.0  # 0.0 - 1.0
    task_message: str = ''
    
    def reset_scan_results(self):
        """重置扫描结果"""
        self.already_gps = []
        self.need_process = []
        self.no_time = []
    
    def reset_match_results(self):
        """重置匹配结果"""
        self.match_results = []
    
    def get_scan_summary(self) -> dict:
        """获取扫描结果摘要"""
        return {
            'total': len(self.already_gps) + len(self.need_process) + len(self.no_time),
            'already_gps': len(self.already_gps),
            'need_process': len(self.need_process),
            'no_time': len(self.no_time)
        }
    
    def get_match_summary(self) -> dict:
        """获取匹配结果摘要"""
        matched = sum(1 for m in self.match_results if m.status == 'matched')
        unmatched = sum(1 for m in self.match_results if m.status in ['unmatched', 'too_far'])
        too_far = sum(1 for m in self.match_results if m.status == 'too_far')
        return {
            'matched': matched,
            'unmatched': unmatched,
            'too_far': too_far,
            'total': len(self.match_results)
        }
    
    def load_from_config(self):
        """从配置文件加载状态"""
        config = config_manager.load()
        if config:
            # 加载文件路径
            self.folder_path = config.get('folder_path', self.folder_path)
            self.track_path = config.get('track_path', self.track_path)
            self.track_type = config.get('track_type', self.track_type)
            self.output_dir = config.get('output_dir', self.output_dir)
            self.output_mode = config.get('output_mode', self.output_mode)
            self.generate_report = config.get('generate_report', self.generate_report)
            
            # 加载参数设置
            self.photo_tz_offset = config.get('photo_tz_offset', self.photo_tz_offset)
            self.camera_offset_sec = config.get('camera_offset_sec', self.camera_offset_sec)
            self.max_error_sec = config.get('max_error_sec', self.max_error_sec)
            self.match_method = config.get('match_method', self.match_method)
            self.max_distance_m = config.get('max_distance_m', self.max_distance_m)
            self.recursive = config.get('recursive', self.recursive)
            
            # 加载CSV参数
            self.csv_col_map = config.get('csv_col_map', self.csv_col_map)
            self.csv_time_is_utc = config.get('csv_time_is_utc', self.csv_time_is_utc)
            self.csv_tz_offset = config.get('csv_tz_offset', self.csv_tz_offset)
    
    def save_to_config(self):
        """保存状态到配置文件"""
        config = {
            # 文件路径
            'folder_path': self.folder_path,
            'track_path': self.track_path,
            'track_type': self.track_type,
            'output_dir': self.output_dir,
            'output_mode': self.output_mode,
            'generate_report': self.generate_report,
            
            # 参数设置
            'photo_tz_offset': self.photo_tz_offset,
            'camera_offset_sec': self.camera_offset_sec,
            'max_error_sec': self.max_error_sec,
            'match_method': self.match_method,
            'max_distance_m': self.max_distance_m,
            'recursive': self.recursive,
            
            # CSV参数
            'csv_col_map': self.csv_col_map,
            'csv_time_is_utc': self.csv_time_is_utc,
            'csv_tz_offset': self.csv_tz_offset,
        }
        config_manager.save(config)


# 全局状态实例
app_state = AppState()

# 启动时加载配置
app_state.load_from_config()

