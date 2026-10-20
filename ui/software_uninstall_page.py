"""
C盘清理工具 - 软件卸载管理页面
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import subprocess
import time

from core.software_scanner import SoftwareScanner, SoftwareInfo
from core.utils import format_file_size


CHECKBOX_UNCHECKED = "☐"
CHECKBOX_CHECKED = "☑"


class SoftwareUninstallPage:
    """软件卸载管理页面"""

    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=10)
        self.scanner = SoftwareScanner()
        self._software_list = []
        self._item_map = {}
        self._scan_start_time = None
        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.configure("Blue.Horizontal.TProgressbar",
                        troughcolor="#ecf0f1", background="#3498db",
                        bordercolor="#bdc3c7", lightcolor="#3498db", darkcolor="#3498db")
        style.configure("Unused.Treeview.Cell", background="#fff3cd")

    def _build_ui(self):
        top_bar = ttk.Frame(self.frame)
        top_bar.pack(fill=tk.X, pady=(0, 8))

        self.scan_btn = ttk.Button(top_bar, text="扫描已安装软件",
                                   command=self._start_scan)
        self.scan_btn.pack(side=tk.LEFT)

        self.uninstall_btn = ttk.Button(top_bar, text="卸载选中",
                                        command=self._start_uninstall,
                                        state=tk.DISABLED)
        self.uninstall_btn.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Separator(top_bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        self.filter_unused_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            top_bar, text="仅显示超过半年未使用的软件",
            variable=self.filter_unused_var,
            command=self._apply_filter,
        ).pack(side=tk.LEFT)

        ttk.Button(top_bar, text="全选", command=self._select_all).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(top_bar, text="全不选", command=self._select_none).pack(side=tk.LEFT, padx=(4, 0))

        self.progress = ttk.Progressbar(self.frame, mode="determinate",
                                        style="Blue.Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(0, 4))

        self.info_label = ttk.Label(
            self.frame,
            text="点击「扫描已安装软件」列出所有程序",
            foreground="gray",
        )
        self.info_label.pack(anchor=tk.W, pady=(0, 6))

        tree_frame = ttk.Frame(self.frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("check", "name", "version", "publisher", "install_date",
                   "size", "last_used", "status")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                 selectmode="extended")

        self.tree.heading("check", text="")
        self.tree.heading("name", text="软件名称")
        self.tree.heading("version", text="版本")
        self.tree.heading("publisher", text="发布者")
        self.tree.heading("install_date", text="安装日期")
        self.tree.heading("size", text="占用空间")
        self.tree.heading("last_used", text="最近活动")
        self.tree.heading("status", text="状态")

        self.tree.column("check", width=32, minwidth=32, anchor=tk.CENTER, stretch=False)
        self.tree.column("name", width=240, anchor=tk.W)
        self.tree.column("version", width=90, anchor=tk.CENTER)
        self.tree.column("publisher", width=160, anchor=tk.W)
        self.tree.column("install_date", width=90, anchor=tk.CENTER)
        self.tree.column("size", width=90, anchor=tk.E)
        self.tree.column("last_used", width=100, anchor=tk.CENTER)
        self.tree.column("status", width=120, anchor=tk.CENTER)

        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)

        legend = ttk.Frame(self.frame)
        legend.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(
            legend,
            text="提示：「最近活动」基于安装目录内文件修改时间推断；"
                 "「状态」为「超过半年未使用」的软件可酌情卸载",
            foreground="#7f8c8d", font=("Microsoft YaHei UI", 8),
        ).pack(side=tk.LEFT)

    def _start_scan(self):
        self.scan_btn.config(state=tk.DISABLED)
        self.uninstall_btn.config(state=tk.DISABLED)
        self.progress["value"] = 0
        self._scan_start_time = time.time()
        self._software_list = []
        self._item_map = {}
        for item in self.tree.get_children():
            self.tree.delete(item)

        def progress_cb(text, ratio):
            self.frame.after(0, lambda t=text, r=ratio: self._update_progress(t, r))

        def scan_task():
            software = self.scanner.scan_installed(progress_callback=progress_cb)
            self.scanner.detect_unused(software, progress_callback=progress_cb)
            self.frame.after(0, lambda: self._on_scan_done(software))

        threading.Thread(target=scan_task, daemon=True).start()

    def _update_progress(self, text: str, ratio: float):
        self.progress["value"] = ratio * 100
        self.info_label.config(text=text)

    def _on_scan_done(self, software: list):
        self._software_list = software
        self.progress["value"] = 100

        total_size = sum(s.estimated_size for s in software)
        unused_count = sum(1 for s in software if s.is_unused)

        elapsed = time.time() - self._scan_start_time if self._scan_start_time else 0
        self.info_label.config(
            text=f"扫描完成：共 {len(software)} 个软件，"
                 f"占用 {format_file_size(total_size)}，"
                 f"其中 {unused_count} 个超过半年未使用（耗时 {elapsed:.1f}s）"
        )

        for sw in software:
            self._insert_software(sw)

        self.scan_btn.config(state=tk.NORMAL)
        self.uninstall_btn.config(state=tk.NORMAL)
        self._apply_filter()

    def _insert_software(self, sw: SoftwareInfo):
        status = "超过半年未使用" if sw.is_unused else "近期使用"
        install_date_display = self._format_install_date(sw.install_date)
        values = (
            CHECKBOX_UNCHECKED,
            sw.name,
            sw.version,
            sw.publisher,
            install_date_display,
            format_file_size(sw.estimated_size) if sw.estimated_size else "-",
            sw.last_used_display,
            status,
        )
        tags = ("unused",) if sw.is_unused else ()
        item_id = self.tree.insert("", tk.END, values=values, tags=tags)
        self._item_map[item_id] = sw

    @staticmethod
    def _format_install_date(date_str: str) -> str:
        if not date_str or len(date_str) != 8:
            return date_str or "-"
        try:
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        except Exception:
            return date_str

    def _on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        if col != "#1":
            return
        item = self.tree.identify_row(event.y)
        if not item:
            return
        if item not in self.tree.get_children():
            return
        current = self.tree.set(item, "check")
        new_val = CHECKBOX_UNCHECKED if current == CHECKBOX_CHECKED else CHECKBOX_CHECKED
        self.tree.set(item, "check", new_val)

    def _select_all(self):
        for item in self.tree.get_children():
            self.tree.set(item, "check", CHECKBOX_CHECKED)

    def _select_none(self):
        for item in self.tree.get_children():
            self.tree.set(item, "check", CHECKBOX_UNCHECKED)

    def _select_unused(self):
        self._select_none()
        for item in self.tree.get_children():
            tags = self.tree.item(item, "tags")
            if "unused" in tags:
                self.tree.set(item, "check", CHECKBOX_CHECKED)

    def _apply_filter(self):
        show_only_unused = self.filter_unused_var.get()
        all_items = list(self._item_map.keys())
        for item in all_items:
            tags = self.tree.item(item, "tags")
            is_unused = "unused" in tags
            try:
                self.tree.parent(item)
                in_tree = True
            except tk.TclError:
                in_tree = False
            if item in self.tree.get_children():
                in_tree = True
            if show_only_unused and not is_unused:
                if in_tree:
                    self.tree.detach(item)
            else:
                if not in_tree:
                    try:
                        self.tree.reattach(item, "", "end")
                    except tk.TclError:
                        pass

    def _start_uninstall(self):
        selected = []
        for item in self.tree.get_children():
            if self.tree.set(item, "check") == CHECKBOX_CHECKED:
                sw = self._item_map.get(item)
                if sw:
                    selected.append(sw)

        if not selected:
            messagebox.showinfo("提示", "请先勾选要卸载的软件")
            return

        names = "\n".join(f"• {s.name}" for s in selected[:10])
        if len(selected) > 10:
            names += f"\n... 共 {len(selected)} 个"
        msg = (
            f"确定要卸载以下软件吗？\n\n{names}\n\n"
            "将依次调用各软件自带的卸载程序，请在弹出的卸载向导中完成操作。"
        )
        if not messagebox.askyesno("确认卸载", msg):
            return

        self.uninstall_btn.config(state=tk.DISABLED)
        self.scan_btn.config(state=tk.DISABLED)

        def uninstall_task():
            results = []
            for sw in selected:
                success = self._launch_uninstaller(sw)
                results.append((sw.name, success))
            self.frame.after(0, lambda: self._on_uninstall_done(results))

        threading.Thread(target=uninstall_task, daemon=True).start()

    @staticmethod
    def _launch_uninstaller(sw: SoftwareInfo) -> bool:
        if not sw.uninstall_string:
            return False
        cmd = sw.uninstall_string
        try:
            if cmd.lower().startswith("msiexec"):
                subprocess.Popen(cmd, shell=True)
            else:
                subprocess.Popen(cmd, shell=True)
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    def _on_uninstall_done(self, results):
        success = sum(1 for _, ok in results if ok)
        failed = len(results) - success
        msg = f"卸载调用完成：{success} 个已启动卸载程序"
        if failed:
            msg += f"，{failed} 个失败（可能缺少卸载命令）"
        self.info_label.config(text=msg)
        self.uninstall_btn.config(state=tk.NORMAL)
        self.scan_btn.config(state=tk.NORMAL)
        if success:
            messagebox.showinfo(
                "卸载已启动",
                "请在弹出的卸载向导窗口中完成卸载操作。\n"
                "完成后可重新点击「扫描已安装软件」刷新列表。",
            )
