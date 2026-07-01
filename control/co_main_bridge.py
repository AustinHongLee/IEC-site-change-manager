# -*- coding: utf-8 -*-
"""co_main_bridge.py — 新版主介面的前後端橋（transport-agnostic，先做「讀」路徑）

定位同 co_bridge：**不認 UI、不認傳輸層**，JSON 進 JSON 出，每個對外方法回
``{"ok": bool, "data": ..., "error": str|None}`` 信封；pywebview 的 js_api 直接拿它
（見 co_main_app.py），未來 FastAPI 也能無痛包成 HTTP route。

第一刀只做唯讀讀取，先把「橋 → pywebview → 前端」這條鏈打通：
    - ``pricebook()``：讀 records/material_pricebook.json（舊系統真實料表，442 筆），
      對映成主介面前端 material 價目表的形狀。
    - ``records()``：讀舊 store records.json（目前空），對映成前端記錄形狀。

不放任何業務邏輯；之後寫入 / 產出 / 中央查價再逐刀加。
"""
from __future__ import annotations

import functools
import json
import traceback
from pathlib import Path
from typing import Any, Callable

API_VERSION = "main-0.1"


def _enveloped(fn: Callable) -> Callable:
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        try:
            return {"ok": True, "data": fn(self, *args, **kwargs), "error": None}
        except Exception as exc:  # 橋不可把例外漏給前端
            return {
                "ok": False,
                "data": None,
                "error": f"{type(exc).__name__}: {exc}",
                "trace": traceback.format_exc(),
            }
    return wrapper


def _num(v: Any) -> Any:
    """單價等欄位：'100' → 100、'' → 0；無法轉的原樣回（不炸）。"""
    if v is None:
        return 0
    try:
        s = str(v).strip().replace(",", "")
        if s == "":
            return 0
        f = float(s)
        return int(f) if f == int(f) else f
    except (TypeError, ValueError):
        return v


def _read_json(path: Path) -> Any:
    """容錯讀 JSON（utf-8-sig 吃 BOM）；不存在 / 壞檔回 None。"""
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


class MainBridge:
    """主介面橋。對外方法皆回信封；`project_root` 下的 records/ 放舊系統資料。"""

    def __init__(self, project_root: Any, *, pick_file_fn: Optional[Callable[[str], Optional[str]]] = None):
        self.root = Path(project_root)
        self.records_dir = self.root / "records"
        self._pick_file_fn = pick_file_fn  # 由 launcher 注入原生檔案對話框
        self._save_file_fn = None          # 由 launcher 注入原生存檔對話框

    # ---- 對外 API（皆回信封） -------------------------------------------- #
    @_enveloped
    def info(self) -> dict:
        return {
            "api_version": API_VERSION,
            "root": str(self.root),
            "records_dir": str(self.records_dir),
            "pricebook_exists": (self.records_dir / "material_pricebook.json").exists(),
        }

    @_enveloped
    def pricebook(self) -> list:
        """讀真實料表 → 對映成前端 PRICE 形狀；缺檔回 []。"""
        data = _read_json(self.records_dir / "material_pricebook.json")
        items = data.get("items") if isinstance(data, dict) else data
        out = []
        for it in (items or []):
            if not isinstance(it, dict):
                continue
            out.append({
                "id": it.get("id") or "",
                "part": it.get("零件類型") or "",
                "size": it.get("尺寸") or "",
                "sch": it.get("SCH") or "",
                "mat": it.get("材質") or "",
                "cat": it.get("類別") or "",
                "unit": it.get("單位") or "",
                "src": it.get("來源") or "",
                "remark": it.get("備註") or "",
            })
        return out

    @_enveloped
    def records(self) -> list:
        """讀舊 store records.json → 對映成前端 records 形狀（目前空，回 []）。"""
        data = _read_json(self.records_dir / "records.json")
        recs = (data or {}).get("records") if isinstance(data, dict) else None
        # 舊 store details / materials 需以報告編號 join；目前 store 為空，
        # 待有真資料時再補 join，這裡先安全回基本欄位（空則 []）。
        out = []
        for r in (recs or []):
            if not isinstance(r, dict):
                continue
            out.append({
                "id": r.get("報告編號") or "",
                "date": r.get("日期") or "",
                "series": r.get("Series NO") or r.get("Series") or "",
                "status": "done" if str(r.get("需重產", "")).strip() != "1" else "pending",
                "reason": r.get("說明") or "",
                "welds": [],
                "mats": [],
                "photos": [],
            })
        return out


    @_enveloped
    def dates(self) -> list:
        """產出報告左欄：attachments 的日期資料夾 → 每日的圖號(流水號)清單。

        來源優先用 records/weld_snapshot.json 的 folders（已解析好 serial/welds）；
        沒有就回 []。狀態先一律 'pending'（記錄空、尚未產出）。
        """
        snap = _read_json(self.records_dir / "weld_snapshot.json") or {}
        folders = snap.get("folders") if isinstance(snap, dict) else None
        by_date: dict[str, list] = {}
        for key, info in (folders or {}).items():
            if not isinstance(info, dict):
                continue
            date = str(key).split("/", 1)[0]
            serial = info.get("serial") or info.get("raw_serial") or ""
            welds = len(info.get("welds") or [])
            by_date.setdefault(date, []).append({
                "series": str(serial),
                "welds": welds,
                "status": "pending",
                "sel": False,
                "folder": str(key),
            })
        out = []
        for date in sorted(by_date.keys(), reverse=True):
            out.append({"date": date, "open": False, "items": by_date[date]})
        if out:
            out[0]["open"] = True
        return out

    @_enveloped
    def billing(self) -> dict:
        """請款：目前 store 空 → 回空清單 + 批次 + 稅率設定。"""
        batches_doc = _read_json(self.records_dir / "billing_batches.json") or {}
        meta = batches_doc.get("meta") or {}
        batches = []
        for b in (batches_doc.get("batches") or []):
            if isinstance(b, dict):
                batches.append(b)
        return {"rows": [], "batches": batches, "tax_rate": meta.get("tax_rate", "5%")}

    @_enveloped
    def health(self) -> dict:
        """健康：跑既有 integrity_audit / project_guard，回計數 + 問題 + 狀態。"""
        counts: dict = {}
        issues: list = []
        try:
            from integrity_audit import audit_integrity
            a = audit_integrity(str(self.root))
            counts = dict(getattr(a, "counts", {}) or {})
            for it in (getattr(a, "issues", []) or []):
                issues.append(_issue_dict("資料稽核", it))
        except Exception:
            pass
        try:
            from project_guard import inspect_project
            g = inspect_project(str(self.root))
            for it in (getattr(g, "issues", []) or []):
                issues.append(_issue_dict("啟動守門", it))
        except Exception:
            pass
        errs = sum(1 for i in issues if i["level"] == "error")
        warns = sum(1 for i in issues if i["level"] == "warning")
        infos = sum(1 for i in issues if i["level"] == "info")
        if errs:
            status, label = "err", f"需要人工確認：{errs} 個錯誤"
        elif warns or infos:
            status, label = "warn", f"可使用，有 {warns} 個提醒"
        else:
            status, label = "ok", "正常：未發現問題"
        return {
            "status": status, "label": label, "counts": counts, "issues": issues,
            "root": str(self.root), "errors": errs, "warnings": warns, "infos": infos,
        }

    @_enveloped
    def pick_file(self, kind: str = "excel") -> dict:
        """開原生檔案對話框（由 launcher 注入）；純環境未注入則回明確錯。"""
        if self._pick_file_fn is None:
            raise RuntimeError("檔案對話框未注入（此環境不支援選檔）")
        return {"path": self._pick_file_fn(kind)}

    @_enveloped
    def import_material_excel(self, path: str) -> dict:
        """匯入管制單 Excel（自動辨識多格式）→ 併入總庫（去重、不覆蓋、只加新品項）。"""
        new_items = _parse_material_xlsx(path)
        self.records_dir.mkdir(parents=True, exist_ok=True)
        p = self.records_dir / "material_pricebook.json"
        doc = _read_json(p)
        existing = (doc.get("items") if isinstance(doc, dict) else doc) or []

        def _key(it):
            g = lambda k: " ".join(str(it.get(k, "")).split()).lower()
            return f"{g('零件類型')}|{g('尺寸')}|{g('SCH')}|{g('材質')}"   # 顯示鍵：畫面看到的四欄相同即視為同一料

        seen = {_key(it) for it in existing}
        added = []
        for it in new_items:
            k = _key(it)
            if k in seen:
                continue
            seen.add(k)
            added.append(it)
        merged = list(existing) + added
        for i, it in enumerate(merged):
            it["id"] = f"{i + 1:04d}"
        if p.exists():                            # 備份用時間戳，絕不蓋掉 442 的 .backup.json
            import shutil
            import datetime
            stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy(p, self.records_dir / f"material_pricebook.{stamp}.bak.json")
        p.write_text(
            json.dumps({"items": merged, "history": [],
                        "meta": {"version": "3.1", "kind": "總庫",
                                 "count": len(merged), "priced": False}},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
        return {"added": len(added), "total": len(merged)}

    # ---- 本案配件登記（總庫 → 本案子集，只記品項不記數量）------------------ #
    def _project_parts_path(self) -> Path:
        return self.records_dir / "project_parts.json"

    def _read_registered(self) -> set:
        data = _read_json(self._project_parts_path()) or {}
        reg = data.get("registered") if isinstance(data, dict) else None
        return set(str(x) for x in (reg or []))

    def _write_registered(self, reg) -> None:
        self.records_dir.mkdir(parents=True, exist_ok=True)
        ids = sorted(set(str(x) for x in reg))
        self._project_parts_path().write_text(
            json.dumps({"registered": ids, "meta": {"count": len(ids)}},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")

    @_enveloped
    def project_parts(self) -> dict:
        """本案已登記的料號清單（前端據此把總庫過濾成本案配件）。"""
        return {"registered": sorted(self._read_registered())}

    @_enveloped
    def register_parts(self, ids) -> dict:
        """把料號加入本案配件（勾選登記）。"""
        cur = self._read_registered()
        add = [str(x) for x in (ids or [])]
        cur.update(add)
        self._write_registered(cur)
        return {"registered": sorted(cur), "added": add}

    @_enveloped
    def unregister_parts(self, ids) -> dict:
        """把料號移出本案配件（取消登記）。"""
        cur = self._read_registered()
        rem = [str(x) for x in (ids or [])]
        cur.difference_update(rem)
        self._write_registered(cur)
        return {"registered": sorted(cur), "removed": rem}

    # ---- 匯出（總庫 / 本案配件 → Excel，交回採購/收料）--------------------- #
    def _all_materials(self) -> list:
        doc = _read_json(self.records_dir / "material_pricebook.json")
        return (doc.get("items") if isinstance(doc, dict) else doc) or []

    def _export_materials(self, items, path, sheet_name, default_stem) -> dict:
        if not path:
            if self._save_file_fn is None:
                raise RuntimeError("存檔對話框未注入（此環境不支援匯出）")
            path = self._save_file_fn("excel", f"{default_stem}.xlsx")
            if not path:
                return {"cancelled": True}
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name
        cols = ["料號", "零件類型", "尺寸", "SCH", "材質", "類別", "單位", "來源", "規格", "備註"]
        keys = ["id", "零件類型", "尺寸", "SCH", "材質", "類別", "單位", "來源", "規格", "備註"]
        ws.append(cols)
        for it in items:
            ws.append([it.get(k, "") for k in keys])
        wb.save(path)
        return {"path": str(path), "count": len(items)}

    @_enveloped
    def export_master(self, path: str = "") -> dict:
        """匯出整個總庫成 Excel。"""
        return self._export_materials(self._all_materials(), path, "總庫", "總庫材料")

    @_enveloped
    def export_project_parts(self, path: str = "") -> dict:
        """匯出本案已登記配件成 Excel（交回採購/收料）。"""
        reg = self._read_registered()
        items = [it for it in self._all_materials() if str(it.get("id")) in reg]
        return self._export_materials(items, path, "本案配件", "本案配件")


def _pm_clean(s):
    return " ".join(str(s or "").split())


_INCH_DN = {
    '1/8"': 'DN6', '1/4"': 'DN8', '3/8"': 'DN10', '1/2"': 'DN15', '3/4"': 'DN20',
    '1"': 'DN25', '1.1/4"': 'DN32', '1.1/2"': 'DN40', '2"': 'DN50', '2.1/2"': 'DN65',
    '3"': 'DN80', '3.1/2"': 'DN90', '4"': 'DN100', '5"': 'DN125', '6"': 'DN150',
    '8"': 'DN200', '10"': 'DN250', '12"': 'DN300', '14"': 'DN350', '16"': 'DN400',
    '18"': 'DN450', '20"': 'DN500', '22"': 'DN550', '24"': 'DN600', '26"': 'DN650',
    '28"': 'DN700', '30"': 'DN750', '32"': 'DN800', '36"': 'DN900', '40"': 'DN1000',
    '42"': 'DN1050', '48"': 'DN1200',
}


def _canon_size(s):
    """尺寸統一成 DN（吋 → DN；DN 保留；認不出原樣回）。"""
    s = " ".join(str(s or "").split())
    return _INCH_DN.get(s, s)


def _canon_mat(m):
    """材質正規化：收空白、去尾點、A182-F304→A182 F304（合併空格/連字號的重複值）。"""
    import re
    m = " ".join(str(m or "").split())
    m = re.sub(r'\s*\.\s*$', '', m)
    m = re.sub(r'^(A\d+)-', r'\1 ', m)
    return " ".join(m.split())


def _pm_size(d):
    import re
    m = re.search(r'(\d[\d./]*)\s*"', str(d))
    if m:
        return m.group(1) + '"'
    for t in str(d).split(","):               # 退而求其次抓 DN 代號
        t = t.strip()
        if t.upper().startswith("DN"):
            return t
    return ""


def _pm_sch(d):
    import re
    s = str(d)
    for t in s.split(","):                 # 逗號式規格：整段保留（SCH40S、SCH40XSCH80、150#）不截斷
        t = t.strip()
        if t.upper().startswith("SCH") or t.endswith("#"):
            return t.upper().replace(" ", "")
    m = re.search(r'(SCH\s*\d+[A-Z]*|\d+#)', s.upper())   # 描述式：抓 SCHxx(含尾字母) 或 xxx#
    return m.group(1).replace(" ", "") if m else ""


def _pm_mat(s, fb=""):
    import re
    m = re.search(r'(A\d{2,3}\s*GR\.?\s*[A-Z0-9]+|A182[^ ]*|A105|A234[^ ]*|A106[^ ]*|SUS\s?\d{3}[A-Z]?|SS\d{3}|WPB)', str(s).upper())
    return m.group(1).strip() if m else fb


def _pm_type(d):
    """從英文規格描述抽出乾淨的中文零件類型；認不出回 ''（呼叫端保留原字串）。"""
    import re
    u = str(d).upper()
    ang = "90°" if re.search(r'X90|-90|\b90\b', u) else ("45°" if re.search(r'X45|-45|\b45\b', u) else "")
    if 'ELBOW' in u or re.search(r'\bEB-', u):
        return ang + "彎頭"
    if 'OLET' in u:
        return "OLET"
    if 'REDUCING TEE' in u:
        return "異徑三通"
    if 'TEE' in u or re.search(r'\bTE-', u):
        return "三通"
    if 'REDUCER' in u or re.search(r'\bRE-|\bCR-|\bER-', u):
        return "大小頭"
    if 'CAP' in u:
        return "管帽"
    if 'BLIND' in u:
        return "盲法蘭"
    if 'FLANGE' in u or re.search(r'\bFLG|\bSOF-|\bWNF-|\bSWF-', u):
        return "法蘭"
    if 'GASKET' in u or re.search(r'\bGR-', u):
        return "墊片"
    if 'COUPLING' in u or 'CPLG' in u:
        return "COUPLING"
    if 'NIPPLE' in u or re.search(r'\bNIP', u):
        return "短節"
    if 'UNION' in u:
        return "由令"
    if 'BUSHING' in u:
        return "補心"
    if 'PLUG' in u:
        return "管塞"
    if 'VALVE' in u or re.search(r'\bVA-', u):
        if 'GATE' in u:
            return "閘閥"
        if 'GLOBE' in u:
            return "球心閥"
        if 'BALL' in u:
            return "球閥"
        if 'CHECK' in u:
            return "止回閥"
        if 'BUTTERFLY' in u:
            return "蝶閥"
        if 'KNIFE' in u:
            return "刀閘閥"
        return "閥"
    if 'BOLT' in u or 'STUD' in u or re.search(r'\bNUT\b', u) or re.match(r'^M\d', u):
        return "螺栓"
    if 'PIPE' in u or 'SMLS' in u:
        return "鋼管"
    return ""


def _pm_cat(n):
    u = str(n or "").upper()
    n = str(n or "")
    if "閥" in n or "VALVE" in u:
        return "閥件"
    if "墊" in n or "GASKET" in u:
        return "墊料"
    if "螺" in n or "BOLT" in u or "NUT" in u:
        return "螺栓"
    if "法蘭" in n or "FLANGE" in u:
        return "法蘭"
    return "配管"


def _parse_material_xlsx(path: Any) -> list:
    """讀管制單 Excel → 正規化成總庫品項（無單價）。自動辨識 4 種格式：

    - 0408 品名式：項次/品名/規格型號/材質/單位（名稱已是乾淨中文 → 原樣保留）
    - 消防 規格式：項次/規格型號/材質/單位（無品名 → 名稱＝規格，抽中文類型）
    - 工業級：項次/品名及規格/尺寸/單位（名稱是英文描述 → 抽中文類型）
    - GASKET：Item/品名/Size/Description/Unit
    以表頭欄名定位欄位、以「有無單位」跳過分節列；規格全文保留供比對/匯出。
    """
    import openpyxl
    import os
    import re
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))

    stem = os.path.splitext(os.path.basename(str(path)))[0]      # 來源標記＝檔名括號內容
    paren = re.findall(r"[（(]([^）)]+)[）)]", stem)
    src = _pm_clean(paren[-1]) if paren else _pm_clean(stem)[:16]

    hi, header = None, []
    for idx, r in enumerate(rows[:6]):
        cells = [_pm_clean(c) for c in (r or [])]
        if any(("項次" in c) or (c.lower() == "item") for c in cells):
            hi, header = idx, cells
            break
    if hi is None:
        hi = 2
        header = [_pm_clean(c) for c in (rows[2] if len(rows) > 2 else [])]

    def find(*names):
        for i, c in enumerate(header):
            cl = c.replace(" ", "").lower()          # 表頭常含全形/半形空白（品  名、材   質）
            if any(n.replace(" ", "").lower() in cl for n in names):
                return i
        return None

    i_pname = find("品名")
    i_spec = find("規格型號")
    i_size = find("尺寸", "size")
    i_desc = find("description", "描述")
    i_mat = find("材質")
    i_unit = find("單位", "unit")

    name_i = i_pname if i_pname is not None else i_spec
    if name_i is None:
        name_i = 1
    spec_i = i_spec if i_spec is not None else i_size
    if spec_i is None:
        spec_i = name_i
    # 只有「同時有 品名 與 規格型號」的 0408 式才原樣保留名稱；其餘名稱是英文/規格 → 正規化
    derive = not (i_pname is not None and i_spec is not None)

    items, seen = [], set()
    for r in rows[hi + 1:]:
        if not r:
            continue
        row = [_pm_clean(c) for c in r] + [""] * 12
        raw = row[name_i]
        unit = row[i_unit] if i_unit is not None else ""
        if not raw or not unit:               # 分節列/空列（無單位）跳過
            continue
        spec = row[spec_i] if spec_i is not None else ""
        if i_desc is not None:
            spec = _pm_clean(spec + " " + row[i_desc])
        matcol = row[i_mat] if i_mat is not None else ""
        k = f"{raw}|{spec}|{matcol}".lower()
        if k in seen:
            continue
        seen.add(k)
        blob = raw + " " + spec
        typ = (_pm_type(blob) or raw) if derive else raw
        items.append({
            "零件類型": typ, "尺寸": _canon_size(_pm_size(blob)), "SCH": _pm_sch(blob),
            "材質": _canon_mat(matcol or _pm_mat(blob)), "類別": _pm_cat(typ),
            "單位": unit, "規格": spec, "來源": src, "備註": "",
        })
    return items


def _issue_dict(source: str, it: Any) -> dict:
    sev = getattr(it, "severity", None) or (it.get("severity") if isinstance(it, dict) else None) or "info"
    sev = str(sev).lower()
    if sev not in ("error", "warning", "info"):
        sev = "info"
    g = lambda *names: next((getattr(it, n, None) or (it.get(n) if isinstance(it, dict) else None)
                             for n in names if (getattr(it, n, None) or (isinstance(it, dict) and it.get(n)))), "")
    return {
        "source": source,
        "level": sev,
        "title": g("title", "name", "code") or "",
        "message": g("message", "detail", "content") or "",
        "ref": g("path", "ref", "reference") or "",
    }


__all__ = ["MainBridge", "API_VERSION"]
