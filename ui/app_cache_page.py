"""
C盘清理工具 - 应用缓存清理页面
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os
import subprocess

from core.app_cache_scanner import AppCacheScanner, AppCacheInfo, CacheCategory
from core.cleaner import FileCleaner
from core.utils import format_file_size


CHECKBOX_UNCHECKED = "☐"
CHECKBOX_CHECKED = "☑"

APP_ICONS = {
    "WeChat": "💬",
    "QQ": "🐧",
    "DingTalk": "📌",
    "QQBrowser": "🌐",
}


class AppCachePage:
    """应用缓存清理页面"""

    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=10)
        self.scanner = AppCacheScanner()
        self.cleaner = FileCleaner(use_trash=True)
        self._app_cache_info: dict = {}
        self._app_vars: dict = {}
        self._cat_vars: dict = {}
        self._scan_start_time = None
        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.configure("Blue.Horizontal.TProgressbar",
                        troughcolor="#ecf0f1", background="#3498db",
                        bordercolor="#bdc3c7", lightcolor="#3498db", darkcolor="#3498db")
        style.configure("AppCard.TFrame", background="white", relief="solid", borderwidth=1)
        style.configure("AppCard.TLabel", background="white", font=("Microsoft YaHei UI", 10))
        style.configure("AppSize.TLabel", background="white", font=("Microsoft YaHei UI", 11, "bold"),
                        foreground="#e74c3c")
        style.configure("CatName.TLabel", background="white", font=("Microsoft YaHei UI", 9),
                        foreground="#7f8c8d")
        style.configure("CatSize.TLabel", background="white", font=("Microsoft YaHei UI", 9),
                        foreground="#2c3e50")

    def _build_ui(self):
        top_bar = ttk.Frame(self.frame)
        top_bar.pack(fill=tk.X, pady=(0, 8))

        self.scan_btn = ttk.Button(top_bar, text="扫描缓存", command=self._start_scan)
        self.scan_btn.pack(side=tk.LEFT)

        self.clean_btn = ttk.Button(
            top_bar, text="清理选中缓存", command=self._start_clean, state=tk.DISABLED,
        )
        self.clean_btn.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(top_bar, text="全选", command=self._select_all).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(top_bar, text="全不选", command=self._select_none).pack(side=tk.LEFT, padx=(4, 0))

        self.progress = ttk.Progressbar(self.frame, mode="determinate",
                                        style="Blue.Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(0, 4))

        self.info_label = ttk.Label(
            self.frame, text="点击「扫描缓存」检测应用缓存占用",
            foreground="gray",
        )
        self.info_label.pack(anchor=tk.W, pady=(0, 6))

        self.apps_container = ttk.Frame(self.frame)
        self.apps_container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(self.apps_container, highlightthickness=0)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(self.apps_container, orient=tk.VERTICAL, command=canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.configure(yscrollcommand=scrollbar.set)

        self._apps_frame = ttk.Frame(canvas)
        canvas_window = canvas.create_window((0, 0), window=self._apps_frame, anchor=tk.NW)

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=event.width)

        self._apps_frame.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)

    def _start_scan(self):
        self.scan_btn.config(state=tk.DISABLED)
        self.clean_btn.config(state=tk.DISABLED)
        self.progress["value"] = 0
        self._scan_start_time = None

        for widget in self._apps_frame.winfo_children():
            widget.destroy()
        self._app_cache_info = {}
        self._app_vars = {}
        self._cat_vars = {}

        import time
        self._scan_start_time = time.time()

        def progress_cb(text, ratio):
            self.frame.after(0, lambda t=text, r=ratio: self._update_progress(t, r))

        def scan_task():
            results = self.scanner.scan_all(progress_callback=progress_cb)
            self.frame.after(0, lambda: self._on_scan_done(results))

        threading.Thread(target=scan_task, daemon=True).start()

    def _update_progress(self, text: str, ratio: float):
        self.progress["value"] = ratio * 100
        self.info_label.config(text=text)

    def _on_scan_done(self, results: dict):
        self._app_cache_info = results
        self.progress["value"] = 100

        installed_apps = {k: v for k, v in results.items() if v.is_installed}
        total_size = sum(v.total_size for v in installed_apps.values())

        self.info_label.config(
            text=f"扫描完成：检测到 {len(installed_apps)} 个应用，"
                 f"缓存总占用 {format_file_size(total_size)}"
        )

        for app_key, info in installed_apps.items():
            self._create_app_card(app_key, info)

        self.scan_btn.config(state=tk.NORMAL)
        if installed_apps:
            self.clean_btn.config(state=tk.NORMAL)

    def _create_app_card(self, app_key: str, info: AppCacheInfo):
        card = ttk.Frame(self._apps_frame, style="AppCard.TFrame", padding=12)
        card.pack(fill=tk.X, pady=(0, 8))

        header = ttk.Frame(card, style="AppCard.TFrame")
        header.pack(fill=tk.X)

        icon = APP_ICONS.get(app_key, "📦")
        var = tk.BooleanVar(value=True)
        self._app_vars[app_key] = var

        cb = tk.Checkbutton(
            header, variable=var,
            activebackground="white", bg="white", selectcolor="white",
            command=lambda: self._on_app_toggle(app_key, var.get()),
        )
        cb.pack(side=tk.LEFT)

        ttk.Label(header, text=f"{icon} {info.display_name}",
                  style="AppCard.TLabel", font=("Microsoft YaHei UI", 11, "bold")).pack(
            side=tk.LEFT, padx=(4, 0),
        )

        ttk.Label(header, text=info.total_size_display,
                  style="AppSize.TLabel").pack(side=tk.RIGHT)

        if info.categories:
            sep = ttk.Separator(card, orient=tk.HORIZONTAL)
            sep.pack(fill=tk.X, pady=(8, 6))

            cats_grid = ttk.Frame(card, style="AppCard.TFrame")
            cats_grid.pack(fill=tk.X)

            for i, cat in enumerate(info.categories):
                row = i // 2
                col = (i % 2) * 2

                cat_var = tk.BooleanVar(value=True)
                self._cat_vars.setdefault(app_key, {})[cat.path] = cat_var

                cat_cb = tk.Checkbutton(
                    cats_grid, variable=cat_var,
                    activebackground="white", bg="white", selectcolor="white",
                )
                cat_cb.grid(row=row, column=col, sticky=tk.W, padx=(4, 0), pady=2)

                ttk.Label(cats_grid, text=f"{cat.name}:",
                          style="CatName.TLabel").grid(
                    row=row, column=col + 1, sticky=tk.W, padx=(0, 8), pady=2,
                )

                ttk.Label(cats_grid, text=format_file_size(cat.size),
                          style="CatSize.TLabel").grid(
                    row=row, column=col + 2, sticky=tk.E, padx=(0, 16), pady=2,
                )

            for col_idx in range(6):
                cats_grid.columnconfigure(col_idx, weight=1 if col_idx % 3 == 2 else 0)

        path_label = ttk.Label(card, text=f"路径: {info.base_dir}",
                               style="CatName.TLabel", foreground="#95a5a6")
        path_label.pack(anchor=tk.W, pady=(6, 0))

    def _on_app_toggle(self, app_key: str, checked: bool):
        if app_key in self._cat_vars:
            for cat_var in self._cat_vars[app_key].values():
                cat_var.set((checked))

    def _select_all(self):
        for var in self._app_vars.values():
            var.set(True)
        for app_cats in self._cat_vars.values():
            for var in app_cats.values():
                var.set(True)

    def _select_none(self):
        for var in self._app_vars.values():
            var.set(False)
        for app_cats in self._cat_vars.values():
            for var in app_cats.values():
                var.set(False)

    def _start_clean(self):
        dirs_to_clean = []
        for app_key, app_var in self._app_vars.items():
            if not app_var.get():
                continue
            if app_key in self._cat_vars:
                for cat_path, cat_var in self._cat_vars[app_key].items():
                    if cat_var.get() and os.path.isdir(cat_path):
                        dirs_to_clean.append(cat_path)

        if not dirs_to_clean:
            messagebox.showinfo("提示", "请先勾选要清理的缓存")
            return

        total_size = 0
        for d in dirs_to_clean:
            for root, subdirs, files in os.walk(d):
                for f in files:
                    total_size += os.path.getsize(os.path.join(root, f))

        msg = (
            f"确定要清理 {len(dirs_to_clean)} 个缓存目录吗？\n"
            f"共可释放约 {format_file_size(total_size)} 空间\n\n"
            "清理后应用可能需要重新加载部分数据。"
        )
        if not messagebox.askyesno("确认清理", msg):
            return

        self.clean_btn.config(state=tk.DISABLED)
        self.scan_btn.config(state=tk.DISABLED)

        def clean_task():
            cleaned = 0
            failed = 0
            freed_bytes = 0
            for dir_path in dirs_to_clean:
                s, f, b = self._clean_directory(dir_path)
                cleaned += s
                failed += f
                freed_bytes += b
            self.frame.after(
                0, lambda: self._on_clean_done(cleaned, failed, freed_bytes),
            )

        threading.Thread(target=clean_task, daemon=True).start()

    def _clean_directory(self, dir_path: str):
        cleaned = 0
        failed = 0
        freed_bytes = 0
        try:
            for root, dirs, files in os.walk(dir_path, topdown=False):
                for name in files:
                    filepath = os.path.join(root, name)
                    try:
                        file_size = os.path.getsize(filepath) if os.path.isfile(filepath) else 0
                        if os.path.isfile(filepath) or os.path.islink(filepath):
                            os.remove(filepath)
                        cleaned += 1
                        freed_bytes += file_size
                    except (PermissionError, OSError):
                        failed += 1
                for name in dirs:
                    try:
                        os.rmdir(os.path.join(root, name))
                    except OSError:
                        pass
        except (PermissionError, OSError):
            failed += 1
        return cleaned, failed, freed_bytes

    def _on_clean_done(self, cleaned: int, failed: int, freed_bytes: int):
        msg = f"清理完成：成功删除 {cleaned} 个文件，释放 {format_file_size(freed_bytes)}"
        if failed:
            msg += f"\n{failed} 个文件因被占用无法删除（请关闭对应应用后重试）"
        self.info_label.config(text=msg)

        self._start_rescan()

    def _start_rescan(self):
        """清理后自动重新扫描以更新显示"""
        self.progress["value"] = 0

        for widget in self._apps_frame.winfo_children():
            widget.destroy()
        self._app_cache_info = {}
        self._app_vars = {}
        self._cat_vars = {}

        def progress_cb(text, ratio):
            self.frame.after(0, lambda t=text, r=ratio: self._update_progress(t, r))

        def scan_task():
            results = self.scanner.scan_all(progress_callback=progress_cb)
            self.frame.after(0, lambda: self._on_rescan_done(results))

        threading.Thread(target=scan_task, daemon=True).start()

    def _on_rescan_done(self, results: dict):
        self._app_cache_info = results
        self.progress["value"] = 100

        installed_apps = {k: v for k, v in results.items() if v.is_installed}
        total_size = sum(v.total_size for v in installed_apps.values())

        self.info_label.config(
            text=f"重新扫描完成：{len(installed_apps)} 个应用，"
                 f"当前缓存占用 {format_file_size(total_size)}"
        )

        for app_key, info in installed_apps.items():
            self._create_app_card(app_key, info)

        self.scan_btn.config(state=tk.NORMAL)
        if installed_apps:
            self.clean_btn.config(state=tk.NORMAL)
