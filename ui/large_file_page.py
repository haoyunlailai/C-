"""
C盘清理工具 - 大文件扫描页面
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import time

from core.scanner import LargeFileScanner, ScanReport
from core.cleaner import FileCleaner
from core.utils import format_file_size
from config import LARGE_FILE_THRESHOLD_MB


SUGGESTION_COLORS = {
    "建议清理": "#27ae60",
    "可酌情清理": "#f39c12",
    "不建议删除": "#e74c3c",
}


class LargeFilePage:
    """大文件扫描页面"""

    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=10)
        self.scanner = LargeFileScanner()
        self.cleaner = FileCleaner(use_trash=True)
        self.scan_report: ScanReport = None
        self.scan_dirs: list = []
        self._build_ui()

    def _build_ui(self):
        config_bar = ttk.Frame(self.frame)
        config_bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(config_bar, text="扫描目录:").pack(side=tk.LEFT)

        self.dir_listbox = tk.Listbox(config_bar, height=2, width=45, selectmode=tk.EXTENDED,
                                       font=("Microsoft YaHei UI", 9))
        self.dir_listbox.pack(side=tk.LEFT, padx=(5, 5))
        self.dir_listbox.insert(tk.END, "C:\\Users")
        self.scan_dirs = ["C:\\Users"]

        dir_btn_frame = ttk.Frame(config_bar)
        dir_btn_frame.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(dir_btn_frame, text="添加", command=self._add_dir).pack(fill=tk.X)
        ttk.Button(dir_btn_frame, text="移除", command=self._remove_dir).pack(fill=tk.X, pady=(2, 0))

        ttk.Label(config_bar, text="最小(MB):").pack(side=tk.LEFT)
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
        ttk.Button(config_bar, text="反选", command=self._invert_selection).pack(side=tk.LEFT, padx=(4, 0))

        self.progress = ttk.Progressbar(self.frame, mode="determinate")
        self.progress.pack(fill=tk.X, pady=(0, 4))

        self.info_label = ttk.Label(
            self.frame, text="添加目录后点击「开始扫描」查找大文件", foreground="gray",
        )
        self.info_label.pack(anchor=tk.W, pady=(0, 6))

        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("check", "suggestion", "path", "size", "last_used")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="extended", height=15,
        )
        self.tree.heading("check", text="选")
        self.tree.heading("suggestion", text="建议")
        self.tree.heading("path", text="文件路径")
        self.tree.heading("size", text="大小")
        self.tree.heading("last_used", text="上次使用")
        self.tree.column("check", width=35, minwidth=30, anchor=tk.CENTER)
        self.tree.column("suggestion", width=80, minwidth=70, anchor=tk.CENTER)
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
                self.tree.set(item, "check", "" if current == "\u2714" else "\u2714")

    def _select_all(self):
        for item in self.tree.get_children():
            self.tree.set(item, "check", "\u2714")

    def _invert_selection(self):
        for item in self.tree.get_children():
            current = self.tree.set(item, "check")
            self.tree.set(item, "check", "" if current == "\u2714" else "\u2714")

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

    def _start_scan(self):
        if not self.scan_dirs:
            messagebox.showwarning("提示", "请至少添加一个扫描目录")
            return

        self.scan_btn.config(state=tk.DISABLED)
        self.clean_btn.config(state=tk.DISABLED)
        self._clear_tree()
        self.progress["value"] = 0

        threshold = self.threshold_var.get()
        self.scanner = LargeFileScanner(threshold_mb=threshold)

        def progress_cb(ratio, text):
            self.frame.after(0, lambda: self._update_progress(ratio, text))

        def scan_task():
            report = self.scanner.scan(
                scan_dirs=list(self.scan_dirs), progress_callback=progress_cb,
            )
            self.frame.after(0, lambda: self._on_scan_done(report))

        threading.Thread(target=scan_task, daemon=True).start()

    def _update_progress(self, ratio: float, text: str):
        self.progress["value"] = ratio * 100
        self.info_label.config(text=text)

    def _on_scan_done(self, report: ScanReport):
        self.scan_report = report
        for item in report.results:
            self.tree.insert("", tk.END, values=(
                "",
                item.suggestion,
                item.path,
                format_file_size(item.size),
                item.last_used,
            ), tags=(item.suggestion,))

        self.info_label.config(
            text=f"扫描完成：找到 {report.total_count} 个大文件，"
                 f"共占用 {format_file_size(report.total_size)}"
        )
        self.scan_btn.config(state=tk.NORMAL)
        if report.total_count > 0:
            self.clean_btn.config(state=tk.NORMAL)

    def _start_clean(self):
        selected_items = []
        for item in self.tree.get_children():
            if self.tree.set(item, "check") == "\u2714":
                selected_items.append(item)

        if not selected_items:
            messagebox.showinfo("提示", "请先勾选要删除的文件")
            return

        indices = [self.tree.index(item) for item in selected_items]
        files_to_clean = [self.scan_report.results[i] for i in indices]

        warn_count = sum(1 for f in files_to_clean if f.suggestion == "不建议删除")
        msg = f"确定要将选中的 {len(files_to_clean)} 个文件移入回收站吗？"
        if warn_count > 0:
            msg += f"\n\n注意：其中有 {warn_count} 个文件标记为「不建议删除」，请确认后再操作。"

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
