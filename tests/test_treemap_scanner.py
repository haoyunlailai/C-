from core.treemap_scanner import TOP_N, TreemapNode, TreemapScanner


def write_file(path, size):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


class TestTreemapNode:
    def test_file_is_leaf(self):
        node = TreemapNode(name="a.txt", path="C:\\a.txt", is_dir=False)
        assert node.is_leaf is True

    def test_empty_dir_is_leaf(self):
        assert TreemapNode(name="a", path="C:\\a").is_leaf is True

    def test_dir_with_children_is_not_leaf(self):
        node = TreemapNode(name="a", path="C:\\a")
        node.children.append(TreemapNode(name="b", path="C:\\a\\b"))
        assert node.is_leaf is False


class TestScanRoot:
    def test_sums_file_and_directory_sizes(self, tmp_path):
        write_file(tmp_path / "small.bin", 1000)
        write_file(tmp_path / "large.bin", 3000)
        write_file(tmp_path / "sub" / "nested.bin", 500)

        root = TreemapScanner().scan_root(str(tmp_path))

        assert root.path == str(tmp_path)
        assert root.size == 4500
        by_name = {child.name: child for child in root.children}
        assert by_name["large.bin"].size == 3000
        assert by_name["small.bin"].size == 1000
        assert by_name["sub"].size == 500
        assert by_name["sub"].is_dir is True

    def test_children_sorted_by_size_desc(self, tmp_path):
        write_file(tmp_path / "a.bin", 10)
        write_file(tmp_path / "b.bin", 30)
        write_file(tmp_path / "c.bin", 20)

        root = TreemapScanner().scan_root(str(tmp_path))

        assert [c.name for c in root.children] == ["b.bin", "c.bin", "a.bin"]

    def test_recurses_one_level_into_directories(self, tmp_path):
        write_file(tmp_path / "sub" / "direct.bin", 100)
        write_file(tmp_path / "sub" / "nested" / "deep.bin", 50)

        root = TreemapScanner().scan_root(str(tmp_path))

        sub = next(c for c in root.children if c.name == "sub")
        child_names = {c.name for c in sub.children}
        assert "direct.bin" in child_names
        nested = next(c for c in sub.children if c.name == "nested")
        assert nested.children == []

    def test_keeps_top_n_and_aggregates_the_rest(self, tmp_path):
        for i in range(1, 21):
            write_file(tmp_path / f"f{i:02d}.bin", i)

        root = TreemapScanner().scan_root(str(tmp_path))

        assert len(root.children) == TOP_N + 1
        assert root.size == sum(range(1, 21))
        other = root.children[-1]
        assert other.is_other is True
        assert other.is_dir is False
        assert other.path == ""
        assert other.name == "其他 5 项"
        assert other.size == 1 + 2 + 3 + 4 + 5

    def test_skips_recycle_bin(self, tmp_path):
        write_file(tmp_path / "$RECYCLE.BIN" / "junk.bin", 5000)
        write_file(tmp_path / "keep.bin", 10)

        root = TreemapScanner().scan_root(str(tmp_path))

        assert [c.name for c in root.children] == ["keep.bin"]
        assert root.size == 10

    def test_progress_callback_starts_and_finishes(self, tmp_path):
        write_file(tmp_path / "a.bin", 1)
        calls = []

        TreemapScanner().scan_root(
            str(tmp_path),
            progress_callback=lambda message, ratio: calls.append((message, ratio)),
        )

        assert calls[0][1] == 0.0
        assert calls[-1] == ("扫描完成", 1.0)


class TestScanDrilldown:
    def test_missing_directory_returns_file_node(self, tmp_path):
        missing = tmp_path / "missing"
        node = TreemapScanner().scan_drilldown(str(missing))

        assert node.path == str(missing)
        assert node.is_dir is False
        assert node.size == 0

    def test_matches_root_scan_for_same_directory(self, tmp_path):
        write_file(tmp_path / "sub" / "a.bin", 200)
        write_file(tmp_path / "sub" / "b.bin", 300)

        node = TreemapScanner().scan_drilldown(str(tmp_path / "sub"))

        assert node.size == 500
        assert [c.name for c in node.children] == ["b.bin", "a.bin"]


class TestDirSize:
    def test_limits_walk_depth(self, tmp_path):
        sub = tmp_path / "sub"
        write_file(sub / "a.bin", 100)
        write_file(sub / "l1" / "b.bin", 200)
        write_file(sub / "l1" / "l2" / "deep.bin", 400)

        assert TreemapScanner._dir_size(str(sub), max_depth=2) == 300

    def test_missing_directory_is_zero(self, tmp_path):
        assert TreemapScanner._dir_size(str(tmp_path / "missing")) == 0
