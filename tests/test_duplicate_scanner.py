import hashlib

import pytest

from core.duplicate_scanner import (
    DuplicateGroup,
    DuplicateReport,
    DuplicateScanner,
    _is_safe_to_delete,
)
from core.scanner import ScanResult


def make_result(path, size):
    return ScanResult(path=path, size=size, category="重复文件")


class TestIsSafeToDelete:
    def test_text_file_in_downloads_is_safe(self):
        assert _is_safe_to_delete(r"C:\Users\alice\Downloads\a.txt") is True

    def test_executable_in_downloads_is_risky(self):
        assert _is_safe_to_delete(r"C:\Users\alice\Downloads\setup.exe") is False

    def test_extension_check_is_case_insensitive(self):
        assert _is_safe_to_delete(r"C:\Users\alice\Desktop\SETUP.EXE") is False

    def test_appdata_is_never_safe(self):
        assert _is_safe_to_delete(r"C:\Users\alice\AppData\Roaming\notes.txt") is False

    def test_file_outside_user_dirs_is_unsafe(self):
        assert _is_safe_to_delete(r"C:\Temp\notes.txt") is False

    @pytest.mark.parametrize(
        "folder", ["Desktop", "Downloads", "Documents", "Pictures", "Videos", "Music"]
    )
    def test_all_safe_user_dirs(self, folder):
        assert _is_safe_to_delete(rf"C:\Users\alice\{folder}\file.txt") is True


class TestDuplicateGroup:
    def test_compute_waste_ignores_the_original(self):
        files = [
            make_result(r"C:\Users\alice\Downloads\a.txt", 100),
            make_result(r"C:\Users\alice\Downloads\b.txt", 100),
            make_result(r"C:\Users\alice\Downloads\c.txt", 100),
        ]
        group = DuplicateGroup(files=files, hash_value="abc")
        group.compute_waste()

        assert group.file_size == 100
        assert group.waste == 200
        assert group.safe_files == files[1:]

    def test_safe_files_exclude_risky_extensions(self):
        files = [
            make_result(r"C:\Users\alice\Downloads\a.txt", 50),
            make_result(r"C:\Users\alice\Downloads\b.txt", 50),
            make_result(r"C:\Users\alice\Downloads\c.exe", 50),
        ]
        group = DuplicateGroup(files=files, hash_value="abc")
        group.compute_waste()

        assert [f.path for f in group.safe_files] == [files[1].path]

    def test_empty_group_is_zero(self):
        group = DuplicateGroup(files=[], hash_value="abc")
        group.compute_waste()
        assert group.waste == 0
        assert group.safe_files == []


class TestDuplicateReport:
    def test_add_group_accumulates_totals(self):
        report = DuplicateReport()
        group_a = DuplicateGroup(
            files=[
                make_result(r"C:\Users\alice\Downloads\a.txt", 100),
                make_result(r"C:\Users\alice\Downloads\a2.txt", 100),
            ],
            hash_value="a",
        )
        group_b = DuplicateGroup(
            files=[
                make_result(r"C:\Users\alice\Pictures\b.jpg", 50),
                make_result(r"C:\Users\alice\Pictures\b2.jpg", 50),
            ],
            hash_value="b",
        )

        report.add_group(group_a)
        report.add_group(group_b)

        assert report.total_groups == 2
        assert report.total_waste == 150
        assert [g.hash_value for g in report.groups] == ["a", "b"]


class TestGrouping:
    def test_group_by_size_keeps_only_duplicate_sizes(self):
        scanner = DuplicateScanner(threshold_mb=0)
        a = make_result("a", 10)
        b = make_result("b", 10)
        c = make_result("c", 20)

        groups = scanner._group_by_size([a, b, c])

        assert list(groups) == [10]
        assert groups[10] == [a, b]

    def test_compute_md5(self, tmp_path):
        path = tmp_path / "data.bin"
        path.write_bytes(b"hello duplicate")
        expected = hashlib.md5(b"hello duplicate").hexdigest()

        assert DuplicateScanner()._compute_md5(str(path)) == expected


class TestScan:
    def test_finds_duplicates_by_content(self, tmp_path):
        (tmp_path / "a.txt").write_bytes(b"same content")
        (tmp_path / "b.txt").write_bytes(b"same content")
        (tmp_path / "c.txt").write_bytes(b"different!!!!")

        scanner = DuplicateScanner(threshold_mb=0)
        report = scanner.scan(scan_dirs=[str(tmp_path)])

        assert report.total_files_scanned == 3
        assert report.total_groups == 1
        group = report.groups[0]
        assert group.file_size == 12
        assert group.waste == 12
        assert {f.path for f in group.files} == {
            str(tmp_path / "a.txt"),
            str(tmp_path / "b.txt"),
        }

    def test_same_size_different_content_is_not_a_group(self, tmp_path):
        (tmp_path / "a.txt").write_bytes(b"aaaa")
        (tmp_path / "b.txt").write_bytes(b"bbbb")

        report = DuplicateScanner(threshold_mb=0).scan(scan_dirs=[str(tmp_path)])

        assert report.total_groups == 0
        assert report.total_waste == 0

    def test_reports_final_progress(self, tmp_path):
        (tmp_path / "a.txt").write_bytes(b"x")
        (tmp_path / "b.txt").write_bytes(b"x")
        calls = []

        DuplicateScanner(threshold_mb=0).scan(
            scan_dirs=[str(tmp_path)],
            progress_callback=lambda ratio, message, count: calls.append((ratio, message, count)),
        )

        assert calls[-1][0] == 1.0
        assert "扫描完成" in calls[-1][1]
