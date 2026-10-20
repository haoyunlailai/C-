"""
C盘清理工具 - 临时文件清理页面
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import subprocess

from core.scanner import TempFileScanner, ScanReport
from core.cleaner import FileCleaner
from core.utils import format_file_size


CHECKBOX_UNCHECKED = "☐"
CHECKBOX_CHECKED = "☑"

SUGGESTION_COLORS = {
    "建议清理": "#27ae60",
    "可酌情清理": "#f39c12",
    "不建议删除": "#e74c3c",
}

CATEGORY_COLORS = [
    "#3498db", "#e74c3c", "#2ecc71", "#f39c12",
    "#9b59b6", "#1abc9c", "#e67e22", "#34495e",
]


class TempCleanPage:
    """临时文件清理页面"""

    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=10)
        self.scanner = TempFileScanner()
        self.cleaner = FileCleaner(use_trash=True)
        self.scan_report: ScanReport = None
        self.show_unsafe = tk.BooleanVar(value=False)
        self._item_to_index: dict = {}
        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.configure("Blue.Horizontal.TProgressbar", troughcolor="#ecf0f1", background="#3498db", bordercolor="#bdc3c7", lightcolor="#3498db", darkcolor="#3498db")

    def _build_ui(self):
        top_bar = ttk.Frame(self.frame)
        top_bar.pack(fill=tk.X, pady=(0, 8))

        self.scan_btn = ttk.Button(top_bar, text="开始扫描", command=self._start_scan)
        self.scan_btn.pack(side=tk.LEFT)

        self.clean_btn = ttk.Button(
            top_bar, text="清理选中项", command=self._start_clean, state=tk.DISABLED,
        )
        self.clean_btn.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(top_bar, text="全选", command=self._select_all).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(top_bar, text="选中建议清理", command=self._select_recommended).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(top_bar, text="全不选", command=self._select_none).pack(side=tk.LEFT, padx=(4, 0))

        ttk.Separator(top_bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Checkbutton(
            top_bar, text="显示不建议删除的文件", variable=self.show_unsafe,
            command=self._toggle_unsafe_view,
        ).pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(self.frame, mode="determinate", style="Blue.Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(0, 4))

        self.info_label = ttk.Label(self.frame, text="点击「开始扫描」查找可清理的临时文件", foreground="gray")
        self.info_label.pack(anchor=tk.W, pady=(0, 6))

        self.summary_frame = ttk.LabelFrame(self.frame, text="分类概览", padding=8)
        self.summary_frame.pack(fill=tk.X, pady=(0, 8))
        self.summary_canvas = tk.Canvas(self.summary_frame, height=60, highlightthickness=0)
        self.summary_canvas.pack(fill=tk.X)

        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("check", "suggestion", "category", "path", "size", "last_used")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", selectmode="extended", height=12,
        )
        self.tree.heading("check", text="选择")
        self.tree.heading("suggestion", text="建议")
        self.tree.heading("category", text="分类")
        self.tree.heading("path", text="文件路径")
        self.tree.heading("size", text="大小")
        self.tree.heading("last_used", text="上次使用")
        self.tree.column("check", width=50, minwidth=40, anchor=tk.CENTER)
        self.tree.column("suggestion", width=90, minwidth=80, anchor=tk.CENTER)
        self.tree.column("category", width=130, minwidth=100)
        self.tree.column("path", width=350, minwidth=150)
        self.tree.column("size", width=80, minwidth=60, anchor=tk.E)
        self.tree.column("last_used", width=130, minwidth=100)

        for tag, color in SUGGESTION_COLORS.items():
            self.tree.tag_configure(tag, foreground=color)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_doubleclick)

    def _on_tree_click(self, event):
        col = self.tree.identify_column(event.x)
        if col == "#1":
            item = self.tree.identify_row(event.y)
            if item:
                current = self.tree.set(item, "check")
                new_val = CHECKBOX_UNCHECKED if current == CHECKBOX_CHECKED else CHECKBOX_CHECKED
                self.tree.set(item, "check", new_val)

    def _on_tree_doubleclick(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        filepath = self.tree.set(item, "path")
        if filepath and os.path.exists(filepath):
            subprocess.Popen(f'explorer /select,"{filepath}"')

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

    def _toggle_unsafe_view(self):
        if self.scan_report:
            self._refresh_tree()

    def _refresh_tree(self):
        self._clear_tree()
        if not self.scan_report:
            return

        self._item_to_index = {}
        category_sizes = {}
        visible_count = 0
        for orig_idx, item in enumerate(self.scan_report.results):
            category_sizes[item.category] = category_sizes.get(item.category, 0) + item.size
            if not self.show_unsafe.get() and item.suggestion == "不建议删除":
                continue
            tree_id = self.tree.insert("", tk.END, values=(
                CHECKBOX_UNCHECKED,
                item.suggestion,
                item.category,
                item.path,
                format_file_size(item.size),
                item.last_used,
            ), tags=(item.suggestion,))
            self._item_to_index[tree_id] = orig_idx
            visible_count += 1

        self._draw_summary(category_sizes)
        self.info_label.config(
            text=f"显示 {visible_count} / {self.scan_report.total_count} 个文件，"
                 f"共占用 {format_file_size(self.scan_report.total_size)}"
        )
        self.clean_btn.config(state=tk.NORMAL if visible_count > 0 else tk.DISABLED)

    def _draw_summary(self, category_sizes: dict):
        self.summary_canvas.delete("all")
        if not category_sizes:
            return
        self.summary_canvas.update_idletasks()
        canvas_width = self.summary_canvas.winfo_width()
        total = sum(category_sizes.values())
        if total == 0:
            return

        x = 0
        for idx, (cat, size) in enumerate(category_sizes.items()):
            ratio = size / total
            box_width = max(int(canvas_width * ratio), 2)
            color = CATEGORY_COLORS[idx % len(CATEGORY_COLORS)]
            self.summary_canvas.create_rectangle(
                x, 2, x + box_width, 35, fill=color, outline="white", width=1,
            )
            label = f"{cat} {format_file_size(size)}"
            if box_width > 60:
                self.summary_canvas.create_text(
                    x + box_width / 2, 50, text=label,
                    font=("Microsoft YaHei UI", 8), fill="#333",
                )
            x += box_width

    def _start_scan(self):
        self.scan_btn.config(state=tk.DISABLED)
        self.clean_btn.config(state=tk.DISABLED)
        self._clear_tree()
        self.progress["value"] = 0
        self._scan_start_time = None

        def progress_cb(ratio, text, files_found=0):
            self.frame.after(0, lambda t=text, f=files_found: self._update_progress(ratio, t, f))

        def scan_task():
            report = self.scanner.scan(progress_callback=progress_cb)
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
            messagebox.showinfo("提示", "请先勾选要清理的文件")
            return

        files_to_clean = [self.scan_report.results[self._item_to_index[item]] for item in selected_items]

        msg = f"确定要清理选中的 {len(files_to_clean)} 个文件吗？\n\n文件将移入回收站，可随时恢复。"
        confirm = messagebox.askyesno("确认清理", msg)
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
        self.summary_canvas.delete("all")
