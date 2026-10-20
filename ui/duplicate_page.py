"""
C盘清理工具 - 重复文件扫描页面
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import time
import os
import subprocess

from core.duplicate_scanner import DuplicateScanner, DuplicateReport, DuplicateGroup
from core.cleaner import FileCleaner
from core.utils import format_file_size


CHECKBOX_UNCHECKED = "☐"
CHECKBOX_CHECKED = "☑"

GROUP_ICON = "📁"
ORIGINAL_ICON = "🟢"
DUPLICATE_ICON = "🔴"
SAFE_ICON = "✅"
RISKY_ICON = "⚠️"


class DuplicatePage:
    """重复文件扫描页面"""

    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=10)
        self.scanner = DuplicateScanner()
        self.cleaner = FileCleaner(use_trash=True)
        self.report: DuplicateReport = None
        self.scan_dirs: list = []
        self._group_files: dict = {}
        self._group_info: dict = {}
        self._file_item_map: dict = {}
        self._scan_start_time = None
        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.configure("Blue.Horizontal.TProgressbar",
                        troughcolor="#ecf0f1", background="#3498db",
                        bordercolor="#bdc3c7", lightcolor="#3498db", darkcolor="#3498db")

    def _build_ui(self):
        dir_frame = ttk.LabelFrame(self.frame, text="扫描目录", padding=8)
        dir_frame.pack(fill=tk.X, pady=(0, 8))

        self.dir_listbox = tk.Listbox(
            dir_frame, height=2, width=50, selectmode=tk.EXTENDED,
            font=("Microsoft YaHei UI", 9),
        )
        self.dir_listbox.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)

        dir_btn_frame = ttk.Frame(dir_frame)
        dir_btn_frame.pack(side=tk.LEFT)
        ttk.Button(dir_btn_frame, text="添加目录", command=self._add_dir).pack(fill=tk.X)
        ttk.Button(dir_btn_frame, text="移除选中", command=self._remove_dir).pack(fill=tk.X, pady=(2, 0))

        config_bar = ttk.Frame(self.frame)
        config_bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(config_bar, text="最小文件大小 (MB):").pack(side=tk.LEFT)
        self.threshold_var = tk.IntVar(value=1)
        ttk.Spinbox(
            config_bar, from_=1, to=10000, textvariable=self.threshold_var, width=6,
        ).pack(side=tk.LEFT, padx=(5, 10))

        self.scan_btn = ttk.Button(config_bar, text="开始扫描", command=self._start_scan)
        self.scan_btn.pack(side=tk.LEFT)

        self.clean_btn = ttk.Button(
            config_bar, text="删除选中项", command=self._start_clean, state=tk.DISABLED,
        )
        self.clean_btn.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(config_bar, text="选中建议删除", command=self._select_duplicates).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(config_bar, text="选中放心删除", command=self._select_safe).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(config_bar, text="全不选", command=self._select_none).pack(side=tk.LEFT, padx=(4, 0))

        self.progress = ttk.Progressbar(self.frame, mode="determinate", style="Blue.Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(0, 4))

        self.info_label = ttk.Label(
            self.frame, text="添加目录后点击「开始扫描」查找重复文件", foreground="gray",
        )
        self.info_label.pack(anchor=tk.W, pady=(0, 6))

        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("check", "status", "path", "size", "last_used")
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="tree headings",
            selectmode="extended", height=15,
        )
        self.tree.heading("#0", text="重复组")
        self.tree.heading("check", text="选择")
        self.tree.heading("status", text="状态")
        self.tree.heading("path", text="文件路径")
        self.tree.heading("size", text="大小")
        self.tree.heading("last_used", text="上次使用")

        self.tree.column("#0", width=200, minwidth=150)
        self.tree.column("check", width=50, minwidth=40, anchor=tk.CENTER)
        self.tree.column("status", width=70, minwidth=60, anchor=tk.CENTER)
        self.tree.column("path", width=380, minwidth=200)
        self.tree.column("size", width=80, minwidth=60, anchor=tk.E)
        self.tree.column("last_used", width=130, minwidth=100)

        self.tree.tag_configure("group", background="#eaf2f8", font=("Microsoft YaHei UI", 9, "bold"))
        self.tree.tag_configure("original", foreground="#27ae60")
        self.tree.tag_configure("duplicate", foreground="#e74c3c")
        self.tree.tag_configure("safe", foreground="#27ae60")

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)

        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_doubleclick)

    def _on_tree_click(self, event):
        col = self.tree.identify_column(event.x)
        item = self.tree.identify_row(event.y)
        if not item:
            return
        if col == "#1":
            current = self.tree.set(item, "check")
            new_val = CHECKBOX_UNCHECKED if current == CHECKBOX_CHECKED else CHECKBOX_CHECKED
            self.tree.set(item, "check", new_val)

            parent = self.tree.parent(item)
            if parent:
                self._update_group_checkbox(parent)
            elif item in self._group_files:
                for child in self.tree.get_children(item):
                    self.tree.set(child, "check", new_val)

    def _on_tree_doubleclick(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        filepath = self.tree.set(item, "path")
        if filepath and os.path.exists(filepath):
            subprocess.Popen(f'explorer /select,"{filepath}"')

    def _update_group_checkbox(self, group_id):
        children = self.tree.get_children(group_id)
        checked = sum(1 for c in children if self.tree.set(c, "check") == CHECKBOX_CHECKED)
        if checked == 0:
            self.tree.set(group_id, "check", CHECKBOX_UNCHECKED)
        elif checked == len(children):
            self.tree.set(group_id, "check", CHECKBOX_CHECKED)
        else:
            self.tree.set(group_id, "check", "◐")

    def _select_duplicates(self):
        for group_id in self._group_files:
            for child in self.tree.get_children(group_id):
                status = self.tree.set(child, "status")
                if DUPLICATE_ICON in status or SAFE_ICON in status:
                    self.tree.set(child, "check", CHECKBOX_CHECKED)
            self._update_group_checkbox(group_id)

    def _select_safe(self):
        for group_id in self._group_files:
            for child in self.tree.get_children(group_id):
                status = self.tree.set(child, "status")
                if SAFE_ICON in status:
                    self.tree.set(child, "check", CHECKBOX_CHECKED)
            self._update_group_checkbox(group_id)

    def _select_none(self):
        for item in self.tree.get_children(""):
            self._set_all_checks(item, CHECKBOX_UNCHECKED)

    def _set_all_checks(self, item, value):
        self.tree.set(item, "check", value)
        for child in self.tree.get_children(item):
            self.tree.set(child, "check", value)

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

    def _refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._group_files = {}
        self._group_info = {}
        self._file_item_map = {}

        if not self.report:
            return

        for group_idx, group in enumerate(self.report.groups):
            group_id = self.tree.insert(
                "", tk.END,
                text=f"{GROUP_ICON} 重复组 {group_idx + 1}（{len(group.files)} 个文件，浪费 {format_file_size(group.waste)}）",
                values=(CHECKBOX_UNCHECKED, "", "", "", ""),
                tags=("group",),
            )
            self._group_files[group_id] = []
            self._group_info[group_id] = group

            for file_idx, f in enumerate(group.files):
                if file_idx == 0:
                    icon, status_text, tag = ORIGINAL_ICON, "保留", "original"
                elif f in group.safe_files:
                    icon, status_text, tag = SAFE_ICON, "放心删除", "safe"
                else:
                    icon, status_text, tag = RISKY_ICON, "谨慎删除", "duplicate"

                file_id = self.tree.insert(
                    group_id, tk.END,
                    text="",
                    values=(
                        CHECKBOX_UNCHECKED if file_idx > 0 else "—",
                        f"{icon} {status_text}",
                        f.path,
                        format_file_size(f.size),
                        f.last_used,
                    ),
                    tags=(tag,),
                )
                self._group_files[group_id].append(file_id)
                self._file_item_map[file_id] = f

        total_safe = sum(len(g.safe_files) for g in self.report.groups)
        safe_waste = sum(f.size for g in self.report.groups for f in g.safe_files)

        self.info_label.config(
            text=f"发现 {self.report.total_groups} 组重复文件，"
                 f"可释放 {format_file_size(self.report.total_waste)} 空间"
                 f"  |  其中 {total_safe} 个可放心删除（{format_file_size(safe_waste)}）"
        )
        self.clean_btn.config(state=tk.NORMAL if self.report.total_groups > 0 else tk.DISABLED)

    def _start_scan(self):
        if not self.scan_dirs:
            messagebox.showwarning("提示", "请至少添加一个扫描目录")
            return

        self.scan_btn.config(state=tk.DISABLED)
        self.clean_btn.config(state=tk.DISABLED)
        self.progress["value"] = 0
        self._scan_start_time = None

        threshold = self.threshold_var.get()
        self.scanner = DuplicateScanner(threshold_mb=threshold)
        dirs_to_scan = list(self.scan_dirs)

        def progress_cb(ratio, text, groups_found=0):
            self.frame.after(0, lambda t=text, g=groups_found: self._update_progress(ratio, t, g))

        def scan_task():
            report = self.scanner.scan(scan_dirs=dirs_to_scan, progress_callback=progress_cb)
            self.frame.after(0, lambda: self._on_scan_done(report))

        threading.Thread(target=scan_task, daemon=True).start()

    def _update_progress(self, ratio: float, text: str, groups_found: int = 0):
        if self._scan_start_time is None:
            self._scan_start_time = time.time()
        self.progress["value"] = ratio * 100
        elapsed = int(time.time() - self._scan_start_time)
        mins, secs = divmod(elapsed, 60)
        time_str = f"{mins}分{secs}秒" if mins > 0 else f"{secs}秒"
        self.info_label.config(text=f"{text}  |  已耗时 {time_str}  |  重复组 {groups_found}")

    def _on_scan_done(self, report: DuplicateReport):
        self.report = report
        self._refresh_tree()
        self.scan_btn.config(state=tk.NORMAL)

    def _start_clean(self):
        files_to_clean = []
        items_to_remove = []

        for group_id, file_ids in self._group_files.items():
            for file_id in file_ids:
                if self.tree.set(file_id, "check") == CHECKBOX_CHECKED:
                    if file_id in self._file_item_map:
                        files_to_clean.append(self._file_item_map[file_id])
                        items_to_remove.append((group_id, file_id))

        if not files_to_clean:
            messagebox.showinfo("提示", "请先勾选要删除的重复文件")
            return

        msg = (
            f"确定要将 {len(files_to_clean)} 个重复文件移入回收站吗？\n"
            f"共可释放 {format_file_size(sum(f.size for f in files_to_clean))} 空间\n\n"
            "文件可随时从回收站恢复。"
        )
        confirm = messagebox.askyesno("确认删除", msg)
        if not confirm:
            return

        succeeded, failed = self.cleaner.clean_files(files_to_clean)

        for group_id, file_id in items_to_remove:
            self.tree.delete(file_id)
            if file_id in self._group_files.get(group_id, []):
                self._group_files[group_id].remove(file_id)
            self._file_item_map.pop(file_id, None)

        groups_to_delete = []
        for group_id, file_ids in self._group_files.items():
            remaining = len(file_ids)
            if remaining <= 1:
                groups_to_delete.append(group_id)
            else:
                group = self._group_info[group_id]
                remaining_files = [self._file_item_map[fid] for fid in file_ids if fid in self._file_item_map]
                group.files = remaining_files if remaining_files else group.files[:1]
                new_waste = group.file_size * (len(group.files) - 1)
                group.waste = new_waste
                self.tree.item(
                    group_id,
                    text=f"{GROUP_ICON} 重复组（{len(group.files)} 个文件，浪费 {format_file_size(new_waste)}）",
                )

        for group_id in groups_to_delete:
            remaining_children = self.tree.get_children(group_id)
            self.tree.delete(group_id)
            for child in remaining_children:
                self._file_item_map.pop(child, None)
            del self._group_files[group_id]
            del self._group_info[group_id]

        result_msg = f"成功清理 {len(succeeded)} 个文件"
        if failed:
            result_msg += f"，{len(failed)} 个文件清理失败"
        self.info_label.config(text=result_msg)

        if not self.tree.get_children(""):
            self.clean_btn.config(state=tk.DISABLED)
