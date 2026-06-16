# -*- coding: utf-8 -*-
"""
test_utils.py — utils.py 的單元測試

測試涵蓋：
- 指紋計算（compute_fingerprint）
- 報告編號解析（parse_seq_from_report_id）
- 日期資料夾掃描（scan_date_folders）
- ProcessingSummary 統計
- 完整性檢查
"""

import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from utils import (
    parse_seq_from_report_id,
    scan_date_folders,
    scan_subfolders,
    compute_fingerprint,
    ProcessingSummary,
    _file_ok_min_kb,
    write_error_marker,
    clear_error_marker,
    find_attachment_pdf,
    copy_prefab_pdf,
)


# ========= parse_seq_from_report_id =========

class TestParseSeqFromReportId:
    """報告編號序號解析"""

    def test_basic(self):
        assert parse_seq_from_report_id("20260112-01") == 1

    def test_double_digit(self):
        assert parse_seq_from_report_id("20260112-15") == 15

    def test_invalid_format(self):
        assert parse_seq_from_report_id("abc") is None

    def test_none_input(self):
        assert parse_seq_from_report_id("None") is None

    def test_empty(self):
        assert parse_seq_from_report_id("") is None

    def test_partial(self):
        assert parse_seq_from_report_id("20260112-") is None


# ========= scan_date_folders =========

class TestScanDateFolders:
    """日期資料夾掃描"""

    def test_finds_valid_dates(self, tmp_path):
        # 建立合法的日期資料夾
        (tmp_path / "20260101").mkdir()
        (tmp_path / "20260115").mkdir()
        (tmp_path / "20260112").mkdir()

        result = scan_date_folders(str(tmp_path))
        assert result == ["20260101", "20260112", "20260115"]  # 排序

    def test_ignores_non_date(self, tmp_path):
        (tmp_path / "20260101").mkdir()
        (tmp_path / "_archived").mkdir()
        (tmp_path / "notes.txt").touch()
        (tmp_path / "abc12345").mkdir()

        result = scan_date_folders(str(tmp_path))
        assert result == ["20260101"]

    def test_empty_dir(self, tmp_path):
        result = scan_date_folders(str(tmp_path))
        assert result == []

    def test_nonexistent_dir(self):
        result = scan_date_folders("/nonexistent/path/xyz")
        assert result == []


# ========= scan_subfolders =========

class TestScanSubfolders:
    """子資料夾掃描"""

    def test_finds_subfolders(self, tmp_path):
        (tmp_path / "234_15r1").mkdir()
        (tmp_path / "101_AG").mkdir()
        (tmp_path / "note.txt").touch()

        result = scan_subfolders(str(tmp_path))
        assert "234_15r1" in result
        assert "101_AG" in result
        assert "note.txt" not in result

    def test_sorted(self, tmp_path):
        (tmp_path / "zzz_1a1").mkdir()
        (tmp_path / "aaa_2r1").mkdir()

        result = scan_subfolders(str(tmp_path))
        assert result == ["aaa_2r1", "zzz_1a1"]


# ========= compute_fingerprint =========

class TestComputeFingerprint:
    """指紋計算"""

    def test_same_input_same_fingerprint(self, tmp_path):
        # 建立測試資料夾和圖片
        folder = tmp_path / "test"
        folder.mkdir()
        (folder / "before.jpg").write_bytes(b"fake jpg data")
        (folder / "after.jpg").write_bytes(b"fake jpg data 2")

        fp1 = compute_fingerprint(
            "20260112", "test", "0234", ["15r1"], "note", "",
            str(folder)
        )
        fp2 = compute_fingerprint(
            "20260112", "test", "0234", ["15r1"], "note", "",
            str(folder)
        )
        assert fp1 == fp2

    def test_different_note_different_fp(self, tmp_path):
        folder = tmp_path / "test"
        folder.mkdir()

        fp1 = compute_fingerprint(
            "20260112", "test", "0234", ["15r1"], "note1", "",
            str(folder)
        )
        fp2 = compute_fingerprint(
            "20260112", "test", "0234", ["15r1"], "note2", "",
            str(folder)
        )
        assert fp1 != fp2

    def test_fingerprint_is_hex_string(self, tmp_path):
        folder = tmp_path / "test"
        folder.mkdir()

        fp = compute_fingerprint(
            "20260112", "test", "0234", ["15r1"], "", "",
            str(folder)
        )
        assert len(fp) == 32  # MD5 hex length
        assert all(c in "0123456789abcdef" for c in fp)


# ========= ProcessingSummary =========

class TestProcessingSummary:
    """處理摘要統計"""

    def test_initial_state(self):
        s = ProcessingSummary()
        assert s.total == 0
        assert s.success == 0
        assert s.skipped == 0
        assert s.failed == 0
        assert s.failed_list == []

    def test_add_success(self):
        s = ProcessingSummary()
        s.add_success()
        assert s.total == 1
        assert s.success == 1

    def test_add_skipped(self):
        s = ProcessingSummary()
        s.add_skipped()
        assert s.total == 1
        assert s.skipped == 1

    def test_add_failed(self):
        s = ProcessingSummary()
        s.add_failed("test/folder")
        assert s.total == 1
        assert s.failed == 1
        assert s.failed_list == ["test/folder"]

    def test_mixed(self):
        s = ProcessingSummary()
        s.add_success()
        s.add_success()
        s.add_skipped()
        s.add_failed("a")
        assert s.total == 4
        assert s.success == 2
        assert s.skipped == 1
        assert s.failed == 1


# ========= _file_ok_min_kb =========

class TestFileOkMinKb:
    """檔案大小檢查"""

    def test_exists_and_big_enough(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"x" * 2048)  # 2 KB
        assert _file_ok_min_kb(str(f), 1.0) is True

    def test_too_small(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"x")
        assert _file_ok_min_kb(str(f), 1.0) is False

    def test_nonexistent(self):
        assert _file_ok_min_kb("/no/such/file.txt", 1.0) is False


# ========= Error Marker =========

class TestErrorMarker:
    """錯誤標記檔案"""

    def test_write_and_clear(self, tmp_path):
        write_error_marker(str(tmp_path), "test error")
        error_file = tmp_path / "_ERROR.txt"
        assert error_file.exists()
        assert "test error" in error_file.read_text(encoding="utf-8")

        result = clear_error_marker(str(tmp_path))
        assert result is True
        assert not error_file.exists()

    def test_clear_nonexistent(self, tmp_path):
        result = clear_error_marker(str(tmp_path))
        assert result is True


# ========== copy_prefab_pdf 測試 ==========
class TestCopyPrefabPdf:
    """copy_prefab_pdf 單元測試"""

    def test_copies_matching_pdf(self, tmp_path):
        """正常情境：找到匹配 PDF 並複製"""
        prefab = tmp_path / "prefab"
        prefab.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        pdf = prefab / "243.DW-1302-25-AA1B-NA-3.pdf"
        pdf.write_bytes(b"%PDF-fake-content")

        result = copy_prefab_pdf(str(target), "243", prefab_dir=str(prefab))
        assert result is not None
        assert os.path.basename(result) == "243.DW-1302-25-AA1B-NA-3.pdf"
        assert os.path.exists(result)
        assert (target / "243.DW-1302-25-AA1B-NA-3.pdf").read_bytes() == b"%PDF-fake-content"

    def test_no_match_returns_none(self, tmp_path):
        """prefab 目錄存在但無匹配 PDF"""
        prefab = tmp_path / "prefab"
        prefab.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        (prefab / "999.DW-other.pdf").write_bytes(b"%PDF")

        result = copy_prefab_pdf(str(target), "243", prefab_dir=str(prefab))
        assert result is None

    def test_empty_prefab_dir_returns_none(self, tmp_path):
        """prefab_dir 為空字串"""
        target = tmp_path / "target"
        target.mkdir()
        result = copy_prefab_pdf(str(target), "243", prefab_dir="")
        assert result is None

    def test_nonexistent_prefab_dir_returns_none(self, tmp_path):
        """prefab_dir 不存在"""
        target = tmp_path / "target"
        target.mkdir()
        result = copy_prefab_pdf(str(target), "243", prefab_dir=str(tmp_path / "nope"))
        assert result is None

    def test_skips_copy_when_same_size(self, tmp_path):
        """目標已存在且大小相同時不重複複製"""
        prefab = tmp_path / "prefab"
        prefab.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        content = b"%PDF-same-content-12345"
        (prefab / "100.DW-test.pdf").write_bytes(content)
        dst = target / "100.DW-test.pdf"
        dst.write_bytes(content)
        mtime_before = dst.stat().st_mtime

        result = copy_prefab_pdf(str(target), "100", prefab_dir=str(prefab))
        assert result is not None
        # 檔案不應被重新複製（mtime 不變）
        assert dst.stat().st_mtime == mtime_before

    def test_overwrites_when_different_size(self, tmp_path):
        """目標已存在但大小不同時重新複製"""
        prefab = tmp_path / "prefab"
        prefab.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        (prefab / "50.DW-new.pdf").write_bytes(b"%PDF-new-version-longer")
        (target / "50.DW-new.pdf").write_bytes(b"%PDF-old")

        result = copy_prefab_pdf(str(target), "50", prefab_dir=str(prefab))
        assert result is not None
        assert (target / "50.DW-new.pdf").read_bytes() == b"%PDF-new-version-longer"

    def test_empty_series_no_returns_none(self, tmp_path):
        """series_no 為空"""
        prefab = tmp_path / "prefab"
        prefab.mkdir()
        result = copy_prefab_pdf(str(tmp_path), "", prefab_dir=str(prefab))
        assert result is None

    def test_case_insensitive_match(self, tmp_path):
        """匹配不分大小寫"""
        prefab = tmp_path / "prefab"
        prefab.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        pdf = prefab / "77.DW-Test.PDF"
        pdf.write_bytes(b"%PDF")

        result = copy_prefab_pdf(str(target), "77", prefab_dir=str(prefab))
        assert result is not None

    def test_multiple_matches_picks_first_sorted(self, tmp_path):
        """多個匹配時取字母序第一個"""
        prefab = tmp_path / "prefab"
        prefab.mkdir()
        target = tmp_path / "target"
        target.mkdir()
        (prefab / "10.DW-B.pdf").write_bytes(b"%PDF-B")
        (prefab / "10.DW-A.pdf").write_bytes(b"%PDF-A")

        result = copy_prefab_pdf(str(target), "10", prefab_dir=str(prefab))
        assert os.path.basename(result) == "10.DW-A.pdf"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
