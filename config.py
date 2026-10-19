"""
C盘清理工具 - 配置模块
所有扫描路径、安全策略、排除规则均在此定义
"""

import os

APP_NAME = "C盘清理助手"
APP_VERSION = "0.1.0"

# ============================================================
# 安全排除列表 — 扫描时自动跳过这些路径，保护系统和用户隐私
# ============================================================

PROTECTED_SYSTEM_DIRS = [
    os.path.join("C:", os.sep, "Windows", "System32"),
    os.path.join("C:", os.sep, "Windows", "SysWOW64"),
    os.path.join("C:", os.sep, "Windows", "WinSxS"),
    os.path.join("C:", os.sep, "Windows", "Installer"),
    os.path.join("C:", os.sep, "Windows", "servicing"),
    os.path.join("C:", os.sep, "Windows", "Boot"),
    os.path.join("C:", os.sep, "Program Files"),
    os.path.join("C:", os.sep, "Program Files (x86)"),
    os.path.join("C:", os.sep, "ProgramData"),
]

PROTECTED_USER_DIRS = [
    os.path.join(".ssh"),
    os.path.join(".gnupg"),
    os.path.join(".aws"),
    os.path.join(".config"),
    "AppData\\Local\\Microsoft\\Credentials",
    "AppData\\Roaming\\Microsoft\\Credentials",
]

SENSITIVE_FILE_PATTERNS = [
    "*.key",
    "*.pem",
    "*.pfx",
    "*.p12",
    "*.cer",
    "id_rsa*",
    "id_ed25519*",
    "*.keystore",
    "credentials",
    "secrets",
    ".env",
    ".htpasswd",
]

# ============================================================
# 临时文件扫描目标
# ============================================================

TEMP_SCAN_TARGETS = {
    "user_temp": os.environ.get("TEMP", ""),
    "windows_temp": os.path.join("C:", os.sep, "Windows", "Temp"),
    "prefetch": os.path.join("C:", os.sep, "Windows", "Prefetch"),
}

BROWSER_CACHE_DIRS = {
    "Chrome": os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Google", "Chrome", "User Data", "Default", "Cache",
    ),
    "Edge": os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Microsoft", "Edge", "User Data", "Default", "Cache",
    ),
    "Firefox": os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Mozilla", "Firefox", "Profiles",
    ),
}

# ============================================================
# 大文件扫描配置
# ============================================================

LARGE_FILE_THRESHOLD_MB = 100
DEFAULT_SCAN_DIRS = ["C:\\Users"]

# ============================================================
# 清理建议规则
# ============================================================

SAFE_TO_CLEAN_EXTENSIONS = [
    ".tmp", ".temp", ".log", ".bak", ".old", ".cache",
    ".dmp", ".chk", ".gid", ".fts",
]

NOT_RECOMMENDED_EXTENSIONS = [
    ".dll", ".exe", ".sys", ".drv", ".msi",
    ".db", ".sqlite", ".dat",
]

SAFE_TO_CLEAN_CATEGORIES = [
    "系统临时文件",
    "浏览器缓存",
]

# ============================================================
# 应用缓存扫描目标（第二阶段）
# ============================================================

APP_CACHE_DIRS = {
    "WeChat": os.path.join(
        os.environ.get("APPDATA", ""), "..", "Local", "WeChat Files",
    ),
    "QQ": os.path.join(
        os.environ.get("APPDATA", ""), "..", "Local", "Tencent", "QQ",
    ),
    "DingTalk": os.path.join(
        os.environ.get("APPDATA", ""), "..", "Local", "DingTalk",
    ),
}
