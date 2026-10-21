"""
C盘清理工具 - 磁盘空间树状图扫描引擎
基于 squarified treemap 算法将目录空间占用可视化
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional, Callable, Tuple

from core.utils import get_file_size_safe


TOP_N = 15


@dataclass
class TreemapNode:
    """树状图节点（文件或目录）"""
    name: str
    path: str
    size: int = 0
    is_dir: bool = True
    children: List["TreemapNode"] = field(default_factory=list)
    is_other: bool = False

    @property
    def is_leaf(self) -> bool:
        return not self.is_dir or (self.is_dir and not self.children)


class TreemapScanner:
    """磁盘空间树状图扫描器"""

    def __init__(self):
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def scan_root(
        self,
        root_path: str,
        progress_callback: Optional[Callable] = None,
    ) -> TreemapNode:
        """扫描指定根目录，返回带子节点的根节点"""
        self._stop_requested = False
        if progress_callback:
            progress_callback(f"正在扫描 {root_path}", 0.0)

        root = TreemapNode(
            name=os.path.basename(root_path) or root_path,
            path=root_path,
            is_dir=True,
        )
        root.size, root.children = self._scan_children(root_path, depth=0)
        root.is_other = False

        if progress_callback:
            progress_callback("扫描完成", 1.0)
        return root

    def scan_drilldown(
        self,
        dir_path: str,
        progress_callback: Optional[Callable] = None,
    ) -> TreemapNode:
        """下钻扫描：返回指定目录的节点（含子节点）"""
        if progress_callback:
            progress_callback(f"正在扫描 {dir_path}", 0.0)
        if not os.path.isdir(dir_path):
            return TreemapNode(name=os.path.basename(dir_path), path=dir_path, is_dir=False)

        node = TreemapNode(
            name=os.path.basename(dir_path) or dir_path,
            path=dir_path,
            is_dir=True,
        )
        node.size, node.children = self._scan_children(dir_path, depth=0)

        if progress_callback:
            progress_callback("扫描完成", 1.0)
        return node

    def _scan_children(self, dir_path: str, depth: int) -> Tuple[int, List[TreemapNode]]:
        """扫描目录的直接子项，返回 (总大小, 子节点列表)；子节点限制为 TOP_N"""
        total_size = 0
        entries = []

        try:
            with os.scandir(dir_path) as it:
                for entry in it:
                    if self._stop_requested:
                        break
                    try:
                        if entry.is_file(follow_symlinks=False):
                            size = get_file_size_safe(entry.path)
                            total_size += size
                            entries.append((entry.name, entry.path, False, size))
                        elif entry.is_dir(follow_symlinks=False):
                            if entry.name in ("$RECYCLE.BIN", "System Volume Information",
                                              "Recovery", "$WINDOWS.~BT", "$WINDOWS.~WS"):
                                continue
                            size = self._dir_size(entry.path, max_depth=2)
                            total_size += size
                            entries.append((entry.name, entry.path, True, size))
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            pass

        entries.sort(key=lambda e: e[3], reverse=True)

        top_entries = entries[:TOP_N]
        rest = entries[TOP_N:]
        other_size = sum(e[3] for e in rest)
        other_count = len(rest)

        children: List[TreemapNode] = []
        for name, path, is_dir, size in top_entries:
            node = TreemapNode(name=name, path=path, size=size, is_dir=is_dir)
            if is_dir and depth < 1:
                _, node.children = self._scan_children(path, depth + 1)
            children.append(node)

        if other_count > 0:
            children.append(TreemapNode(
                name=f"其他 {other_count} 项",
                path="",
                size=other_size,
                is_dir=False,
                is_other=True,
            ))

        return total_size, children

    @staticmethod
    def _dir_size(dir_path: str, max_depth: int = 2) -> int:
        """快速估算目录大小（限制深度避免过慢）"""
        total = 0
        try:
            for root, dirs, files in os.walk(dir_path):
                depth = root.replace(dir_path, "").count(os.sep)
                if depth >= max_depth:
                    dirs.clear()
                    continue
                for f in files:
                    total += get_file_size_safe(os.path.join(root, f))
        except (PermissionError, OSError):
            pass
        return total


def squarified_layout(
    node: TreemapNode,
    rect: Tuple[float, float, float, float],
) -> List[Tuple[TreemapNode, Tuple[float, float, float, float]]]:
    """
    对给定节点执行 squarified treemap 布局。
    rect = (x, y, w, h)。返回 [(子节点, (x, y, w, h)), ...]
    """
    x, y, w, h = rect
    if w <= 0 or h <= 0 or not node.children:
        return []

    total_size = sum(c.size for c in node.children)
    if total_size <= 0:
        return []

    area = w * h
    scaled = [(c, max(c.size / total_size * area, 0)) for c in node.children if c.size > 0]
    if not scaled:
        return []

    return _layout_rows(scaled, x, y, w, h)


def _layout_rows(items, x, y, w, h):
    """squarified 算法主循环：保证所有 items 都被放置"""
    result = []
    remaining = list(items)

    while remaining:
        if w < 0.5 or h < 0.5:
            for node, _ in remaining:
                result.append((node, (x, y, 0, 0)))
            break

        short_side = min(w, h)
        row = [remaining[0]]
        row_area = remaining[0][1]
        remaining = remaining[1:]

        while remaining:
            next_item = remaining[0]
            next_area = next_item[1]
            new_area = row_area + next_area

            current_worst = _worst_aspect([a for _, a in row], short_side, row_area)
            test_row = [a for _, a in row] + [next_area]
            new_worst = _worst_aspect(test_row, short_side, new_area)

            if new_worst <= current_worst:
                row.append(next_item)
                row_area = new_area
                remaining = remaining[1:]
            else:
                break

        if w >= h:
            row_height = row_area / w if w > 0 else 0
            rx = x
            while row:
                node, a = row.pop(0)
                rw = a / row_height if row_height > 0 else 0
                result.append((node, (rx, y, rw, row_height)))
                rx += rw
            y += row_height
            h -= row_height
        else:
            row_width = row_area / h if h > 0 else 0
            ry = y
            while row:
                node, a = row.pop(0)
                rh = a / row_width if row_width > 0 else 0
                result.append((node, (x, ry, row_width, rh)))
                ry += rh
            x += row_width
            w -= row_width

    return result


def _worst_aspect(areas, short_side, row_area):
    """计算一行的最差长宽比（越接近 1 越好）"""
    if row_area <= 0 or short_side <= 0:
        return float("inf")
    s = sum(areas)
    if s <= 0:
        return float("inf")
    worst = 0.0
    for a in areas:
        if a <= 0:
            continue
        r = (short_side * short_side * a) / (s * s)
        if r > worst:
            worst = r
    return max(worst, 1.0 / worst) if worst > 0 else float("inf")
