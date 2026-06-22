# -*- coding: utf-8 -*-

import os
import sys

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from PyQt6.QtWidgets import QApplication, QPushButton, QDialog, QTreeWidget

from gui_panels import RecordManagerPanel


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_record_manager_panel_exposes_output_center_entry(qapp):
    panel = RecordManagerPanel()
    try:
        buttons = panel.findChildren(QPushButton)
        output_buttons = [button for button in buttons if button.text() == "輸出中心"]

        assert output_buttons
        assert "attachments" in output_buttons[0].toolTip()
        assert hasattr(panel, "_export_site_output_center")
    finally:
        panel.deleteLater()


def test_output_center_result_dialog_builds_expected_controls(qapp, monkeypatch, tmp_path):
    panel = RecordManagerPanel()
    dialogs = []

    def fake_exec(self):
        dialogs.append(self)
        return 0

    monkeypatch.setattr(QDialog, "exec", fake_exec)

    stats_path = tmp_path / "site_statistics.xlsx"
    photo_path = tmp_path / "site_photo_grid_0547_AG.pdf"
    summary_path = tmp_path / "output_center_summary.json"
    report_set_path = tmp_path / "canonical_report_set.json"
    for path in (stats_path, photo_path, summary_path, report_set_path):
        path.write_text("x", encoding="utf-8")

    result = {
        "ok": True,
        "output_center": str(tmp_path),
        "report_count": 1,
        "aggregates": {
            "weld_count": 2,
            "material_row_count": 1,
            "photo_count": 2,
        },
        "files": {
            "statistics_xlsx": str(stats_path),
            "summary": str(summary_path),
            "report_set": str(report_set_path),
        },
        "renders": [
            {
                "template": "photo_grid",
                "folder": "0547_AG",
                "ok": True,
                "pages": 1,
                "path": str(photo_path),
            }
        ],
        "issues": [
            {
                "report": "0547_AG",
                "code": "note",
                "message": "缺少現場 note",
            }
        ],
    }

    try:
        panel._show_output_center_result_dialog(result)

        assert dialogs
        dialog = dialogs[0]
        assert dialog.windowTitle() == "輸出中心結果"

        tree = dialog.findChild(QTreeWidget)
        assert tree is not None
        assert tree.topLevelItemCount() >= 3

        button_texts = {button.text() for button in dialog.findChildren(QPushButton)}
        assert "開啟選取檔案" in button_texts
        assert "定位修改單" in button_texts
        assert "處理提醒" in button_texts
        assert "開啟輸出資料夾" in button_texts
    finally:
        panel.deleteLater()
        for dialog in dialogs:
            dialog.deleteLater()
