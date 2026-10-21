from core.utils import format_file_size, get_file_size_safe, is_path_accessible


class TestFormatFileSize:
    def test_zero(self):
        assert format_file_size(0) == "0.00 B"

    def test_negative_returns_zero(self):
        assert format_file_size(-1) == "0 B"

    def test_bytes(self):
        assert format_file_size(1023) == "1023.00 B"

    def test_kilobytes(self):
        assert format_file_size(1024) == "1.00 KB"
        assert format_file_size(1536) == "1.50 KB"

    def test_megabytes(self):
        assert format_file_size(1024 ** 2) == "1.00 MB"
        assert format_file_size(int(2.5 * 1024 ** 2)) == "2.50 MB"

    def test_gigabytes_and_terabytes(self):
        assert format_file_size(1024 ** 3) == "1.00 GB"
        assert format_file_size(1024 ** 4) == "1.00 TB"

    def test_caps_at_terabytes(self):
        assert format_file_size(1024 ** 5) == "1024.00 TB"


class TestGetFileSizeSafe:
    def test_returns_size_for_existing_file(self, tmp_path):
        path = tmp_path / "data.bin"
        path.write_bytes(b"x" * 123)
        assert get_file_size_safe(str(path)) == 123

    def test_returns_zero_for_missing_file(self, tmp_path):
        assert get_file_size_safe(str(tmp_path / "missing.bin")) == 0


class TestIsPathAccessible:
    def test_existing_directory(self, tmp_path):
        assert is_path_accessible(str(tmp_path)) is True

    def test_missing_directory(self, tmp_path):
        assert is_path_accessible(str(tmp_path / "missing")) is False

    def test_file_is_not_a_directory(self, tmp_path):
        path = tmp_path / "file.txt"
        path.write_text("x", encoding="utf-8")
        assert is_path_accessible(str(path)) is False
