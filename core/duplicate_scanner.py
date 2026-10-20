"""
C盘清理工具 - 重复文件扫描引擎
基于文件大小 + MD5 哈希的两阶段检测
"""

import os
import hashlib
from dataclasses import dataclass, field
from typing import List, Callable, Optional, Dict

from config import DEFAULT_DUPLICATE_THRESHOLD_MB
from core.scanner import SafetyGuard, ScanResult
from core.utils import get_file_size_safe


SAFE_USER_DIRS = [
    "Desktop", "Downloads", "Documents", "Pictures", "Videos", "Music",
]
RISKY_EXTENSIONS = {
    ".exe", ".dll", ".sys", ".drv", ".msi", ".bat", ".cmd", ".ps1",
}


def _is_safe_to_delete(filepath: str) -> bool:
    """判断文件是否可以放心删除（在个人目录中且非可执行文件）"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext in RISKY_EXTENSIONS:
        return False
    path_lower = filepath.lower()
    if "appdata" in path_lower:
        return False
    for dirname in SAFE_USER_DIRS:
        if dirname.lower() in path_lower:
            return True
    return False


@dataclass
class DuplicateGroup:
    """一组重复文件"""
    files: List[ScanResult]
    hash_value: str
    file_size: int = 0
    waste: int = 0
    safe_files: List[ScanResult] = field(default_factory=list)

    def compute_waste(self):
        if self.files:
            self.file_size = self.files[0].size
            self.waste = self.file_size * (len(self.files) - 1)
            self.safe_files = [f for f in self.files[1:] if _is_safe_to_delete(f.path)]


@dataclass
class DuplicateReport:
    """重复文件扫描报告"""
    groups: List[DuplicateGroup] = field(default_factory=list)
    total_waste: int = 0
    total_files_scanned: int = 0
    total_groups: int = 0

    def add_group(self, group: DuplicateGroup):
        group.compute_waste()
        self.groups.append(group)
        self.total_waste += group.waste
        self.total_groups += 1


class DuplicateScanner:
    """重复文件扫描器 — 两阶段检测：文件大小 → MD5 哈希"""

    def __init__(self, threshold_mb: int = DEFAULT_DUPLICATE_THRESHOLD_MB):
        self.safety = SafetyGuard()
        self.threshold_bytes = threshold_mb * 1024 * 1024

    def scan(
        self,
        scan_dirs: Optional[List[str]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> DuplicateReport:
        report = DuplicateReport()
        dirs = scan_dirs or ["C:\\Users"]

        # 阶段1: 收集所有符合条件的文件
        if progress_callback:
            progress_callback(0.0, "阶段 1/3: 正在收集文件...", 0)
        all_files = self._collect_files(dirs, progress_callback)
        report.total_files_scanned = len(all_files)

        # 阶段2: 按文件大小分组
        if progress_callback:
            progress_callback(0.3, "阶段 2/3: 正在按大小分组...", 0)
        size_groups = self._group_by_size(all_files)

        # 阶段3: 对同大小文件计算哈希
        candidates = []
        for group in size_groups.values():
            candidates.extend(group)
        total_candidates = len(candidates)

        if progress_callback:
            progress_callback(0.5, f"阶段 3/3: 正在计算哈希（{total_candidates} 个候选文件）...", 0)
        hash_groups = self._group_by_hash(candidates, total_candidates, progress_callback)

        for hash_val, files in hash_groups.items():
            if len(files) >= 2:
                group = DuplicateGroup(files=list(files), hash_value=hash_val)
                report.add_group(group)

        report.groups.sort(key=lambda g: g.waste, reverse=True)

        if progress_callback:
            progress_callback(
                1.0,
                f"扫描完成，发现 {report.total_groups} 组重复文件",
                report.total_groups,
            )
        return report

    def _collect_files(
        self, dirs: List[str], progress_callback: Optional[Callable]
    ) -> List[ScanResult]:
        all_dirs = []
        for d in dirs:
            if not os.path.isdir(d):
                continue
            all_dirs.extend(self._collect_subdirs(d))

        files = []
        total = len(all_dirs) or 1
        for idx, dir_path in enumerate(all_dirs):
            if progress_callback and idx % 30 == 0:
                progress_callback(
                    0.3 * (idx / total),
                    f"阶段 1/3: 正在扫描 {dir_path}",
                    0,
                )
            try:
                for filename in os.listdir(dir_path):
                    filepath = os.path.join(dir_path, filename)
                    if self.safety.should_skip(filepath):
                        continue
                    if os.path.isfile(filepath):
                        size = get_file_size_safe(filepath)
                        if size >= self.threshold_bytes:
                            result = ScanResult(path=filepath, size=size, category="重复文件")
                            result.compute_last_used()
                            files.append(result)
            except (PermissionError, FileNotFoundError, OSError):
                pass
        return files

    def _collect_subdirs(self, base_dir: str) -> List[str]:
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

    def _group_by_size(self, files: List[ScanResult]) -> Dict[int, List[ScanResult]]:
        groups: Dict[int, List[ScanResult]] = {}
        for f in files:
            groups.setdefault(f.size, []).append(f)
        return {size: group for size, group in groups.items() if len(group) >= 2}

    def _group_by_hash(
        self,
        files: List[ScanResult],
        total: int,
        progress_callback: Optional[Callable],
    ) -> Dict[str, List[ScanResult]]:
        groups: Dict[str, List[ScanResult]] = {}
        for idx, f in enumerate(files):
            if progress_callback and idx % 10 == 0:
                ratio = 0.5 + 0.5 * (idx / max(total, 1))
                progress_callback(ratio, f"阶段 3/3: 哈希计算 {idx}/{total}", 0)
            try:
                hash_val = self._compute_md5(f.path)
                groups.setdefault(hash_val, []).append(f)
            except (PermissionError, OSError):
                pass
        return groups

    def _compute_md5(self, filepath: str) -> str:
        h = hashlib.md5()
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
