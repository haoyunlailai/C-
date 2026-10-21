"""
C盘清理工具 - 主窗口
"""

import tkinter as tk
from tkinter import ttk

from config import APP_NAME, APP_VERSION
from ui.temp_clean_page import TempCleanPage
from ui.disk_scan_page import DiskScanPage
from ui.duplicate_page import DuplicatePage
from ui.app_cache_page import AppCachePage
from ui.software_uninstall_page import SoftwareUninstallPage
from ui.treemap_page import TreemapPage


class MainWindow:
    """应用程序主窗口"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1000x700")
        self.root.minsize(850, 600)
        self.root.configure(bg="#f5f6fa")
        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(".", background="#f5f6fa", font=("Microsoft YaHei UI", 9))

        style.configure("TFrame", background="#f5f6fa")
        style.configure("TLabel", background="#f5f6fa")

        style.configure("Header.TFrame", background="#2c3e50")
        style.configure("Header.TLabel", background="#2c3e50", foreground="white",
                         font=("Microsoft YaHei UI", 18, "bold"))
        style.configure("HeaderSub.TLabel", background="#2c3e50", foreground="#bdc3c7",
                         font=("Microsoft YaHei UI", 10))

        style.configure("TNotebook", background="#f5f6fa", borderwidth=0)
        style.configure("TNotebook.Tab", font=("Microsoft YaHei UI", 10, "bold"),
                         padding=[16, 6], background="#ecf0f1")
        style.map("TNotebook.Tab",
                   background=[("selected", "#fff")],
                   expand=[("selected", [1, 1, 1, 0])])

        style.configure("TLabelframe", background="#f5f6fa")
        style.configure("TLabelframe.Label", font=("Microsoft YaHei UI", 9, "bold"),
                         background="#f5f6fa", foreground="#2c3e50")

        style.configure("TButton", font=("Microsoft YaHei UI", 9), padding=6)
        style.configure("Treeview", font=("Microsoft YaHei UI", 9), rowheight=26,
                         background="white", fieldbackground="white", borderwidth=1)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"),
                         background="#ecf0f1", foreground="#2c3e50")
        style.map("Treeview", background=[("selected", "#3498db")],
                   foreground=[("selected", "white")])

    def _build_ui(self):
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(20, 12))
        header.pack(fill=tk.X)

        title_frame = ttk.Frame(header, style="Header.TFrame")
        title_frame.pack(side=tk.LEFT)
        ttk.Label(title_frame, text=APP_NAME, style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Label(title_frame, text=f"  v{APP_VERSION}", style="HeaderSub.TLabel").pack(
            side=tk.LEFT, pady=(6, 0),
        )

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=(10, 5))

        self.temp_page = TempCleanPage(notebook)
        self.disk_scan_page = DiskScanPage(notebook)
        self.duplicate_page = DuplicatePage(notebook)
        self.app_cache_page = AppCachePage(notebook)
        self.software_page = SoftwareUninstallPage(notebook)
        self.treemap_page = TreemapPage(notebook)

        notebook.add(self.temp_page.frame, text="  临时文件清理  ")
        notebook.add(self.disk_scan_page.frame, text="  磁盘扫描  ")
        notebook.add(self.duplicate_page.frame, text="  重复文件  ")
        notebook.add(self.app_cache_page.frame, text="  应用缓存  ")
        notebook.add(self.software_page.frame, text="  软件卸载  ")
        notebook.add(self.treemap_page.frame, text="  磁盘可视化  ")

        status_bar = ttk.Frame(self.root, padding=(15, 4))
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = ttk.Label(
            status_bar, text="就绪  |  所有删除操作均先移入回收站，可恢复",
            foreground="gray", font=("Microsoft YaHei UI", 8),
        )
        self.status_label.pack(side=tk.LEFT)

    def set_status(self, text: str):
        self.status_label.config(text=text)

    def run(self):
        self.root.mainloop()
