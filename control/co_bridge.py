# -*- coding: utf-8 -*-
"""co_bridge.py — 新精靈前後端「橋」（transport-agnostic）

設計重點（給接手者）：
    - 這個類別**不認 UI、也不認傳輸層**：JSON 進、JSON 出，每個對外方法都回
      ``{"ok": bool, "data": ..., "error": str|None}`` 信封。
    - **現在**：pywebview 的 ``js_api`` 直接拿它（見 ``co_wizard_app.py``）；
      JS 端 ``await pywebview.api.build(payload)`` → 直呼這裡，非 HTTP。
    - **未來**：FastAPI 之類把同一批方法包成 HTTP route（``@app.post("/build")`` →
      ``bridge.build(payload)``），**方法簽名一行不用改** → 中央/網頁版無痛接。
    - **不 import pywebview / Qt**，可在無顯示環境單元測試（見 tests/test_co_bridge.py）。

風險防護（這是「強橋」的重點）：
    1. **信封 + 例外護欄**：每個對外方法 try/except 成信封，前端永遠拿到可用結果、
       不會卡死或拿到半截例外。
    2. **無狀態 build**：前端送完整 payload，後端用 builder 重放重算，避免 stale state。
    3. **檔案對話框用注入**（預設 None → 回明確錯）：保持純淨可測；launcher 才注入
       pywebview 的原生對話框。
    4. **邊界正規化 / 防呆**：series 去前導零；op / role / 材料欄位容錯，
       前端送髒資料也不炸。
"""
from __future__ import annotations

import base64
import dataclasses
import functools
import json
import mimetypes
import re
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import unquote, urlparse

from change_order import (
    Material,
    Op,
    Scenario,
    Spec,
)
from change_order_builder import ChangeOrderBuilder
from change_order_store import export_change_order

API_VERSION = "1.0"


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #
def _enveloped(fn: Callable) -> Callable:
    """把回傳/例外都包成 {ok,data,error} 信封——前端永遠拿到可用結果。"""
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            return {"ok": True, "data": fn(self, *args, **kwargs), "error": None}
        except Exception as exc:  # 故意全捕——橋不可以把例外漏給前端變成卡死
            return {
                "ok": False,
                "data": None,
                "error": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc(),
            }
    return wrapper


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _norm_series(series: Any) -> str:
    text = "" if series is None else str(series).strip()
    return text.lstrip("0") or "0"


def _as_op(value: Any) -> Any:
    if isinstance(value, Op):
        return value
    aliases = {
        "重焊": Op.REWORK,
        "原焊口重接": Op.REWORK,
        "拆除不重焊": Op.REWORK,
        "裁切": Op.REWORK,
        "加長": Op.REWORK,
        "縮短": Op.REWORK,
        "新焊": Op.NEW,
        "新增焊口": Op.NEW,
    }
    if value in aliases:
        return aliases[value]
    try:
        return Op(value)
    except Exception:
        return value              # 容錯：未知值原樣保留，不炸


def _op_for_weld_kind(kind: Any, value: Any) -> Any:
    if kind == "existing":
        return Op.REWORK
    if kind == "new":
        return Op.NEW
    return _as_op(value)


_MATERIAL_FIELDS = {f.name for f in dataclasses.fields(Material)}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
_IMAGE_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".bmp": "image/bmp",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
_PDF_EXTS = {".pdf"}
_SERIES_PDF_DELIMITERS = {".", "-", "_", " ", "　"}


# --------------------------------------------------------------------------- #
# 橋
# --------------------------------------------------------------------------- #
class ChangeOrderBridge:
    """新精靈的前後端橋。對外方法皆回信封；內部 _ 開頭的不對外、不包信封。"""

    def __init__(
        self,
        builder: Optional[ChangeOrderBuilder] = None,
        *,
        attachments_root: Any = None,
        records_dir: Any = None,
        pick_file_fn: Optional[Callable[[str], Optional[str]]] = None,
    ):
        self.builder = builder if builder is not None else ChangeOrderBuilder()
        self.attachments_root = (
            Path(attachments_root) if attachments_root else Path.cwd() / "change_order_records"
        )
        self.records_dir = (
            Path(records_dir) if records_dir else Path(__file__).resolve().parent.parent / "records"
        )
        # 由 launcher 注入（pywebview 原生對話框）；純測試環境留 None。
        self._pick_file_fn = pick_file_fn

    # ---- 對外 API（皆回信封） -------------------------------------------- #
    @_enveloped
    def info(self) -> dict:
        return {
            "api_version": API_VERSION,
            "attachments_root": str(self.attachments_root),
            "lookup_ready": bool(getattr(self.builder, "lookup", None)),
        }

    @_enveloped
    def existing_welds(self, series: Any) -> dict:
        """源頭驅動：回該流水號可挑的既有焊口 + 規格（給前端做『挑』而非『打』）。"""
        s = _norm_series(series)
        lookup = getattr(self.builder, "lookup", None)
        source = self._weld_source_status(lookup, s)
        welds = []
        if not source.get("ok"):
            return {"series": s, "welds": welds, "source": source}

        for wid in (lookup.existing_weld_ids(s) if lookup is not None else []):
            spec = lookup.lookup_spec(s, wid)
            welds.append({
                "weld_no": wid,
                "size": getattr(spec, "size", None),
                "sch": getattr(spec, "sch", None),
                "material": getattr(spec, "material", None),
                "weld_type": getattr(spec, "weld_type", None),
            })
        source["series_count"] = len(welds)
        if not welds:
            sheet = source.get("sheet") or "焊口表"
            source["message"] = f"已讀取 {sheet}，但流水號 {s} 沒有可用焊口列"
        return {"series": s, "welds": welds, "source": source}

    @_enveloped
    def history(self, series: Any) -> list[dict]:
        """回這張流水號過去已出單紀錄；壞檔略過，查詢不影響任何狀態。"""
        s = _norm_series(series)
        root = self.attachments_root
        if not root.exists():
            return []

        prefix = f"{s}_"
        items = []
        for folder in root.iterdir():
            if not folder.is_dir() or not folder.name.startswith(prefix):
                continue
            record_path = folder / "change_order.json"
            try:
                data = json.loads(record_path.read_text(encoding="utf-8-sig"))
            except Exception:
                continue
            welds = [
                w.get("code")
                for w in (data.get("welds") or [])
                if isinstance(w, dict) and w.get("code")
            ]
            items.append({
                "id": data.get("id") or folder.name,
                "date": data.get("date") or "",
                "welds": welds,
                "reason": data.get("reason") or "",
                "folder": str(folder),
            })
        items.sort(key=lambda item: (str(item.get("date") or ""), str(item.get("id") or "")), reverse=True)
        return items

    @_enveloped
    def build(self, payload: Any) -> dict:
        """無狀態重放：吃完整 payload → 回算好的 ChangeOrder + 狀態 + 缺漏。"""
        co = self._build_co(payload)
        issues = self.builder.validate(co)
        status = self.builder.compute_status(co)
        return {"co": co.to_dict(), "status": _enum_value(status), "issues": issues}

    @_enveloped
    def export(self, payload: Any, finalize: bool = False) -> dict:
        """出單。finalize=True 時非『完整』就擋；存草稿 finalize=False 一律可。"""
        co = self._build_co(payload)
        issues = self.builder.validate(co)
        status = self.builder.compute_status(co)
        if finalize and issues:
            return {"exported": False, "reason": "not_complete",
                    "status": _enum_value(status), "issues": issues}
        self.builder.finalize_id(co, self._existing_record_ids())
        result = export_change_order(co, self.attachments_root, overwrite=False)
        return {
            "exported": True,
            "id": co.id,
            "folder": str(result.folder),
            "record": str(result.record_path),
            "copied": result.copied,
            "missing": result.missing,
            "status": _enum_value(status),
        }

    @_enveloped
    def pick_file(self, kind: str = "image") -> dict:
        """開原生檔案對話框（由 launcher 注入）；純環境未注入則回明確錯。"""
        if self._pick_file_fn is None:
            raise RuntimeError("檔案對話框未注入（此環境不支援選檔）")
        return {"path": self._pick_file_fn(kind)}

    @_enveloped
    def auto_drawing_pdf(self, series: Any, prefab_dir: str = "") -> dict:
        """依流水號從設定的圖面 PDF 資料夾找對應圖面；只回來源路徑，不搬檔。"""
        raw_series = str(series or "").strip()
        if not raw_series:
            return {"found": False, "reason": "missing_series", "path": "", "source_dir": ""}
        normalized = _norm_series(raw_series)

        root_text = str(prefab_dir or "").strip()
        if not root_text:
            try:
                from settings_manager import get_prefab_drawing_dir

                root_text = str(get_prefab_drawing_dir() or "").strip()
            except Exception:
                root_text = ""
        if not root_text:
            return {"found": False, "reason": "not_configured", "path": "", "source_dir": ""}

        root = Path(root_text)
        if not root.is_dir():
            return {"found": False, "reason": "missing_dir", "path": "", "source_dir": str(root)}

        pdf = _find_series_pdf(root, normalized)
        if pdf is None:
            return {"found": False, "reason": "not_found", "path": "", "source_dir": str(root)}

        return {
            "found": True,
            "path": str(pdf),
            "name": pdf.name,
            "source_dir": str(root),
            "series": normalized,
        }

    @_enveloped
    def list_staging(self) -> list[dict]:
        """列出 staging 收件匣中的圖片檔；只讀、不搬檔、不刪檔。"""
        root = self._staging_root()
        if not root.exists():
            return []
        items = []
        for path in root.iterdir():
            if not path.is_file() or path.suffix.lower() not in _IMAGE_EXTS:
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            items.append({"name": path.name, "path": str(path), "mtime": stat.st_mtime})
        items.sort(key=lambda item: (item["mtime"], item["name"]), reverse=True)
        return [{"name": item["name"], "path": item["path"]} for item in items]

    @_enveloped
    def project_parts(self) -> dict:
        """讀本案配件完整資料；精靈只取用，不直接登記/修改總庫。"""
        registered = self._read_project_part_ids()
        items = [
            _material_part_to_frontend(item)
            for item in self._read_material_items()
            if str(item.get("id") or "") in registered
        ]
        return {
            "registered": sorted(registered),
            "items": items,
            "count": len(items),
        }

    @_enveloped
    def save_annotated(self, data_url: str, base_name: str = "annotated") -> dict:
        """儲存前端 canvas 合成後的 PNG，回傳可放進 state.photos 的本機路徑。"""
        raw = _decode_data_url(data_url, "標註資料")
        out_dir = self.attachments_root.parent / "_annotated"
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(str(base_name or "annotated")).stem).strip("._")
        if not stem:
            stem = "annotated"
        out_path = out_dir / f"{stem}_{uuid.uuid4().hex[:8]}.png"
        out_path.write_bytes(raw)
        return {"name": out_path.name, "path": str(out_path)}

    @_enveloped
    def image_data_url(self, file_path: str) -> dict:
        """把本機圖片讀成 data URL，避免 WebView2 對 file:// 圖片/canvas 的限制。"""
        text = str(file_path or "").strip()
        if not text:
            raise ValueError("缺少照片路徑")
        if text.lower().startswith("data:"):
            return {"name": "", "path": text, "url": text}

        path = self._resolve_image_path(text)
        suffix = path.suffix.lower()
        if suffix not in _IMAGE_EXTS:
            raise ValueError(f"不支援的照片格式：{suffix or path.name}")

        raw = path.read_bytes()
        mime = _IMAGE_MIME.get(suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(raw).decode("ascii")
        return {"name": path.name, "path": str(path), "url": f"data:{mime};base64,{encoded}"}

    @_enveloped
    def pdf_page_data_url(self, file_path: str, page_index: int = 0, zoom: float = 2.0) -> dict:
        """把本機 PDF 指定頁渲染成 PNG data URL，供前端 canvas 標註。"""
        path = self._resolve_pdf_path(str(file_path or ""))
        try:
            import fitz
        except Exception as exc:
            raise RuntimeError("缺少 PyMuPDF(fitz)，無法渲染 PDF") from exc

        doc = fitz.open(path)
        try:
            if doc.page_count < 1:
                raise ValueError("PDF 沒有頁面")
            page_count = doc.page_count
            index = max(0, min(int(page_index or 0), page_count - 1))
            scale = max(0.5, min(float(zoom or 2.0), 4.0))
            page = doc[index]
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            raw = pix.tobytes("png")
        finally:
            doc.close()

        encoded = base64.b64encode(raw).decode("ascii")
        return {
            "name": path.name,
            "path": str(path),
            "page_index": index,
            "page_count": page_count,
            "width": pix.width,
            "height": pix.height,
            "url": f"data:image/png;base64,{encoded}",
        }

    @_enveloped
    def save_pdf_annotation(self, data_url: str, source_pdf: str, page_index: int = 0) -> dict:
        """把前端合成後的 PDF 頁面圖包回 PDF；輸出新檔，不覆蓋原圖面。"""
        raw = _decode_data_url(data_url, "PDF 標註資料")
        source = self._resolve_pdf_path(str(source_pdf or ""))
        try:
            import fitz
        except Exception as exc:
            raise RuntimeError("缺少 PyMuPDF(fitz)，無法儲存 PDF 標註") from exc

        out_dir = self.attachments_root.parent / "_annotated"
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", source.stem).strip("._") or "drawing"
        out_path = out_dir / f"{stem}_{uuid.uuid4().hex[:8]}.pdf"

        src = fitz.open(source)
        out = fitz.open()
        try:
            if src.page_count < 1:
                raise ValueError("PDF 沒有頁面")
            index = max(0, min(int(page_index or 0), src.page_count - 1))
            for i in range(src.page_count):
                src_page = src[i]
                page = out.new_page(width=src_page.rect.width, height=src_page.rect.height)
                if i == index:
                    page.insert_image(page.rect, stream=raw)
                else:
                    page.show_pdf_page(page.rect, src, i)
            out.save(out_path)
        finally:
            out.close()
            src.close()

        return {
            "name": out_path.name,
            "path": str(out_path),
            "source": str(source),
            "page_index": index,
        }

    # ---- 內部（不對外、不包信封） ---------------------------------------- #
    def _build_co(self, payload: Any):
        p = payload or {}
        co = self.builder.start(
            _norm_series(p.get("series")),
            (p.get("date") or "").strip(),
            scenario=Scenario.NORMAL,
        )
        self.builder.set_reason(co, p.get("reason"))

        for w in (p.get("welds") or []):
            kind = (w or {}).get("kind")
            if kind == "existing":
                self.builder.add_existing_weld(co, w.get("base"), _op_for_weld_kind(kind, w.get("op")))
            elif kind == "new":
                self.builder.add_new_weld(co, _op_for_weld_kind(kind, w.get("op")), Spec.from_dict(w.get("spec") or {}))

        for ph in (p.get("photos") or []):
            if ph and ph.get("file"):
                self.builder.add_photo(co, ph.get("role"), ph.get("file"))

        if p.get("drawing_pdf"):
            self.builder.set_drawing_pdf(co, p["drawing_pdf"])

        for m in (p.get("materials") or []):
            clean = {k: v for k, v in (m or {}).items() if k in _MATERIAL_FIELDS}  # 防呆：濾掉未知欄
            if clean:
                self.builder.add_material(co, **clean)

        return co

    def _existing_record_ids(self) -> list:
        root = self.attachments_root
        if not root.exists():
            return []
        return [x.name for x in root.iterdir() if x.is_dir()]

    def _weld_source_status(self, lookup: Any, series: str) -> dict:
        if lookup is None:
            return {
                "ok": False,
                "message": "修改單精靈尚未接上焊口查詢器",
                "sheet": "",
                "count": 0,
                "series_count": 0,
            }

        manager = getattr(lookup, "manager", None)
        if manager is None:
            return {
                "ok": False,
                "message": "修改單精靈沒有焊口表管理器",
                "sheet": "",
                "count": 0,
                "series_count": 0,
            }

        is_configured = getattr(manager, "is_configured", None)
        if callable(is_configured) and not is_configured():
            return {
                "ok": False,
                "message": "焊口表尚未設定，或設定的檔案不存在",
                "sheet": getattr(manager, "sheet_name", "") or "",
                "count": 0,
                "series_count": 0,
            }

        loaded = True
        load = getattr(manager, "load", None)
        if callable(load):
            loaded = bool(load())
        if not loaded:
            return {
                "ok": False,
                "message": "焊口表載入失敗，請到設定檢查路徑、工作表與欄位對應",
                "sheet": getattr(manager, "sheet_name", "") or "",
                "count": 0,
                "series_count": 0,
            }

        cache = getattr(manager, "_cache", {}) or {}
        sheet = getattr(manager, "_sheet_name", "") or getattr(manager, "sheet_name", "") or ""
        serial_index = getattr(manager, "_serial_index", {}) or {}
        raw_series_count = len(serial_index.get(series, []))
        return {
            "ok": True,
            "message": f"已讀取 {sheet} · {len(cache)} 筆資料",
            "sheet": sheet,
            "count": len(cache),
            "series_count": raw_series_count,
            "header_row": getattr(manager, "_header_row", 1),
        }

    def _staging_root(self) -> Path:
        nearby = self.attachments_root.parent / "staging"
        if nearby.exists():
            return nearby
        return Path(__file__).resolve().parent.parent / "staging"

    def _read_material_items(self) -> list[dict]:
        doc = _read_json_file(self.records_dir / "material_pricebook.json")
        if isinstance(doc, dict):
            items = doc.get("items")
            return items if isinstance(items, list) else []
        return doc if isinstance(doc, list) else []

    def _read_project_part_ids(self) -> set[str]:
        doc = _read_json_file(self.records_dir / "project_parts.json")
        if not isinstance(doc, dict):
            return set()
        registered = doc.get("registered")
        if not isinstance(registered, list):
            return set()
        return {str(item) for item in registered}

    def _resolve_image_path(self, value: str) -> Path:
        requested = _path_from_file_value(value)
        candidates: list[Path] = []
        if requested.is_absolute():
            candidates.append(requested)
        else:
            candidates.extend([
                requested,
                self.attachments_root / requested,
                self.attachments_root.parent / requested,
                self._staging_root() / requested,
                self.attachments_root.parent / "_annotated" / requested,
            ])
            if len(requested.parts) == 1:
                candidates.extend(self._find_nearby_images(requested.name))

        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            try:
                if candidate.is_file():
                    return candidate.resolve()
            except OSError:
                continue
        raise FileNotFoundError(f"找不到照片：{value}")

    def _resolve_pdf_path(self, value: str) -> Path:
        text = str(value or "").strip()
        if not text:
            raise ValueError("缺少 PDF 路徑")
        requested = _path_from_file_value(text)
        candidates: list[Path] = []
        if requested.is_absolute():
            candidates.append(requested)
        else:
            candidates.extend([
                requested,
                self.attachments_root / requested,
                self.attachments_root.parent / requested,
                self._staging_root() / requested,
                self.attachments_root.parent / "_annotated" / requested,
            ])
            if len(requested.parts) == 1:
                candidates.extend(self._find_nearby_pdfs(requested.name))

        seen: set[str] = set()
        for candidate in candidates:
            key = str(candidate)
            if key in seen:
                continue
            seen.add(key)
            try:
                if candidate.is_file() and candidate.suffix.lower() in _PDF_EXTS:
                    return candidate.resolve()
            except OSError:
                continue
        raise FileNotFoundError(f"找不到 PDF：{value}")

    def _find_nearby_images(self, name: str) -> list[Path]:
        matches: list[Path] = []
        for root in [self.attachments_root, self._staging_root(), self.attachments_root.parent / "_annotated"]:
            try:
                if not root.exists():
                    continue
                matches.extend(path for path in root.rglob(name) if path.is_file())
            except OSError:
                continue
        matches.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
        return matches

    def _find_nearby_pdfs(self, name: str) -> list[Path]:
        matches: list[Path] = []
        for root in [self.attachments_root, self._staging_root(), self.attachments_root.parent / "_annotated"]:
            try:
                if not root.exists():
                    continue
                matches.extend(path for path in root.rglob(name) if path.is_file() and path.suffix.lower() in _PDF_EXTS)
            except OSError:
                continue
        matches.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
        return matches


def _path_from_file_value(value: str) -> Path:
    text = str(value or "").strip()
    if re.match(r"^file:", text, re.IGNORECASE):
        parsed = urlparse(text)
        raw = unquote(parsed.path or "")
        if parsed.netloc:
            raw = f"//{parsed.netloc}{raw}"
        if re.match(r"^/[A-Za-z]:/", raw):
            raw = raw[1:]
        return Path(raw)
    return Path(text)


def _series_pdf_variants(series: str) -> list[str]:
    text = _norm_series(series)
    variants = [text]
    if text.isdigit():
        variants.extend([text.zfill(3), text.zfill(4)])
    out: list[str] = []
    seen: set[str] = set()
    for item in variants:
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _series_pdf_score(path: Path, variants: list[str], root: Path) -> tuple[int, int, str] | None:
    stem = path.stem.strip().lower()
    for index, variant in enumerate(variants):
        prefix = variant.lower()
        if stem == prefix:
            return (0, _path_depth(path, root), path.name.lower())
        if stem.startswith(prefix):
            tail = stem[len(prefix):len(prefix) + 1]
            if tail in _SERIES_PDF_DELIMITERS:
                return (1 + index, _path_depth(path, root), path.name.lower())
    return None


def _path_depth(path: Path, root: Path) -> int:
    try:
        return max(0, len(path.relative_to(root).parts) - 1)
    except ValueError:
        return 99


def _find_series_pdf(root: Path, series: str) -> Path | None:
    variants = _series_pdf_variants(series)
    matches: list[tuple[tuple[int, int, str], float, Path]] = []
    try:
        iterator = root.rglob("*.pdf")
        for path in iterator:
            if not path.is_file():
                continue
            score = _series_pdf_score(path, variants, root)
            if score is None:
                continue
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0
            matches.append((score, -mtime, path))
    except OSError:
        return None
    if not matches:
        return None
    matches.sort(key=lambda item: (item[0], item[1]))
    return matches[0][2]


def _decode_data_url(data_url: str, label: str) -> bytes:
    payload = str(data_url or "")
    if "," in payload:
        header, payload = payload.split(",", 1)
        if "base64" not in header.lower():
            raise ValueError(f"{label}必須是 base64 data URL")
    return base64.b64decode(payload, validate=True)


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _material_part_to_frontend(item: dict) -> dict:
    return {
        "id": str(item.get("id") or ""),
        "part": item.get("零件類型") or item.get("part") or "",
        "size": item.get("尺寸") or item.get("size") or "",
        "sch": item.get("SCH") or item.get("sch") or "",
        "mat": item.get("材質") or item.get("mat") or "",
        "cat": item.get("類別") or item.get("cat") or "",
        "unit": item.get("單位") or item.get("unit") or "",
        "src": item.get("來源") or item.get("src") or "",
        "remark": item.get("備註") or item.get("remark") or "",
    }


__all__ = ["ChangeOrderBridge", "API_VERSION"]
