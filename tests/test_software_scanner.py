import os
import time

import pytest

import core.software_scanner as software_scanner_module
from core.software_scanner import (
    SoftwareInfo,
    SoftwareScanner,
)


@pytest.fixture
def app_dir(tmp_path):
    path = tmp_path / "Program Files" / "Demo App"
    path.mkdir(parents=True)
    (path / "demo.exe").write_bytes(b"MZ")
    (path / "uninstall.exe").write_bytes(b"MZ")
    return path


class TestSoftwareInfo:
    def test_size_display_is_human_readable(self):
        sw = SoftwareInfo(name="Demo", estimated_size=5 * 1024 * 1024)
        assert sw.estimated_size_display == "5.00 MB"

    def test_unknown_last_used(self):
        assert SoftwareInfo(name="Demo").last_used_display == "未知"

    def test_last_used_formats_date(self):
        ts = time.mktime((2024, 1, 2, 12, 0, 0, 0, 0, -1))
        sw = SoftwareInfo(name="Demo", last_used_ts=ts)
        assert sw.last_used_display == "2024-01-02"


class TestInferInstallDir:
    def test_quoted_display_icon_with_icon_index(self, app_dir):
        icon = f'"{app_dir / "demo.exe"}",0'
        assert SoftwareScanner._infer_install_dir(icon, "") == str(app_dir)

    def test_unquoted_display_icon_with_negative_icon_index(self, app_dir):
        icon = f'{app_dir / "demo.exe"},-101'
        assert SoftwareScanner._infer_install_dir(icon, "") == str(app_dir)

    def test_comma_in_directory_name_is_preserved(self, tmp_path):
        target = tmp_path / "Foo, Inc" / "App"
        target.mkdir(parents=True)
        (target / "app.exe").write_bytes(b"MZ")
        icon = f'{target / "app.exe"},0'
        assert SoftwareScanner._infer_install_dir(icon, "") == str(target)

    def test_unquoted_executable_path(self, app_dir):
        assert SoftwareScanner._infer_install_dir(str(app_dir / "demo.exe"), "") == str(app_dir)

    def test_uninstall_string_with_flags(self, app_dir):
        uninstall = f'"{app_dir / "uninstall.exe"}" /S'
        assert SoftwareScanner._infer_install_dir("", uninstall) == str(app_dir)

    def test_plain_directory_path(self, app_dir):
        assert SoftwareScanner._infer_install_dir(str(app_dir), "") == str(app_dir)

    def test_falls_back_to_uninstall_string(self, app_dir):
        uninstall = f'"{app_dir / "uninstall.exe"}"'
        assert SoftwareScanner._infer_install_dir("", uninstall) == str(app_dir)

    def test_skips_msi_product_code(self):
        guid = "{90160000-008C-0000-1000-0000000FF1CE}"
        assert SoftwareScanner._infer_install_dir(guid, "") == ""

    def test_skips_unquoted_msiexec(self):
        uninstall = "MsiExec.exe /I{90160000-008C-0000-1000-0000000FF1CE}"
        assert SoftwareScanner._infer_install_dir("", uninstall) == ""

    def test_skips_quoted_msiexec_path(self):
        uninstall = r'"C:\Windows\System32\msiexec.exe" /I{GUID}'
        assert SoftwareScanner._infer_install_dir("", uninstall) == ""

    def test_nonexistent_path_returns_empty(self, tmp_path):
        icon = str(tmp_path / "missing" / "app.exe")
        assert SoftwareScanner._infer_install_dir(icon, "") == ""

    def test_empty_inputs_return_empty(self):
        assert SoftwareScanner._infer_install_dir("", "") == ""


class TestIsSystemComponent:
    @pytest.mark.parametrize(
        "name,publisher",
        [
            ("Microsoft Edge", "Microsoft Corporation"),
            ("Intel(R) Graphics Driver", "Intel Corporation"),
            ("NVIDIA GeForce Experience", "NVIDIA Corporation"),
            ("AMD Chipset Software", "Advanced Micro Devices, Inc."),
            ("Realtek Audio Console", "Realtek Semiconductor"),
            ("Update for Windows 10", ""),
            ("Security Update for .NET Framework", ""),
            ("Microsoft Visual C++ 2015 Redistributable", ""),
            ("Windows PC Health Check", ""),
        ],
    )
    def test_system_components_are_detected(self, name, publisher):
        assert SoftwareScanner._is_system_component(
            SoftwareInfo(name=name, publisher=publisher)
        ) is True

    @pytest.mark.parametrize(
        "name,publisher",
        [
            ("Spotify", "Spotify AB"),
            ("钉钉", "DingTalk"),
            ("WeChat", "Tencent"),
            ("7-Zip", "Igor Pavlov"),
        ],
    )
    def test_third_party_apps_are_not_system_components(self, name, publisher):
        assert SoftwareScanner._is_system_component(
            SoftwareInfo(name=name, publisher=publisher)
        ) is False


class TestDetectUnused:
    @staticmethod
    def _make_app(tmp_path, name, days_ago):
        path = tmp_path / name
        path.mkdir()
        file = path / "app.exe"
        file.write_bytes(b"MZ")
        ts = time.time() - days_ago * 24 * 3600
        os.utime(file, (ts, ts))
        return path

    def test_flags_install_dirs_untouched_for_over_six_months(self, tmp_path):
        old_dir = self._make_app(tmp_path, "OldApp", 200)
        new_dir = self._make_app(tmp_path, "NewApp", 5)

        old_app = SoftwareInfo(name="OldApp", install_location=str(old_dir))
        new_app = SoftwareInfo(name="NewApp", install_location=str(new_dir))
        unknown_app = SoftwareInfo(name="UnknownApp")

        SoftwareScanner().detect_unused([old_app, new_app, unknown_app])

        assert old_app.is_unused is True
        assert old_app.last_used_ts == pytest.approx(
            (old_dir / "app.exe").stat().st_mtime, abs=2
        )
        assert new_app.is_unused is False
        assert new_app.last_used_ts > 0
        assert unknown_app.is_unused is False
        assert unknown_app.last_used_ts == 0.0

    @pytest.mark.parametrize("days_ago,expected", [(179, False), (181, True)])
    def test_threshold_boundary(self, tmp_path, days_ago, expected):
        path = self._make_app(tmp_path, f"App{days_ago}", days_ago)
        sw = SoftwareInfo(name="Demo", install_location=str(path))

        SoftwareScanner().detect_unused([sw])

        assert sw.is_unused is expected

    def test_reports_completion(self, tmp_path):
        path = self._make_app(tmp_path, "Demo", 1)
        calls = []

        SoftwareScanner().detect_unused(
            [SoftwareInfo(name="Demo", install_location=str(path))],
            progress_callback=lambda message, ratio: calls.append((message, ratio)),
        )

        assert calls[-1] == ("分析完成", 1.0)


class TestLatestActivity:
    def test_missing_location_returns_zero(self):
        assert SoftwareScanner._get_latest_activity_ts("") == 0.0
        assert SoftwareScanner._get_latest_activity_ts(r"C:\does\not\exist") == 0.0

    def test_returns_newest_file_mtime(self, tmp_path):
        old = tmp_path / "old.bin"
        new = tmp_path / "nested" / "new.bin"
        new.parent.mkdir()
        old.write_bytes(b"x")
        new.write_bytes(b"x")
        os.utime(old, (1_600_000_000, 1_600_000_000))
        os.utime(new, (1_700_000_000, 1_700_000_000))

        assert SoftwareScanner._get_latest_activity_ts(str(tmp_path)) == pytest.approx(
            1_700_000_000
        )


class TestParseSubkey:
    def test_maps_registry_values_and_infers_location(self, monkeypatch, app_dir):
        values = {
            "DisplayName": "DemoApp",
            "DisplayVersion": "1.2.3",
            "Publisher": "Demo Corp",
            "InstallDate": "20240101",
            "DisplayIcon": f'"{app_dir / "demo.exe"}",0',
            "UninstallString": f'"{app_dir / "uninstall.exe"}" /S',
            "EstimatedSize": "2048",
        }

        def fake_query(_key, name):
            if name not in values:
                raise FileNotFoundError(name)
            return values[name], 1

        monkeypatch.setattr(software_scanner_module.winreg, "QueryValueEx", fake_query)

        sw = SoftwareScanner()._parse_subkey(object())

        assert sw is not None
        assert sw.name == "DemoApp"
        assert sw.version == "1.2.3"
        assert sw.publisher == "Demo Corp"
        assert sw.install_date == "20240101"
        assert sw.uninstall_string == values["UninstallString"]
        assert sw.install_location == str(app_dir)
        assert sw.estimated_size == 2048 * 1024

    def test_missing_display_name_returns_none(self, monkeypatch):
        def fake_query(_key, name):
            raise FileNotFoundError(name)

        monkeypatch.setattr(software_scanner_module.winreg, "QueryValueEx", fake_query)

        assert SoftwareScanner()._parse_subkey(object()) is None

    def test_invalid_estimated_size_defaults_to_zero(self, monkeypatch):
        values = {"DisplayName": "Demo", "EstimatedSize": "not-a-number"}

        def fake_query(_key, name):
            if name not in values:
                raise FileNotFoundError(name)
            return values[name], 1

        monkeypatch.setattr(software_scanner_module.winreg, "QueryValueEx", fake_query)

        assert SoftwareScanner()._parse_subkey(object()).estimated_size == 0
