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

import dataclasses
import functools
import json
import traceback
from pathlib import Path
from typing import Any, Callable, Optional

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
    try:
        return Op(value)          # 中文字串如 "裁切" → Op.CUT
    except Exception:
        return value              # 容錯：未知值原樣保留，不炸


_MATERIAL_FIELDS = {f.name for f in dataclasses.fields(Material)}


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
        pick_file_fn: Optional[Callable[[str], Optional[str]]] = None,
    ):
        self.builder = builder if builder is not None else ChangeOrderBuilder()
        self.attachments_root = (
            Path(attachments_root) if attachments_root else Path.cwd() / "change_order_records"
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
        welds = []
        for wid in (lookup.existing_weld_ids(s) if lookup is not None else []):
            spec = lookup.lookup_spec(s, wid)
            welds.append({
                "weld_no": wid,
                "size": getattr(spec, "size", None),
                "sch": getattr(spec, "sch", None),
                "material": getattr(spec, "material", None),
                "weld_type": getattr(spec, "weld_type", None),
            })
        return {"series": s, "welds": welds}

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
                self.builder.add_existing_weld(co, w.get("base"), _as_op(w.get("op")))
            elif kind == "new":
                self.builder.add_new_weld(co, _as_op(w.get("op")), Spec.from_dict(w.get("spec") or {}))

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


__all__ = ["ChangeOrderBridge", "API_VERSION"]
