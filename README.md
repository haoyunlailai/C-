# C盘清理助手

一款轻量级的 Windows C盘空间清理工具，帮助你快速找出并清理占用磁盘空间的无用文件。

## 功能特性

### 已实现（MVP）

- **系统临时文件清理** — 扫描 Windows 临时目录、浏览器缓存等，一键清理
- **大文件扫描** — 自定义阈值和扫描目录，按大小排序展示，支持选择性删除
- **安全优先** — 所有删除操作均先扫描展示、用户确认后才执行，文件移入回收站可恢复
- **信息保护** — 自动跳过系统关键目录（System32 等）和敏感文件（密钥、证书等），不记录、不上传任何用户数据

### 计划中

- 重复文件扫描（基于文件哈希）
- 软件卸载管理
- 应用缓存清理（微信、QQ、钉钉等）
- 磁盘空间可视化树状图

## 快速开始

### 方式一：直接下载可执行文件（推荐）

前往 [Releases 页面](../../releases) 下载最新版本的 `C盘清理助手.exe`，双击即可运行，无需安装 Python。

### 方式二：从源码运行

#### 环境要求

- Python 3.10+
- Windows 10/11

#### 安装与运行

```bash
# 克隆项目
git clone <repo-url>
cd C盘内存处理项目

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

### 自行打包为 exe

```bash
# 安装 PyInstaller
pip install pyinstaller

# 打包
pyinstaller --onefile --windowed --name "C盘清理助手" --hidden-import send2trash main.py

# 可执行文件位于 dist/ 目录
```

## 项目结构

```
├── main.py                  # 程序入口
├── config.py                # 配置（扫描路径、安全策略）
├── requirements.txt         # Python 依赖
├── core/
│   ├── scanner.py           # 文件扫描引擎
│   ├── cleaner.py           # 文件清理执行器
│   └── utils.py             # 工具函数
└── ui/
    ├── main_window.py       # 主窗口
    ├── temp_clean_page.py   # 临时文件清理页
    └── disk_scan_page.py    # 磁盘扫描页
```

## 安全设计

本工具遵循以下安全原则：

1. **只读扫描** — 扫描阶段不修改任何文件
2. **用户确认** — 所有删除操作需用户手动勾选并确认
3. **回收站优先** — 默认移入回收站而非永久删除，支持恢复
4. **系统保护** — 自动跳过 `System32`、`WinSxS` 等系统关键目录
5. **隐私保护** — 跳过 `.ssh`、`.aws`、密钥文件等敏感路径和文件，不记录任何扫描日志

## 开源许可

[MIT License](LICENSE)
