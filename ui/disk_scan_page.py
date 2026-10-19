"""
C盘清理工具 - 磁盘扫描页面
整合磁盘整体扫描和文件夹扫描功能
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import os

from core.scanner import LargeFileScanner, ScanReport
from core.cleaner import FileCleaner
from core.utils import format_file_size
from config import LARGE_FILE_THRESHOLD_MB


CHECKBOX_UNCHECKED = "☐"
CHECKBOX_CHECKED = "☑"

SUGGESTION_COLORS = {
    "建议清理": "#27ae60",
    "可酌情清理": "#f39c12",
    "不建议删除": "#e74c3c",
}


class DiskScanPage:
    """磁盘扫描页面 — 支持磁盘整体扫描和文件夹扫描"""

    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=10)
        self.scanner = LargeFileScanner()
        self.cleaner = FileCleaner(use_trash=True)
        self.scan_report: ScanReport = None
        self.scan_dirs: list = []
        self.show_unsafe = tk.BooleanVar(value=False)
        self._item_to_index: dict = {}
        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.configure("Blue.Horizontal.TProgressbar", troughcolor="#ecf0f1", background="#3498db", bordercolor="#bdc3c7", lightcolor="#3498db", darkcolor="#3498db")

    def _build_ui(self):
        mode_frame = ttk.LabelFrame(self.frame, text="扫描模式", padding=8)
        mode_frame.pack(fill=tk.X, pady=(0, 8))

        self.mode_var = tk.StringVar(value="disk")
        ttk.Radiobutton(
            mode_frame, text="磁盘整体扫描（扫描C盘所有用户目录）",
            variable=self.mode_var, value="disk", command=self._on_mode_change,
        ).pack(anchor=tk.W, pady=2)
        ttk.Radiobutton(
            mode_frame, text="文件夹扫描（自定义扫描目录）",
            variable=self.mode_var, value="folder", command=self._on_mode_change,
        ).pack(anchor=tk.W, pady=2)

        self.folder_frame = ttk.Frame(mode_frame)
        self.folder_frame.pack(fill=tk.X, pady=(8, 0))

        self.dir_listbox = tk.Listbox(
            self.folder_frame, height=2, width=50, selectmode=tk.EXTENDED,
            font=("Microsoft YaHei UI", 9),
        )
        self.dir_listbox.pack(side=tk.LEFT, padx=(0, 8))

        dir_btn_frame = ttk.Frame(self.folder_frame)
        dir_btn_frame.pack(side=tk.LEFT)
        ttk.Button(dir_btn_frame, text="添加目录", command=self._add_dir).pack(fill=tk.X)
        ttk.Button(dir_btn_frame, text="移除选中", command=self._remove_dir).pack(fill=tk.X, pady=(2, 0))
        self.folder_frame.pack_forget()

        config_bar = ttk.Frame(self.frame)
        config_bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(config_bar, text="文件大小阈值 (MB):").pack(side=tk.LEFT)
        self.threshold_var = tk.IntVar(value=LARGE_FILE_THRESHOLD_MB)
        ttk.Spinbox(
            config_bar, from_=10, to=10000, textvariable=self.threshold_var, width=6,
        ).pack(side=tk.LEFT, padx=(5, 10))

        self.scan_btn = ttk.Button(config_bar, text="开始扫描", command=self._start_scan)
        self.scan_btn.pack(side=tk.LEFT)

        self.clean_btn = ttk.Button(
            config_bar, text="删除选中项", command=self._start_clean, state=tk.DISABLED,
        )
        self.clean_btn.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(config_bar, text="全选", command=self._select_all).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(config_bar, text="选中建议清理", command=self._select_recommended).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(config_bar, text="全不选", command=self._select_none).pack(side=tk.LEFT, padx=(4, 0))

        ttk.Separator(config_bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Checkbutton(
            config_bar, text="显示不建议删除的文件", variable=self.show_unsafe,
            command=self._toggle_unsafe_view,
        ).pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(self.frame, mode="determinate", style="Blue.Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(0, 4))

        self.info_label = ttk.Label(
            self.frame, text="选择扫描模式后点击「开始扫描」", foreground="gray",
        )
        self.info_label.pack(anchor=tk.W, pady=(0, 6))

        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("check", "suggestion", "path", "size", "last_used")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="extended", height=15,
        )
        self.tree.heading("check", text="选择")
        self.tree.heading("suggestion", text="建议")
        self.tree.heading("path", text="文件路径")
        self.tree.heading("size", text="大小")
        self.tree.heading("last_used", text="上次使用")
        self.tree.column("check", width=50, minwidth=40, anchor=tk.CENTER)
        self.tree.column("suggestion", width=90, minwidth=80, anchor=tk.CENTER)
        self.tree.column("path", width=420, minwidth=200)
        self.tree.column("size", width=80, minwidth=60, anchor=tk.E)
        self.tree.column("last_used", width=130, minwidth=100)

        for tag, color in SUGGESTION_COLORS.items():
            self.tree.tag_configure(tag, foreground=color)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)

    def _on_tree_click(self, event):
        col = self.tree.identify_column(event.x)
        if col == "#1":
            item = self.tree.identify_row(event.y)
            if item:
                current = self.tree.set(item, "check")
                self.tree.set(item, "check", CHECKBOX_UNCHECKED if current == CHECKBOX_CHECKED else CHECKBOX_CHECKED)

    def _select_all(self):
        for item in self.tree.get_children():
            self.tree.set(item, "check", CHECKBOX_CHECKED)

    def _select_recommended(self):
        for item in self.tree.get_children():
            values = self.tree.item(item, "values")
            if values[1] == "建议清理":
                self.tree.set(item, "check", CHECKBOX_CHECKED)

    def _select_none(self):
        for item in self.tree.get_children():
            self.tree.set(item, "check", CHECKBOX_UNCHECKED)

    def _on_mode_change(self):
        if self.mode_var.get() == "folder":
            self.folder_frame.pack(fill=tk.X, pady=(8, 0))
        else:
            self.folder_frame.pack_forget()

    def _add_dir(self):
        initial = self.scan_dirs[-1] if self.scan_dirs else "C:\\"
        path = filedialog.askdirectory(initialdir=initial)
        if path and path not in self.scan_dirs:
            self.scan_dirs.append(path)
            self.dir_listbox.insert(tk.END, path)

    def _remove_dir(self):
        selected = list(self.dir_listbox.curselection())
        for idx in reversed(selected):
            self.dir_listbox.delete(idx)
            del self.scan_dirs[idx]

    def _toggle_unsafe_view(self):
        if self.scan_report:
            self._refresh_tree()

    def _refresh_tree(self):
        self._clear_tree()
        if not self.scan_report:
            return

        self._item_to_index = {}
        visible_count = 0
        for orig_idx, item in enumerate(self.scan_report.results):
            if not self.show_unsafe.get() and item.suggestion == "不建议删除":
                continue
            tree_id = self.tree.insert("", tk.END, values=(
                CHECKBOX_UNCHECKED,
                item.suggestion,
                item.path,
                format_file_size(item.size),
                item.last_used,
            ), tags=(item.suggestion,))
            self._item_to_index[tree_id] = orig_idx
            visible_count += 1

        self.info_label.config(
            text=f"显示 {visible_count} / {self.scan_report.total_count} 个文件，"
                 f"共占用 {format_file_size(self.scan_report.total_size)}"
        )
        self.clean_btn.config(state=tk.NORMAL if visible_count > 0 else tk.DISABLED)

    def _start_scan(self):
        mode = self.mode_var.get()
        if mode == "folder":
            if not self.scan_dirs:
                messagebox.showwarning("提示", "请至少添加一个扫描目录")
                return
            dirs_to_scan = list(self.scan_dirs)
        else:
            dirs_to_scan = ["C:\\Users"]

        self.scan_btn.config(state=tk.DISABLED)
        self.clean_btn.config(state=tk.DISABLED)
        self._clear_tree()
        self.progress["value"] = 0
        self._scan_start_time = None

        threshold = self.threshold_var.get()
        self.scanner = LargeFileScanner(threshold_mb=threshold)

        def progress_cb(ratio, text, files_found=0):
            self.frame.after(0, lambda t=text, f=files_found: self._update_progress(ratio, t, f))

        def scan_task():
            report = self.scanner.scan(scan_dirs=dirs_to_scan, progress_callback=progress_cb)
            self.frame.after(0, lambda: self._on_scan_done(report))

        threading.Thread(target=scan_task, daemon=True).start()

    def _update_progress(self, ratio: float, text: str, files_found: int = 0):
        if self._scan_start_time is None:
            self._scan_start_time = time.time()
        self.progress["value"] = ratio * 100
        elapsed = int(time.time() - self._scan_start_time)
        mins, secs = divmod(elapsed, 60)
        time_str = f"{mins}分{secs}秒" if mins > 0 else f"{secs}秒"
        self.info_label.config(text=f"{text}  |  已耗时 {time_str}  |  已发现 {files_found} 个文件")

    def _on_scan_done(self, report: ScanReport):
        self.scan_report = report
        self._refresh_tree()
        self.scan_btn.config(state=tk.NORMAL)

    def _start_clean(self):
        selected_items = []
        for item in self.tree.get_children():
            if self.tree.set(item, "check") == CHECKBOX_CHECKED:
                selected_items.append(item)

        if not selected_items:
            messagebox.showinfo("提示", "请先勾选要删除的文件")
            return

        files_to_clean = [self.scan_report.results[self._item_to_index[item]] for item in selected_items]

        msg = f"确定要将选中的 {len(files_to_clean)} 个文件移入回收站吗？\n\n文件可随时从回收站恢复。"
        confirm = messagebox.askyesno("确认删除", msg)
        if not confirm:
            return

        succeeded, failed = self.cleaner.clean_files(files_to_clean)

        for item in selected_items:
            self.tree.delete(item)

        result_msg = f"成功清理 {len(succeeded)} 个文件"
        if failed:
            result_msg += f"，{len(failed)} 个文件清理失败"
        self.info_label.config(text=result_msg)

        if not self.tree.get_children():
            self.clean_btn.config(state=tk.DISABLED)

    def _clear_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
