"""
扫描照片模块
扫描文件夹内照片并分类：已含GPS、缺GPS且有时间、缺GPS但无时间
"""
from pathlib import Path
from typing import List, Tuple, Optional, Callable
from .models import PhotoItem, PHOTO_STATUS_ALREADY_GPS, PHOTO_STATUS_NEED_PROCESS, PHOTO_STATUS_NO_TIME
from .exif_io import read_exif_info


def scan_photos(
    folder_path: str,
    recursive: bool = False,
    on_progress: Optional[Callable[[int, int, str], None]] = None
) -> Tuple[List[PhotoItem], List[PhotoItem], List[PhotoItem]]:
    """
    扫描照片文件夹并分类
    
    Args:
        folder_path: 照片文件夹路径
        recursive: 是否递归子目录
        on_progress: 进度回调函数 (done, total, current_file)，可选
        
    Returns:
        (already_gps, need_process, no_time) 三个列表
        
    Raises:
        FileNotFoundError: 文件夹不存在
        ValueError: 路径不是目录或无权限访问
        PermissionError: 无权限访问文件夹
    """
    folder = Path(folder_path)
    
    # 验证文件夹
    if not folder.exists():
        raise FileNotFoundError(f"文件夹不存在: {folder_path}")
    
    if not folder.is_dir():
        raise ValueError(f"路径不是目录: {folder_path}")
    
    # 检查读取权限
    try:
        list(folder.iterdir())
    except PermissionError:
        raise PermissionError(f"无权限访问文件夹: {folder_path}")
    except Exception as e:
        raise ValueError(f"无法访问文件夹: {folder_path}, 错误: {e}")
    
    already_gps = []
    need_process = []
    no_time = []
    
    # 支持的扩展名（MVP：仅JPEG）
    extensions = {'.jpg', '.jpeg'}
    
    # 遍历文件
    try:
        if recursive:
            image_files = [f for f in folder.rglob('*') if f.is_file() and f.suffix.lower() in extensions]
        else:
            image_files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in extensions]
    except PermissionError:
        raise PermissionError(f"无权限访问文件夹或其子目录: {folder_path}")
    
    total = len(image_files)
    
    for idx, img_path in enumerate(image_files, 1):
        # 进度回调
        if on_progress:
            on_progress(idx, total, str(img_path))
        
        try:
            has_gps, datetime_utc = read_exif_info(str(img_path))
            
            if has_gps:
                already_gps.append(PhotoItem(
                    path=str(img_path),
                    has_gps=True,
                    datetime_utc=datetime_utc,
                    status=PHOTO_STATUS_ALREADY_GPS
                ))
            elif datetime_utc:
                need_process.append(PhotoItem(
                    path=str(img_path),
                    has_gps=False,
                    datetime_utc=datetime_utc,
                    status=PHOTO_STATUS_NEED_PROCESS
                ))
            else:
                no_time.append(PhotoItem(
                    path=str(img_path),
                    has_gps=False,
                    datetime_utc=None,
                    status=PHOTO_STATUS_NO_TIME
                ))
        except FileNotFoundError:
            # 文件在扫描后被删除，跳过
            continue
        except Exception:
            # 读取失败（EXIF损坏、格式不支持等），归为 no_time
            no_time.append(PhotoItem(
                path=str(img_path),
                has_gps=False,
                datetime_utc=None,
                status=PHOTO_STATUS_NO_TIME
            ))
    
    return already_gps, need_process, no_time

