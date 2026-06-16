# -*- coding: utf-8 -*-
"""
test_staging_manager.py — staging_manager 模組測試
"""

import os
import sys
import shutil
import tempfile
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'control'))

from staging_manager import (
    StagingFile, FileAssignment, DispatchResult,
    scan_staging, group_by_time, dispatch_files, dispatch_summary,
    suggest_date_folder, ensure_staging_dir, _get_mtime,
)


# ─── Fixtures ─────────────────────────────────

@pytest.fixture
def staging_dir(tmp_path):
    """建立臨時 staging 資料夾"""
    d = tmp_path / "staging"
    d.mkdir()
    return str(d)


@pytest.fixture
def attach_dir(tmp_path):
    """建立臨時 attachments 資料夾"""
    d = tmp_path / "attachments"
    d.mkdir()
    return str(d)


def _create_file(directory: str, name: str, content: bytes = b"test") -> str:
    """建立測試用檔案"""
    path = os.path.join(directory, name)
    with open(path, 'wb') as f:
        f.write(content)
    return path


# ─── scan_staging ─────────────────────────────

class TestScanStaging:
    def test_empty_folder(self, staging_dir):
        result = scan_staging(staging_dir)
        assert result == []

    def test_nonexistent_folder(self):
        result = scan_staging("/not/exist")
        assert result == []

    def test_finds_images(self, staging_dir):
        _create_file(staging_dir, "photo1.jpg")
        _create_file(staging_dir, "photo2.png")
        result = scan_staging(staging_dir)
        assert len(result) == 2
        assert all(sf.file_type == "image" for sf in result)

    def test_finds_pdfs(self, staging_dir):
        _create_file(staging_dir, "drawing.pdf")
        result = scan_staging(staging_dir)
        assert len(result) == 1
        assert result[0].file_type == "pdf"

    def test_ignores_other_extensions(self, staging_dir):
        _create_file(staging_dir, "notes.txt")
        _create_file(staging_dir, "data.xlsx")
        _create_file(staging_dir, "photo.jpg")
        result = scan_staging(staging_dir)
        assert len(result) == 1
        assert result[0].filename == "photo.jpg"

    def test_ignores_subdirectories(self, staging_dir):
        os.makedirs(os.path.join(staging_dir, "subdir"))
        _create_file(staging_dir, "photo.jpg")
        result = scan_staging(staging_dir)
        assert len(result) == 1

    def test_size_populated(self, staging_dir):
        _create_file(staging_dir, "photo.jpg", b"x" * 2048)
        result = scan_staging(staging_dir)
        assert result[0].size_kb == pytest.approx(2.0, abs=0.1)


# ─── group_by_time ─────────────────────────────

class TestGroupByTime:
    def _make_sf(self, name, exif_time=None, mtime=None):
        return StagingFile(
            path=f"/fake/{name}", filename=name, file_type="image",
            size_kb=100, exif_time=exif_time, mtime=mtime,
        )

    def test_empty(self):
        assert group_by_time([]) == []

    def test_single_file(self):
        f = self._make_sf("a.jpg", exif_time=datetime(2025, 8, 18, 14, 0))
        groups = group_by_time([f])
        assert len(groups) == 1
        assert len(groups[0]) == 1

    def test_same_time_one_group(self):
        files = [
            self._make_sf("a.jpg", exif_time=datetime(2025, 8, 18, 14, 0)),
            self._make_sf("b.jpg", exif_time=datetime(2025, 8, 18, 14, 10)),
            self._make_sf("c.jpg", exif_time=datetime(2025, 8, 18, 14, 20)),
        ]
        groups = group_by_time(files, threshold_minutes=30)
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_different_times_two_groups(self):
        files = [
            self._make_sf("a.jpg", exif_time=datetime(2025, 8, 18, 10, 0)),
            self._make_sf("b.jpg", exif_time=datetime(2025, 8, 18, 10, 5)),
            self._make_sf("c.jpg", exif_time=datetime(2025, 8, 18, 15, 0)),
            self._make_sf("d.jpg", exif_time=datetime(2025, 8, 18, 15, 10)),
        ]
        groups = group_by_time(files, threshold_minutes=30)
        assert len(groups) == 2
        assert len(groups[0]) == 2
        assert len(groups[1]) == 2

    def test_custom_threshold(self):
        files = [
            self._make_sf("a.jpg", exif_time=datetime(2025, 8, 18, 14, 0)),
            self._make_sf("b.jpg", exif_time=datetime(2025, 8, 18, 14, 8)),
        ]
        # 5 分鐘門檻 → 分兩組
        groups = group_by_time(files, threshold_minutes=5)
        assert len(groups) == 2
        # 10 分鐘門檻 → 一組
        groups = group_by_time(files, threshold_minutes=10)
        assert len(groups) == 1


# ─── FileAssignment ─────────────────────────────

class TestFileAssignment:
    def test_target_filename_before(self):
        a = FileAssignment("/fake/IMG_001.jpg", "20250818", "243", "12a1_12b1", "before")
        assert a.target_filename == "before.jpg"

    def test_target_filename_after_1(self):
        a = FileAssignment("/fake/IMG_002.png", "20250818", "243", "AG", "after_1")
        assert a.target_filename == "after_1.png"

    def test_target_filename_pdf(self):
        a = FileAssignment("/fake/243.DW-1302.pdf", "20250818", "243", "12a1", "pdf")
        assert a.target_filename == "243.DW-1302.pdf"

    def test_folder_name(self):
        a = FileAssignment("/fake/x.jpg", "20250818", "243", "12a1_12b1", "before")
        assert a.folder_name == "243_12a1_12b1"


# ─── dispatch_files ─────────────────────────────

class TestDispatchFiles:
    def test_basic_move(self, staging_dir, attach_dir):
        src = _create_file(staging_dir, "photo.jpg", b"image data")
        assignments = [FileAssignment(src, "20250818", "243", "12a1_12b1", "before")]
        results = dispatch_files(assignments, attach_dir, move=True)

        assert len(results) == 1
        assert results[0].success is True
        assert not os.path.exists(src)  # 原檔已搬走
        target = os.path.join(attach_dir, "20250818", "243_12a1_12b1", "before.jpg")
        assert os.path.isfile(target)

    def test_copy_mode(self, staging_dir, attach_dir):
        src = _create_file(staging_dir, "photo.jpg", b"image data")
        assignments = [FileAssignment(src, "20250818", "243", "12a1_12b1", "after")]
        results = dispatch_files(assignments, attach_dir, move=False)

        assert results[0].success is True
        assert os.path.exists(src)  # 原檔保留
        target = os.path.join(attach_dir, "20250818", "243_12a1_12b1", "after.jpg")
        assert os.path.isfile(target)

    def test_source_not_found(self, attach_dir):
        assignments = [FileAssignment("/no/such/file.jpg", "20250818", "243", "AG", "before")]
        results = dispatch_files(assignments, attach_dir)
        assert results[0].success is False
        assert "來源不存在" in results[0].error

    def test_target_already_exists(self, staging_dir, attach_dir):
        # 先建立目標
        target_dir = os.path.join(attach_dir, "20250818", "243_12a1")
        os.makedirs(target_dir)
        _create_file(target_dir, "before.jpg", b"old")
        # 嘗試分派
        src = _create_file(staging_dir, "new.jpg", b"new")
        assignments = [FileAssignment(src, "20250818", "243", "12a1", "before")]
        results = dispatch_files(assignments, attach_dir)
        assert results[0].success is False
        assert "目標已存在" in results[0].error

    def test_creates_nested_dirs(self, staging_dir, attach_dir):
        src = _create_file(staging_dir, "photo.jpg")
        assignments = [FileAssignment(src, "20260301", "999", "AG", "before_1")]
        results = dispatch_files(assignments, attach_dir)
        assert results[0].success is True
        assert os.path.isdir(os.path.join(attach_dir, "20260301", "999_AG"))

    def test_multiple_assignments(self, staging_dir, attach_dir):
        src1 = _create_file(staging_dir, "a.jpg", b"a")
        src2 = _create_file(staging_dir, "b.jpg", b"b")
        src3 = _create_file(staging_dir, "c.pdf", b"c")
        assignments = [
            FileAssignment(src1, "20250818", "243", "12a1", "before"),
            FileAssignment(src2, "20250818", "243", "12a1", "after"),
            FileAssignment(src3, "20250818", "243", "12a1", "pdf"),
        ]
        results = dispatch_files(assignments, attach_dir)
        assert all(r.success for r in results)


# ─── suggest_date_folder ─────────────────────────

class TestSuggestDateFolder:
    def test_from_exif(self):
        sf = StagingFile("/x.jpg", "x.jpg", "image", 100,
                         exif_time=datetime(2025, 8, 18, 14, 30))
        assert suggest_date_folder(sf) == "20250818"

    def test_from_mtime(self):
        sf = StagingFile("/x.jpg", "x.jpg", "image", 100,
                         mtime=datetime(2025, 10, 20))
        assert suggest_date_folder(sf) == "20251020"

    def test_fallback_today(self):
        sf = StagingFile("/x.jpg", "x.jpg", "image", 100)
        result = suggest_date_folder(sf)
        assert result == datetime.now().strftime("%Y%m%d")


# ─── dispatch_summary ─────────────────────────

class TestDispatchSummary:
    def test_all_success(self):
        a = FileAssignment("/fake/a.jpg", "20250818", "243", "AG", "before")
        results = [DispatchResult(a, success=True, target_path="/t/before.jpg")]
        text = dispatch_summary(results)
        assert "1 成功" in text
        assert "0 失敗" in text

    def test_with_failures(self):
        a = FileAssignment("/fake/a.jpg", "20250818", "243", "AG", "before")
        results = [DispatchResult(a, success=False, error="file not found")]
        text = dispatch_summary(results)
        assert "0 成功" in text
        assert "1 失敗" in text
        assert "file not found" in text


# ─── ensure_staging_dir ─────────────────────────

class TestEnsureStagingDir:
    def test_creates_if_not_exists(self, tmp_path):
        base = str(tmp_path / "project")
        os.makedirs(base)
        result = ensure_staging_dir(base)
        assert os.path.isdir(result)
        assert result.endswith("staging")

    def test_idempotent(self, tmp_path):
        base = str(tmp_path / "project")
        os.makedirs(base)
        r1 = ensure_staging_dir(base)
        r2 = ensure_staging_dir(base)
        assert r1 == r2


# ─── StagingFile properties ─────────────────────

class TestStagingFileProperties:
    def test_sort_time_prefers_exif(self):
        sf = StagingFile("/x.jpg", "x.jpg", "image", 100,
                         exif_time=datetime(2025, 1, 1),
                         mtime=datetime(2025, 6, 1))
        assert sf.sort_time == datetime(2025, 1, 1)

    def test_sort_time_fallback_mtime(self):
        sf = StagingFile("/x.jpg", "x.jpg", "image", 100,
                         mtime=datetime(2025, 6, 1))
        assert sf.sort_time == datetime(2025, 6, 1)

    def test_sort_time_fallback_epoch(self):
        sf = StagingFile("/x.jpg", "x.jpg", "image", 100)
        assert sf.sort_time == datetime(2000, 1, 1)

    def test_time_label_with_exif(self):
        sf = StagingFile("/x.jpg", "x.jpg", "image", 100,
                         exif_time=datetime(2025, 8, 18, 14, 30, 0))
        assert sf.time_label == "2025-08-18 14:30:00"

    def test_time_label_no_time(self):
        sf = StagingFile("/x.jpg", "x.jpg", "image", 100)
        assert sf.time_label == "(無時間資訊)"

    def test_exif_source(self):
        sf1 = StagingFile("/x.jpg", "x.jpg", "image", 100,
                          exif_time=datetime(2025, 1, 1))
        assert sf1.exif_source == "EXIF"

        sf2 = StagingFile("/x.jpg", "x.jpg", "image", 100,
                          mtime=datetime(2025, 1, 1))
        assert sf2.exif_source == "檔案時間"

        sf3 = StagingFile("/x.jpg", "x.jpg", "image", 100)
        assert sf3.exif_source == "無"
