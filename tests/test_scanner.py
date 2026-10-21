import os

import pytest

from core.scanner import SafetyGuard, ScanResult


class TestSafetyGuardProtectedPaths:
    def test_system32_file_is_protected(self):
        guard = SafetyGuard()
        assert guard.is_path_protected(r"C:\Windows\System32\kernel32.dll") is True

    def test_program_files_directory_is_protected(self):
        guard = SafetyGuard()
        assert guard.is_path_protected(r"C:\Program Files\SomeApp") is True

    def test_lookalike_prefix_is_not_protected(self):
        guard = SafetyGuard()
        assert guard.is_path_protected(r"C:\Windows\System32Backup\a.txt") is False

    def test_user_downloads_is_not_protected(self):
        guard = SafetyGuard()
        assert guard.is_path_protected(r"C:\Users\alice\Downloads\a.txt") is False


class TestSafetyGuardSensitivePaths:
    def test_ssh_directory_is_sensitive(self):
        guard = SafetyGuard()
        assert guard.contains_sensitive_snippet(r"C:\Users\alice\.ssh\id_rsa") is True

    def test_aws_directory_is_sensitive(self):
        guard = SafetyGuard()
        assert guard.contains_sensitive_snippet(r"C:\Users\alice\.aws\credentials") is True

    def test_regular_documents_are_not_sensitive(self):
        guard = SafetyGuard()
        assert guard.contains_sensitive_snippet(r"C:\Users\alice\Documents\a.txt") is False

    @pytest.mark.parametrize(
        "filename",
        ["id_rsa", "id_ed25519.pub", "server.pem", "client.p12", ".env", "secrets"],
    )
    def test_sensitive_filenames_match(self, filename):
        assert SafetyGuard().is_sensitive_file(filename) is True

    @pytest.mark.parametrize("filename", ["report.docx", "photo.jpg", "notes.txt"])
    def test_regular_filenames_do_not_match(self, filename):
        assert SafetyGuard().is_sensitive_file(filename) is False

    def test_should_skip_sensitive_file(self, tmp_path):
        guard = SafetyGuard()
        path = tmp_path / "private.pem"
        path.write_text("key", encoding="utf-8")
        assert guard.should_skip(str(path)) is True

    def test_should_not_skip_regular_file(self, tmp_path):
        guard = SafetyGuard()
        path = tmp_path / "notes.txt"
        path.write_text("text", encoding="utf-8")
        assert guard.should_skip(str(path)) is False


class TestScanResultSuggestion:
    @pytest.mark.parametrize("category", ["系统临时文件", "浏览器缓存"])
    def test_cache_categories_are_safe_to_clean(self, category):
        result = ScanResult(path=r"C:\Temp\x.bin", size=1, category=category)
        result.compute_suggestion()
        assert result.suggestion == "建议清理"
        assert result.is_safe is True

    @pytest.mark.parametrize("ext", [".tmp", ".log", ".bak"])
    def test_safe_extensions_are_recommended(self, ext):
        result = ScanResult(path=f"C:\\Users\\alice\\data{ext}", size=1, category="大文件")
        result.compute_suggestion()
        assert result.suggestion == "建议清理"
        assert result.is_safe is True

    @pytest.mark.parametrize("ext", [".dll", ".exe", ".sys", ".DAT"])
    def test_risky_extensions_are_not_recommended(self, ext):
        result = ScanResult(path=f"C:\\Users\\alice\\data{ext}", size=1, category="大文件")
        result.compute_suggestion()
        assert result.suggestion == "不建议删除"
        assert result.is_safe is False

    def test_unknown_extension_is_optional(self):
        result = ScanResult(path=r"C:\Users\alice\movie.mp4", size=1, category="大文件")
        result.compute_suggestion()
        assert result.suggestion == "可酌情清理"
        assert result.is_safe is True


class TestScanResultLastUsed:
    def test_formats_file_mtime(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_text("x", encoding="utf-8")
        os.utime(path, (1_700_000_000, 1_700_000_000))

        result = ScanResult(path=str(path), size=1, category="大文件")
        result.compute_last_used()

        assert result.last_used != "未知"
        assert len(result.last_used) == 16

    def test_missing_file_reports_unknown(self, tmp_path):
        result = ScanResult(path=str(tmp_path / "missing.txt"), size=1, category="大文件")
        result.compute_last_used()
        assert result.last_used == "未知"
