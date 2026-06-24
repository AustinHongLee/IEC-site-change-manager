# -*- coding: utf-8 -*-
"""
gui.py — 管線修改單產出系統 GUI (PyQt6)

功能：
- 日期資料夾選擇（多選）
- 執行進度顯示
- 執行結果摘要
- 設定選項
- 重試失敗項目
"""

import os
import sys
import threading
from typing import List, Dict
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QListWidget, QLineEdit,
    QCheckBox, QProgressBar, QTextEdit, QFileDialog, QMessageBox,
    QAbstractItemView, QTreeWidget, QTreeWidgetItem, QDialog, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject

from theme import (
    apply_theme, Colors, Fonts, set_button_role,
    make_separator,
)

# 確保可以 import 同目錄模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 新增模組
try:
    from validator import validate_folder, validate_date_folder, Severity
    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False

try:
    from image_processor import preprocess_folder as prepare_folder_images
    IMAGE_PROCESSOR_AVAILABLE = True
except ImportError:
    IMAGE_PROCESSOR_AVAILABLE = False

try:
    from wizard import launch_wizard  # noqa: F401 — used in _launch_wizard()
    WIZARD_AVAILABLE = True
except ImportError:
    WIZARD_AVAILABLE = False

try:
    from change_order_wizard import ChangeOrderWizard  # noqa: F401
    CHANGE_ORDER_WIZARD_AVAILABLE = True
except ImportError:
    CHANGE_ORDER_WIZARD_AVAILABLE = False

from config import (
    BASE_DIR, ATTACHMENTS_ROOT, OUTPUT_ROOT, PDF_OUTPUT_DIR,
    RUNTIME, use_dual_images
)
from app_info import format_window_title
from renderer_registry import format_renderer_unavailable, get_renderer_descriptor
from parsers import (
    parse_folder, parse_materials_txt, weld_code_list, build_auto_description, WeldToken
)
from material_pricebook import apply_material_pricing, load_material_pricebook
from utils import (
    scan_date_folders, scan_subfolders, compute_fingerprint,
    find_attachment_pdf, copy_prefab_pdf, ProcessingSummary,
    parse_seq_from_report_id, clear_error_marker
)
from record_manager import (
    load_drawing_map, preload_record_index,
    upsert_record, upsert_detail_rows, upsert_materials_rows
)
from image_processor import (
    check_pillow, auto_preprocess_if_needed
)
from settings_manager import (
    get_settings, get_drawing_list_path, remember_browse_directory,
    get_last_browse_directory
)

# 拆分模組
from gui_panels import RecordManagerPanel, MaterialPricebookPanel, BillingPanel, HealthCheckPanel
from gui_settings import SettingsPanel
from gui_dialogs import SupplementInfoDialog, WeldDuplicateCheckDialog


# ========= 信號橋接器（跨執行緒安全更新 UI）=========
class _UiBridge(QObject):
    """用於從背景執行緒安全地更新 UI 的信號橋接器"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int, str)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    summary_signal = pyqtSignal(object)


def _renderer_status_text(renderer: dict) -> str:
    status = str(renderer.get("status", "") or "")
    if status == "legacy_available":
        return "舊版輸出：COM 可用"
    if status == "unprobed":
        return "舊版輸出：需要時檢查"
    if status == "unavailable":
        return "舊版輸出：不可用"
    return f"舊版輸出：{status or '未知'}"


def _renderer_tooltip(renderer: dict) -> str:
    status = str(renderer.get("status", "") or "")
    if status == "unprobed":
        return "舊版 Excel COM 產出會在開始執行或重試前檢查可用性"
    if status == "legacy_available":
        return "使用舊版 Excel COM 模板產出修改單"
    return format_renderer_unavailable(renderer)


# ========= 主視窗 =========
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(format_window_title())
        self.resize(960, 720)
        self.setMinimumSize(800, 600)

        # 狀態
        self.is_running = False
        self.should_stop = False
        self.worker_thread = None

        # 資料
        self.date_folders: List[str] = []
        self.drawing_map: Dict = {}
        self.record_index = None

        # UI 信號橋接
        self._bridge = _UiBridge()
        self._bridge.log_signal.connect(self.log)
        self._bridge.progress_signal.connect(self._update_progress)
        self._bridge.finished_signal.connect(self._processing_finished)
        self._bridge.error_signal.connect(lambda m: QMessageBox.critical(self, "錯誤", m))
        self._bridge.summary_signal.connect(self._show_summary)

        self._create_ui()
        self._update_excel_com_controls(log_result=False)
        self._load_initial_data()

    # ─── UI 建立 ──────────────────────────────────────────
    def _create_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 8)
        root_layout.setSpacing(8)

        # Notebook → QTabWidget
        self.notebook = QTabWidget()
        root_layout.addWidget(self.notebook)

        # === 頁籤1：產出報告 ===
        report_tab = QWidget()
        self._create_report_tab(report_tab)
        self.notebook.addTab(report_tab, "📋 產出報告")

        # === 頁籤2：紀錄管理 ===
        record_tab = QWidget()
        record_layout = QVBoxLayout(record_tab)
        record_layout.setContentsMargins(8, 8, 8, 8)
        self.record_panel = RecordManagerPanel(record_tab)
        record_layout.addWidget(self.record_panel)
        self.notebook.addTab(record_tab, "📊 紀錄管理")

        # === 頁籤3：材料價目 ===
        pricebook_tab = QWidget()
        pricebook_layout = QVBoxLayout(pricebook_tab)
        pricebook_layout.setContentsMargins(8, 8, 8, 8)
        self.pricebook_panel = MaterialPricebookPanel(pricebook_tab)
        pricebook_layout.addWidget(self.pricebook_panel)
        self.notebook.addTab(pricebook_tab, "📦 材料價目")

        # === 頁籤4：請款追蹤 ===
        billing_tab = QWidget()
        billing_layout = QVBoxLayout(billing_tab)
        billing_layout.setContentsMargins(8, 8, 8, 8)
        self.billing_panel = BillingPanel(billing_tab)
        billing_layout.addWidget(self.billing_panel)
        self.notebook.addTab(billing_tab, "💰 請款追蹤")

        # === 頁簽5：系統設定 ===
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        settings_layout.setContentsMargins(8, 8, 8, 8)
        self.settings_panel = SettingsPanel(settings_tab)
        settings_layout.addWidget(self.settings_panel)
        self.notebook.addTab(settings_tab, "⚙️ 設定")

        # === 頁簽6：健康檢查 ===
        health_tab = QWidget()
        health_layout = QVBoxLayout(health_tab)
        health_layout.setContentsMargins(8, 8, 8, 8)
        self.health_panel = HealthCheckPanel(health_tab)
        health_layout.addWidget(self.health_panel)
        self.notebook.addTab(health_tab, "🩺 健康")

        # 狀態列
        self.status_label = QLabel("就緒")
        self.status_label.setObjectName("statusBar")
        root_layout.addWidget(self.status_label)

        # 頁籤切換事件
        self.notebook.currentChanged.connect(self._on_tab_changed)

    def _create_report_tab(self, parent: QWidget):
        layout = QHBoxLayout(parent)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        # ═══════════════════════════════════════════
        # 左側：日期列表（輕量，不用 GroupBox）
        # ═══════════════════════════════════════════
        left_panel = QWidget()
        left_panel.setFixedWidth(200)
        left_vbox = QVBoxLayout(left_panel)
        left_vbox.setContentsMargins(0, 0, 0, 0)
        left_vbox.setSpacing(4)

        # 標題列
        title_row = QHBoxLayout()
        title_lbl = QLabel("📅 日期")
        title_lbl.setFont(Fonts.subheading(11))
        title_row.addWidget(title_lbl)
        title_row.addStretch()
        btn_refresh = QPushButton("🔄")
        btn_refresh.setFixedSize(28, 28)
        btn_refresh.setToolTip("重新整理")
        btn_refresh.clicked.connect(self._refresh_folders)
        title_row.addWidget(btn_refresh)
        left_vbox.addLayout(title_row)

        # 日期列表
        self.date_listbox = QListWidget()
        self.date_listbox.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.date_listbox.setFont(Fonts.code(10))
        self.date_listbox.setAlternatingRowColors(True)
        self.date_listbox.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.date_listbox.customContextMenuRequested.connect(
            self._show_date_context_menu
        )
        left_vbox.addWidget(self.date_listbox, 1)

        # 底部工具列
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(4)
        btn_select_all = QPushButton("全選")
        btn_select_all.setProperty("role", "flat")
        btn_select_all.clicked.connect(self._select_all)
        bottom_row.addWidget(btn_select_all)
        btn_deselect = QPushButton("取消")
        btn_deselect.setProperty("role", "flat")
        btn_deselect.clicked.connect(self._deselect_all)
        bottom_row.addWidget(btn_deselect)
        bottom_row.addStretch()
        left_vbox.addLayout(bottom_row)

        self.stat_label = QLabel("共 0 個  ·  右鍵開啟工具")
        self.stat_label.setFont(Fonts.small())
        self.stat_label.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        left_vbox.addWidget(self.stat_label)

        layout.addWidget(left_panel)

        # ═══════════════════════════════════════════
        # 右側：主工作區
        # ═══════════════════════════════════════════
        right_vbox = QVBoxLayout()
        right_vbox.setContentsMargins(0, 0, 0, 0)
        right_vbox.setSpacing(6)

        # ── DWG LIST 路徑（簡潔行） ──
        dwg_row = QHBoxLayout()
        dwg_row.setSpacing(6)
        dwg_lbl = QLabel("DWG LIST")
        dwg_lbl.setFont(Fonts.small(9))
        dwg_lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        dwg_lbl.setFixedWidth(60)
        dwg_row.addWidget(dwg_lbl)
        self.dwg_entry = QLineEdit(get_drawing_list_path())
        self.dwg_entry.setPlaceholderText("選擇 DWG LIST Excel 檔案...")
        dwg_row.addWidget(self.dwg_entry, 1)
        btn_browse_dwg = QPushButton("瀏覽")
        btn_browse_dwg.clicked.connect(self._browse_dwg_list)
        dwg_row.addWidget(btn_browse_dwg)
        right_vbox.addLayout(dwg_row)

        # ── 選項列（平鋪 checkbox） ──
        opt_row = QHBoxLayout()
        opt_row.setSpacing(14)
        self.chk_export_pdf = QCheckBox("匯出 PDF")
        self.chk_export_pdf.setChecked(RUNTIME.export_pdf)
        opt_row.addWidget(self.chk_export_pdf)
        self.chk_skip_unchanged = QCheckBox("略過未變更")
        self.chk_skip_unchanged.setChecked(RUNTIME.skip_unchanged)
        opt_row.addWidget(self.chk_skip_unchanged)
        self.chk_auto_preprocess = QCheckBox("自動處理圖片")
        self.chk_auto_preprocess.setChecked(RUNTIME.auto_preprocess_images)
        opt_row.addWidget(self.chk_auto_preprocess)
        self.chk_debug = QCheckBox("Debug")
        self.chk_debug.setChecked(RUNTIME.debug_mode)
        opt_row.addWidget(self.chk_debug)
        self.renderer_status_label = QLabel("")
        self.renderer_status_label.setFont(Fonts.small())
        self.renderer_status_label.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        opt_row.addWidget(self.renderer_status_label)
        opt_row.addStretch()
        right_vbox.addLayout(opt_row)

        # ── 分隔線 ──
        right_vbox.addWidget(make_separator())

        # ── 主要操作列（大按鈕，一行搞定） ──
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.btn_start = QPushButton("▶  開始執行")
        set_button_role(self.btn_start, "primary")
        self.btn_start.setMinimumHeight(34)
        self.btn_start.setMinimumWidth(120)
        self.btn_start.clicked.connect(self._start_processing)
        action_row.addWidget(self.btn_start)

        self.btn_stop = QPushButton("⏹ 停止")
        set_button_role(self.btn_stop, "danger")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setMinimumHeight(34)
        self.btn_stop.clicked.connect(self._stop_processing)
        action_row.addWidget(self.btn_stop)

        self.btn_retry = QPushButton("🔄 重試失敗")
        self.btn_retry.setMinimumHeight(34)
        self.btn_retry.clicked.connect(self._retry_failed)
        action_row.addWidget(self.btn_retry)

        action_row.addStretch()

        # 建立精靈（獨立功能，非日期相關）
        btn_wizard = QPushButton("✨ 建立精靈")
        btn_wizard.setToolTip("啟動資料夾建立精靈")
        btn_wizard.clicked.connect(self._launch_wizard)
        action_row.addWidget(btn_wizard)

        btn_co_wizard = QPushButton("🆕 新修改單精靈 (Beta)")
        btn_co_wizard.setToolTip("啟動新版源頭驅動修改單精靈")
        btn_co_wizard.clicked.connect(self._launch_change_order_wizard)
        action_row.addWidget(btn_co_wizard)

        # 資料夾捷徑（靠右）
        btn_open_output = QPushButton("📂 Output")
        set_button_role(btn_open_output, "flat")
        btn_open_output.clicked.connect(self._open_output_folder)
        action_row.addWidget(btn_open_output)
        btn_open_pdf = QPushButton("📂 PDF")
        set_button_role(btn_open_pdf, "flat")
        btn_open_pdf.clicked.connect(self._open_pdf_folder)
        action_row.addWidget(btn_open_pdf)

        right_vbox.addLayout(action_row)

        # ── 進度條（極簡） ──
        progress_row = QHBoxLayout()
        progress_row.setSpacing(6)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        progress_row.addWidget(self.progress_bar, 1)
        self.progress_label = QLabel("0%")
        self.progress_label.setFixedWidth(36)
        self.progress_label.setFont(Fonts.small())
        self.progress_label.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        progress_row.addWidget(self.progress_label)
        right_vbox.addLayout(progress_row)

        # ── 日誌區（佔據剩餘空間，無外框 GroupBox） ──
        log_header = QLabel("執行日誌")
        log_header.setFont(Fonts.small(9))
        log_header.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        right_vbox.addWidget(log_header)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(Fonts.code(9))
        right_vbox.addWidget(self.log_text, 1)

        layout.addLayout(right_vbox, 1)

    # ─── 事件 ─────────────────────────────────────────────
    def _on_tab_changed(self, index: int):
        if index == 1:
            self.record_panel.load_records()
        elif index == 2:
            self.pricebook_panel.load_data()
        elif index == 3:
            self.billing_panel.load_data()
        elif index == 5:
            self.health_panel.run_check()

    # ─── 日期列表右鍵選單 ─────────────────────────────────
    def _show_date_context_menu(self, pos):
        """在日期列表上顯示右鍵選單"""
        menu = QMenu(self)
        has_selection = bool(self.date_listbox.selectedItems())

        actions = [
            ("🔍  驗證資料夾", self._validate_folders, "驗證選取的資料夾結構"),
            ("🖼  預處理圖片", self._preprocess_images, "調整圖片尺寸"),
            ("📋  選擇子資料夾", self._show_folder_selector, "展開選擇子資料夾"),
            ("📝  補充焊口資訊", self._supplement_info, "補充 weld_info.json"),
            ("🔍  焊口重複檢查", self._open_weld_duplicate_check, "檢查焊口重複性"),
        ]
        for text, handler, tooltip in actions:
            act = menu.addAction(text)
            act.setToolTip(tooltip)
            act.triggered.connect(handler)
            act.setEnabled(has_selection)

        menu.addSeparator()

        act_all = menu.addAction("全選")
        act_all.triggered.connect(self._select_all)
        act_none = menu.addAction("取消全選")
        act_none.triggered.connect(self._deselect_all)

        menu.exec(self.date_listbox.mapToGlobal(pos))

    # ─── 初始載入 ─────────────────────────────────────────
    def _load_initial_data(self):
        self._refresh_folders()
        self.log("✅ 系統啟動完成")
        self.log(f"📁 基準目錄: {BASE_DIR}")
        renderer = getattr(self, "_xlsx_com_renderer", None)
        if renderer and renderer.get("status") == "unavailable":
            self.log(f"⚠️ 舊版 COM 產出停用：{renderer.get('reason', '')}")

    def _refresh_folders(self):
        self.date_listbox.clear()
        self.date_folders = scan_date_folders(ATTACHMENTS_ROOT)
        for d in self.date_folders:
            subfolders = scan_subfolders(os.path.join(ATTACHMENTS_ROOT, d))
            self.date_listbox.addItem(f"{d} ({len(subfolders)})")
        self.stat_label.setText(f"共 {len(self.date_folders)} 個日期資料夾")
        self.log(f"🔄 已載入 {len(self.date_folders)} 個日期資料夾")

    def _browse_dwg_list(self):
        initial_dir = get_last_browse_directory()
        if not initial_dir or not os.path.exists(initial_dir):
            initial_dir = os.path.dirname(BASE_DIR)
        filepath, _ = QFileDialog.getOpenFileName(
            self, "選擇 DWG LIST 檔案", initial_dir,
            "Excel 檔案 (*.xlsm *.xlsx);;所有檔案 (*.*)"
        )
        if filepath:
            self.dwg_entry.setText(filepath)
            sm = get_settings()
            sm.set_path("drawing_list", filepath)
            remember_browse_directory(filepath)
            self.log(f"📂 DWG LIST 已更新: {os.path.basename(filepath)}")

    # ─── 選取 ─────────────────────────────────────────────
    def _select_all(self):
        self.date_listbox.selectAll()

    def _deselect_all(self):
        self.date_listbox.clearSelection()

    def _get_selected_dates(self) -> List[str]:
        return [self.date_folders[idx.row()]
                for idx in self.date_listbox.selectedIndexes()]

    # ─── 日誌 ─────────────────────────────────────────────
    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")

    def _update_progress(self, current: int, total: int, message: str = ""):
        if total > 0:
            pct = int(current / total * 100)
            self.progress_bar.setValue(pct)
            self.progress_label.setText(f"{pct}%")
        if message:
            self.status_label.setText(message)

    # ─── 處理 ─────────────────────────────────────────────
    def _start_processing(self):
        if self.is_running:
            QMessageBox.information(self, "提示", "目前正在處理中，請稍候。")
            return

        renderer = get_renderer_descriptor("xlsx_com", probe_com_application=True)
        if not renderer.get("available"):
            self._update_excel_com_controls(renderer, log_result=True)
            QMessageBox.warning(self, "舊版產出不可用", format_renderer_unavailable(renderer))
            return
        self._update_excel_com_controls(renderer, log_result=False)

        selected_dates = self._get_selected_dates()
        if not selected_dates:
            QMessageBox.warning(self, "警告", "請先選擇要處理的日期資料夾")
            return

        RUNTIME.export_pdf = self.chk_export_pdf.isChecked()
        RUNTIME.skip_unchanged = self.chk_skip_unchanged.isChecked()
        RUNTIME.debug_mode = self.chk_debug.isChecked()
        RUNTIME.auto_preprocess_images = self.chk_auto_preprocess.isChecked()

        self.is_running = True
        self.should_stop = False
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

        self.log(f"🚀 開始處理 {len(selected_dates)} 個日期資料夾...")

        self.worker_thread = threading.Thread(
            target=self._process_folders,
            args=(selected_dates,),
            daemon=True,
        )
        self.worker_thread.start()

    def _stop_processing(self):
        self.should_stop = True
        self.log("⏸️ 正在停止...")
        self.status_label.setText("正在停止...")

    def _process_folders(self, date_list: List[str]):
        """背景處理資料夾（在工作執行緒中執行）"""
        bridge = self._bridge
        pythoncom = None
        com_initialized = False
        get_excel_manager = None

        try:
            renderer = get_renderer_descriptor("xlsx_com", probe_com_application=True)
            if not renderer.get("available"):
                raise RuntimeError(format_renderer_unavailable(renderer))

            import pythoncom as pythoncom_module
            pythoncom = pythoncom_module
            pythoncom.CoInitialize()
            com_initialized = True

            from excel_handler import get_excel_manager as load_excel_manager
            from excel_handler import generate_report, check_images_exist
            get_excel_manager = load_excel_manager
            em = get_excel_manager()
            em.restart()

            bridge.log_signal.emit("📖 載入 DWG LIST...")
            self.drawing_map = load_drawing_map()

            bridge.log_signal.emit("📖 載入紀錄索引...")
            existing_key_set, key_to_row, key_to_meta, max_seq_by_date = preload_record_index()
            material_pricebook = load_material_pricebook()

            summary = ProcessingSummary()
            record_rows: list = []
            detail_rows: list = []
            materials_rows: list = []

            total_items = 0
            for date_str in date_list:
                subfolders = scan_subfolders(os.path.join(ATTACHMENTS_ROOT, date_str))
                total_items += len(subfolders)

            current_item = 0

            for date_str in date_list:
                if self.should_stop:
                    break

                attach_dir = os.path.join(ATTACHMENTS_ROOT, date_str)
                subfolders = scan_subfolders(attach_dir)
                if not subfolders:
                    continue

                idx_seq = max_seq_by_date.get(date_str, 0)
                out_dir = os.path.join(OUTPUT_ROOT, date_str)
                os.makedirs(out_dir, exist_ok=True)

                for folder in subfolders:
                    if self.should_stop:
                        break

                    current_item += 1
                    folder_path = os.path.join(attach_dir, folder)

                    msg = f"處理中: {date_str}/{folder}"
                    bridge.progress_signal.emit(current_item, total_items, msg)

                    try:
                        info = parse_folder(folder_path)
                        line_number, dwg_no = self.drawing_map.get(info.series_no, ("", ""))
                        desc = build_auto_description(
                            info.tokens, info.note_text, RUNTIME.show_dims_in_desc
                        )

                        # ① 圖片預處理（必須在指紋計算之前，否則 mtime 變動會導致指紋永遠不穩定）
                        if RUNTIME.auto_preprocess_images and check_pillow():
                            pp_result = auto_preprocess_if_needed(
                                folder_path,
                                max_edge=RUNTIME.preprocess_max_edge,
                                quality=RUNTIME.preprocess_quality,
                                backup=RUNTIME.preprocess_backup,
                                force=False,
                            )
                            if pp_result.get("processed"):
                                bridge.log_signal.emit(
                                    f"  ↳ 預處理了 {len(pp_result['processed'])} 張圖片"
                                )

                        # ①-b 預製圖自動複製
                        prefab_copied = copy_prefab_pdf(folder_path, info.series_no)
                        if prefab_copied:
                            bridge.log_signal.emit(
                                f"  ↳ 已複製預製圖: {os.path.basename(prefab_copied)}"
                            )

                        # ② 指紋計算（在預處理之後，確保反映最終檔案狀態）
                        suffixes_raw = [t.raw for t in info.tokens]
                        dual = use_dual_images(info.mode, len(info.tokens))
                        fp_new = compute_fingerprint(
                            date_str, folder, info.series_no, suffixes_raw,
                            info.note_text, info.materials_text, folder_path,
                            is_group=(info.mode == "group"), use_dual_images=dual
                        )

                        # ③ 略過檢查
                        key = (date_str, folder)
                        existed = key in existing_key_set
                        old_meta = key_to_meta.get(key, {})

                        if existed and RUNTIME.skip_unchanged:
                            old_fp = (old_meta.get('fingerprint') or "").strip()
                            if old_fp and old_fp == fp_new:
                                report_id = old_meta.get('report_id') or f"{date_str}-??"
                                for t in info.tokens:
                                    detail_rows.append(self._build_detail_row(
                                        t, report_id, date_str, info.series_no, dwg_no, desc
                                    ))
                                summary.add_skipped()
                                bridge.log_signal.emit(f"⏭️ 略過: {folder}（未變更）")
                                continue

                        # ④ 報告編號
                        if existed and old_meta.get('report_id'):
                            report_id = old_meta['report_id']
                            seq = parse_seq_from_report_id(report_id) or 0
                        else:
                            idx_seq += 1
                            seq = idx_seq
                            report_id = f"{date_str}-{seq:02}"
                            max_seq_by_date[date_str] = seq

                        result = generate_report(
                            folder_path=folder_path,
                            folder_name=folder,
                            date_str=date_str,
                            series_no=info.series_no,
                            mode=info.mode,
                            tokens=info.tokens,
                            note_text=info.note_text,
                            materials_text=info.materials_text,
                            line_number=line_number or "",
                            dwg_no=dwg_no or "",
                            report_id=report_id,
                            seq=seq,
                            output_dir=out_dir,
                            pdf_dir=PDF_OUTPUT_DIR,
                            description=desc,
                            on_progress=lambda m: bridge.log_signal.emit(f"  ↳ {m}"),
                        )

                        if result.success:
                            summary.add_success()
                            clear_error_marker(folder_path)
                            bridge.log_signal.emit(f"✅ 完成: {folder}")

                            codes = weld_code_list(info.tokens)
                            images = check_images_exist(folder_path, info.mode, len(info.tokens))
                            dims_pairs = [
                                f"{t.weld_no}{t.tag}={t.size}"
                                for t in info.tokens if t.weld_no and t.tag and t.size
                            ]
                            ap_name = (
                                os.path.basename(
                                    find_attachment_pdf(folder_path, info.series_no) or ""
                                ) or "無"
                            )

                            record_rows.append({
                                "日期": date_str,
                                "報告編號": report_id,
                                "Series NO": info.series_no,
                                "LINE NUMBER": line_number or "",
                                "DWG NO": dwg_no or "",
                                "變更類型": "裁切重焊" if all(t.is_cut for t in info.tokens) else "加長",
                                "焊口清單": "、".join(codes),
                                "焊口與尺寸": "；".join(dims_pairs),
                                "說明": desc,
                                "材料附加": info.materials_text,
                                "附件PDF": ap_name,
                                "資料夾名": folder,
                                "before.jpg": "有" if images['has_before'] else "無",
                                "after.jpg": "有" if images['has_after'] else "無",
                                "內容指紋": fp_new,
                            })

                            for t in info.tokens:
                                detail_rows.append(self._build_detail_row(
                                    t, report_id, date_str, info.series_no, dwg_no, desc
                                ))

                            parsed_mats = apply_material_pricing(
                                parse_materials_txt(folder_path),
                                material_pricebook,
                            )
                            for mat in parsed_mats:
                                materials_rows.append({
                                    "項目": None,
                                    "報告編號": report_id,
                                    "修改日期": date_str,
                                    "Series NO": info.series_no,
                                    "零件類型": mat.get("零件類型", ""),
                                    "尺寸": mat.get("尺寸", ""),
                                    "SCH": mat.get("SCH", ""),
                                    "材質": mat.get("材質", ""),
                                    "類別": mat.get("類別", "材料"),
                                    "數量": mat.get("數量", ""),
                                    "單位": mat.get("單位", ""),
                                    "單價": mat.get("單價", ""),
                                    "金額": mat.get("金額", ""),
                                    "單價來源": mat.get("單價來源", ""),
                                    "金額來源": mat.get("金額來源", ""),
                                    "價目表ID": mat.get("價目表ID", ""),
                                    "價目來源": mat.get("價目來源", ""),
                                    "價目生效日": mat.get("價目生效日", ""),
                                    "配價狀態": mat.get("配價狀態", ""),
                                    "備註": mat.get("備註", ""),
                                })
                        else:
                            summary.add_failed(f"{date_str}\\{folder}")
                            bridge.log_signal.emit(f"❌ 失敗: {folder} - {result.error}")

                    except Exception as e:
                        summary.add_failed(f"{date_str}\\{folder}")
                        bridge.log_signal.emit(f"❌ 錯誤: {folder} - {e}")

            # 儲存紀錄
            if record_rows:
                upsert_record(record_rows)
                bridge.log_signal.emit(f"📝 已更新 record: {len(record_rows)} 筆")
            if detail_rows:
                upsert_detail_rows(detail_rows)
                bridge.log_signal.emit(f"📝 已更新明細: {len(detail_rows)} 筆")
            if materials_rows:
                upsert_materials_rows(materials_rows)
                bridge.log_signal.emit(f"📝 已更新材料明細: {len(materials_rows)} 筆")

            bridge.summary_signal.emit(summary)

        except Exception as e:
            bridge.log_signal.emit(f"💥 嚴重錯誤: {e}")
            bridge.error_signal.emit(str(e))

        finally:
            try:
                if get_excel_manager is not None:
                    em2 = get_excel_manager()
                    em2.quit()
            except Exception:
                pass
            if com_initialized and pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
            bridge.finished_signal.emit()

    def _build_detail_row(self, token: WeldToken, report_id: str, date_str: str,
                          series_no: str, dwg_no: str, desc: str) -> Dict:
        weld_code = token.code if hasattr(token, 'code') else token.get('raw', '')
        size_val = token.size if hasattr(token, 'size') else token.get('size')
        return {
            "項目": None,
            "紀錄編號": report_id,
            "修改日期": date_str,
            "修改原因敘述": desc,
            "Series NO": series_no,
            "DWG NO": dwg_no or "",
            "焊口編號": weld_code,
            "焊口尺寸": size_val if size_val else "",
            "係數": "",
            "單價/DB": "",
            "金額": "",
            "備註": "",
        }

    def _show_summary(self, summary: ProcessingSummary):
        self.log("\n" + "═" * 40)
        self.log("📊 執行摘要")
        self.log("─" * 40)
        self.log(f"✅ 成功產出: {summary.success}")
        self.log(f"⏭️ 略過（未變更）: {summary.skipped}")
        self.log(f"❌ 失敗: {summary.failed}")
        if summary.failed_list:
            self.log("   失敗清單:")
            for p in summary.failed_list[:10]:
                self.log(f"   - {p}")
            if len(summary.failed_list) > 10:
                self.log(f"   ... 還有 {len(summary.failed_list) - 10} 筆")
        self.log("═" * 40)

    def _processing_finished(self):
        self.is_running = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_label.setText("完成")
        self._update_progress(100, 100, "完成")
        self._update_excel_com_controls(log_result=False)

    def _update_excel_com_controls(self, renderer=None, *, log_result: bool = False):
        renderer = renderer or get_renderer_descriptor("xlsx_com", probe_com_application=False)
        self._xlsx_com_renderer = renderer
        status = str(renderer.get("status", "") or "")
        if status in {"legacy_available", "unprobed"}:
            if not self.is_running:
                self.btn_start.setEnabled(True)
                self.btn_retry.setEnabled(True)
            tooltip = _renderer_tooltip(renderer)
            self.btn_start.setToolTip(tooltip)
            self.btn_retry.setToolTip(tooltip)
            self.renderer_status_label.setText(_renderer_status_text(renderer))
            return

        self.btn_start.setEnabled(False)
        self.btn_retry.setEnabled(False)
        message = format_renderer_unavailable(renderer)
        self.btn_start.setToolTip(message)
        self.btn_retry.setToolTip(message)
        self.renderer_status_label.setText(_renderer_status_text(renderer))
        if log_result:
            self.log(f"⚠️ 舊版 COM 產出不可用：{renderer.get('reason', '')}")

    # ─── 重試失敗 ─────────────────────────────────────────
    def _retry_failed(self):
        if self.is_running:
            QMessageBox.information(self, "提示", "目前正在處理中，請稍候完成後再重試。")
            return

        renderer = get_renderer_descriptor("xlsx_com", probe_com_application=True)
        if not renderer.get("available"):
            self._update_excel_com_controls(renderer, log_result=True)
            QMessageBox.warning(self, "舊版產出不可用", format_renderer_unavailable(renderer))
            return
        self._update_excel_com_controls(renderer, log_result=False)

        failed_folders = []
        for date_str in self.date_folders:
            attach_dir = os.path.join(ATTACHMENTS_ROOT, date_str)
            for folder in scan_subfolders(attach_dir):
                error_file = os.path.join(attach_dir, folder, "_ERROR.txt")
                if os.path.exists(error_file):
                    failed_folders.append((date_str, folder))

        if not failed_folders:
            QMessageBox.information(self, "提示", "沒有找到失敗的項目")
            return

        reply = QMessageBox.question(
            self, "確認",
            f"找到 {len(failed_folders)} 個失敗項目，要重試嗎？",
        )
        if reply == QMessageBox.StandardButton.Yes:
            dates_to_retry = list(set(d for d, _ in failed_folders))
            for date_str, folder in failed_folders:
                error_file = os.path.join(ATTACHMENTS_ROOT, date_str, folder, "_ERROR.txt")
                try:
                    os.remove(error_file)
                except Exception:
                    pass
            self.date_listbox.clearSelection()
            for i, d in enumerate(self.date_folders):
                if d in dates_to_retry:
                    self.date_listbox.item(i).setSelected(True)
            self.log(f"🔄 準備重試 {len(failed_folders)} 個失敗項目...")
            self._start_processing()

    # ─── 工具按鈕 ─────────────────────────────────────────
    def _open_pdf_folder(self):
        os.startfile(PDF_OUTPUT_DIR)

    def _open_output_folder(self):
        os.startfile(OUTPUT_ROOT)

    def _validate_folders(self):
        if not VALIDATOR_AVAILABLE:
            QMessageBox.warning(self, "功能不可用", "validator 模組未載入")
            return
        selected_dates = self._get_selected_dates()
        if not selected_dates:
            QMessageBox.warning(self, "警告", "請先選擇要驗證的日期資料夾")
            return

        self.log("\n🔍 開始驗證資料夾...")
        all_results = {}
        for date_str in selected_dates:
            date_folder = os.path.join(ATTACHMENTS_ROOT, date_str)
            results = validate_date_folder(date_folder)
            for name, v in results.items():
                all_results[f"{date_str}/{name}"] = v

        total = len(all_results)
        valid_count = sum(1 for v in all_results.values() if v.is_valid)
        error_count = total - valid_count

        self.log(f"📊 驗證完成: 共 {total} 個資料夾")
        self.log(f"   ✅ 通過: {valid_count}")
        self.log(f"   ❌ 有問題: {error_count}")

        if error_count > 0:
            self.log("\n❌ 需要修正的資料夾:")
            for name, v in all_results.items():
                if not v.is_valid:
                    self.log(f"   📁 {name}")
                    if v.missing_required:
                        self.log(f"      缺少: {', '.join(v.missing_required)}")
                    for issue in v.issues:
                        if issue.severity == Severity.ERROR:
                            self.log(f"      ⛔ {issue.message}")

        missing_info_folders = []
        for name, v in all_results.items():
            if v.is_valid:
                folder_path = os.path.join(ATTACHMENTS_ROOT, name)
                weld_info_path = os.path.join(folder_path, "weld_info.json")
                if not os.path.exists(weld_info_path):
                    missing_info_folders.append(name)

        if missing_info_folders:
            self.log(f"\n📝 {len(missing_info_folders)} 個資料夾缺少詳細資訊 (weld_info.json)")
            self.log("   可使用『📝 補充資訊』按鈕添加材質/厚度等資訊")

        warning_count = sum(1 for v in all_results.values() if v.is_valid and v.warning_count > 0)
        if warning_count > 0:
            self.log(f"\n⚠️ {warning_count} 個資料夾有警告")

        if error_count == 0:
            if missing_info_folders:
                QMessageBox.information(
                    self, "驗證完成",
                    f"✅ 所有 {total} 個資料夾驗證通過！\n\n"
                    f"📝 其中 {len(missing_info_folders)} 個缺少詳細資訊\n"
                    f"可點擊『📝 補充資訊』按鈕補充材質/厚度",
                )
            else:
                QMessageBox.information(self, "驗證完成", f"✅ 所有 {total} 個資料夾驗證通過！")
        else:
            QMessageBox.warning(self, "驗證完成", f"發現 {error_count} 個資料夾有問題\n請查看日誌了解詳情")

    def _launch_wizard(self):
        if not WIZARD_AVAILABLE:
            QMessageBox.warning(self, "功能不可用", "wizard 模組未載入")
            return
        from wizard import FolderWizard
        wiz = FolderWizard(self)
        wiz.show()
        self.log("✨ 已啟動資料夾建立精靈")

    def _launch_change_order_wizard(self):
        if not CHANGE_ORDER_WIZARD_AVAILABLE:
            QMessageBox.warning(self, "功能不可用", "新修改單精靈模組未載入")
            return
        wiz = ChangeOrderWizard(attachments_root=ATTACHMENTS_ROOT)
        wiz.exec()
        self.log("🆕 已啟動新修改單精靈")

    def _supplement_info(self):
        selected_dates = self._get_selected_dates()
        if not selected_dates:
            QMessageBox.warning(self, "警告", "請先選擇要補充資訊的日期資料夾")
            return

        folders_to_supplement = []
        for date_str in selected_dates:
            date_folder = os.path.join(ATTACHMENTS_ROOT, date_str)
            if not os.path.isdir(date_folder):
                continue
            for sub_name in os.listdir(date_folder):
                sub_path = os.path.join(date_folder, sub_name)
                if not os.path.isdir(sub_path) or sub_name.startswith('_'):
                    continue
                weld_info_path = os.path.join(sub_path, "weld_info.json")
                if not os.path.exists(weld_info_path):
                    folders_to_supplement.append({
                        'folder_path': sub_path,
                        'folder_name': sub_name,
                        'date': date_str,
                    })

        if not folders_to_supplement:
            QMessageBox.information(self, "提示", "✅ 所選日期資料夾都已有完整資訊（weld_info.json）！")
            return

        self.log(f"\n📝 找到 {len(folders_to_supplement)} 個資料夾需要補充資訊")
        dlg = SupplementInfoDialog(self, folders_to_supplement)
        dlg.exec()

    def _open_weld_duplicate_check(self):
        dlg = WeldDuplicateCheckDialog(self)
        dlg.exec()

    def _preprocess_images(self):
        if not IMAGE_PROCESSOR_AVAILABLE:
            QMessageBox.warning(self, "功能不可用", "image_processor 模組未載入\n請安裝 Pillow: pip install Pillow")
            return
        if not check_pillow():
            QMessageBox.warning(self, "功能不可用", "Pillow 未安裝\n請執行: pip install Pillow")
            return
        selected_dates = self._get_selected_dates()
        if not selected_dates:
            QMessageBox.warning(self, "警告", "請先選擇要處理的日期資料夾")
            return
        reply = QMessageBox.question(
            self, "確認",
            "這將預處理所有選擇資料夾中的圖片\n"
            "• 調整尺寸以符合模板\n• 校正 EXIF 旋轉\n"
            "• 原始檔案會被備份為 .orig\n\n是否繼續？",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.log("\n🖼️ 開始預處理圖片...")
        processed_count = 0
        error_count = 0
        for date_str in selected_dates:
            attach_dir = os.path.join(ATTACHMENTS_ROOT, date_str)
            subfolders = scan_subfolders(attach_dir)
            for folder in subfolders:
                folder_path = os.path.join(attach_dir, folder)
                try:
                    results = prepare_folder_images(folder_path)
                    if results['processed']:
                        processed_count += len(results['processed'])
                        self.log(f"   ✅ {folder}: 處理 {len(results['processed'])} 張")
                    if results['errors']:
                        error_count += len(results['errors'])
                except Exception as e:
                    error_count += 1
                    self.log(f"   ❌ {folder}: {e}")

        self.log(f"\n📊 圖片預處理完成: 處理 {processed_count} 張, 錯誤 {error_count} 個")
        QMessageBox.information(self, "完成", f"圖片預處理完成\n處理: {processed_count} 張\n錯誤: {error_count} 個")

    def _show_folder_selector(self):
        selected_dates = self._get_selected_dates()
        if not selected_dates:
            QMessageBox.warning(self, "警告", "請先選擇日期資料夾")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("選擇子資料夾")
        dlg.resize(500, 600)

        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("勾選要處理的資料夾（取消勾選表示略過）"))

        tree = QTreeWidget()
        tree.setHeaderLabels(["資料夾", "狀態", "模式"])
        tree.setColumnWidth(0, 300)
        tree.setColumnWidth(1, 60)
        tree.setColumnWidth(2, 60)

        for date_str in selected_dates:
            date_item = QTreeWidgetItem(tree, [f"📅 {date_str}"])
            date_item.setExpanded(True)
            attach_dir = os.path.join(ATTACHMENTS_ROOT, date_str)
            for folder in scan_subfolders(attach_dir):
                folder_path = os.path.join(attach_dir, folder)
                mode = "Group" if folder.endswith('G') and '_' in folder else "Single"
                if VALIDATOR_AVAILABLE:
                    v = validate_folder(folder_path)
                    status = "✅" if v.is_valid else "❌"
                else:
                    status = "?"
                child = QTreeWidgetItem(date_item, [f"📁 {folder}", status, mode])
                child.setCheckState(0, Qt.CheckState.Checked)

        layout.addWidget(tree)

        btn_row = QHBoxLayout()
        btn_all = QPushButton("全選")
        btn_none = QPushButton("取消全選")

        def _check_all(state):
            for i in range(tree.topLevelItemCount()):
                parent_it = tree.topLevelItem(i)
                for j in range(parent_it.childCount()):
                    parent_it.child(j).setCheckState(0, state)

        btn_all.clicked.connect(lambda: _check_all(Qt.CheckState.Checked))
        btn_none.clicked.connect(lambda: _check_all(Qt.CheckState.Unchecked))
        btn_row.addWidget(btn_all)
        btn_row.addWidget(btn_none)
        btn_row.addStretch()

        btn_ok = QPushButton("確定")
        btn_cancel = QPushButton("取消")
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)
        btn_row.addWidget(btn_cancel)
        btn_row.addWidget(btn_ok)
        layout.addLayout(btn_row)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            count = 0
            for i in range(tree.topLevelItemCount()):
                parent_it = tree.topLevelItem(i)
                for j in range(parent_it.childCount()):
                    if parent_it.child(j).checkState(0) == Qt.CheckState.Checked:
                        count += 1
            self.log(f"📋 已選擇 {count} 個資料夾進行處理")


# ========= 主程式 =========
def main():
    app = QApplication(sys.argv)
    apply_theme(app)

    # 確保目錄存在
    os.makedirs(OUTPUT_ROOT, exist_ok=True)
    os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)

    window = MainWindow()
    window.show()

    exit_code = app.exec()

    # 清理
    try:
        from excel_handler import get_excel_manager
        em = get_excel_manager()
        em.quit()
    except Exception:
        pass

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
