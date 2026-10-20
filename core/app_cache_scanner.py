"""
C盘清理工具 - 应用缓存扫描引擎
扫描微信、QQ、钉钉、QQ浏览器等应用的缓存文件
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable

from config import APP_CACHE_CONFIG
from core.utils import get_file_size_safe


@dataclass
class CacheCategory:
    """单个缓存分类"""
    name: str
    path: str
    size: int = 0
    file_count: int = 0


@dataclass
class AppCacheInfo:
    """单个应用的缓存信息"""
    app_key: str
    display_name: str
    base_dir: str
    categories: List[CacheCategory] = field(default_factory=list)
    total_size: int = 0
    total_files: int = 0
    is_installed: bool = False

    @property
    def total_size_display(self) -> str:
        from core.utils import format_file_size
        return format_file_size(self.total_size)


class AppCacheScanner:
    """应用缓存扫描器"""

    def __init__(self):
        self.config = APP_CACHE_CONFIG

    def detect_installed_apps(self) -> Dict[str, AppCacheInfo]:
        """检测已安装的应用，返回各应用的缓存信息"""
        results = {}
        for app_key, app_config in self.config.items():
            info = AppCacheInfo(
                app_key=app_key,
                display_name=app_config["display_name"],
                base_dir="",
            )
            for base_dir in app_config["base_dirs"]:
                if os.path.isdir(base_dir):
                    info.base_dir = base_dir
                    info.is_installed = True
                    break
            results[app_key] = info
        return results

    def scan_app_cache(
        self,
        app_key: str,
        progress_callback: Optional[Callable] = None,
    ) -> AppCacheInfo:
        """扫描指定应用的缓存目录"""
        app_config = self.config.get(app_key)
        if not app_config:
            return AppCacheInfo(app_key=app_key, display_name=app_key, base_dir="")

        info = AppCacheInfo(
            app_key=app_key,
            display_name=app_config["display_name"],
            base_dir="",
        )

        base_dir = None
        for d in app_config["base_dirs"]:
            if os.path.isdir(d):
                base_dir = d
                break

        if not base_dir:
            return info

        info.base_dir = base_dir
        info.is_installed = True

        for subdir_rel in app_config["cache_subdirs"]:
            subdir = os.path.join(base_dir, subdir_rel.replace("/", os.sep))
            if not os.path.isdir(subdir):
                continue

            if progress_callback:
                progress_callback(f"正在扫描 {app_config['display_name']} - {subdir_rel}", 0.5)

            cat = CacheCategory(
                name=subdir_rel.split("/")[-1],
                path=subdir,
            )
            self._scan_directory(subdir, cat)
            if cat.size > 0:
                info.categories.append(cat)
                info.total_size += cat.size
                info.total_files += cat.file_count

        return info

    def scan_all(
        self,
        progress_callback: Optional[Callable] = None,
    ) -> Dict[str, AppCacheInfo]:
        """扫描所有已安装应用的缓存"""
        results = {}
        app_keys = list(self.config.keys())
        total = len(app_keys)

        for idx, app_key in enumerate(app_keys):
            app_config = self.config[app_key]
            if progress_callback:
                progress_callback(
                    f"正在检测 {app_config['display_name']}...",
                    idx / total,
                )
            info = self.scan_app_cache(app_key, progress_callback)
            results[app_key] = info

        if progress_callback:
            progress_callback("扫描完成", 1.0)

        return results

    def _scan_directory(self, dir_path: str, cat: CacheCategory):
        """递归扫描目录，统计大小和文件数"""
        try:
            for entry in os.scandir(dir_path):
                try:
                    if entry.is_file(follow_symlinks=False):
                        size = get_file_size_safe(entry.path)
                        cat.size += size
                        cat.file_count += 1
                    elif entry.is_dir(follow_symlinks=False):
                        self._scan_directory(entry.path, cat)
                except (PermissionError, FileNotFoundError, OSError):
                    pass
        except (PermissionError, FileNotFoundError, OSError):
            pass
