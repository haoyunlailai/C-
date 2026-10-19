"""
C盘清理工具 - 工具函数模块
"""

import os


def format_file_size(size_bytes: int) -> str:
    """将字节数格式化为人类可读的字符串"""
    if size_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    size = float(size_bytes)
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    return f"{size:.2f} {units[unit_index]}"


def get_file_size_safe(path: str) -> int:
    """安全获取文件大小，遇到权限问题返回0"""
    try:
        return os.path.getsize(path)
    except (OSError, PermissionError):
        return 0


def is_path_accessible(path: str) -> bool:
    """检查路径是否可访问"""
    try:
        os.listdir(path)
        return True
    except (OSError, PermissionError):
        return False
