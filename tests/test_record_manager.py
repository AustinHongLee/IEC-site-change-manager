# -*- coding: utf-8 -*-
"""
test_record_manager.py — record_manager.py 的單元測試

測試涵蓋：
- auto_backup 功能
"""

import os
import sys
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))


class TestAutoBackup:
    """自動備份測試"""

    def test_backup_creates_file(self, tmp_path):
        from record_manager import auto_backup

        # 建立假的 Excel 檔
        fake_xlsx = tmp_path / "test.xlsx"
        fake_xlsx.write_bytes(b"fake excel content")

        result = auto_backup(str(fake_xlsx), max_backups=3)
        assert result != ""
        assert os.path.exists(result)

    def test_backup_max_limit(self, tmp_path):
        from record_manager import auto_backup

        fake_xlsx = tmp_path / "test.xlsx"
        fake_xlsx.write_bytes(b"fake excel content")

        # 建立 5 個備份
        for _ in range(5):
            auto_backup(str(fake_xlsx), max_backups=3)
            time.sleep(0.01)  # 確保時間戳不同

        backup_dir = tmp_path / "backups"
        backups = [f for f in os.listdir(str(backup_dir)) if f.endswith(".xlsx")]
        assert len(backups) <= 3

    def test_backup_nonexistent_file(self, tmp_path):
        from record_manager import auto_backup

        result = auto_backup(str(tmp_path / "nonexistent.xlsx"))
        assert result == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
