# -*- coding: utf-8 -*-
"""
gui_panels.py — 紀錄管理面板 + 請款追蹤面板 (PyQt6)

從 gui.py 拆分而來，降低單檔複雜度。
"""

import os
import re
import shutil
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QLineEdit, QTreeWidget, QTreeWidgetItem, QTabWidget, QComboBox,
    QMessageBox, QFileDialog, QHeaderView, QGridLayout, QAbstractItemView,
    QFrame, QSizePolicy, QMenu,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QBrush, QColor, QFont, QImage, QPixmap

# PDF 縮圖渲染
try:
    import fitz as _fitz
    _FITZ_OK = True
except ImportError:
    _fitz = None
    _FITZ_OK = False

from config import RECORD_XLSX_PATH, ATTACHMENTS_ROOT, PDF_OUTPUT_DIR
from record_manager import (
    RECORDS_JSON_PATH, BILLING_JSON_PATH,
    _load_store, _save_store, export_records_to_excel,
)
from utils import atomic_save_wb
from theme import Colors, Fonts, set_button_role, make_separator, make_stat_card, make_hint_label

try:
    from openpyxl import load_workbook
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False


# ──────────────── hover-to-zoom 圖片預覽 ────────────────
class _ZoomLabel(QLabel):
    """滑鼠懸停時顯示的放大預覽浮窗"""
    _ZOOM = 380

    def __init__(self):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(
            "QLabel { background: white; border: 2px solid #2563eb; border-radius: 8px; padding: 4px; }"
        )
        self.setFixedSize(self._ZOOM + 8, self._ZOOM + 8)
        self.hide()

    def show_image(self, pixmap, gpos):
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                self._ZOOM, self._ZOOM,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)
            self.move(gpos.x() + 16, gpos.y() + 16)
            self.show()


_zoom_inst = None

def _get_zoom():
    global _zoom_inst
    if _zoom_inst is None:
        _zoom_inst = _ZoomLabel()
    return _zoom_inst


class _HoverThumb(QLabel):
    """可 hover 放大的縮圖 QLabel"""

    def __init__(self, full_pixmap, thumb_size: int, tag: str = "", parent=None):
        super().__init__(parent)
        self._full = full_pixmap
        self.setFixedSize(thumb_size, thumb_size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"border: 1px solid {Colors.BORDER}; border-radius: 4px; background: white;"
        )
        self.setToolTip(tag)
        if full_pixmap and not full_pixmap.isNull():
            self.setPixmap(full_pixmap.scaled(
                thumb_size, thumb_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        else:
            self.setText(tag or "—")
            self.setFont(QFont("Segoe UI", 10))
        self.setMouseTracking(True)

    def enterEvent(self, ev):
        super().enterEvent(ev)
        self.setStyleSheet(
            f"border: 2px solid {Colors.PRIMARY}; border-radius: 4px; background: white;"
        )
        if self._full and not self._full.isNull():
            _get_zoom().show_image(self._full, self.mapToGlobal(self.rect().topRight()))

    def leaveEvent(self, ev):
        super().leaveEvent(ev)
        self.setStyleSheet(
            f"border: 1px solid {Colors.BORDER}; border-radius: 4px; background: white;"
        )
        _get_zoom().hide()

    def mouseMoveEvent(self, ev):
        super().mouseMoveEvent(ev)
        z = _get_zoom()
        if z.isVisible() and self._full:
            z.move(ev.globalPosition().toPoint().x() + 16,
                   ev.globalPosition().toPoint().y() + 16)


# ──────────────── helper: inline cell edit ────────────────
class _CellEditor:
    """在 QTreeWidget 上方疊加編輯 widget，模擬 tkinter 行內編輯。"""

    def __init__(self):
        self._widget = None

    def destroy(self):
        if self._widget:
            self._widget.setParent(None)
            self._widget.deleteLater()
            self._widget = None

    def start_entry(self, tree: QTreeWidget, item: QTreeWidgetItem,
                    col: int, callback):
        """文字輸入編輯"""
        self.destroy()
        rect = tree.visualItemRect(item)
        header = tree.header()
        x = header.sectionPosition(col) - tree.horizontalScrollBar().value()
        w = header.sectionSize(col)

        edit = QLineEdit(tree.viewport())
        current = item.text(col) or ""
        clean = current.replace("$", "").replace(",", "")
        edit.setText(clean)
        edit.selectAll()
        edit.setGeometry(x, rect.y(), w, rect.height())
        edit.show()
        edit.setFocus()

        def finish():
            val = edit.text().strip()
            self.destroy()
            callback(item, col, val)

        edit.returnPressed.connect(finish)
        edit.editingFinished.connect(finish)
        self._widget = edit

    def start_combo(self, tree: QTreeWidget, item: QTreeWidgetItem,
                    col: int, options: list, callback):
        """下拉選單編輯"""
        self.destroy()
        rect = tree.visualItemRect(item)
        header = tree.header()
        x = header.sectionPosition(col) - tree.horizontalScrollBar().value()
        w = header.sectionSize(col)

        combo = QComboBox(tree.viewport())
        combo.addItems(options)
        cur = item.text(col)
        if cur in options:
            combo.setCurrentText(cur)
        combo.setGeometry(x, rect.y(), w, rect.height())
        combo.show()
        combo.setFocus()
        combo.showPopup()

        def on_select(_idx):
            val = combo.currentText()
            self.destroy()
            callback(item, col, val)

        combo.activated.connect(on_select)
        self._widget = combo


# ========= 紀錄管理面板 =========
class RecordManagerPanel(QWidget):
    """紀錄管理面板 - 顯示與編輯紀錄清單 (PyQt6)"""

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.records = []
        self.details = []
        self.materials = []
        self.details_modified = False
        self.materials_modified = False
        self._editor = _CellEditor()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        # ── 篩選工具列 ──
        filter_group = QGroupBox("🔍 篩選")
        fr = QHBoxLayout(filter_group)
        fr.setSpacing(8)
        fr.addWidget(QLabel("日期："))
        self.date_from_edit = QLineEdit()
        self.date_from_edit.setPlaceholderText("YYYYMMDD")
        self.date_from_edit.setFixedWidth(95)
        fr.addWidget(self.date_from_edit)
        sep_lbl = QLabel("–")
        sep_lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; border:none; background:transparent;")
        fr.addWidget(sep_lbl)
        self.date_to_edit = QLineEdit()
        self.date_to_edit.setPlaceholderText("YYYYMMDD")
        self.date_to_edit.setFixedWidth(95)
        fr.addWidget(self.date_to_edit)
        fr.addSpacing(12)
        fr.addWidget(QLabel("🔎"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜尋編號 / 說明...")
        self.search_edit.setFixedWidth(180)
        fr.addWidget(self.search_edit)
        # 狀態篩選
        fr.addSpacing(8)
        fr.addWidget(QLabel("狀態："))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["全部", "已產出", "未產出", "已歸檔"])
        self.status_combo.setFixedWidth(90)
        self.status_combo.currentIndexChanged.connect(lambda: self.load_records())
        fr.addWidget(self.status_combo)
        btn_reload = QPushButton("🔄 載入")
        btn_reload.clicked.connect(self.load_records)
        fr.addWidget(btn_reload)
        btn_excel = QPushButton("� 匯出 Excel")
        btn_excel.setProperty("role", "flat")
        btn_excel.setToolTip("從 JSON 資料匯出為 Excel 紀錄清單")
        btn_excel.clicked.connect(self._open_excel)
        fr.addWidget(btn_excel)
        fr.addStretch()
        root.addWidget(filter_group)

        # ── 主紀錄 + 明細 ──
        main_h = QHBoxLayout()
        main_h.setSpacing(10)

        # 左側：主紀錄
        record_group = QGroupBox("📋 報告紀錄")
        rg_layout = QVBoxLayout(record_group)
        self.record_tree = QTreeWidget()
        self.record_tree.setAlternatingRowColors(True)
        self.record_tree.setSortingEnabled(True)
        self.record_tree.setHeaderLabels(["報告編號", "日期", "Series", "焊口清單", "變更類型", "說明", "狀態"])
        for i, w in enumerate([100, 80, 60, 150, 80, 180, 70]):
            self.record_tree.setColumnWidth(i, w)
        self.record_tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.record_tree.itemSelectionChanged.connect(self._on_record_select)
        self.record_tree.itemDoubleClicked.connect(lambda: self._open_folder())
        self.record_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.record_tree.customContextMenuRequested.connect(self._show_context_menu)
        rg_layout.addWidget(self.record_tree)
        main_h.addWidget(record_group, 1)

        # 右側：明細 notebook
        detail_nb = QTabWidget()

        # 焊口明細
        detail_w = QWidget()
        dv = QVBoxLayout(detail_w)
        dv.setContentsMargins(6, 6, 6, 6)
        self.detail_tree = QTreeWidget()
        self.detail_tree.setAlternatingRowColors(True)
        self.detail_tree.setHeaderLabels(
            ["焊口編號", "標記", "尺寸", "材質", "厚度", "係數", "單價", "金額"]
        )
        for i, w in enumerate([70, 45, 55, 70, 60, 55, 70, 70]):
            self.detail_tree.setColumnWidth(i, w)
        self.detail_tree.itemDoubleClicked.connect(self._on_detail_double_click)
        dv.addWidget(self.detail_tree)
        detail_nb.addTab(detail_w, "🔧 焊口明細")

        # 材料明細
        mat_w = QWidget()
        mv = QVBoxLayout(mat_w)
        mv.setContentsMargins(6, 6, 6, 6)
        self.material_tree = QTreeWidget()
        self.material_tree.setAlternatingRowColors(True)
        self.material_tree.setHeaderLabels(["零件類型", "尺寸", "SCH", "材質", "數量", "單價", "金額"])
        for i, w in enumerate([100, 60, 55, 80, 60, 80, 80]):
            self.material_tree.setColumnWidth(i, w)
        self.material_tree.itemDoubleClicked.connect(self._on_material_double_click)
        mv.addWidget(self.material_tree)
        detail_nb.addTab(mat_w, "📦 材料明細")

        # 圖片明細
        img_w = QWidget()
        iv = QVBoxLayout(img_w)
        iv.setContentsMargins(6, 6, 6, 6)
        iv.setSpacing(8)
        self._img_hint = QLabel("選取左側紀錄以顯示圖片")
        self._img_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_hint.setStyleSheet(
            f"color: {Colors.TEXT_MUTED}; border:none; background:transparent; padding: 30px;"
        )
        iv.addWidget(self._img_hint)
        # 圖片容器
        self._img_container = QWidget()
        self._img_layout = QHBoxLayout(self._img_container)
        self._img_layout.setContentsMargins(0, 0, 0, 0)
        self._img_layout.setSpacing(12)
        self._img_layout.addStretch()
        self._img_container.hide()
        iv.addWidget(self._img_container, stretch=1)
        detail_nb.addTab(img_w, "🖼️ 圖片明細")

        main_h.addWidget(detail_nb, 1)
        root.addLayout(main_h, 1)

        # ── 底部按鈕 ──
        bot = QHBoxLayout()
        bot.setSpacing(8)
        self.stat_label = QLabel("共 0 筆紀錄")
        self.stat_label.setFont(Fonts.small())
        self.stat_label.setStyleSheet(f"color: {Colors.TEXT_MUTED}; border:none; background:transparent;")
        bot.addWidget(self.stat_label)
        self.modified_label = QLabel("")
        self.modified_label.setStyleSheet(f"color: {Colors.DANGER}; font-weight:bold; border:none; background:transparent;")
        bot.addWidget(self.modified_label)
        bot.addStretch()
        for txt, slot, role in [
            ("💾 儲存", self._save_changes, "primary"),
            ("� 匯出", self._open_excel, "success"),
            ("�📄 PDF", self._open_pdf, ""),
            ("📂 資料夾", self._open_folder, ""),
            (" 補登", self._open_backfill_tool, ""),
            ("🔍 稽查", self._open_orphan_audit, ""),
        ]:
            b = QPushButton(txt)
            if role:
                b.setProperty("role", role)
            b.clicked.connect(slot)
            bot.addWidget(b)
        root.addLayout(bot)

    # ────────────────── 資料載入 ──────────────────
    def load_records(self):
        self.record_tree.setSortingEnabled(False)   # 批次插入時關閉排序
        self.record_tree.clear()
        self.records.clear()

        try:
            store = _load_store()
            search_text = self.search_edit.text().lower()
            status_filter = self.status_combo.currentText()

            # ── 1) 從 JSON 載入已產出紀錄 ──
            json_folders = set()          # (日期, 資料夾名) — 追蹤已有紀錄的
            for rec in store["records"]:
                date_val = rec.get("日期", "")
                folder_name = rec.get("資料夾名", "")
                json_folders.add((date_val, folder_name))
                record = {
                    "report_id": rec.get("報告編號", ""),
                    "date": date_val,
                    "series": rec.get("Series NO", ""),
                    "welds": rec.get("焊口清單", ""),
                    "change_type": rec.get("變更類型", ""),
                    "desc": rec.get("說明", ""),
                    "folder": folder_name,
                    "status": "已產出",
                    "folder_path": os.path.join(ATTACHMENTS_ROOT, date_val, folder_name),
                    "is_archived": False,
                }
                self.records.append(record)

            # ── 2) 掃描 attachments/ 找未產出的 ──
            if os.path.isdir(ATTACHMENTS_ROOT):
                for date_dir in sorted(os.listdir(ATTACHMENTS_ROOT)):
                    date_path = os.path.join(ATTACHMENTS_ROOT, date_dir)
                    if not os.path.isdir(date_path) or date_dir.startswith("_"):
                        continue
                    if not re.match(r"^\d{8}$", date_dir):
                        continue
                    for fn in sorted(os.listdir(date_path)):
                        fp = os.path.join(date_path, fn)
                        if not os.path.isdir(fp) or fn.startswith("_"):
                            continue
                        if (date_dir, fn) in json_folders:
                            continue  # 已在 JSON 裡
                        parts = fn.split("_")
                        serial = parts[0] if parts and parts[0].isdigit() else ""
                        welds_str = "_".join(parts[1:]) if len(parts) > 1 else ""
                        self.records.append({
                            "report_id": "",
                            "date": date_dir,
                            "series": serial,
                            "welds": welds_str,
                            "change_type": "",
                            "desc": "",
                            "folder": fn,
                            "status": "未產出",
                            "folder_path": fp,
                            "is_archived": False,
                        })

            # ── 3) 掃描 _archived/ 找已歸檔的 ──
            archived_root = os.path.join(ATTACHMENTS_ROOT, "_archived")
            if os.path.isdir(archived_root):
                for date_dir in sorted(os.listdir(archived_root)):
                    date_path = os.path.join(archived_root, date_dir)
                    if not os.path.isdir(date_path):
                        continue
                    for fn in sorted(os.listdir(date_path)):
                        fp = os.path.join(date_path, fn)
                        if not os.path.isdir(fp):
                            continue
                        parts = fn.split("_")
                        serial = parts[0] if parts and parts[0].isdigit() else ""
                        welds_str = "_".join(parts[1:]) if len(parts) > 1 else ""
                        self.records.append({
                            "report_id": "",
                            "date": date_dir,
                            "series": serial,
                            "welds": welds_str,
                            "change_type": "",
                            "desc": "",
                            "folder": fn,
                            "status": "已歸檔",
                            "folder_path": fp,
                            "is_archived": True,
                        })

            # ── 4) 篩選 + 新增到 tree ──
            visible_count = 0
            for rec_idx, record in enumerate(self.records):
                # 狀態篩選
                if status_filter != "全部" and record["status"] != status_filter:
                    continue
                # 文字搜尋
                if search_text:
                    searchable = (
                        f"{record['report_id']} {record['series']} "
                        f"{record['welds']} {record['desc']} {record['folder']}"
                    ).lower()
                    if search_text not in searchable:
                        continue

                welds_s = str(record["welds"])
                desc_s = str(record["desc"])
                status_s = record["status"]
                item = QTreeWidgetItem(self.record_tree, [
                    str(record["report_id"]),
                    str(record["date"]),
                    str(record["series"]),
                    welds_s[:30] + "..." if len(welds_s) > 30 else welds_s,
                    str(record["change_type"]),
                    desc_s[:30] + "..." if len(desc_s) > 30 else desc_s,
                    status_s,
                ])
                item.setData(0, Qt.ItemDataRole.UserRole, rec_idx)
                # 狀態顏色
                if status_s == "未產出":
                    item.setForeground(6, QBrush(QColor("#d97706")))  # 橘
                elif status_s == "已歸檔":
                    item.setForeground(6, QBrush(QColor("#9ca3af")))  # 灰
                    for col in range(6):
                        item.setForeground(col, QBrush(QColor("#9ca3af")))
                else:
                    item.setForeground(6, QBrush(QColor("#16a34a")))  # 綠
                visible_count += 1

            # 明細
            self.details.clear()
            for det in store["details"]:
                self.details.append({
                    "report_id": det.get("紀錄編號", ""),
                    "weld_code": det.get("焊口編號", ""),
                    "size": det.get("焊口尺寸", ""),
                    "coefficient": det.get("係數", ""),
                    "price": det.get("單價/DB", ""),
                    "amount": det.get("金額", ""),
                })

            # 材料明細（若有）
            self.materials.clear()
            for mat in store.get("materials", []):
                self.materials.append({
                    "report_id": mat.get("報告編號", ""),
                    "component": mat.get("零件類型", ""),
                    "size": mat.get("尺寸", ""),
                    "sch": mat.get("SCH", ""),
                    "material": mat.get("材質", ""),
                    "qty": mat.get("數量", ""),
                    "unit": mat.get("單位", ""),
                    "price": mat.get("單價", ""),
                    "amount": mat.get("金額", ""),
                })

            produced = sum(1 for r in self.records if r["status"] == "已產出")
            unproduced = sum(1 for r in self.records if r["status"] == "未產出")
            archived = sum(1 for r in self.records if r["status"] == "已歸檔")
            self.stat_label.setText(
                f"總計 {len(self.records)} 筆 │ "
                f"✅ 已產出 {produced}  ⏳ 未產出 {unproduced}  📦 已歸檔 {archived}"
                + (f"  │ 篩選 {visible_count}" if status_filter != "全部" or search_text else "")
            )

        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"載入紀錄失敗：{e}")
        finally:
            self.record_tree.setSortingEnabled(True)  # 重新啟用欄位擊點排序
            self.record_tree.sortByColumn(1, Qt.SortOrder.AscendingOrder)  # 預設日期升冪

    # ────────────────── 選擇 / 雙擊 ──────────────────
    def _on_record_select(self):
        items = self.record_tree.selectedItems()
        if not items:
            return
        report_id = items[0].text(0)
        record = self._find_record_by_item(items[0])

        # ── 焊口明細 ──
        self.detail_tree.clear()

        # 從 weld_info.json 載入材質/厚度（如果有）
        weld_extra = {}  # key: weld_code → {mark, material, thickness}
        if record:
            import json as _json
            wip = os.path.join(record.get("folder_path", ""), "weld_info.json")
            if os.path.isfile(wip):
                try:
                    with open(wip, "r", encoding="utf-8") as f:
                        wi = _json.load(f)
                    for w in wi.get("welds", []):
                        wn = str(w.get("weld_no", ""))
                        mk = str(w.get("mark", ""))
                        m_sp = re.match(r'^(\d+)([rab])', wn)
                        if m_sp:
                            wn = m_sp.group(1)
                            mk = mk or m_sp.group(2)
                        # key = weld_no + mark 以匹配 detail 的焊口編號
                        code = f"{wn}{mk}"
                        weld_extra[code] = {
                            "mark": mk,
                            "material": w.get("material", ""),
                            "thickness": w.get("thickness", ""),
                        }
                except Exception:
                    pass

        for d in self.details:
            if str(d["report_id"]) == report_id:
                wc = str(d["weld_code"])
                extra = weld_extra.get(wc, {})
                # 合併到 detail 供存檔用
                d["mark"] = d.get("mark") or extra.get("mark", "")
                d["material"] = d.get("material") or extra.get("material", "")
                d["thickness"] = d.get("thickness") or extra.get("thickness", "")
                QTreeWidgetItem(self.detail_tree, [
                    wc,
                    str(d["mark"]),
                    str(d["size"]),
                    str(d["material"]),
                    str(d["thickness"]),
                    str(d["coefficient"]),
                    str(d["price"]),
                    str(d["amount"]),
                ])

        # ── 材料明細 ──
        self.material_tree.clear()
        for m in self.materials:
            if str(m["report_id"]) == report_id:
                qty_str = f"{m['qty']} {m.get('unit', '')}".strip()
                QTreeWidgetItem(self.material_tree, [
                    str(m["component"]), str(m["size"]),
                    str(m.get("sch", "")), str(m["material"]),
                    qty_str, str(m["price"]), str(m["amount"]),
                ])

        # ── 圖片明細 ──
        self._update_image_detail(record)

    # ── 焊口明細欄位對照 ──
    _DETAIL_COL_MAP = {
        0: "weld_code",    # 焊口編號
        1: "mark",         # 標記 (r/a/b)
        2: "size",         # 尺寸
        3: "material",     # 材質
        4: "thickness",    # 厚度
        5: "coefficient",  # 係數
        6: "price",        # 單價
        7: "amount",       # 金額
    }

    def _on_detail_double_click(self, item: QTreeWidgetItem, col: int):
        if col not in self._DETAIL_COL_MAP:
            return

        def cb(it, c, val):
            it.setText(c, val)
            field = self._DETAIL_COL_MAP[c]
            self._update_detail_data(it, field, val)
            self.details_modified = True
            self._update_modified_label()

        # 標記欄用下拉選單
        if col == 1:
            self._editor.start_combo(
                self.detail_tree, item, col, ["r", "a", "b"], cb
            )
        else:
            self._editor.start_entry(self.detail_tree, item, col, cb)

    def _on_material_double_click(self, item: QTreeWidgetItem, col: int):
        editable = {5: "price", 6: "amount"}
        if col not in editable:
            return

        def cb(it, c, val):
            it.setText(c, val)
            self._update_material_data(it, editable[c], val)
            self.materials_modified = True
            self._update_modified_label()

        self._editor.start_entry(self.material_tree, item, col, cb)

    def _update_detail_data(self, item: QTreeWidgetItem, field: str, val: str):
        """更新 self.details 中對應項目的欄位值（用 tree 行索引精確匹配）"""
        sel = self.record_tree.selectedItems()
        if not sel:
            return
        report_id = sel[0].text(0)
        # 用行索引而非焊口編號匹配（因為焊口編號本身可被修改）
        row_idx = self.detail_tree.indexOfTopLevelItem(item)
        matching = [d for d in self.details if str(d["report_id"]) == report_id]
        if 0 <= row_idx < len(matching):
            matching[row_idx][field] = val

    def _update_material_data(self, item: QTreeWidgetItem, field: str, val: str):
        comp = item.text(0)
        size = item.text(1)
        sel = self.record_tree.selectedItems()
        if not sel:
            return
        report_id = sel[0].text(0)
        for m in self.materials:
            if str(m["report_id"]) == report_id and str(m["component"]) == comp and str(m["size"]) == size:
                m[field] = val
                break

    def _update_modified_label(self):
        parts = []
        if self.details_modified:
            parts.append("焊口明細")
        if self.materials_modified:
            parts.append("材料明細")
        self.modified_label.setText(f"⚠️ 已修改: {', '.join(parts)}" if parts else "")

    # ────────────────── 圖片明細 ──────────────────

    def _update_image_detail(self, record: dict | None):
        """根據選取的紀錄更新圖片明細 tab"""
        # 清除舊卡片
        while self._img_layout.count() > 1:
            item = self._img_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not record:
            self._img_hint.setText("此紀錄沒有資料夾資訊")
            self._img_hint.show()
            self._img_container.hide()
            return

        folder_path = record.get("folder_path", "")
        if not folder_path or not os.path.isdir(folder_path):
            self._img_hint.setText(f"資料夾不存在:\n{folder_path}")
            self._img_hint.show()
            self._img_container.hide()
            return

        self._img_hint.hide()
        self._img_container.show()

        # before / after（支援 single + group 模式）
        for img_path, label in self._find_images(folder_path):
            card = self._make_image_card(img_path, label, folder_path=folder_path)
            self._img_layout.insertWidget(self._img_layout.count() - 1, card)

        # PDF
        pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
        for pdf_name in pdf_files[:2]:
            pdf_path = os.path.join(folder_path, pdf_name)
            card = self._make_image_card(pdf_path, f"📄 {pdf_name}", is_pdf=True)
            self._img_layout.insertWidget(self._img_layout.count() - 1, card)

        # ➕ 新增圖片 按鈕卡
        add_card = self._make_add_image_card(folder_path)
        self._img_layout.insertWidget(self._img_layout.count() - 1, add_card)

    def _make_image_card(self, path: str, label: str, is_pdf: bool = False,
                         folder_path: str = "") -> QFrame:
        """建立一張圖片預覽卡片（含縮圖 + 標籤，hover 放大）"""
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: {Colors.BG_WHITE}; border: 1px solid {Colors.BORDER_LIGHT};"
            f" border-radius: 6px; }}"
        )
        card.setFixedWidth(160)
        clay = QVBoxLayout(card)
        clay.setContentsMargins(6, 6, 6, 6)
        clay.setSpacing(4)
        clay.setAlignment(Qt.AlignmentFlag.AlignTop)

        THUMB_SIZE = 140
        full_pm = None

        if is_pdf:
            full_pm = self._render_pdf_thumb(path, 400)
        elif os.path.exists(path):
            full_pm = QPixmap(path)

        thumb_lbl = _HoverThumb(full_pm, THUMB_SIZE, label)
        clay.addWidget(thumb_lbl, alignment=Qt.AlignmentFlag.AlignCenter)

        # 標籤
        txt = QLabel(label)
        txt.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt.setStyleSheet(f"color: {Colors.TEXT}; border:none; background:transparent;")
        clay.addWidget(txt)

        # 存在/不存在狀態
        exists = (full_pm is not None and not full_pm.isNull())
        if not exists and not is_pdf:
            st = QLabel("(檔案不存在)")
            st.setFont(QFont("Segoe UI", 7))
            st.setAlignment(Qt.AlignmentFlag.AlignCenter)
            st.setStyleSheet(f"color: {Colors.TEXT_MUTED}; border:none; background:transparent;")
            clay.addWidget(st)

        # PDF 可點擊開啟
        if is_pdf and os.path.exists(path):
            btn = QPushButton("📂 開啟 PDF")
            btn.setFixedHeight(24)
            btn.setFont(QFont("Segoe UI", 7))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, p=path: os.startfile(p))
            clay.addWidget(btn)

        # 🔄 替換圖片 按鈕（非 PDF 才顯示）
        if not is_pdf:
            btn_replace = QPushButton("🔄 替換圖片")
            btn_replace.setFixedHeight(24)
            btn_replace.setFont(QFont("Segoe UI", 7))
            btn_replace.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_replace.clicked.connect(lambda _, p=path: self._replace_image(p))
            clay.addWidget(btn_replace)

        # ✏️ 標註（圖片和 PDF 都可使用）
        if os.path.exists(path):
            btn_annotate = QPushButton("✏️ 標註")
            btn_annotate.setFixedHeight(24)
            btn_annotate.setFont(QFont("Segoe UI", 7))
            btn_annotate.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_annotate.clicked.connect(
                lambda _, p=path, pdf=is_pdf: self._open_annotator(p, pdf)
            )
            clay.addWidget(btn_annotate)

        return card

    def _make_add_image_card(self, folder_path: str) -> QFrame:
        """建立 ➕ 新增圖片 卡片"""
        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: {Colors.BG_WHITE}; border: 2px dashed {Colors.BORDER_LIGHT};"
            f" border-radius: 6px; }}"
        )
        card.setFixedWidth(160)
        card.setFixedHeight(160)
        clay = QVBoxLayout(card)
        clay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_lbl = QLabel("➕")
        icon_lbl.setFont(QFont("Segoe UI", 28))
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet("border:none; background:transparent;")
        clay.addWidget(icon_lbl)

        txt = QLabel("新增圖片")
        txt.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt.setStyleSheet(f"color: {Colors.TEXT_MUTED}; border:none; background:transparent;")
        clay.addWidget(txt)

        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.mousePressEvent = lambda e, fp=folder_path: self._add_image(fp)
        return card

    def _replace_image(self, target_path: str):
        """以檔案對話框選取圖片替換指定路徑"""
        from PyQt6.QtWidgets import QFileDialog
        src, _ = QFileDialog.getOpenFileName(
            self, "選擇替換圖片", "",
            "圖片 (*.jpg *.jpeg *.png *.bmp);;所有檔案 (*)"
        )
        if not src:
            return
        import shutil
        shutil.copy2(src, target_path)
        # 重新整理
        items = self.record_tree.selectedItems()
        if items:
            record = self._find_record_by_item(items[0])
            self._update_image_detail(record)

    def _add_image(self, folder_path: str):
        """新增一張圖片到資料夾（自動命名 before_N / after_N）"""
        from PyQt6.QtWidgets import QFileDialog, QInputDialog
        src, _ = QFileDialog.getOpenFileName(
            self, "選擇圖片", "",
            "圖片 (*.jpg *.jpeg *.png *.bmp);;所有檔案 (*)"
        )
        if not src:
            return
        # 讓使用者選擇類型
        choices = ["修改前 (before)", "修改後 (after)"]
        choice, ok = QInputDialog.getItem(
            self, "圖片類型", "此圖片屬於：", choices, 0, False
        )
        if not ok:
            return
        prefix = "before" if "before" in choice else "after"
        # 找下一個可用編號
        existing = set(os.listdir(folder_path)) if os.path.isdir(folder_path) else set()
        base_name = f"{prefix}.jpg"
        if base_name not in existing:
            dest = os.path.join(folder_path, base_name)
        else:
            idx = 1
            while f"{prefix}_{idx}.jpg" in existing:
                idx += 1
            dest = os.path.join(folder_path, f"{prefix}_{idx}.jpg")
        import shutil
        shutil.copy2(src, dest)
        # 重新整理
        items = self.record_tree.selectedItems()
        if items:
            record = self._find_record_by_item(items[0])
            self._update_image_detail(record)

    def _open_annotator(self, path: str, is_pdf: bool):
        """開啟標註對話框"""
        from gui_annotator import AnnotationDialog
        dlg = AnnotationDialog(path, is_pdf=is_pdf, parent=self)
        if not dlg._load_ok:
            QMessageBox.warning(self, "無法載入", f"無法開啟標註工具:\n{path}")
            return
        dlg.exec()
        if dlg.was_saved:
            items = self.record_tree.selectedItems()
            if items:
                record = self._find_record_by_item(items[0])
                self._update_image_detail(record)

    @staticmethod
    def _find_images(folder_path: str) -> list:
        """找出 before/after 圖片（支援 single + group 模式）

        Returns: [(path, label), ...]
        """
        result = []
        files = set(os.listdir(folder_path)) if os.path.isdir(folder_path) else set()
        # single: before.jpg / after.jpg
        if "before.jpg" in files:
            result.append((os.path.join(folder_path, "before.jpg"), "修改前"))
        if "after.jpg" in files:
            result.append((os.path.join(folder_path, "after.jpg"), "修改後"))
        # group: before_1.jpg, before_2.jpg, ... / after_1.jpg, after_2.jpg, ...
        idx = 1
        while True:
            bf = f"before_{idx}.jpg"
            af = f"after_{idx}.jpg"
            found = False
            if bf in files:
                result.append((os.path.join(folder_path, bf), f"修改前 {idx}"))
                found = True
            if af in files:
                result.append((os.path.join(folder_path, af), f"修改後 {idx}"))
                found = True
            if not found:
                break
            idx += 1
        return result

    @staticmethod
    def _render_pdf_thumb(pdf_path: str, size: int = 400):
        """用 PyMuPDF 渲染 PDF 第一頁為 QPixmap"""
        if not _FITZ_OK or not os.path.exists(pdf_path):
            return None
        try:
            doc = _fitz.open(pdf_path)
            page = doc[0]
            rect = page.rect
            zoom = size / min(rect.width, rect.height)
            mat = _fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            pm = QPixmap.fromImage(img)
            doc.close()
            return pm
        except Exception:
            return None

    # ────────────────── 右鍵選單 ──────────────────
    def _show_context_menu(self, pos):
        item = self.record_tree.itemAt(pos)
        if not item:
            return
        record = self._find_record_by_item(item)
        if not record:
            return

        menu = QMenu(self)
        is_produced = record["status"] == "已產出"
        is_archived = record["status"] == "已歸檔"

        act_folder = menu.addAction("📂 開啟資料夾")
        act_pdf = menu.addAction("📄 開啟 PDF")
        act_pdf.setEnabled(is_produced)
        menu.addSeparator()

        act_edit = menu.addAction("✏️ 修改焊口 / 尺寸")
        act_edit.setEnabled(not is_archived)

        if is_archived:
            act_archive = menu.addAction("📤 還原（取消歸檔）")
        else:
            act_archive = menu.addAction("📦 歸檔")

        menu.addSeparator()
        act_backfill = menu.addAction("🔧 補登")
        act_audit = menu.addAction("🔍 孤兒稽查")

        chosen = menu.exec(self.record_tree.viewport().mapToGlobal(pos))
        if chosen == act_folder:
            self._open_folder_for(record)
        elif chosen == act_pdf:
            self._open_pdf_for(record)
        elif chosen == act_edit:
            self._edit_record(record)
        elif chosen == act_archive:
            if is_archived:
                self._restore_record(record)
            else:
                self._archive_record(record)
        elif chosen == act_backfill:
            self._open_backfill_tool()
        elif chosen == act_audit:
            self._open_orphan_audit()

    def _find_record_by_item(self, item: QTreeWidgetItem) -> dict | None:
        """根據 tree item 在 self.records 中找到對應的 record"""
        rec_idx = item.data(0, Qt.ItemDataRole.UserRole)
        if rec_idx is not None and 0 <= rec_idx < len(self.records):
            return self.records[rec_idx]
        # fallback: 先用 report_id 精準比對
        report_id = item.text(0)
        if report_id:
            for r in self.records:
                if str(r["report_id"]) == report_id:
                    return r
        # 再用 date + 焊口清單 比對
        date_val = item.text(1)
        folder_text = item.text(3)
        for r in self.records:
            if str(r["date"]) == date_val:
                welds_s = str(r["welds"])
                display = welds_s[:30] + "..." if len(welds_s) > 30 else welds_s
                if display == folder_text:
                    return r
        return None

    # ────────────────── 歸檔 / 還原 ──────────────────
    def _archive_record(self, record: dict):
        folder = record.get("folder", "")
        date_val = record.get("date", "")
        if QMessageBox.question(
            self, "歸檔記錄",
            f"確定要歸檔以下記錄嗎？\n\n📁 {folder}\n📅 {date_val}\n\n"
            f"將移至 _archived/{date_val}/ 資料夾",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            src = record["folder_path"]
            archived_date_dir = os.path.join(ATTACHMENTS_ROOT, "_archived", date_val)
            os.makedirs(archived_date_dir, exist_ok=True)
            dst = os.path.join(archived_date_dir, folder)
            if os.path.exists(dst):
                ts = datetime.now().strftime("%H%M%S")
                dst = os.path.join(archived_date_dir, f"{folder}_{ts}")
            shutil.move(src, dst)
            QMessageBox.information(self, "成功", f"✅ 已歸檔至:\n{dst}")
            self.load_records()
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"歸檔失敗: {e}")

    def _restore_record(self, record: dict):
        folder = record.get("folder", "")
        date_val = record.get("date", "")
        if QMessageBox.question(
            self, "還原記錄",
            f"確定要還原以下記錄嗎？\n\n📁 {folder}\n📅 {date_val}\n\n"
            f"將從 _archived 移回 attachments/{date_val}/",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            src = record["folder_path"]
            target_dir = os.path.join(ATTACHMENTS_ROOT, date_val)
            os.makedirs(target_dir, exist_ok=True)
            dst = os.path.join(target_dir, folder)
            if os.path.exists(dst):
                QMessageBox.critical(self, "錯誤", f"目標位置已存在同名資料夾:\n{dst}")
                return
            shutil.move(src, dst)
            QMessageBox.information(self, "成功", f"✅ 已還原至:\n{dst}")
            self.load_records()
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"還原失敗: {e}")

    # ────────────────── 編輯焊口 ──────────────────
    def _edit_record(self, record: dict):
        """開啟 EditRecordDialog 來編輯焊口/尺寸/資料夾名稱"""
        import json
        folder_path = record["folder_path"]
        if not os.path.isdir(folder_path):
            QMessageBox.warning(self, "提示", f"資料夾不存在:\n{folder_path}")
            return

        # 組裝 EditRecordDialog 需要的 record 格式
        parts = record["folder"].split("_")
        serial = parts[0] if parts and parts[0].isdigit() else ""
        welds_str = "_".join(parts[1:]) if len(parts) > 1 else ""

        weld_info = None
        wip = os.path.join(folder_path, "weld_info.json")
        if os.path.exists(wip):
            try:
                with open(wip, "r", encoding="utf-8") as f:
                    weld_info = json.load(f)
            except Exception:
                pass

        dialog_record = {
            "date": record["date"],
            "folder_name": record["folder"],
            "folder_path": folder_path,
            "serial": serial,
            "welds_str": welds_str,
            "weld_info": weld_info,
        }
        from gui_dialogs import EditRecordDialog
        EditRecordDialog(self, dialog_record, self.load_records).exec()

    # ────────────────── 動作（通用）──────────────────
    def _open_folder_for(self, record: dict):
        fp = record.get("folder_path", "")
        if fp and os.path.exists(fp):
            os.startfile(fp)
        else:
            QMessageBox.warning(self, "提示", f"資料夾不存在：{fp}")

    def _open_pdf_for(self, record: dict):
        report_id = record.get("report_id", "")
        if not report_id:
            QMessageBox.warning(self, "提示", "此項目尚無報告編號")
            return
        pdf = os.path.join(PDF_OUTPUT_DIR, f"{report_id}.pdf")
        if os.path.exists(pdf):
            os.startfile(pdf)
        else:
            QMessageBox.warning(self, "提示", f"PDF 不存在：{pdf}")

    # ────────────────── 動作（按鈕列）──────────────────

    def _open_backfill_tool(self):
        from gui_dialogs import WeldBackfillDialog
        WeldBackfillDialog(self, None).exec()

    def _open_orphan_audit(self):
        from gui_dialogs import WeldOrphanAuditDialog
        WeldOrphanAuditDialog(self).exec()

    def _open_folder(self):
        items = self.record_tree.selectedItems()
        if not items:
            return
        record = self._find_record_by_item(items[0])
        if record:
            self._open_folder_for(record)

    def _open_pdf(self):
        items = self.record_tree.selectedItems()
        if not items:
            return
        record = self._find_record_by_item(items[0])
        if record:
            self._open_pdf_for(record)

    def _open_excel(self):
        """匯出並開啟 Excel 紀錄清單"""
        try:
            path = export_records_to_excel()
            os.startfile(path)
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"匯出失敗：{e}")

    # ────────────────── 儲存 ──────────────────
    def _save_changes(self):
        if not self.details_modified and not self.materials_modified:
            QMessageBox.information(self, "提示", "沒有需要儲存的變更")
            return
        try:
            import json as _json
            from collections import defaultdict
            from gui_dialogs import (
                _collect_and_merge_weld_sources, _apply_conflict_choices,
                WeldSyncConflictDialog,
            )
            from record_manager import auto_backup, RECORDS_JSON_PATH

            store = _load_store()
            renamed_folders = []   # 記錄需 rename 的資料夾

            if self.details_modified:
                # 按 report_id 分組 self.details
                mod_groups: dict[str, list] = defaultdict(list)
                for d in self.details:
                    mod_groups[d["report_id"]].append(d)

                # 依索引位置更新 store["details"]（焊口編號本身可能被修改）
                for rid, mods in mod_groups.items():
                    store_group = [
                        det for det in store["details"]
                        if det.get("紀錄編號", "") == rid
                    ]
                    for i, mod in enumerate(mods):
                        if i >= len(store_group):
                            break
                        det = store_group[i]
                        det["焊口編號"] = mod.get("weld_code", "")
                        det["焊口尺寸"] = mod.get("size", "")
                        det["係數"] = mod.get("coefficient", "")
                        det["單價/DB"] = mod.get("price", "")
                        det["金額"] = mod.get("amount", "")

                # ── 同步 weld_info.json ──
                for record in self.records:
                    rid = str(record.get("report_id", ""))
                    if rid not in mod_groups:
                        continue
                    folder_path = record.get("folder_path", "")
                    if not folder_path or not os.path.isdir(folder_path):
                        continue

                    wip = os.path.join(folder_path, "weld_info.json")
                    wi_data = {}
                    if os.path.isfile(wip):
                        try:
                            with open(wip, "r", encoding="utf-8") as f:
                                wi_data = _json.load(f)
                        except Exception:
                            wi_data = {}

                    old_welds = wi_data.get("welds", [])
                    new_welds = []
                    for i, mod in enumerate(mod_groups[rid]):
                        w = dict(old_welds[i]) if i < len(old_welds) else {}
                        weld_code = str(mod.get("weld_code", ""))
                        mark = str(mod.get("mark", ""))
                        # 一律 regex 拆分: "1001a" → weld_no="1001", mark="a"
                        m_wn = re.match(r'^(\d+)([rab])', weld_code, re.IGNORECASE)
                        if m_wn:
                            weld_code = m_wn.group(1)
                            mark = mark or m_wn.group(2).lower()
                        w["weld_no"] = weld_code
                        w["mark"] = mark
                        w["size"] = mod.get("size", "")
                        w["material"] = mod.get("material", "")
                        w["thickness"] = mod.get("thickness", "")
                        new_welds.append(w)
                    # 防空口編號重複
                    _seen_wids: set[str] = set()
                    _unique_welds: list[dict] = []
                    for _w in new_welds:
                        _wid = f"{_w.get('weld_no','')}{_w.get('mark','')}"
                        if _wid not in _seen_wids:
                            _seen_wids.add(_wid)
                            _unique_welds.append(_w)
                    wi_data["welds"] = _unique_welds

                    with open(wip, "w", encoding="utf-8") as f:
                        _json.dump(wi_data, f, ensure_ascii=False, indent=2)

                    # ── 同步 records[] 主表的焊口欄位 ──
                    merged_for_main = []
                    for _mod in mod_groups[rid]:
                        _wn = str(_mod.get("weld_code", ""))
                        _mk = str(_mod.get("mark", ""))
                        _m_sp = re.match(r'^(\d+)([rab])', _wn, re.IGNORECASE)
                        if _m_sp:
                            _wn = _m_sp.group(1)
                            _mk = _mk or _m_sp.group(2).lower()
                        merged_for_main.append({
                            "weld_no": _wn,
                            "mark": _mk,
                            "size": _mod.get("size", ""),
                        })

                    for rec in store["records"]:
                        if rec.get("報告編號", "") == rid:
                            weld_list_str = "、".join(
                                f"{w['weld_no']}{w['mark']}" for w in merged_for_main
                            )
                            weld_size_str = "；".join(
                                f"{w['weld_no']}{w['mark']}={w['size']}" for w in merged_for_main
                            )
                            rec["焊口清單"] = weld_list_str
                            rec["焊口與尺寸"] = weld_size_str

                            # ── 檢查是否需要改資料夾名 ──
                            old_folder = rec.get("資料夾名", "")
                            serial = record.get("series", "")
                            codes = [f"{w['weld_no']}{w['mark']}{w['size']}"
                                     for w in merged_for_main if w['weld_no'] and w['mark'] and w['size']]
                            if serial and codes:
                                new_folder = f"{serial}_{'_'.join(codes)}"
                                if new_folder != old_folder:
                                    old_fp = os.path.join(ATTACHMENTS_ROOT, record["date"], old_folder)
                                    new_fp = os.path.join(ATTACHMENTS_ROOT, record["date"], new_folder)
                                    renamed_folders.append((old_fp, new_fp, old_folder, new_folder, rec))
                            break

            if self.materials_modified:
                for mat in store.get("materials", []):
                    rid = mat.get("報告編號", "")
                    comp = mat.get("零件類型", "")
                    sz = mat.get("尺寸", "")
                    for m in self.materials:
                        if m["report_id"] == rid and m["component"] == comp and m["size"] == sz:
                            mat["單價"] = m.get("price", "")
                            mat["金額"] = m.get("amount", "")
                            break

            # ── 處理資料夾重新命名 ──
            for old_fp, new_fp, old_fn, new_fn, rec in renamed_folders:
                if os.path.isdir(old_fp) and not os.path.exists(new_fp):
                    answer = QMessageBox.question(
                        self, "資料夾名稱同步",
                        f"焊口已修改，是否同步更新資料夾名稱？\n\n"
                        f"📁 {old_fn}\n→ {new_fn}",
                    )
                    if answer == QMessageBox.StandardButton.Yes:
                        os.rename(old_fp, new_fp)
                        rec["資料夾名"] = new_fn

            auto_backup(RECORDS_JSON_PATH)
            _save_store(store)
            self.details_modified = False
            self.materials_modified = False
            self._update_modified_label()
            QMessageBox.information(self, "成功", "變更已儲存（含主表 + 明細同步）")

        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"儲存失敗：{e}")


# ========= 請款追蹤面板 =========
class BillingPanel(QWidget):
    """請款追蹤面板 - 管理請款狀態、彙總計算、匯出功能 (PyQt6)"""

    BILLING_STATUS = ["", "未請款", "已請款", "已結案", "暫緩"]

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.records = []
        self.modified = False
        self._editor = _CellEditor()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)

        # ── 工具列 ──
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        filter_group = QGroupBox("🔍 篩選")
        fg = QHBoxLayout(filter_group)
        fg.setSpacing(8)
        fg.addWidget(QLabel("日期："))
        self.date_from_edit = QLineEdit()
        self.date_from_edit.setPlaceholderText("YYYYMMDD")
        self.date_from_edit.setFixedWidth(95)
        fg.addWidget(self.date_from_edit)
        sep_lbl = QLabel("–")
        sep_lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; border:none; background:transparent;")
        fg.addWidget(sep_lbl)
        self.date_to_edit = QLineEdit()
        self.date_to_edit.setPlaceholderText("YYYYMMDD")
        self.date_to_edit.setFixedWidth(95)
        fg.addWidget(self.date_to_edit)
        fg.addSpacing(8)
        fg.addWidget(QLabel("狀態："))
        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(["全部"] + self.BILLING_STATUS[1:])
        self.status_filter_combo.setFixedWidth(90)
        self.status_filter_combo.currentIndexChanged.connect(lambda: self._apply_filter())
        fg.addWidget(self.status_filter_combo)
        btn_load = QPushButton("🔄 載入")
        btn_load.clicked.connect(self.load_data)
        fg.addWidget(btn_load)
        btn_filter = QPushButton("🔍 篩選")
        btn_filter.clicked.connect(self._apply_filter)
        fg.addWidget(btn_filter)
        toolbar.addWidget(filter_group, 1)

        action_group = QGroupBox("📤 操作")
        ag = QHBoxLayout(action_group)
        ag.setSpacing(6)
        btn_save = QPushButton("💾 儲存")
        btn_save.setProperty("role", "primary")
        btn_save.clicked.connect(self._save_changes)
        ag.addWidget(btn_save)
        btn_rpt = QPushButton("📊 匯出報表")
        btn_rpt.clicked.connect(self._export_report)
        ag.addWidget(btn_rpt)
        btn_bill = QPushButton("📋 請款單")
        btn_bill.setProperty("role", "success")
        btn_bill.clicked.connect(self._export_billing)
        ag.addWidget(btn_bill)
        toolbar.addWidget(action_group)
        root.addLayout(toolbar)

        # ── 主列表 ──
        self.tree = QTreeWidget()
        self.tree.setAlternatingRowColors(True)
        col_config = [
            ("報告編號", 90), ("修改日期", 80), ("Series", 55), ("說明", 150),
            ("請款狀態", 70), ("請款日期", 80), ("焊口金額", 80),
            ("材料金額", 80), ("總金額", 80), ("備註", 120),
        ]
        self.tree.setHeaderLabels([h for h, _ in col_config])
        for i, (_, w) in enumerate(col_config):
            self.tree.setColumnWidth(i, w)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        root.addWidget(self.tree, 1)

        # ── 統計 ──
        stat_group = QGroupBox("📈 彙總統計")
        sg = QVBoxLayout(stat_group)
        sg.setSpacing(8)

        # 第一行：統計卡片
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)

        self._stat_total_card = make_stat_card("總筆數", "0", Colors.TEXT)
        cards_row.addWidget(self._stat_total_card)
        self._stat_pending_card = make_stat_card("未請款", "0", Colors.DANGER)
        cards_row.addWidget(self._stat_pending_card)
        self._stat_billed_card = make_stat_card("已請款", "0", Colors.SUCCESS)
        cards_row.addWidget(self._stat_billed_card)
        self._stat_closed_card = make_stat_card("已結案", "0", Colors.TEXT_MUTED)
        cards_row.addWidget(self._stat_closed_card)
        sg.addLayout(cards_row)

        # 第二行：金額
        amt_row = QHBoxLayout()
        amt_row.setSpacing(10)
        self._stat_weld_card = make_stat_card("焊口總額", "$0", Colors.PRIMARY)
        amt_row.addWidget(self._stat_weld_card)
        self._stat_mat_card = make_stat_card("材料總額", "$0", Colors.INFO)
        amt_row.addWidget(self._stat_mat_card)
        self._stat_pend_amt_card = make_stat_card("未請款額", "$0", Colors.DANGER)
        amt_row.addWidget(self._stat_pend_amt_card)
        self._stat_bill_amt_card = make_stat_card("已請款額", "$0", Colors.SUCCESS)
        amt_row.addWidget(self._stat_bill_amt_card)
        sg.addLayout(amt_row)

        mod_row = QHBoxLayout()
        mod_row.addStretch()
        self.modified_label = QLabel("")
        self.modified_label.setStyleSheet(f"color: {Colors.DANGER}; font-weight:bold; border:none; background:transparent;")
        mod_row.addWidget(self.modified_label)
        sg.addLayout(mod_row)
        root.addWidget(stat_group)

    # ────────────────── 載入 ──────────────────
    def load_data(self):
        self.records.clear()
        self.tree.clear()
        try:
            store = _load_store()
            billing = self._load_billing()

            for rec in store["records"]:
                rid = rec.get("報告編號", "")
                bill = billing.get(rid, {})
                self.records.append({
                    "report_id": rid,
                    "date": str(rec.get("日期", "")),
                    "series": rec.get("Series NO", ""),
                    "desc": rec.get("說明", ""),
                    "status": bill.get("status", ""),
                    "billing_date": str(bill.get("billing_date", "")),
                    "weld_amount": bill.get("weld_amount", ""),
                    "material_amount": bill.get("material_amount", ""),
                    "total": bill.get("total", ""),
                    "remark": bill.get("remark", ""),
                })
            self._apply_filter()
            self._update_statistics()
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"載入失敗：{e}")

    def _load_billing(self) -> dict:
        """載入 billing.json，回傳 {report_id: {...}}"""
        if not os.path.exists(BILLING_JSON_PATH):
            # 嘗試從舊 Excel 遷移
            self._migrate_billing_from_excel()
        if os.path.exists(BILLING_JSON_PATH):
            import json
            with open(BILLING_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("billing", {})
        return {}

    def _migrate_billing_from_excel(self):
        """從舊 Excel 的請款欄位遷移到 billing.json"""
        if not os.path.exists(RECORD_XLSX_PATH) or not OPENPYXL_AVAILABLE:
            return
        try:
            wb = load_workbook(RECORD_XLSX_PATH, read_only=True, data_only=True)
            if 'record' not in wb.sheetnames:
                wb.close()
                return
            ws = wb['record']
            headers = [c.value for c in ws[1]]
            col_map = {h: i for i, h in enumerate(headers) if h}
            # 需要有請款欄位才遷移
            if "請款狀態" not in col_map:
                wb.close()
                return
            billing = {}
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or not row[0]:
                    continue
                rid = str(row[col_map.get("報告編號", 1)] or "")
                if not rid:
                    continue
                status = row[col_map.get("請款狀態")] or ""
                if status or row[col_map.get("焊口金額", 17)]:
                    billing[rid] = {
                        "status": str(status),
                        "billing_date": str(row[col_map.get("請款日期", 16)] or ""),
                        "weld_amount": str(row[col_map.get("焊口金額", 17)] or ""),
                        "material_amount": str(row[col_map.get("材料金額", 18)] or ""),
                        "total": str(row[col_map.get("總金額", 19)] or ""),
                        "remark": str(row[col_map.get("備註", 20)] or ""),
                    }
            wb.close()
            if billing:
                self._save_billing_json(billing)
        except Exception:
            pass

    def _save_billing_json(self, billing: dict):
        """儲存 billing.json"""
        import json
        os.makedirs(os.path.dirname(BILLING_JSON_PATH), exist_ok=True)
        data = {
            "billing": billing,
            "meta": {
                "version": "1.0",
                "last_modified": datetime.now().isoformat(),
            }
        }
        tmp = BILLING_JSON_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if os.path.exists(BILLING_JSON_PATH):
            os.replace(tmp, BILLING_JSON_PATH)
        else:
            os.rename(tmp, BILLING_JSON_PATH)

    # ────────────────── 篩選 ──────────────────
    def _apply_filter(self):
        self.tree.clear()
        date_from = self.date_from_edit.text().strip()
        date_to = self.date_to_edit.text().strip()
        status_filter = self.status_filter_combo.currentText()

        for r in self.records:
            if date_from and str(r["date"]) < date_from:
                continue
            if date_to and str(r["date"]) > date_to:
                continue
            if status_filter != "全部":
                if status_filter == "未請款" and r["status"] not in ["", "未請款"]:
                    continue
                elif status_filter != "未請款" and r["status"] != status_filter:
                    continue
            desc_s = str(r["desc"])
            QTreeWidgetItem(self.tree, [
                str(r["report_id"]), str(r["date"]), str(r["series"]),
                desc_s[:20] + "..." if len(desc_s) > 20 else desc_s,
                r["status"] or "未請款", str(r["billing_date"]),
                self._format_amount(r["weld_amount"]),
                self._format_amount(r["material_amount"]),
                self._format_amount(r["total"]),
                str(r["remark"]),
            ])
        self._update_statistics()

    # ────────────────── 統計 ──────────────────
    @staticmethod
    def _format_amount(val):
        if not val:
            return ""
        try:
            return f"${float(val):,.0f}"
        except Exception:
            return str(val)

    @staticmethod
    def _parse_amount(val):
        if not val:
            return 0
        try:
            return float(str(val).replace("$", "").replace(",", ""))
        except Exception:
            return 0

    def _update_statistics(self):
        tc = pc = bc = cc = 0
        wt = mt = pa = ba = 0.0
        for i in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(i)
            tc += 1
            status = it.text(4)
            wa = self._parse_amount(it.text(6))
            ma = self._parse_amount(it.text(7))
            ta = self._parse_amount(it.text(8)) or (wa + ma)
            wt += wa
            mt += ma
            if status in ["", "未請款"]:
                pc += 1; pa += ta
            elif status == "已請款":
                bc += 1; ba += ta
            elif status == "已結案":
                cc += 1; ba += ta

        # 更新統計卡片
        def _set_card_value(card, value_text):
            v_lbl = card.layout().itemAt(0).widget()
            if v_lbl:
                v_lbl.setText(value_text)

        _set_card_value(self._stat_total_card, str(tc))
        _set_card_value(self._stat_pending_card, str(pc))
        _set_card_value(self._stat_billed_card, str(bc))
        _set_card_value(self._stat_closed_card, str(cc))
        _set_card_value(self._stat_weld_card, f"${wt:,.0f}")
        _set_card_value(self._stat_mat_card, f"${mt:,.0f}")
        _set_card_value(self._stat_pend_amt_card, f"${pa:,.0f}")
        _set_card_value(self._stat_bill_amt_card, f"${ba:,.0f}")

    # ────────────────── 雙擊編輯 ──────────────────
    def _on_double_click(self, item: QTreeWidgetItem, col: int):
        editable_map = {
            4: ("status", "combo"),
            5: ("billing_date", "entry"),
            6: ("weld_amount", "entry"),
            7: ("material_amount", "entry"),
            8: ("total", "entry"),
            9: ("remark", "entry"),
        }
        if col not in editable_map:
            return
        field, etype = editable_map[col]

        def cb(it, c, val):
            if c in [6, 7, 8] and val:
                try:
                    val = f"${float(val):,.0f}"
                except Exception:
                    pass
            it.setText(c, val)
            rid = it.text(0)
            for r in self.records:
                if str(r["report_id"]) == rid:
                    raw = str(val).replace("$", "").replace(",", "") if c in [6, 7, 8] else val
                    r[field] = raw
                    break
            self.modified = True
            self.modified_label.setText("⚠️ 有未儲存的變更")
            self._update_statistics()

        if etype == "combo":
            self._editor.start_combo(self.tree, item, col, self.BILLING_STATUS[1:], cb)
        else:
            self._editor.start_entry(self.tree, item, col, cb)

    # ────────────────── 儲存 ──────────────────
    def _save_changes(self):
        if not self.modified:
            QMessageBox.information(self, "提示", "沒有需要儲存的變更")
            return
        try:
            billing = {}
            for r in self.records:
                rid = r["report_id"]
                if not rid:
                    continue
                billing[rid] = {
                    "status": r.get("status", ""),
                    "billing_date": r.get("billing_date", ""),
                    "weld_amount": r.get("weld_amount", ""),
                    "material_amount": r.get("material_amount", ""),
                    "total": r.get("total", ""),
                    "remark": r.get("remark", ""),
                }
            self._save_billing_json(billing)
            self.modified = False
            self.modified_label.setText("")
            QMessageBox.information(self, "成功", "變更已儲存")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"儲存失敗：{e}")

    # ────────────────── 匯出 ──────────────────
    def _export_report(self):
        fp, _ = QFileDialog.getSaveFileName(
            self, "匯出統計報表", f"請款統計報表_{datetime.now().strftime('%Y%m%d')}.xlsx",
            "Excel 檔案 (*.xlsx)")
        if not fp:
            return
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            from openpyxl.utils import get_column_letter
            from record_manager import _apply_excel_styles

            wb = Workbook()
            ws = wb.active
            ws.title = "請款統計"
            ws.sheet_properties.tabColor = "1F3864"

            hds = ["報告編號", "修改日期", "Series", "說明", "請款狀態",
                   "請款日期", "焊口金額", "材料金額", "總金額", "備註"]

            # 表頭 (row 2), row 1 留給標題
            for i, h in enumerate(hds, 1):
                ws.cell(row=2, column=i, value=h)

            ri = 3
            for idx in range(self.tree.topLevelItemCount()):
                it = self.tree.topLevelItem(idx)
                for ci in range(10):
                    val = it.text(ci)
                    # 金額欄嘗試轉為數值
                    if ci in (6, 7, 8):
                        try:
                            val = float(val.replace('$', '').replace(',', '')) if val else ""
                        except (ValueError, TypeError):
                            pass
                    ws.cell(row=ri, column=ci + 1, value=val)
                ri += 1

            data_end = max(3, ri - 1)
            _apply_excel_styles(
                ws, header_row=2, data_start=3, data_end=data_end,
                col_count=10,
                col_widths=[14, 11, 10, 32, 10, 11, 14, 14, 14, 22],
                title=f"管線修改單請款統計報表 — {datetime.now().strftime('%Y/%m/%d')}",
                money_cols=[7, 8, 9],
            )

            # 合計列
            total_row = data_end + 1
            NAVY = "1F3864"
            TOTAL_BG = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
            bold_f = Font(name="Microsoft JhengHei UI", bold=True, size=10, color=NAVY)
            side_thin = Side(style="thin", color="B4C6E7")
            bdr = Border(left=side_thin, right=side_thin, top=side_thin, bottom=side_thin)

            ws.cell(row=total_row, column=1, value="合計")
            for ci in range(1, 11):
                c = ws.cell(row=total_row, column=ci)
                c.fill = TOTAL_BG
                c.font = bold_f
                c.border = bdr
            # 金額合計公式
            for col_idx in (7, 8, 9):
                letter = get_column_letter(col_idx)
                ws.cell(row=total_row, column=col_idx,
                        value=f"=SUM({letter}3:{letter}{data_end})")
                ws.cell(row=total_row, column=col_idx).number_format = '#,##0'
                ws.cell(row=total_row, column=col_idx).alignment = Alignment(horizontal="right")

            atomic_save_wb(wb, fp)
            QMessageBox.information(self, "成功", f"報表已匯出：{fp}")
            os.startfile(fp)
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"匯出失敗：{e}")

    def _export_billing(self):
        pending = []
        for idx in range(self.tree.topLevelItemCount()):
            it = self.tree.topLevelItem(idx)
            if it.text(4) in ["", "未請款"]:
                pending.append([it.text(c) for c in range(10)])
        if not pending:
            QMessageBox.information(self, "提示", "沒有未請款的項目")
            return

        fp, _ = QFileDialog.getSaveFileName(
            self, "匯出請款單", f"請款單_{datetime.now().strftime('%Y%m%d')}.xlsx",
            "Excel 檔案 (*.xlsx)")
        if not fp:
            return
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
            from openpyxl.utils import get_column_letter
            from record_manager import _apply_excel_styles

            wb = Workbook()
            ws = wb.active
            ws.title = "請款單"
            ws.sheet_properties.tabColor = "C00000"

            hds = ["項次", "報告編號", "修改日期", "Series", "說明", "焊口金額", "材料金額", "小計"]
            for i, h in enumerate(hds, 1):
                ws.cell(row=2, column=i, value=h)

            total_amt = 0
            for idx_val, vals in enumerate(pending, 1):
                r = 2 + idx_val
                ws.cell(row=r, column=1, value=idx_val)
                ws.cell(row=r, column=2, value=vals[0])
                ws.cell(row=r, column=3, value=vals[1])
                ws.cell(row=r, column=4, value=vals[2])
                ws.cell(row=r, column=5, value=vals[3])
                w = self._parse_amount(vals[6])
                m = self._parse_amount(vals[7])
                sub = self._parse_amount(vals[8]) or (w + m)
                ws.cell(row=r, column=6, value=w)
                ws.cell(row=r, column=7, value=m)
                ws.cell(row=r, column=8, value=sub)
                total_amt += sub

            data_end = max(3, 2 + len(pending))
            _apply_excel_styles(
                ws, header_row=2, data_start=3, data_end=data_end,
                col_count=8,
                col_widths=[7, 14, 11, 10, 34, 14, 14, 14],
                title=f"管線修改單請款單 — {datetime.now().strftime('%Y/%m/%d')}　共 {len(pending)} 筆",
                number_cols=[1],
                money_cols=[6, 7, 8],
            )

            # 合計列
            NAVY = "1F3864"
            total_row = data_end + 1
            TOTAL_BG = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
            bold_f = Font(name="Microsoft JhengHei UI", bold=True, size=10, color=NAVY)
            red_f  = Font(name="Microsoft JhengHei UI", bold=True, size=11, color="C00000")
            side_thin = Side(style="thin", color="B4C6E7")
            bdr = Border(left=side_thin, right=side_thin, top=side_thin, bottom=side_thin)

            ws.cell(row=total_row, column=1, value="合計")
            for ci in range(1, 9):
                c = ws.cell(row=total_row, column=ci)
                c.fill = TOTAL_BG
                c.font = bold_f
                c.border = bdr

            for col_idx in (6, 7, 8):
                letter = get_column_letter(col_idx)
                ws.cell(row=total_row, column=col_idx,
                        value=f"=SUM({letter}3:{letter}{data_end})")
                ws.cell(row=total_row, column=col_idx).number_format = '#,##0'
                ws.cell(row=total_row, column=col_idx).alignment = Alignment(horizontal="right")
            # 小計用紅色粗體
            ws.cell(row=total_row, column=8).font = red_f

            # 頁尾簽核區
            sign_row = total_row + 3
            sign_font = Font(name="Microsoft JhengHei UI", size=10, color="333333")
            for ci, label in [(1, "承辦人："), (4, "主管："), (6, "核准：")]:
                ws.cell(row=sign_row, column=ci, value=label).font = sign_font
                # 底線
                for offset in range(1, 3 if ci == 1 else 2):
                    uc = ws.cell(row=sign_row, column=ci + offset)
                    uc.border = Border(bottom=Side(style="thin", color="999999"))

            # ── 材料明細附表 ──
            pending_rids = set(v[0] for v in pending)
            store = _load_store()
            mat_rows = [m for m in store.get("materials", [])
                        if m.get("報告編號", "") in pending_rids]

            if mat_rows:
                ws_mat = wb.create_sheet("材料明細")
                ws_mat.sheet_properties.tabColor = "BF8F00"
                mat_hds = ["報告編號", "零件類型", "尺寸", "SCH", "材質",
                           "數量", "單位", "單價", "金額"]
                for i, h in enumerate(mat_hds, 1):
                    ws_mat.cell(row=2, column=i, value=h)
                for ri, m in enumerate(mat_rows, 3):
                    ws_mat.cell(row=ri, column=1, value=m.get("報告編號", ""))
                    ws_mat.cell(row=ri, column=2, value=m.get("零件類型", ""))
                    ws_mat.cell(row=ri, column=3, value=m.get("尺寸", ""))
                    ws_mat.cell(row=ri, column=4, value=m.get("SCH", ""))
                    ws_mat.cell(row=ri, column=5, value=m.get("材質", ""))
                    try:
                        ws_mat.cell(row=ri, column=6, value=float(m.get("數量", 0) or 0))
                    except (ValueError, TypeError):
                        ws_mat.cell(row=ri, column=6, value=m.get("數量", ""))
                    ws_mat.cell(row=ri, column=7, value=m.get("單位", ""))
                    try:
                        ws_mat.cell(row=ri, column=8, value=float(m.get("單價", 0) or 0) if m.get("單價") else "")
                    except (ValueError, TypeError):
                        ws_mat.cell(row=ri, column=8, value=m.get("單價", ""))
                    try:
                        ws_mat.cell(row=ri, column=9, value=float(m.get("金額", 0) or 0) if m.get("金額") else "")
                    except (ValueError, TypeError):
                        ws_mat.cell(row=ri, column=9, value=m.get("金額", ""))

                m_end = max(3, 2 + len(mat_rows))
                _apply_excel_styles(
                    ws_mat, header_row=2, data_start=3, data_end=m_end,
                    col_count=9,
                    col_widths=[14, 20, 8, 10, 10, 8, 6, 12, 14],
                    title=f"請款材料明細 — 共 {len(mat_rows)} 筆",
                    number_cols=[6],
                    money_cols=[8, 9],
                )

                # 材料合計
                m_total_row = m_end + 1
                ws_mat.cell(row=m_total_row, column=1, value="合計")
                for ci in range(1, 10):
                    c = ws_mat.cell(row=m_total_row, column=ci)
                    c.fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
                    c.font = bold_f
                    c.border = bdr
                amt_letter = get_column_letter(9)
                ws_mat.cell(row=m_total_row, column=9,
                            value=f"=SUM({amt_letter}3:{amt_letter}{m_end})")
                ws_mat.cell(row=m_total_row, column=9).number_format = '#,##0'
                ws_mat.cell(row=m_total_row, column=9).alignment = Alignment(horizontal="right")

            atomic_save_wb(wb, fp)
            QMessageBox.information(self, "成功", f"請款單已匯出：{fp}\n\n共 {len(pending)} 筆，合計 ${total_amt:,.0f}")
            os.startfile(fp)
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"匯出失敗：{e}")
