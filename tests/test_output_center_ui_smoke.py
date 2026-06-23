# -*- coding: utf-8 -*-

import os
import sys

import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "control"))

from PyQt6.QtWidgets import QApplication, QPushButton, QDialog, QMessageBox, QTreeWidget

from gui import MainWindow
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
        assert not hasattr(panel, "_export_real_attachments_showcase")
        for legacy_name in (
            "_show_showcase_result_dialog",
            "_choose_showcase_scope",
            "_showcase_report_keys",
            "_showcase_scope_options",
            "_format_showcase_content_label",
            "_normalize_showcase_output_dir",
            "_showcase_output_items",
            "_showcase_output_groups",
            "_showcase_issue_items",
            "_showcase_issue_action",
            "_format_showcase_issue_tooltip",
            "_showcase_issue_record_ref",
            "_showcase_filters_are_narrowed",
            "_showcase_note_text_is_valid",
            "_format_showcase_export_confirmation",
            "_format_showcase_export_message",
        ):
            assert not hasattr(panel, legacy_name)
    finally:
        panel.deleteLater()


def test_main_window_smoke_keeps_output_center_reachable(qapp):
    window = MainWindow()
    try:
        tab_texts = [window.notebook.tabText(index) for index in range(window.notebook.count())]

        assert any("產出報告" in text for text in tab_texts)
        assert any("紀錄管理" in text for text in tab_texts)
        assert any("材料價目" in text for text in tab_texts)
        assert any("請款追蹤" in text for text in tab_texts)
        assert any("設定" in text for text in tab_texts)
        assert any("健康" in text for text in tab_texts)

        output_buttons = [
            button for button in window.record_panel.findChildren(QPushButton)
            if button.text() == "輸出中心"
        ]
        assert output_buttons

        health_buttons = {button.text() for button in window.health_panel.findChildren(QPushButton)}
        assert "支援診斷包" in health_buttons
        assert "深度診斷包" in health_buttons
        assert "版本資訊" in health_buttons
    finally:
        window.close()
        window.deleteLater()


def test_health_panel_support_bundle_button_uses_diagnostics(qapp, monkeypatch):
    import diagnostics

    window = MainWindow()
    messages = []
    captured = []

    def fake_collect(project_root, **kwargs):
        captured.append({"project_root": str(project_root), **kwargs})
        return {
            "ok": True,
            "bundle_path": r"C:\Temp\support_bundle.zip",
            "startup_action": "healthy",
        }

    def fake_information(parent, title, message):
        messages.append((title, message))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(diagnostics, "collect_support_bundle", fake_collect)
    monkeypatch.setattr(QMessageBox, "information", fake_information)

    try:
        window.health_panel.create_support_bundle()
        window.health_panel.create_support_bundle(probe=True)

        assert captured[0]["project_root"]
        assert captured[0]["probe_com_application"] is False
        assert captured[0]["probe_libreoffice_version"] is False
        assert captured[1]["probe_com_application"] is True
        assert captured[1]["probe_libreoffice_version"] is True
        assert len(messages) == 2
        assert messages[0][0] == "支援診斷包完成"
        assert messages[1][0] == "深度診斷包完成"
        assert "support_bundle.zip" in messages[0][1]
    finally:
        window.close()
        window.deleteLater()


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
