"""
配置管理模块
处理应用配置的保存和加载
"""
import json
from pathlib import Path
from typing import Optional, Dict, Any


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_file: str = 'config.json'):
        """
        初始化配置管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config_file = Path(config_file)
        self.config: Dict[str, Any] = {}
    
    def load(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        Returns:
            配置字典
        """
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                return self.config
            except Exception:
                # 配置文件损坏，返回空配置
                self.config = {}
                return self.config
        else:
            # 配置文件不存在，返回空配置
            self.config = {}
            return self.config
    
    def save(self, config: Dict[str, Any]) -> bool:
        """
        保存配置到文件
        
        Args:
            config: 配置字典
            
        Returns:
            是否保存成功
        """
        try:
            self.config = config
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """
        设置配置项并保存
        
        Args:
            key: 配置键
            value: 配置值
            
        Returns:
            是否保存成功
        """
        self.config[key] = value
        return self.save(self.config)
    
    def update(self, config: Dict[str, Any]) -> bool:
        """
        更新多个配置项并保存
        
        Args:
            config: 配置字典
            
        Returns:
            是否保存成功
        """
        self.config.update(config)
        return self.save(self.config)


# 全局配置管理器实例
config_manager = ConfigManager()

