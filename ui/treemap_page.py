"""
C盘清理工具 - 磁盘空间可视化树状图页面
基于 squarified treemap 算法，支持交互式下钻
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import string

from core.treemap_scanner import TreemapScanner, TreemapNode, squarified_layout
from core.utils import format_file_size


DRIVE_COLORS = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
    "#3498db", "#e67e22", "#27ae60", "#9b59b6", "#1abc9c",
    "#e74c3c",
]


class TreemapPage:
    """磁盘空间树状图页面"""

    def __init__(self, parent):
        self.frame = ttk.Frame(parent, padding=10)
        self.scanner = TreemapScanner()
        self._current_node = None
        self._rects = []
        self._color_map = {}
        self._hovered_rect = None
        self._tooltip = None
        self._node_stack = []
        self._scan_start_time = None
        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.configure("Blue.Horizontal.TProgressbar",
                        troughcolor="#ecf0f1", background="#3498db",
                        bordercolor="#bdc3c7", lightcolor="#3498db", darkcolor="#3498db")

    def _build_ui(self):
        top_bar = ttk.Frame(self.frame)
        top_bar.pack(fill=tk.X, pady=(0, 6))

        self.drive_var = tk.StringVar(value="C:\\")
        drive_combo = ttk.Combobox(top_bar, textvariable=self.drive_var, width=8,
                                   values=self._list_drives(), state="readonly")
        drive_combo.pack(side=tk.LEFT)

        self.scan_btn = ttk.Button(top_bar, text="开始扫描", command=self._start_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.back_btn = ttk.Button(top_bar, text="◀ 返回上一级",
                                   command=self._go_back, state=tk.DISABLED)
        self.back_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.home_btn = ttk.Button(top_bar, text="⌂ 回到根",
                                   command=self._go_home, state=tk.DISABLED)
        self.home_btn.pack(side=tk.LEFT, padx=(4, 0))

        self.breadcrumb_frame = ttk.Frame(self.frame)
        self.breadcrumb_frame.pack(fill=tk.X, pady=(0, 4))

        self.progress = ttk.Progressbar(self.frame, mode="determinate",
                                        style="Blue.Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(0, 4))

        self.info_label = ttk.Label(
            self.frame,
            text="选择磁盘或文件夹，点击「开始扫描」查看空间占用分布",
            foreground="gray",
        )
        self.info_label.pack(anchor=tk.W, pady=(0, 4))

        canvas_container = ttk.Frame(self.frame)
        canvas_container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_container, bg="#2c3e50", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<Leave>", self._on_mouse_leave)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", self._on_right_click)

    @staticmethod
    def _list_drives():
        drives = []
        for letter in string.ascii_uppercase:
            path = f"{letter}:\\"
            if os.path.exists(path):
                drives.append(path)
        return drives

    def _start_scan(self):
        path = self.drive_var.get()
        if not path:
            return
        if os.path.isfile(path):
            path = os.path.dirname(path)
        self._node_stack = []
        self._scan_path(path)

    def _scan_path(self, path: str):
        self.scan_btn.config(state=tk.DISABLED)
        self.back_btn.config(state=tk.DISABLED)
        self.home_btn.config(state=tk.DISABLED)
        self.progress["value"] = 0
        self._scan_start_time = time.time()
        self._rects = []
        self._color_map = {}
        self.canvas.delete("all")

        def progress_cb(text, ratio):
            self.frame.after(0, lambda t=text, r=ratio: self._update_progress(t, r))

        def scan_task():
            node = self.scanner.scan_root(path, progress_callback=progress_cb)
            self.frame.after(0, lambda: self._on_scan_done(node))

        threading.Thread(target=scan_task, daemon=True).start()

    def _drill_down(self, node: TreemapNode):
        if not node.is_dir or node.is_other:
            return
        if node.children:
            self._navigate_to(node)
            return
        self.scan_btn.config(state=tk.DISABLED)
        self.back_btn.config(state=tk.DISABLED)
        self.home_btn.config(state=tk.DISABLED)
        self.progress["value"] = 0
        self._rects = []
        self._color_map = {}
        self.canvas.delete("all")

        def progress_cb(text, ratio):
            self.frame.after(0, lambda t=text, r=ratio: self._update_progress(t, r))

        def scan_task():
            new_node = self.scanner.scan_drilldown(node.path, progress_callback=progress_cb)
            self.frame.after(0, lambda: self._on_drill_done(new_node))

        threading.Thread(target=scan_task, daemon=True).start()

    def _navigate_to(self, node: TreemapNode):
        self._current_node = node
        self.progress["value"] = 100
        self.info_label.config(
            text=f"{node.name}：{format_file_size(node.size)}，"
                 f"{len(node.children)} 个子项（缓存命中）"
        )
        self._update_breadcrumb()
        self._render()
        self.scan_btn.config(state=tk.NORMAL)
        self.back_btn.config(state=tk.NORMAL if self._node_stack else tk.DISABLED)
        self.home_btn.config(state=tk.NORMAL if self._node_stack else tk.DISABLED)

    def _update_progress(self, text: str, ratio: float):
        self.progress["value"] = ratio * 100
        self.info_label.config(text=text)

    def _on_scan_done(self, node: TreemapNode):
        self._current_node = node
        self._node_stack = []
        self._finish_scan(node)

    def _on_drill_done(self, node: TreemapNode):
        self._current_node = node
        self._finish_scan(node)

    def _finish_scan(self, node: TreemapNode):
        self.progress["value"] = 100
        elapsed = time.time() - self._scan_start_time if self._scan_start_time else 0
        self.info_label.config(
            text=f"{node.name}：{format_file_size(node.size)}，"
                 f"{len(node.children)} 个子项（耗时 {elapsed:.1f}s）"
        )
        self._update_breadcrumb()
        self._render()
        self.scan_btn.config(state=tk.NORMAL)
        self.back_btn.config(state=tk.NORMAL if self._node_stack else tk.DISABLED)
        self.home_btn.config(state=tk.NORMAL if self._node_stack else tk.DISABLED)

    def _update_breadcrumb(self):
        for widget in self.breadcrumb_frame.winfo_children():
            widget.destroy()

        full_path = self._node_stack + [self._current_node]
        for idx, node in enumerate(full_path):
            is_last = idx == len(full_path) - 1
            if idx > 0:
                ttk.Label(self.breadcrumb_frame, text=" › ",
                          foreground="#95a5a6").pack(side=tk.LEFT)
            if is_last:
                ttk.Label(self.breadcrumb_frame, text=node.name,
                          font=("Microsoft YaHei UI", 9, "bold")).pack(side=tk.LEFT)
            else:
                link = ttk.Label(self.breadcrumb_frame, text=node.name,
                                 foreground="#3498db", cursor="hand2")
                link.pack(side=tk.LEFT)
                target_idx = idx
                link.bind("<Button-1>",
                          lambda e, i=target_idx: self._jump_to(i))

    def _jump_to(self, index: int):
        target = self._node_stack[index]
        self._node_stack = self._node_stack[:index]
        self._navigate_to(target)

    def _go_back(self):
        if not self._node_stack:
            return
        prev = self._node_stack.pop()
        self._navigate_to(prev)

    def _go_home(self):
        if not self._node_stack:
            return
        first = self._node_stack[0]
        self._node_stack = []
        self._navigate_to(first)

    def _on_canvas_resize(self, event):
        if self._current_node:
            self._render()

    def _render(self):
        self.canvas.delete("all")
        self._rects = []
        self._color_map = {}
        if not self._current_node or not self._current_node.children:
            return

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        if width <= 1 or height <= 1:
            return

        layout = squarified_layout(self._current_node, (0, 0, width, height))
        total_size = self._current_node.size or 1

        for idx, (node, rect) in enumerate(layout):
            x, y, w, h = rect
            color = self._pick_color(node, idx)
            self._color_map[id(node)] = color

            fill = color
            outline = "#1a252f"
            width_line = 1

            rect_id = self.canvas.create_rectangle(
                x, y, x + w, y + h, fill=fill, outline=outline, width=width_line,
            )
            self._rects.append((rect_id, node, rect, color))

            self._draw_label(node, rect, total_size)

    def _pick_color(self, node: TreemapNode, idx: int) -> str:
        if node.is_other:
            return "#7f8c8d"
        return DRIVE_COLORS[idx % len(DRIVE_COLORS)]

    def _draw_label(self, node: TreemapNode, rect, total_size: int):
        x, y, w, h = rect
        if w < 50 or h < 22:
            return

        pct = (node.size / total_size * 100) if total_size > 0 else 0
        size_text = format_file_size(node.size)
        name_text = node.name

        max_chars = int(w / 10)
        if len(name_text) > max_chars:
            name_text = name_text[:max(max_chars - 1, 1)] + "…"

        text_color = "white"
        if h >= 42:
            self.canvas.create_text(
                x + 6, y + 8, anchor=tk.NW, text=name_text,
                fill=text_color, font=("Microsoft YaHei UI", 9, "bold"),
            )
            self.canvas.create_text(
                x + 6, y + 28, anchor=tk.NW,
                text=f"{size_text} ({pct:.1f}%)",
                fill="#ecf0f1", font=("Microsoft YaHei UI", 8),
            )
        else:
            self.canvas.create_text(
                x + 6, y + h / 2, anchor=tk.W,
                text=f"{name_text}  {size_text}",
                fill=text_color, font=("Microsoft YaHei UI", 8),
            )

    def _find_rect_at(self, x: float, y: float):
        for rect_id, node, rect, color in self._rects:
            rx, ry, rw, rh = rect
            if rx <= x <= rx + rw and ry <= y <= ry + rh:
                return rect_id, node, rect, color
        return None

    def _on_mouse_move(self, event):
        hit = self._find_rect_at(event.x, event.y)

        if self._hovered_rect:
            prev_id, prev_node, prev_rect, prev_color = self._hovered_rect
            try:
                self.canvas.itemconfig(prev_id, fill=prev_color, outline="#1a252f", width=1)
            except tk.TclError:
                pass
            self._hovered_rect = None

        if hit:
            rect_id, node, rect, color = hit
            hover_color = self._lighten(color, 0.25)
            self.canvas.itemconfig(rect_id, fill=hover_color, outline="#f1c40f", width=2)
            self._hovered_rect = hit
            self._show_tooltip(event, node)
            self.canvas.config(cursor="hand2" if node.is_dir and not node.is_other else "arrow")
        else:
            self._hide_tooltip()
            self.canvas.config(cursor="arrow")

    def _on_mouse_leave(self, event):
        if self._hovered_rect:
            prev_id, prev_node, prev_rect, prev_color = self._hovered_rect
            try:
                self.canvas.itemconfig(prev_id, fill=prev_color, outline="#1a252f", width=1)
            except tk.TclError:
                pass
            self._hovered_rect = None
        self._hide_tooltip()

    def _on_click(self, event):
        hit = self._find_rect_at(event.x, event.y)
        if not hit:
            return
        rect_id, node, rect, color = hit
        if node.is_dir and not node.is_other:
            self._node_stack.append(self._current_node)
            self._drill_down(node)
        elif node.path and os.path.exists(node.path):
            try:
                if os.path.isfile(node.path):
                    os.startfile(os.path.dirname(node.path))
                else:
                    os.startfile(node.path)
            except (OSError, AttributeError):
                pass

    def _on_right_click(self, event):
        if self._node_stack:
            self._go_back()

    def _show_tooltip(self, event, node: TreemapNode):
        self._hide_tooltip()
        if not self._current_node:
            return
        total_size = self._current_node.size or 1
        pct = node.size / total_size * 100
        text = f"{node.name}\n大小: {format_file_size(node.size)}\n占比: {pct:.2f}%"
        if node.path:
            text += f"\n路径: {node.path}"

        tx = event.x + 15
        ty = event.y + 15
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if tx + 250 > canvas_w:
            tx = event.x - 260
        if ty + 80 > canvas_h:
            ty = event.y - 90

        self._tooltip = tk.Toplevel(self.canvas)
        self._tooltip.wm_overrideredirect(True)
        self._tooltip.wm_geometry(f"+{self.canvas.winfo_rootx() + tx}+"
                                  f"{self.canvas.winfo_rooty() + ty}")
        self._tooltip.configure(bg="#34495e")

        label = tk.Label(
            self._tooltip, text=text, justify=tk.LEFT,
            bg="#34495e", fg="white", font=("Microsoft YaHei UI", 9),
            padx=8, pady=6,
        )
        label.pack()

    def _hide_tooltip(self):
        if self._tooltip:
            try:
                self._tooltip.destroy()
            except tk.TclError:
                pass
            self._tooltip = None

    @staticmethod
    def _lighten(hex_color: str, amount: float) -> str:
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = min(255, int(r + (255 - r) * amount))
        g = min(255, int(g + (255 - g) * amount))
        b = min(255, int(b + (255 - b) * amount))
        return f"#{r:02x}{g:02x}{b:02x}"
