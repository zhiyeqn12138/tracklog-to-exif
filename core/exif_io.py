"""
EXIF 读写模块
读取照片的GPS信息和拍摄时间，写入GPS信息到照片
"""
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path
import piexif
from PIL import Image
import warnings

# 提高PIL的图像大小限制，避免DecompressionBombWarning
# 设置为200MP（2亿像素），足够处理绝大多数照片
Image.MAX_IMAGE_PIXELS = 200000000

# 抑制DecompressionBombWarning警告（可选）
# warnings.filterwarnings('ignore', category=Image.DecompressionBombWarning)


def read_exif_info(image_path: str) -> Tuple[bool, Optional[datetime]]:
    """
    读取照片的GPS信息和拍摄时间
    
    Args:
        image_path: 照片路径
        
    Returns:
        (has_gps, datetime_utc) 
        - has_gps: 是否已有GPS信息
        - datetime_utc: 拍摄时间（naive datetime，本地时间），如果读取不到返回None
        
    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件不是有效的图片格式
    """
    # 检查文件是否存在
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"照片文件不存在: {image_path}")
    
    if not path.is_file():
        raise ValueError(f"路径不是文件: {image_path}")
    
    try:
        exif_dict = piexif.load(str(image_path))
        
        # 检查是否有GPS信息
        # GPS信息需要包含经纬度
        has_gps = False
        if 'GPS' in exif_dict and exif_dict['GPS']:
            gps = exif_dict['GPS']
            has_gps = (
                piexif.GPSIFD.GPSLatitude in gps and
                piexif.GPSIFD.GPSLongitude in gps and
                piexif.GPSIFD.GPSLatitudeRef in gps and
                piexif.GPSIFD.GPSLongitudeRef in gps
            )
        
        # 读取拍摄时间（多级回退：DateTimeOriginal -> DateTimeDigitized -> DateTime）
        datetime_utc = None
        if 'Exif' in exif_dict:
            exif = exif_dict['Exif']
            # DateTimeOriginal (36867) - 优先使用
            if piexif.ExifIFD.DateTimeOriginal in exif:
                try:
                    dt_str = exif[piexif.ExifIFD.DateTimeOriginal]
                    if isinstance(dt_str, bytes):
                        dt_str = dt_str.decode('utf-8')
                    datetime_utc = _parse_exif_datetime(dt_str)
                except Exception:
                    pass
            
            # DateTimeDigitized (36868) - 如果DateTimeOriginal不存在
            if datetime_utc is None and piexif.ExifIFD.DateTimeDigitized in exif:
                try:
                    dt_str = exif[piexif.ExifIFD.DateTimeDigitized]
                    if isinstance(dt_str, bytes):
                        dt_str = dt_str.decode('utf-8')
                    datetime_utc = _parse_exif_datetime(dt_str)
                except Exception:
                    pass
        
        # 如果Exif中没有，尝试0th IFD中的DateTime (306)
        if datetime_utc is None and '0th' in exif_dict:
            if piexif.ImageIFD.DateTime in exif_dict['0th']:
                try:
                    dt_str = exif_dict['0th'][piexif.ImageIFD.DateTime]
                    if isinstance(dt_str, bytes):
                        dt_str = dt_str.decode('utf-8')
                    datetime_utc = _parse_exif_datetime(dt_str)
                except Exception:
                    pass
        
        return has_gps, datetime_utc
        
    except piexif.InvalidImageDataError:
        # EXIF数据损坏
        return False, None
    except Exception as e:
        # 其他错误（如文件格式不支持）
        return False, None


def _parse_exif_datetime(dt_str: str) -> Optional[datetime]:
    """
    解析EXIF时间字符串为UTC datetime
    EXIF时间格式通常是 "YYYY:MM:DD HH:MM:SS"（本地时间）
    这里先返回naive datetime，后续在匹配时根据时区转换
    """
    try:
        # EXIF格式: "YYYY:MM:DD HH:MM:SS"
        dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
        return dt
    except Exception:
        return None


def write_gps_to_copy(src_path: str, dst_path: str, lat: float, lon: float) -> bool:
    """
    将GPS信息写入照片副本
    
    Args:
        src_path: 源照片路径
        dst_path: 目标照片路径（副本）
        lat: 纬度（-90到90）
        lon: 经度（-180到180）
        
    Returns:
        是否成功
        
    Raises:
        FileNotFoundError: 源文件不存在
        ValueError: 经纬度超出范围或路径无效
        PermissionError: 目标目录无写权限
    """
    # 验证经纬度范围
    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"纬度超出有效范围 [-90, 90]: {lat}")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(f"经度超出有效范围 [-180, 180]: {lon}")
    
    # 检查源文件
    src = Path(src_path)
    if not src.exists():
        raise FileNotFoundError(f"源照片文件不存在: {src_path}")
    if not src.is_file():
        raise ValueError(f"源路径不是文件: {src_path}")
    
    # 确保目标目录存在
    dst = Path(dst_path)
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        raise PermissionError(f"无法创建目标目录（无写权限）: {dst.parent}")
    except Exception as e:
        raise ValueError(f"目标路径无效: {dst_path}, 错误: {e}")
    
    try:
        # 读取现有EXIF（如果文件没有EXIF，会返回空字典）
        try:
            exif_dict = piexif.load(str(src_path))
        except piexif.InvalidImageDataError:
            # 文件没有EXIF或EXIF损坏，创建新的EXIF字典
            exif_dict = {'0th': {}, 'Exif': {}, 'GPS': {}, '1st': {}, 'thumbnail': None}
        except Exception:
            # 其他错误，也创建新的EXIF字典
            exif_dict = {'0th': {}, 'Exif': {}, 'GPS': {}, '1st': {}, 'thumbnail': None}
        
        # 准备GPS数据
        # GPS纬度：度分秒格式
        lat_ref = 'N' if lat >= 0 else 'S'
        lat_deg = abs(lat)
        lat_d = int(lat_deg)
        lat_m = int((lat_deg - lat_d) * 60)
        lat_s = ((lat_deg - lat_d) * 60 - lat_m) * 60
        
        # GPS经度：度分秒格式
        lon_ref = 'E' if lon >= 0 else 'W'
        lon_deg = abs(lon)
        lon_d = int(lon_deg)
        lon_m = int((lon_deg - lon_d) * 60)
        lon_s = ((lon_deg - lon_d) * 60 - lon_m) * 60
        
        # 构建GPS字典
        gps_ifd = {
            piexif.GPSIFD.GPSLatitudeRef: lat_ref.encode('ascii'),
            piexif.GPSIFD.GPSLatitude: ((lat_d, 1), (lat_m, 1), (int(lat_s * 1000), 1000)),
            piexif.GPSIFD.GPSLongitudeRef: lon_ref.encode('ascii'),
            piexif.GPSIFD.GPSLongitude: ((lon_d, 1), (lon_m, 1), (int(lon_s * 1000), 1000)),
        }
        
        exif_dict['GPS'] = gps_ifd
        
        # 将EXIF数据转换为字节
        exif_bytes = piexif.dump(exif_dict)
        
        # 复制图片并写入EXIF
        try:
            img = Image.open(src_path)
            # 确保图片是RGB模式（某些格式需要转换）
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            img.save(dst_path, exif=exif_bytes, quality=95)
            return True
        except Exception as e:
            # 图片格式不支持或保存失败
            return False
        
    except (FileNotFoundError, ValueError, PermissionError):
        # 重新抛出这些明确的异常
        raise
    except Exception:
        # 其他错误返回False
        return False


def write_gps_inplace(image_path: str, lat: float, lon: float) -> bool:
    """
    直接修改照片文件，写入GPS信息（覆盖原文件）
    
    Args:
        image_path: 照片路径（将被直接修改）
        lat: 纬度 [-90, 90]
        lon: 经度 [-180, 180]
        
    Returns:
        是否成功
        
    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 经纬度超出范围或路径无效
        PermissionError: 无写权限
    """
    # 使用临时文件方式：先写入临时文件，成功后替换原文件
    import tempfile
    import shutil
    
    # 创建临时文件
    temp_fd, temp_path = tempfile.mkstemp(suffix='.jpg', dir=Path(image_path).parent)
    try:
        # 关闭文件描述符
        import os
        os.close(temp_fd)
        
        # 写入临时文件
        success = write_gps_to_copy(image_path, temp_path, lat, lon)
        
        if success:
            # 替换原文件
            shutil.move(temp_path, image_path)
            return True
        else:
            # 删除临时文件
            Path(temp_path).unlink(missing_ok=True)
            return False
    except Exception:
        # 清理临时文件
        Path(temp_path).unlink(missing_ok=True)
        raise

