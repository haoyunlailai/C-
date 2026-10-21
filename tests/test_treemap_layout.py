import pytest

from core.treemap_scanner import (
    TreemapNode,
    _worst_aspect,
    squarified_layout,
)


def make_root(*sizes: int) -> TreemapNode:
    root = TreemapNode(name="root", path="C:\\root")
    root.children = [
        TreemapNode(name=f"n{i}", path=f"C:\\root\\n{i}", size=size)
        for i, size in enumerate(sizes)
    ]
    return root


def area(rect) -> float:
    return rect[2] * rect[3]


def assert_inside(rect, bounds, epsilon=1e-6):
    x, y, w, h = rect
    bx, by, bw, bh = bounds
    assert w >= 0 and h >= 0
    assert x >= bx - epsilon
    assert y >= by - epsilon
    assert x + w <= bx + bw + epsilon
    assert y + h <= by + bh + epsilon


def assert_no_overlap(layout, epsilon=1e-6):
    rects = [rect for _, rect in layout]
    for i, (x1, y1, w1, h1) in enumerate(rects):
        for x2, y2, w2, h2 in rects[i + 1:]:
            overlap_w = min(x1 + w1, x2 + w2) - max(x1, x2)
            overlap_h = min(y1 + h1, y2 + h2) - max(y1, y2)
            assert overlap_w <= epsilon or overlap_h <= epsilon


class TestSquarifiedLayout:
    def test_no_children_returns_empty(self):
        node = TreemapNode(name="root", path="C:\\root")
        assert squarified_layout(node, (0, 0, 100, 100)) == []

    def test_all_zero_sizes_returns_empty(self):
        assert squarified_layout(make_root(0, 0), (0, 0, 100, 100)) == []

    def test_degenerate_rect_returns_empty(self):
        node = make_root(10, 20)
        assert squarified_layout(node, (0, 0, 0, 100)) == []
        assert squarified_layout(node, (0, 0, 100, 0)) == []
        assert squarified_layout(node, (0, 0, -10, 100)) == []

    def test_every_node_placed_exactly_once(self):
        node = make_root(50, 30, 15, 5)
        layout = squarified_layout(node, (0, 0, 100, 100))
        names = [n.name for n, _ in layout]
        assert len(names) == 4
        assert sorted(names) == ["n0", "n1", "n2", "n3"]

    def test_zero_sized_children_are_skipped(self):
        node = make_root(10, 0, 30)
        layout = squarified_layout(node, (0, 0, 100, 100))
        assert [n.name for n, _ in layout] == ["n0", "n2"]

    def test_area_is_proportional_to_size(self):
        node = make_root(50, 30, 15, 5)
        layout = squarified_layout(node, (0, 0, 100, 100))
        areas = {n.name: area(rect) for n, rect in layout}
        assert areas["n0"] == pytest.approx(5000)
        assert areas["n1"] == pytest.approx(3000)
        assert areas["n2"] == pytest.approx(1500)
        assert areas["n3"] == pytest.approx(500)
        assert sum(areas.values()) == pytest.approx(10000)

    def test_rectangular_container_conserves_area(self):
        bounds = (10, 20, 300, 100)
        node = make_root(6, 6, 4, 3, 2, 2, 1)
        layout = squarified_layout(node, bounds)
        assert len(layout) == 7
        assert sum(area(rect) for _, rect in layout) == pytest.approx(30000)
        for _, rect in layout:
            assert_inside(rect, bounds)
        assert_no_overlap(layout)

    def test_single_child_fills_container(self):
        node = make_root(42)
        _, rect = squarified_layout(node, (5, 5, 200, 80))[0]
        assert rect == pytest.approx((5, 5, 200, 80))

    def test_uneven_sizes_stay_inside_and_do_not_overlap(self):
        bounds = (0, 0, 640, 480)
        node = make_root(500, 300, 150, 100, 50, 20, 10, 5)
        layout = squarified_layout(node, bounds)
        assert len(layout) == 8
        assert sum(area(rect) for _, rect in layout) == pytest.approx(640 * 480)
        for _, rect in layout:
            assert_inside(rect, bounds)
            assert rect[2] > 0 and rect[3] > 0
        assert_no_overlap(layout)


class TestWorstAspect:
    def test_square_is_one(self):
        assert _worst_aspect([100], 10, 100) == pytest.approx(1.0)

    def test_elongated_rectangle_is_penalised(self):
        assert _worst_aspect([100], 2, 100) == pytest.approx(25.0)

    def test_zero_row_area_is_infinite(self):
        assert _worst_aspect([100], 10, 0) == float("inf")

    def test_zero_short_side_is_infinite(self):
        assert _worst_aspect([100], 0, 100) == float("inf")

    def test_all_zero_areas_is_infinite(self):
        assert _worst_aspect([0, 0], 10, 10) == float("inf")
