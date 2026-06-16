# -*- coding: utf-8 -*-
"""
theme.py — 全域主題與樣式表

提供統一的 QSS 樣式、調色盤常數、元件工廠方法，
讓整個應用程式擁有一致的現代化視覺風格。
"""

from PyQt6.QtWidgets import (
    QApplication, QPushButton, QLabel, QFrame, QWidget, QGroupBox,
    QHBoxLayout, QVBoxLayout, QSizePolicy, QGraphicsDropShadowEffect,
)
from PyQt6.QtGui import QFont, QColor, QIcon, QPalette
from PyQt6.QtCore import Qt


# =====================================================================
#  色彩系統
# =====================================================================
class Colors:
    """語意化調色盤"""
    # 主色
    PRIMARY        = "#2563eb"     # 藍
    PRIMARY_LIGHT  = "#3b82f6"
    PRIMARY_DARK   = "#1d4ed8"
    PRIMARY_BG     = "#eff6ff"

    # 成功 / 危險 / 警告 / 資訊
    SUCCESS        = "#16a34a"
    SUCCESS_BG     = "#f0fdf4"
    DANGER         = "#dc2626"
    DANGER_BG      = "#fef2f2"
    WARNING        = "#d97706"
    WARNING_BG     = "#fffbeb"
    INFO           = "#0891b2"
    INFO_BG        = "#ecfeff"

    # 中性
    TEXT           = "#1e293b"     # slate-800
    TEXT_SECONDARY = "#64748b"     # slate-500
    TEXT_MUTED     = "#94a3b8"     # slate-400
    BORDER         = "#cbd5e1"     # slate-300
    BORDER_LIGHT   = "#e2e8f0"     # slate-200
    BG             = "#f8fafc"     # slate-50
    BG_WHITE       = "#ffffff"
    BG_CARD        = "#ffffff"
    BG_HOVER       = "#f1f5f9"     # slate-100
    BG_SIDEBAR     = "#f1f5f9"

    # 強調
    ACCENT         = "#7c3aed"     # violet-600
    ACCENT_BG      = "#f5f3ff"


# =====================================================================
#  字型系統
# =====================================================================
class Fonts:
    """語意化字型工廠"""
    _BASE = "Microsoft JhengHei UI"
    _MONO = "Consolas"

    @staticmethod
    def heading(size: int = 16) -> QFont:
        f = QFont(Fonts._BASE, size)
        f.setBold(True)
        return f

    @staticmethod
    def subheading(size: int = 12) -> QFont:
        f = QFont(Fonts._BASE, size)
        f.setBold(True)
        return f

    @staticmethod
    def body(size: int = 10) -> QFont:
        return QFont(Fonts._BASE, size)

    @staticmethod
    def small(size: int = 9) -> QFont:
        return QFont(Fonts._BASE, size)

    @staticmethod
    def code(size: int = 10) -> QFont:
        return QFont(Fonts._MONO, size)

    @staticmethod
    def caption() -> QFont:
        f = QFont(Fonts._BASE, 8)
        f.setItalic(True)
        return f


# =====================================================================
#  全域 QSS 樣式表
# =====================================================================
def build_stylesheet() -> str:
    """組建完整的 QSS 字串"""
    C = Colors
    return f"""
/* ── 全域 ─────────────────────────────────────────── */
QMainWindow, QDialog {{
    background-color: {C.BG};
    font-family: "Microsoft JhengHei UI", "Segoe UI";
    font-size: 10pt;
    color: {C.TEXT};
}}

QWidget {{
    font-family: "Microsoft JhengHei UI", "Segoe UI";
    color: {C.TEXT};
}}

QLabel {{
    color: {C.TEXT};
    background: transparent;
    border: none;
}}

/* ── QMenu（右鍵選單） ────────────────────────────── */
QMenu {{
    background: {C.BG_WHITE};
    border: 1px solid {C.BORDER};
    border-radius: 6px;
    padding: 4px 0;
    color: {C.TEXT};
    font-size: 10pt;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    color: {C.TEXT};
    background: transparent;
}}
QMenu::item:selected {{
    background: {C.PRIMARY_BG};
    color: {C.PRIMARY};
}}
QMenu::item:disabled {{
    color: {C.TEXT_MUTED};
}}
QMenu::separator {{
    height: 1px;
    background: {C.BORDER_LIGHT};
    margin: 4px 8px;
}}

/* ── QTabWidget ───────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {C.BORDER};
    border-radius: 6px;
    background: {C.BG_WHITE};
    padding: 8px;
    margin-top: -1px;
}}
QTabBar::tab {{
    background: {C.BG};
    border: 1px solid {C.BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 18px;
    margin-right: 3px;
    font-size: 10pt;
    color: {C.TEXT_SECONDARY};
    min-width: 100px;
}}
QTabBar::tab:selected {{
    background: {C.BG_WHITE};
    color: {C.PRIMARY};
    font-weight: bold;
    border-bottom: 2px solid {C.PRIMARY};
}}
QTabBar::tab:hover:!selected {{
    background: {C.BG_HOVER};
    color: {C.TEXT};
}}

/* ── QGroupBox ────────────────────────────────────── */
QGroupBox {{
    background: {C.BG_WHITE};
    border: 1px solid {C.BORDER_LIGHT};
    border-radius: 8px;
    margin-top: 12px;
    padding: 14px 10px 8px 10px;
    font-weight: bold;
    font-size: 10pt;
    color: {C.TEXT};
}}
QGroupBox QLabel {{
    color: {C.TEXT};
    background: transparent;
    border: none;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 2px 6px;
    color: {C.PRIMARY};
    background: {C.BG_WHITE};
    border-radius: 4px;
}}

/* ── QPushButton ──────────────────────────────────── */
QPushButton {{
    background: {C.BG_WHITE};
    border: 1px solid {C.BORDER};
    border-radius: 6px;
    padding: 6px 16px;
    color: {C.TEXT};
    font-size: 10pt;
    min-height: 18px;
}}
QPushButton:hover {{
    background: {C.BG_HOVER};
    border-color: {C.PRIMARY_LIGHT};
    color: {C.PRIMARY};
}}
QPushButton:pressed {{
    background: {C.PRIMARY_BG};
    border-color: {C.PRIMARY};
}}
QPushButton:disabled {{
    background: {C.BG};
    color: {C.TEXT_MUTED};
    border-color: {C.BORDER_LIGHT};
}}

/* ── 按鈕角色 ─────────────────────────────────────── */
QPushButton[role="primary"] {{
    background: {C.PRIMARY};
    color: white;
    border: none;
    font-weight: bold;
}}
QPushButton[role="primary"]:hover {{
    background: {C.PRIMARY_LIGHT};
    color: white;
}}
QPushButton[role="primary"]:pressed {{
    background: {C.PRIMARY_DARK};
}}

QPushButton[role="success"] {{
    background: {C.SUCCESS};
    color: white;
    border: none;
    font-weight: bold;
}}
QPushButton[role="success"]:hover {{
    background: #15803d;
    color: white;
}}

QPushButton[role="danger"] {{
    background: {C.DANGER};
    color: white;
    border: none;
}}
QPushButton[role="danger"]:hover {{
    background: #b91c1c;
    color: white;
}}

QPushButton[role="flat"] {{
    background: transparent;
    border: none;
    color: {C.PRIMARY};
    padding: 4px 8px;
}}
QPushButton[role="flat"]:hover {{
    background: {C.PRIMARY_BG};
    border-radius: 4px;
}}

/* ── QLineEdit / QComboBox / QSpinBox ─────────────── */
QLineEdit, QComboBox, QSpinBox {{
    border: 1px solid {C.BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    background: {C.BG_WHITE};
    color: {C.TEXT};
    font-size: 10pt;
    min-height: 18px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 2px solid {C.PRIMARY};
    padding: 4px 9px;
}}
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid {C.BORDER_LIGHT};
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}}
QComboBox::down-arrow {{
    image: none;
    border: none;
    width: 0; height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {C.TEXT_SECONDARY};
    margin-right: 6px;
}}

/* ── QTextEdit ────────────────────────────────────── */
QTextEdit {{
    border: 1px solid {C.BORDER};
    border-radius: 6px;
    padding: 8px;
    background: {C.BG_WHITE};
    font-family: "Consolas", "Microsoft JhengHei UI";
    font-size: 10pt;
    color: {C.TEXT};
    selection-background-color: {C.PRIMARY_BG};
}}
QTextEdit:focus {{
    border: 2px solid {C.PRIMARY};
}}

/* ── QTreeWidget / QListWidget ────────────────────── */
QTreeWidget, QListWidget {{
    border: 1px solid {C.BORDER};
    border-radius: 6px;
    background: {C.BG_WHITE};
    alternate-background-color: {C.BG};
    color: {C.TEXT};
    outline: none;
    font-size: 10pt;
}}
QTreeWidget::item, QListWidget::item {{
    padding: 4px 6px;
    color: {C.TEXT};
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {C.PRIMARY_BG};
    color: {C.PRIMARY_DARK};
}}
QTreeWidget::item:hover, QListWidget::item:hover {{
    background: {C.BG_HOVER};
}}
QHeaderView::section {{
    background: {C.BG};
    border: none;
    border-bottom: 2px solid {C.BORDER};
    border-right: 1px solid {C.BORDER_LIGHT};
    padding: 6px 8px;
    font-weight: bold;
    font-size: 9pt;
    color: {C.TEXT_SECONDARY};
}}

/* ── QProgressBar ─────────────────────────────────── */
QProgressBar {{
    border: none;
    border-radius: 4px;
    background: {C.BORDER_LIGHT};
    text-align: center;
    font-size: 9pt;
    color: {C.TEXT_SECONDARY};
    min-height: 8px;
    max-height: 8px;
}}
QProgressBar::chunk {{
    border-radius: 4px;
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {C.PRIMARY}, stop:1 {C.PRIMARY_LIGHT}
    );
}}

/* ── QCheckBox / QRadioButton ─────────────────────── */
QCheckBox, QRadioButton {{
    spacing: 8px;
    font-size: 10pt;
    color: {C.TEXT};
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 18px; height: 18px;
    border: 2px solid {C.BORDER};
    background: {C.BG_WHITE};
}}
QCheckBox::indicator {{
    border-radius: 4px;
}}
QRadioButton::indicator {{
    border-radius: 10px;
}}
QCheckBox::indicator:checked {{
    background: {C.PRIMARY};
    border-color: {C.PRIMARY};
    image: none;
}}
QRadioButton::indicator:checked {{
    background: {C.PRIMARY};
    border-color: {C.PRIMARY};
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {C.PRIMARY_LIGHT};
}}

/* ── QScrollArea ──────────────────────────────────── */
QScrollArea {{
    border: 1px solid {C.BORDER_LIGHT};
    border-radius: 6px;
    background: {C.BG_WHITE};
}}

/* ── QScrollBar ───────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {C.BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {C.TEXT_MUTED};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {C.BORDER};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {C.TEXT_MUTED};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── QSplitter ────────────────────────────────────── */
QSplitter::handle {{
    background: {C.BORDER_LIGHT};
    margin: 2px;
}}
QSplitter::handle:horizontal {{
    width: 5px;
}}
QSplitter::handle:vertical {{
    height: 5px;
}}

/* ── QFrame 分隔線 ────────────────────────────────── */
QFrame[frameShape="4"] {{
    color: {C.BORDER_LIGHT};
    max-height: 1px;
}}

/* ── 狀態列標籤 ───────────────────────────────────── */
QLabel#statusBar {{
    background: {C.BG_WHITE};
    border: 1px solid {C.BORDER_LIGHT};
    border-radius: 4px;
    padding: 5px 12px;
    color: {C.TEXT_SECONDARY};
    font-size: 9pt;
}}

/* ── 工具提示 ─────────────────────────────────────── */
QToolTip {{
    background: {C.TEXT};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 9pt;
}}
"""


# =====================================================================
#  元件工廠
# =====================================================================
def make_card(title: str = "", parent: QWidget = None) -> QGroupBox:
    """帶標題的卡片元件"""
    card = QGroupBox(title, parent)
    return card


def make_section_label(text: str, parent: QWidget = None) -> QLabel:
    """段落標題"""
    lbl = QLabel(text, parent)
    lbl.setFont(Fonts.subheading())
    lbl.setStyleSheet(f"color: {Colors.PRIMARY}; padding: 4px 0; border: none; background: transparent;")
    return lbl


def make_hint_label(text: str, parent: QWidget = None) -> QLabel:
    """淡灰提示文字"""
    lbl = QLabel(text, parent)
    lbl.setFont(Fonts.small())
    lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; border: none; background: transparent;")
    return lbl


def make_badge(text: str, color: str = Colors.PRIMARY,
               bg: str = Colors.PRIMARY_BG, parent: QWidget = None) -> QLabel:
    """圓角徽章"""
    lbl = QLabel(f"  {text}  ", parent)
    lbl.setStyleSheet(
        f"color: {color}; background: {bg}; border-radius: 10px;"
        f" padding: 2px 10px; font-size: 9pt; font-weight: bold; border: none;"
    )
    lbl.setFixedHeight(22)
    return lbl


def make_stat_card(label: str, value: str, color: str = Colors.PRIMARY,
                   parent: QWidget = None) -> QFrame:
    """數值統計小卡"""
    card = QFrame(parent)
    card.setStyleSheet(
        f"QFrame {{ background: {Colors.BG_WHITE}; border: 1px solid {Colors.BORDER_LIGHT};"
        f" border-radius: 8px; padding: 8px; }}"
    )
    lay = QVBoxLayout(card)
    lay.setContentsMargins(12, 8, 12, 8)
    lay.setSpacing(2)

    v_lbl = QLabel(value)
    v_lbl.setFont(Fonts.heading(18))
    v_lbl.setStyleSheet(f"color: {color}; border: none; background: transparent;")
    v_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(v_lbl)

    t_lbl = QLabel(label)
    t_lbl.setFont(Fonts.small())
    t_lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED}; border: none; background: transparent;")
    t_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(t_lbl)
    return card


def make_separator() -> QFrame:
    """水平分隔線"""
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setFrameShadow(QFrame.Shadow.Plain)
    sep.setStyleSheet(f"color: {Colors.BORDER_LIGHT};")
    sep.setFixedHeight(1)
    return sep


def make_toolbar_row() -> QHBoxLayout:
    """工具列 layout（帶預設間距）"""
    row = QHBoxLayout()
    row.setSpacing(6)
    return row


def set_button_role(btn: QPushButton, role: str):
    """設定按鈕的角色樣式（primary / success / danger / flat）"""
    btn.setProperty("role", role)
    btn.style().unpolish(btn)
    btn.style().polish(btn)


def apply_theme(app: QApplication):
    """將主題套用到整個應用程式"""
    app.setStyleSheet(build_stylesheet())
    app.setFont(Fonts.body())
