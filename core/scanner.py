"""
C盘清理工具 - 文件扫描引擎
负责扫描临时文件、大文件等，严格遵循安全排除列表
"""

import os
import time
import fnmatch
from dataclasses import dataclass, field
from typing import List, Callable, Optional

from config import (
    TEMP_SCAN_TARGETS,
    BROWSER_CACHE_DIRS,
    PROTECTED_SYSTEM_DIRS,
    PROTECTED_USER_DIRS,
    SENSITIVE_FILE_PATTERNS,
    LARGE_FILE_THRESHOLD_MB,
    DEFAULT_SCAN_DIRS,
    SAFE_TO_CLEAN_EXTENSIONS,
    NOT_RECOMMENDED_EXTENSIONS,
    SAFE_TO_CLEAN_CATEGORIES,
)
from core.utils import get_file_size_safe


@dataclass
class ScanResult:
    """单个扫描结果"""
    path: str
    size: int
    category: str
    is_safe: bool = True
    last_used: str = ""
    suggestion: str = "建议清理"

    def compute_suggestion(self):
        """根据文件类型和分类计算清理建议"""
        ext = os.path.splitext(self.path)[1].lower()
        if self.category in SAFE_TO_CLEAN_CATEGORIES:
            self.suggestion = "建议清理"
            self.is_safe = True
        elif ext in NOT_RECOMMENDED_EXTENSIONS:
            self.suggestion = "不建议删除"
            self.is_safe = False
        elif ext in SAFE_TO_CLEAN_EXTENSIONS:
            self.suggestion = "建议清理"
            self.is_safe = True
        else:
            self.suggestion = "可酌情清理"
            self.is_safe = True

    def compute_last_used(self):
        """获取文件最后访问时间"""
        try:
            mtime = os.path.getmtime(self.path)
            self.last_used = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
        except OSError:
            self.last_used = "未知"


@dataclass
class ScanReport:
    """扫描报告汇总"""
    results: List[ScanResult] = field(default_factory=list)
    total_size: int = 0
    total_count: int = 0

    def add(self, result: ScanResult):
        self.results.append(result)
        self.total_size += result.size
        self.total_count += 1


class SafetyGuard:
    """安全守卫 — 确保扫描和删除不会触及受保护的路径和文件"""

    def __init__(self):
        self._protected_dirs = [
            os.path.normcase(d) for d in PROTECTED_SYSTEM_DIRS
        ]
        self._protected_user_snippets = PROTECTED_USER_DIRS
        self._sensitive_patterns = SENSITIVE_FILE_PATTERNS

    def is_path_protected(self, path: str) -> bool:
        """检查路径是否在系统保护列表中"""
        normalized = os.path.normcase(os.path.abspath(path))
        for protected in self._protected_dirs:
            protected_norm = os.path.normcase(protected)
            if normalized == protected_norm or normalized.startswith(protected_norm + os.sep):
                return True
        return False

    def contains_sensitive_snippet(self, path: str) -> bool:
        """检查路径是否包含用户隐私敏感目录片段"""
        normalized = os.path.normcase(path)
        for snippet in self._protected_user_snippets:
            if os.path.normcase(snippet) in normalized:
                return True
        return False

    def is_sensitive_file(self, filename: str) -> bool:
        """检查文件名是否匹配敏感文件模式（密钥、证书等）"""
        for pattern in self._sensitive_patterns:
            if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                return True
        return False

    def should_skip(self, path: str) -> bool:
        """综合判断：该路径是否应被跳过"""
        if self.is_path_protected(path):
            return True
        if self.contains_sensitive_snippet(path):
            return True
        if os.path.isfile(path) and self.is_sensitive_file(os.path.basename(path)):
            return True
        return False


class TempFileScanner:
    """临时文件扫描器"""

    def __init__(self):
        self.safety = SafetyGuard()

    def scan(self, progress_callback: Optional[Callable] = None) -> ScanReport:
        """扫描所有临时文件目录，返回扫描报告"""
        report = ScanReport()
        scan_dirs = {}

        for name, path in TEMP_SCAN_TARGETS.items():
            if path and os.path.isdir(path):
                scan_dirs[f"系统临时文件({name})"] = path

        for name, path in BROWSER_CACHE_DIRS.items():
            if path and os.path.isdir(path):
                scan_dirs[f"浏览器缓存({name})"] = path

        all_tasks = []
        for category, base_dir in scan_dirs.items():
            dirs = self._collect_subdirs(base_dir)
            all_tasks.extend([(d, category) for d in dirs])

        total = len(all_tasks) or 1
        for idx, (dir_path, category) in enumerate(all_tasks):
            if progress_callback and idx % 20 == 0:
                progress_callback(idx / total, f"正在扫描: {dir_path}", len(report.results))
            self._scan_directory_impl(dir_path, report, category=category)

        if progress_callback:
            progress_callback(1.0, f"扫描完成，共发现 {len(report.results)} 个文件", len(report.results))
        return report

    def _collect_subdirs(self, base_dir: str) -> List[str]:
        """收集目录及其所有子目录列表"""
        dirs = [base_dir]
        try:
            for root, subdirs, _ in os.walk(base_dir):
                if self.safety.should_skip(root):
                    subdirs.clear()
                    continue
                for d in subdirs:
                    full = os.path.join(root, d)
                    if not self.safety.should_skip(full):
                        dirs.append(full)
        except (PermissionError, FileNotFoundError, OSError):
            pass
        return dirs

    def _scan_directory_impl(self, base_dir: str, report: ScanReport, category: str = "临时文件"):
        """扫描单个目录中的文件"""
        try:
            for filename in os.listdir(base_dir):
                filepath = os.path.join(base_dir, filename)
                if self.safety.should_skip(filepath):
                    continue
                if os.path.isfile(filepath):
                    size = get_file_size_safe(filepath)
                    result = ScanResult(path=filepath, size=size, category=category)
                    result.compute_suggestion()
                    result.compute_last_used()
                    report.add(result)
        except (PermissionError, FileNotFoundError, OSError):
            pass


class LargeFileScanner:
    """大文件扫描器"""

    def __init__(self, threshold_mb: int = LARGE_FILE_THRESHOLD_MB):
        self.safety = SafetyGuard()
        self.threshold_bytes = threshold_mb * 1024 * 1024

    def scan(
        self,
        scan_dirs: Optional[List[str]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> ScanReport:
        """扫描指定目录中的大文件"""
        report = ScanReport()
        dirs_to_scan = scan_dirs or DEFAULT_SCAN_DIRS

        all_dirs = []
        for base_dir in dirs_to_scan:
            if not os.path.isdir(base_dir):
                continue
            all_dirs.extend(self._collect_subdirs(base_dir))

        total = len(all_dirs) or 1
        for idx, dir_path in enumerate(all_dirs):
            if progress_callback and idx % 20 == 0:
                progress_callback(idx / total, f"正在扫描: {dir_path}", len(report.results))
            self._scan_directory_impl(dir_path, report)

        report.results.sort(key=lambda r: r.size, reverse=True)

        if progress_callback:
            progress_callback(1.0, f"扫描完成，共发现 {len(report.results)} 个大文件", len(report.results))
        return report

    def _collect_subdirs(self, base_dir: str) -> List[str]:
        """收集目录及其所有子目录列表"""
        dirs = [base_dir]
        try:
            for root, subdirs, _ in os.walk(base_dir):
                if self.safety.should_skip(root):
                    subdirs.clear()
                    continue
                for d in subdirs:
                    full = os.path.join(root, d)
                    if not self.safety.should_skip(full):
                        dirs.append(full)
        except (PermissionError, FileNotFoundError, OSError):
            pass
        return dirs

    def _scan_directory_impl(self, base_dir: str, report: ScanReport):
        """扫描单个目录中的大文件"""
        try:
            for filename in os.listdir(base_dir):
                filepath = os.path.join(base_dir, filename)
                if self.safety.should_skip(filepath):
                    continue
                if os.path.isfile(filepath):
                    size = get_file_size_safe(filepath)
                    if size >= self.threshold_bytes:
                        result = ScanResult(path=filepath, size=size, category="大文件")
                        result.compute_suggestion()
                        result.compute_last_used()
                        report.add(result)
        except (PermissionError, FileNotFoundError, OSError):
            pass
