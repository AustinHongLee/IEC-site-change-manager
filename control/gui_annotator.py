# -*- coding: utf-8 -*-
"""
gui_annotator.py — 圖片/PDF 標註對話框 (PyQt6)

提供畫筆、箭頭、矩形、圓形、文字五種標註工具，
可直接覆蓋存檔或另存新檔。
"""

import math
import os
from enum import Enum, auto

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import (
    QColor, QFont, QImage, QKeySequence, QPainter, QPainterPath,
    QPen, QPixmap, QPolygonF, QShortcut,
)
from PyQt6.QtWidgets import (
    QButtonGroup, QColorDialog, QDialog, QFileDialog, QFrame,
    QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton,
    QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from theme import Colors

# PDF 渲染
try:
    import fitz as _fitz
    _FITZ_OK = True
except ImportError:
    _fitz = None
    _FITZ_OK = False


# ──────────────── 工具列舉 ────────────────

class _Tool(Enum):
    PEN = auto()
    ARROW = auto()
    RECT = auto()
    ELLIPSE = auto()
    TEXT = auto()
    CLOUD = auto()       # 雲形線（修訂雲框）
    DBLARROW = auto()    # 雙箭頭（尺寸線）
    CROSS = auto()       # 十字定位標記


# ──────────────── 標註筆劃 ────────────────

class _Stroke:
    """一筆標註（座標與寬度皆為原圖像素空間）"""
    __slots__ = ("tool", "color", "width", "points", "text", "font_size")

    def __init__(self, tool: _Tool, color: QColor, width: float):
        self.tool = tool
        self.color = QColor(color)
        self.width = width
        self.points: list[QPointF] = []
        self.text: str = ""
        self.font_size: float = 16.0


# ──────────────── helper ────────────────

def _make_vsep() -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.VLine)
    sep.setStyleSheet(f"color: {Colors.BORDER};")
    sep.setFixedWidth(2)
    return sep


# ──────────────── 標註畫布 ────────────────

class _AnnotationCanvas(QWidget):
    """可繪製標註的畫布。

    座標系統：所有 _Stroke 的座標、線寬、字體大小都以原圖像素為單位。
    顯示時透過 QPainter.translate + scale 縮放；存檔時直接以原圖解析度渲染。
    """

    def __init__(self, base_pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._base = base_pixmap
        self._scaled_base: QPixmap | None = None
        self._strokes: list[_Stroke] = []
        self._current: _Stroke | None = None

        self._tool = _Tool.PEN
        self._color = QColor(Colors.DANGER)
        self._pen_width = 3                    # 螢幕像素
        self._scale = 1.0
        self._offset = QPointF(0, 0)

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._update_transform()

    # ── properties ──

    @property
    def tool(self) -> _Tool:
        return self._tool

    @tool.setter
    def tool(self, t: _Tool):
        self._tool = t
        self.setCursor(
            Qt.CursorShape.IBeamCursor if t == _Tool.TEXT
            else Qt.CursorShape.CrossCursor
        )

    @property
    def color(self) -> QColor:
        return self._color

    @color.setter
    def color(self, c: QColor):
        self._color = QColor(c)

    @property
    def pen_width(self) -> int:
        return self._pen_width

    @pen_width.setter
    def pen_width(self, w: int):
        self._pen_width = max(1, min(w, 20))

    def undo(self):
        if self._strokes:
            self._strokes.pop()
            self.update()

    def clear_all(self):
        self._strokes.clear()
        self.update()

    def has_annotations(self) -> bool:
        return bool(self._strokes)

    # ── 座標轉換 ──

    def _update_transform(self):
        """根據 widget 尺寸計算顯示縮放與偏移"""
        if self._base.isNull():
            return
        cw, ch = self.width(), self.height()
        iw, ih = self._base.width(), self._base.height()
        if iw == 0 or ih == 0:
            return
        self._scale = min(cw / iw, ch / ih, 1.0)
        sw, sh = iw * self._scale, ih * self._scale
        self._offset = QPointF((cw - sw) / 2, (ch - sh) / 2)
        si_w, si_h = int(sw), int(sh)
        if si_w > 0 and si_h > 0:
            self._scaled_base = self._base.scaled(
                si_w, si_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

    def _to_image(self, pos) -> QPointF:
        """widget 座標 → 原圖座標"""
        s = self._scale or 1.0
        return QPointF(
            (pos.x() - self._offset.x()) / s,
            (pos.y() - self._offset.y()) / s,
        )

    # ── events ──

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._update_transform()

    def mousePressEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        ipt = self._to_image(ev.position())
        s = self._scale or 1.0
        img_w = self._pen_width / s

        if self._tool == _Tool.TEXT:
            # 檢查是否有來自常用字的預填文字
            dlg = self.parent()
            pre = ""
            if hasattr(dlg, '_pending_quick_text') and dlg._pending_quick_text:
                pre = dlg._pending_quick_text
                dlg._pending_quick_text = ""
            text, ok = QInputDialog.getText(self, "輸入文字", "標註文字：",
                                            text=pre)
            if ok and text.strip():
                st = _Stroke(_Tool.TEXT, self._color, img_w)
                st.points = [ipt]
                st.text = text.strip()
                st.font_size = max(16, self._pen_width * 4) / s
                self._strokes.append(st)
                self.update()
            return

        if self._tool == _Tool.CROSS:
            st = _Stroke(_Tool.CROSS, self._color, img_w)
            st.points = [ipt]
            self._strokes.append(st)
            self.update()
            return

        self._current = _Stroke(self._tool, self._color, img_w)
        self._current.points = [ipt]

    def mouseMoveEvent(self, ev):
        if self._current is None:
            return
        ipt = self._to_image(ev.position())
        if self._current.tool in (_Tool.PEN, _Tool.CLOUD):
            self._current.points.append(ipt)
        else:
            if len(self._current.points) < 2:
                self._current.points.append(ipt)
            else:
                self._current.points[1] = ipt
        self.update()

    def mouseReleaseEvent(self, ev):
        if ev.button() != Qt.MouseButton.LeftButton or self._current is None:
            return
        ipt = self._to_image(ev.position())
        if self._current.tool in (_Tool.PEN, _Tool.CLOUD):
            self._current.points.append(ipt)
        else:
            if len(self._current.points) < 2:
                self._current.points.append(ipt)
            else:
                self._current.points[1] = ipt
        if len(self._current.points) >= 2:
            self._strokes.append(self._current)
        self._current = None
        self.update()

    # ── 繪製 ──

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#f0f0f0"))
        if self._base.isNull():
            return
        if self._scaled_base and not self._scaled_base.isNull():
            p.drawPixmap(int(self._offset.x()), int(self._offset.y()), self._scaled_base)
        # 標註層：以原圖座標繪製，透過 translate+scale 對齊
        p.save()
        p.translate(self._offset)
        p.scale(self._scale, self._scale)
        for stroke in self._strokes:
            self._paint_stroke(p, stroke)
        if self._current:
            self._paint_stroke(p, self._current)
        p.restore()

    @staticmethod
    def _paint_stroke(p: QPainter, s: _Stroke):
        pen = QPen(s.color, s.width, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)

        if s.tool == _Tool.PEN:
            if len(s.points) < 2:
                return
            path = QPainterPath(s.points[0])
            for pt in s.points[1:]:
                path.lineTo(pt)
            p.drawPath(path)

        elif s.tool == _Tool.ARROW:
            if len(s.points) < 2:
                return
            a, b = s.points[0], s.points[1]
            p.drawLine(a, b)
            _AnnotationCanvas._draw_arrowhead(p, a, b, s.width * 3, s.color)

        elif s.tool == _Tool.RECT:
            if len(s.points) < 2:
                return
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(s.points[0], s.points[1]).normalized())

        elif s.tool == _Tool.ELLIPSE:
            if len(s.points) < 2:
                return
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(s.points[0], s.points[1]).normalized())

        elif s.tool == _Tool.TEXT:
            if not s.points or not s.text:
                return
            font = QFont("Microsoft JhengHei", int(s.font_size))
            p.setFont(font)
            pt = s.points[0]
            fm = p.fontMetrics()
            text_w = fm.horizontalAdvance(s.text)
            text_h = fm.height()
            bg = QRectF(
                pt.x() - 2, pt.y() - fm.ascent() - 2,
                text_w + 4, text_h + 4,
            )
            p.fillRect(bg, QColor(255, 255, 255, 200))
            p.drawText(pt, s.text)

        elif s.tool == _Tool.CLOUD:
            if len(s.points) < 3:
                return
            p.setBrush(Qt.BrushStyle.NoBrush)
            _AnnotationCanvas._draw_cloud_path(p, s.points, s.width * 3, s.color, s.width)

        elif s.tool == _Tool.DBLARROW:
            if len(s.points) < 2:
                return
            a, b = s.points[0], s.points[1]
            p.drawLine(a, b)
            head = s.width * 3
            _AnnotationCanvas._draw_arrowhead(p, a, b, head, s.color)
            _AnnotationCanvas._draw_arrowhead(p, b, a, head, s.color)

        elif s.tool == _Tool.CROSS:
            if not s.points:
                return
            pt = s.points[0]
            arm = max(s.width * 6, 12)
            p.drawLine(QPointF(pt.x() - arm, pt.y()), QPointF(pt.x() + arm, pt.y()))
            p.drawLine(QPointF(pt.x(), pt.y() - arm), QPointF(pt.x(), pt.y() + arm))
            r = arm * 0.7
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(pt, r, r)

    @staticmethod
    def _draw_arrowhead(p: QPainter, start: QPointF, end: QPointF,
                        size: float, color: QColor):
        dx, dy = end.x() - start.x(), end.y() - start.y()
        length = math.hypot(dx, dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        base = QPointF(end.x() - ux * size, end.y() - uy * size)
        left = QPointF(base.x() + px * size * 0.5, base.y() + py * size * 0.5)
        right = QPointF(base.x() - px * size * 0.5, base.y() - py * size * 0.5)
        old_brush = p.brush()
        p.setBrush(color)
        p.drawPolygon(QPolygonF([end, left, right]))
        p.setBrush(old_brush)

    @staticmethod
    def _draw_cloud_path(p: QPainter, points: list,
                         arc_size: float, color: QColor, pen_w: float):
        """沿自由手繪路徑繪製雲形線"""
        arc_r = max(arc_size, 6)
        pen = QPen(color, pen_w, Qt.PenStyle.SolidLine,
                   Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # 沿路徑等距取樣
        seg = arc_r * 1.4
        sampled: list[QPointF] = [points[0]]
        accum = 0.0
        for i in range(1, len(points)):
            dx = points[i].x() - points[i - 1].x()
            dy = points[i].y() - points[i - 1].y()
            accum += math.hypot(dx, dy)
            if accum >= seg:
                sampled.append(points[i])
                accum = 0.0
        if len(sampled) < 2:
            return

        # 計算路徑的大致「內側」中心
        cx = sum(pt.x() for pt in sampled) / len(sampled)
        cy = sum(pt.y() for pt in sampled) / len(sampled)

        # 用二次貝塞爾弧連接取樣點，每段向外凸
        path = QPainterPath()
        path.moveTo(sampled[0])
        for i in range(len(sampled) - 1):
            curr = sampled[i]
            nxt = sampled[i + 1]
            mid = QPointF((curr.x() + nxt.x()) / 2, (curr.y() + nxt.y()) / 2)
            dx, dy = nxt.x() - curr.x(), nxt.y() - curr.y()
            seg_len = math.hypot(dx, dy)
            if seg_len < 0.5:
                continue
            # 法線
            nx, ny = -dy / seg_len, dx / seg_len
            # 向外凸：遠離路徑重心方向
            outx, outy = mid.x() - cx, mid.y() - cy
            if nx * outx + ny * outy < 0:
                nx, ny = -nx, -ny
            bulge = arc_r * 0.5
            ctrl = QPointF(mid.x() + nx * bulge, mid.y() + ny * bulge)
            path.quadTo(ctrl, nxt)

        p.drawPath(path)

    # ── 匯出 ──

    def render_final(self) -> QPixmap:
        """以原圖解析度渲染最終結果（底圖 + 標註）"""
        result = QPixmap(self._base.size())
        result.fill(Qt.GlobalColor.transparent)
        p = QPainter(result)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.drawPixmap(0, 0, self._base)
        for s in self._strokes:
            self._paint_stroke(p, s)
        p.end()
        return result


# ──────────────── 顏色預設 ────────────────

_COLOR_PRESETS = [
    ("#dc2626", "紅"),
    ("#2563eb", "藍"),
    ("#16a34a", "綠"),
    ("#d97706", "橙"),
    ("#1e293b", "黑"),
]


# ──────────────── 標註對話框 ────────────────

class AnnotationDialog(QDialog):
    """圖片/PDF 標註對話框（模態）"""

    def __init__(self, image_path: str, is_pdf: bool = False, parent=None):
        super().__init__(parent)
        self._image_path = image_path
        self._is_pdf = is_pdf
        self._saved = False
        self._saved_path: str = ""   # 存檔後的實際路徑
        self._load_ok = False
        self._pending_quick_text: str = ""

        self.setWindowTitle(f"標註 — {os.path.basename(image_path)}")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint
        )
        self.setMinimumSize(900, 650)
        self.resize(1100, 750)

        pm = self._load_pdf(image_path) if is_pdf else QPixmap(image_path)
        if pm is None or pm.isNull():
            return
        self._load_ok = True
        self._setup_ui(pm)

    @property
    def was_saved(self) -> bool:
        return self._saved

    @property
    def saved_path(self) -> str:
        """存檔後的實際路徑（PDF → _annotated.png、圖片 → 原路徑、另存 → 指定路徑）"""
        return self._saved_path

    # ── 載入 ──

    @staticmethod
    def _load_pdf(path: str) -> QPixmap | None:
        if not _FITZ_OK or not os.path.exists(path):
            return None
        try:
            doc = _fitz.open(path)
            page = doc[0]
            mat = _fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = QImage(pix.samples, pix.width, pix.height,
                         pix.stride, QImage.Format.Format_RGB888)
            pm = QPixmap.fromImage(img)
            doc.close()
            return pm
        except Exception:
            return None

    # ── UI 建構 ──

    def _setup_ui(self, pm: QPixmap):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        # canvas（先建立，toolbar 的信號需要它）
        self._canvas = _AnnotationCanvas(pm, self)

        # ── toolbar ──
        tb = QHBoxLayout()
        tb.setSpacing(4)

        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        tool_defs = [
            (_Tool.PEN,      "🖊️ 畫筆"),
            (_Tool.ARROW,    "➡️ 箭頭"),
            (_Tool.DBLARROW, "↔️ 尺寸線"),
            (_Tool.RECT,     "⬜ 矩形"),
            (_Tool.ELLIPSE,  "⭕ 圓形"),
            (_Tool.CLOUD,    "☁️ 雲形線"),
            (_Tool.TEXT,     "📝 文字"),
            (_Tool.CROSS,    "✛ 定位"),
        ]
        tool_qss = self._tool_btn_qss()
        for tool, label in tool_defs:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setFont(QFont("Segoe UI", 9))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(tool_qss)
            self._btn_group.addButton(btn)
            btn.clicked.connect(lambda _, t=tool: self._set_tool(t))
            tb.addWidget(btn)

        self._btn_group.buttons()[0].setChecked(True)

        tb.addWidget(_make_vsep())

        # 顏色快選
        self._color_btns: list[QPushButton] = []
        for hex_c, tip in _COLOR_PRESETS:
            cb = QPushButton()
            cb.setFixedSize(26, 26)
            cb.setToolTip(tip)
            cb.setCursor(Qt.CursorShape.PointingHandCursor)
            cb.clicked.connect(lambda _, h=hex_c: self._quick_color(h))
            tb.addWidget(cb)
            self._color_btns.append(cb)

        self._highlight_active_color(_COLOR_PRESETS[0][0])

        btn_custom = QPushButton("🎨")
        btn_custom.setFixedSize(26, 26)
        btn_custom.setToolTip("自訂顏色")
        btn_custom.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_custom.clicked.connect(self._pick_color)
        tb.addWidget(btn_custom)

        tb.addWidget(_make_vsep())

        # 粗細
        tb.addWidget(QLabel("粗細:"))
        self._width_spin = QSpinBox()
        self._width_spin.setRange(1, 20)
        self._width_spin.setValue(3)
        self._width_spin.setFixedWidth(55)
        self._width_spin.valueChanged.connect(
            lambda v: setattr(self._canvas, "pen_width", v)
        )
        tb.addWidget(self._width_spin)

        tb.addWidget(_make_vsep())

        btn_undo = QPushButton("↩️ 復原")
        btn_undo.setFixedHeight(32)
        btn_undo.setFont(QFont("Segoe UI", 9))
        btn_undo.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_undo.clicked.connect(self._canvas.undo)
        tb.addWidget(btn_undo)

        btn_clear = QPushButton("🗑️ 清除")
        btn_clear.setFixedHeight(32)
        btn_clear.setFont(QFont("Segoe UI", 9))
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.clicked.connect(self._clear_all)
        tb.addWidget(btn_clear)

        tb.addStretch()
        lay.addLayout(tb)

        # ── 常用字快選列 ──
        qt_row = QHBoxLayout()
        qt_row.setSpacing(3)
        qt_lbl = QLabel("常用字：")
        qt_lbl.setFont(QFont("Segoe UI", 8))
        qt_lbl.setStyleSheet(f"color: {Colors.TEXT_MUTED};")
        qt_row.addWidget(qt_lbl)

        quick_texts = self._load_quick_texts()
        qt_qss = (
            f"QPushButton {{ background: {Colors.BG_WHITE}; border: 1px solid {Colors.BORDER_LIGHT};"
            f" border-radius: 3px; padding: 1px 6px; font-size: 8pt; }}"
            f"QPushButton:hover {{ background: {Colors.PRIMARY_BG};"
            f" border-color: {Colors.PRIMARY}; }}"
        )
        for txt in quick_texts:
            qb = QPushButton(txt)
            qb.setFixedHeight(24)
            qb.setCursor(Qt.CursorShape.PointingHandCursor)
            qb.setStyleSheet(qt_qss)
            qb.clicked.connect(lambda _, t=txt: self._insert_quick_text(t))
            qt_row.addWidget(qb)
        qt_row.addStretch()
        lay.addLayout(qt_row)

        # ── canvas ──
        lay.addWidget(self._canvas, stretch=1)

        # ── 快捷鍵 ──
        QShortcut(QKeySequence.StandardKey.Undo, self, self._canvas.undo)

        # ── 底部按鈕 ──
        bot = QHBoxLayout()
        bot.addStretch()

        btn_save = QPushButton("💾 儲存標註")
        btn_save.setFixedHeight(36)
        btn_save.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet(
            f"QPushButton {{ background: {Colors.PRIMARY}; color: white; "
            f"border-radius: 6px; padding: 0 20px; }}"
            f"QPushButton:hover {{ background: {Colors.PRIMARY_DARK}; }}"
        )
        btn_save.clicked.connect(self._save)
        bot.addWidget(btn_save)

        btn_save_as = QPushButton("📁 另存新檔")
        btn_save_as.setFixedHeight(36)
        btn_save_as.setFont(QFont("Segoe UI", 10))
        btn_save_as.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_as.clicked.connect(self._save_as)
        bot.addWidget(btn_save_as)

        btn_cancel = QPushButton("取消")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setFont(QFont("Segoe UI", 10))
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        bot.addWidget(btn_cancel)

        lay.addLayout(bot)

    # ── toolbar helpers ──

    @staticmethod
    def _tool_btn_qss() -> str:
        return (
            f"QPushButton {{ background: {Colors.BG_WHITE}; border: 1px solid {Colors.BORDER};"
            f" border-radius: 4px; padding: 2px 8px; }}"
            f"QPushButton:checked {{ background: {Colors.PRIMARY_BG};"
            f" border: 2px solid {Colors.PRIMARY}; color: {Colors.PRIMARY_DARK}; font-weight: bold; }}"
            f"QPushButton:hover {{ background: {Colors.BG_HOVER}; }}"
        )

    def _set_tool(self, t: _Tool):
        self._canvas.tool = t

    @staticmethod
    def _load_quick_texts() -> list[str]:
        """從 wizard_data.json 載入 note_presets 作為常用字（與 Step5 同源）"""
        try:
            import json
            from resources import resource_path
            wdata_path = resource_path("control", "wizard_data.json")
            if os.path.exists(wdata_path):
                with open(wdata_path, "r", encoding="utf-8") as f:
                    wdata = json.load(f)
                presets = wdata.get("note_presets", {})
                texts: list[str] = []
                for phrases in presets.values():
                    texts.extend(phrases)
                if texts:
                    return texts
        except Exception:
            pass
        # fallback
        return ["修改", "新增", "刪除", "返工", "裁切", "延長", "OK", "NG"]

    def _insert_quick_text(self, text: str):
        """將常用字設為文字工具，等使用者點擊位置後插入"""
        self._canvas.tool = _Tool.TEXT
        # 選中 TEXT 按鈕
        for btn in self._btn_group.buttons():
            if btn.text().endswith("文字"):
                btn.setChecked(True)
                break
        self._pending_quick_text = text

    def _quick_color(self, hex_color: str):
        self._canvas.color = QColor(hex_color)
        self._highlight_active_color(hex_color)

    def _pick_color(self):
        c = QColorDialog.getColor(self._canvas.color, self, "選擇標註顏色")
        if c.isValid():
            self._canvas.color = c
            self._highlight_active_color(None)

    def _highlight_active_color(self, active_hex: str | None):
        for i, (hex_c, _) in enumerate(_COLOR_PRESETS):
            if hex_c == active_hex:
                self._color_btns[i].setStyleSheet(
                    f"QPushButton {{ background: {hex_c};"
                    f" border: 2px solid {Colors.TEXT}; border-radius: 4px; }}"
                )
            else:
                self._color_btns[i].setStyleSheet(
                    f"QPushButton {{ background: {hex_c};"
                    f" border: 2px solid transparent; border-radius: 4px; }}"
                    f"QPushButton:hover {{ border-color: {Colors.TEXT}; }}"
                )

    def _clear_all(self):
        if not self._canvas.has_annotations():
            return
        r = QMessageBox.question(self, "清除全部", "確定要清除所有標註嗎？")
        if r == QMessageBox.StandardButton.Yes:
            self._canvas.clear_all()

    # ── 存檔 ──

    def _save(self):
        """覆蓋存檔（圖片覆蓋原檔；PDF → 生成 _annotated.png → 轉新 PDF → 替換原檔）"""
        if not self._canvas.has_annotations():
            QMessageBox.information(self, "提示", "尚未新增任何標註")
            return

        pm = self._canvas.render_final()

        if self._is_pdf:
            base = os.path.splitext(self._image_path)[0]
            png_path = base + "_annotated.png"
            pdf_path = base + "_annotated.pdf"
            try:
                # 1) 存 PNG
                if not pm.save(png_path, "PNG"):
                    raise RuntimeError(f"無法儲存 PNG: {png_path}")
                # 2) PNG → 新 PDF
                doc = _fitz.open()
                img = _fitz.open(png_path)
                pdf_bytes = img.convert_to_pdf()
                img.close()
                img_pdf = _fitz.open("pdf", pdf_bytes)
                page = doc.new_page(width=img_pdf[0].rect.width,
                                    height=img_pdf[0].rect.height)
                page.show_pdf_page(page.rect, img_pdf)
                img_pdf.close()
                doc.save(pdf_path)
                doc.close()
                # 3) 刪除原 PDF，重新命名
                os.remove(self._image_path)
                os.replace(pdf_path, self._image_path)
                # 4) 清除暫存 PNG
                if os.path.exists(png_path):
                    os.remove(png_path)
            except Exception as e:
                QMessageBox.warning(self, "儲存失敗", f"無法產生標註 PDF:\n{e}")
                return
            QMessageBox.information(
                self, "儲存成功",
                f"已覆蓋存檔:\n{os.path.basename(self._image_path)}"
            )
            self._saved_path = self._image_path
        else:
            if not pm.save(self._image_path, "JPEG", 95):
                QMessageBox.warning(self, "儲存失敗", f"無法儲存至:\n{self._image_path}")
                return
            QMessageBox.information(
                self, "儲存成功",
                f"已覆蓋存檔:\n{os.path.basename(self._image_path)}"
            )
            self._saved_path = self._image_path
        self._saved = True
        self.accept()

    def _save_as(self):
        """另存新檔"""
        if not self._canvas.has_annotations():
            QMessageBox.information(self, "提示", "尚未新增任何標註")
            return

        default_dir = os.path.dirname(self._image_path)
        base = os.path.splitext(os.path.basename(self._image_path))[0]
        default_name = os.path.join(default_dir, f"{base}_annotated.png")

        out, _ = QFileDialog.getSaveFileName(
            self, "另存標註檔案", default_name,
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;所有檔案 (*)",
        )
        if not out:
            return

        pm = self._canvas.render_final()
        ext = os.path.splitext(out)[1].lower()
        fmt = "JPEG" if ext in (".jpg", ".jpeg") else "PNG"
        quality = 95 if fmt == "JPEG" else -1

        if not pm.save(out, fmt, quality):
            QMessageBox.warning(self, "儲存失敗", f"無法儲存至:\n{out}")
            return

        QMessageBox.information(self, "儲存成功", f"已儲存至:\n{os.path.basename(out)}")
        self._saved_path = out
        self._saved = True
        self.accept()
