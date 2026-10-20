"""
C盘清理工具 - 软件卸载管理引擎
扫描已安装软件，识别长期未使用的程序
"""

import os
import time
import winreg
from dataclasses import dataclass
from typing import List, Optional, Callable

from core.utils import get_file_size_safe


UNUSED_THRESHOLD_SECONDS = 180 * 24 * 3600


@dataclass
class SoftwareInfo:
    """单个已安装软件信息"""
    name: str
    version: str = ""
    publisher: str = ""
    install_date: str = ""
    install_location: str = ""
    uninstall_string: str = ""
    estimated_size: int = 0
    last_used_ts: float = 0.0
    is_unused: bool = False
    is_system_component: bool = False

    @property
    def estimated_size_display(self) -> str:
        from core.utils import format_file_size
        return format_file_size(self.estimated_size)

    @property
    def last_used_display(self) -> str:
        if self.last_used_ts <= 0:
            return "未知"
        return time.strftime("%Y-%m-%d", time.localtime(self.last_used_ts))


_REGISTRY_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE,
     r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER,
     r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]

_SYSTEM_PUBLISHER_HINTS = ("microsoft", "windows", "intel", "amd", "nvidia", "realtek")
_SYSTEM_NAME_HINTS = (
    "update for", "security update", "service pack", "visual c++ redistributable",
    "visual c++ ", ".net ", "windows ", "msi ", "microsoft ", "kb",
)


class SoftwareScanner:
    """已安装软件扫描器"""

    def __init__(self):
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def scan_installed(
        self,
        progress_callback: Optional[Callable] = None,
    ) -> List[SoftwareInfo]:
        """枚举已安装软件列表"""
        results: List[SoftwareInfo] = []
        seen_names = set()

        total = len(_REGISTRY_KEYS)
        for idx, (hive, sub_path) in enumerate(_REGISTRY_KEYS):
            if self._stop_requested:
                break
            if progress_callback:
                progress_callback(f"正在读取注册表 ({idx + 1}/{total})", idx / total)
            self._read_registry_key(hive, sub_path, results, seen_names)

        results.sort(key=lambda s: (s.name or "").lower())
        return results

    def detect_unused(
        self,
        software_list: List[SoftwareInfo],
        progress_callback: Optional[Callable] = None,
    ) -> None:
        """对每个软件检测是否超过半年未使用（基于安装目录内文件最新修改时间）"""
        total = len(software_list)
        for idx, sw in enumerate(software_list):
            if self._stop_requested:
                break
            if progress_callback and idx % 5 == 0:
                progress_callback(
                    f"正在分析使用状态 ({idx + 1}/{total}) {sw.name}",
                    idx / total,
                )
            latest_ts = self._get_latest_activity_ts(sw.install_location)
            sw.last_used_ts = latest_ts
            if latest_ts > 0 and (time.time() - latest_ts) > UNUSED_THRESHOLD_SECONDS:
                sw.is_unused = True

        if progress_callback:
            progress_callback("分析完成", 1.0)

    def _read_registry_key(self, hive, sub_path, results, seen_names):
        try:
            with winreg.OpenKey(hive, sub_path) as key:
                count = winreg.QueryInfoKey(key)[0]
                for i in range(count):
                    if self._stop_requested:
                        return
                    try:
                        subname = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subname) as subkey:
                            sw = self._parse_subkey(subkey)
                            if sw and sw.name and sw.name not in seen_names:
                                sw.is_system_component = self._is_system_component(sw)
                                results.append(sw)
                                seen_names.add(sw.name)
                    except (OSError, winreg.error):
                        continue
        except (OSError, winreg.error):
            pass

    @staticmethod
    def _get_value(subkey, name: str) -> str:
        try:
            value, _ = winreg.QueryValueEx(subkey, name)
            return str(value).strip() if value is not None else ""
        except (OSError, winreg.error):
            return ""

    def _parse_subkey(self, subkey) -> Optional[SoftwareInfo]:
        name = self._get_value(subkey, "DisplayName")
        if not name:
            return None
        version = self._get_value(subkey, "DisplayVersion")
        publisher = self._get_value(subkey, "Publisher")
        install_date = self._get_value(subkey, "InstallDate")
        install_location = self._get_value(subkey, "InstallLocation")
        uninstall_string = self._get_value(subkey, "UninstallString")
        display_icon = self._get_value(subkey, "DisplayIcon")
        size_str = self._get_value(subkey, "EstimatedSize")
        try:
            size_kb = int(size_str) if size_str else 0
        except ValueError:
            size_kb = 0

        if not install_location:
            install_location = self._infer_install_dir(display_icon, uninstall_string)

        return SoftwareInfo(
            name=name,
            version=version,
            publisher=publisher,
            install_date=install_date,
            install_location=install_location,
            uninstall_string=uninstall_string,
            estimated_size=size_kb * 1024,
        )

    @staticmethod
    def _is_system_component(sw: SoftwareInfo) -> bool:
        name_l = (sw.name or "").lower()
        pub_l = (sw.publisher or "").lower()
        for hint in _SYSTEM_PUBLISHER_HINTS:
            if hint in pub_l:
                return True
        for hint in _SYSTEM_NAME_HINTS:
            if hint in name_l:
                return True
        return False

    @staticmethod
    def _infer_install_dir(display_icon: str, uninstall_string: str) -> str:
        """从 DisplayIcon 或 UninstallString 反推安装目录"""
        for raw in (display_icon, uninstall_string):
            if not raw:
                continue
            path = raw.strip()
            if not path:
                continue
            if path.startswith("{") and path.endswith("}"):
                continue
            if path.lower().startswith("msiexec"):
                continue
            path = path.strip('"')
            for sep in (",", " ",):
                if sep in path and path.count(sep) == 1 and sep == ",":
                    path = path.split(sep)[0].strip()
                    break
            if path.lower().endswith((".exe", ".msi", ".bat", ".cmd")):
                path = os.path.dirname(path)
            elif "." in os.path.basename(path):
                path = os.path.dirname(path)
            if path and os.path.isdir(path):
                return path
        return ""

    @staticmethod
    def _get_latest_activity_ts(install_location: str) -> float:
        """返回安装目录中文件最新修改时间；若无有效目录返回 0"""
        if not install_location or not os.path.isdir(install_location):
            return 0.0
        latest = 0.0
        scanned = 0
        try:
            for root, _dirs, files in os.walk(install_location):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    try:
                        ts = os.path.getmtime(fpath)
                        if ts > latest:
                            latest = ts
                    except (OSError, PermissionError):
                        pass
                    scanned += 1
                    if scanned > 2000:
                        return latest
                if scanned > 2000:
                    break
        except (OSError, PermissionError):
            pass
        return latest
