"""
C盘清理工具 - 文件清理执行器
负责安全地删除用户确认的文件
"""

import os
import shutil
from typing import List, Tuple
from dataclasses import dataclass

from core.scanner import ScanResult, SafetyGuard

try:
    import send2trash
    HAS_SEND2TRASH = True
except ImportError:
    HAS_SEND2TRASH = False


@dataclass
class CleanResult:
    """单个文件的清理结果"""
    path: str
    success: bool
    message: str = ""


class FileCleaner:
    """文件清理器 — 将确认后的文件移入回收站"""

    def __init__(self, use_trash: bool = True):
        self.safety = SafetyGuard()
        self.use_trash = use_trash and HAS_SEND2TRASH

    def clean_files(self, files: List[ScanResult]) -> Tuple[List[CleanResult], List[CleanResult]]:
        """
        清理文件列表
        返回: (成功列表, 失败列表)
        """
        succeeded = []
        failed = []

        for file_item in files:
            if self.safety.is_path_protected(file_item.path):
                failed.append(CleanResult(
                    path=file_item.path,
                    success=False,
                    message="受保护的系统路径，已跳过",
                ))
                continue

            result = self._remove_single(file_item.path)
            if result.success:
                succeeded.append(result)
            else:
                failed.append(result)

        return succeeded, failed

    def _remove_single(self, path: str) -> CleanResult:
        """删除单个文件，优先移入回收站，失败则尝试直接删除"""
        if not os.path.exists(path):
            return CleanResult(path=path, success=False, message="文件不存在")

        try:
            if self.use_trash:
                try:
                    send2trash.send2trash(path)
                    return CleanResult(path=path, success=True, message="已移入回收站")
                except Exception:
                    pass

            if os.path.isfile(path) or os.path.islink(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=False)
            return CleanResult(path=path, success=True, message="已删除")

        except PermissionError:
            return CleanResult(path=path, success=False, message="权限不足，无法删除")
        except Exception as e:
            return CleanResult(path=path, success=False, message=str(e))
