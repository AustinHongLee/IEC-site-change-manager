# -*- coding: utf-8 -*-
"""change_order.py - 修改單記錄 canonical 資料層（Task 1）

權威定義見 ``docs/00_big_bang_產品進化總控室/修改單記錄_schema_v0.1_草稿.md``（內容 v0.2）。

定位：
    這份記錄 = 精靈收集的東西 = 存進檔案的格式 = 未來資料庫的表。
    精靈 UI / Excel 版面 / 檔名都是它的下游。

本模組為**純資料層**：只負責「欄位定義 + JSON 存讀 + 結構驗證」。
    - 零 Qt / UI 依賴，可在無顯示環境 import 與測試。
    - 只做結構驗證（型別 / Enum 取值），**不做業務必填驗證**——
      「哪些欄位必填、group 要不要圖號 PDF」屬每案設定 / 完整度層（後續任務）。
    - **不**在此實作 a/b、1000+ 編號或管制表查詢——那是 Task 2 / Task 3。

設計重點：
    - Enum 在 JSON 中一律存其 ``value``（中文字串），``from_dict`` 以 value 反查還原。
    - 前向相容：每筆帶 ``schema_version``；載入時容忍「多出的未知欄位」與
      「缺少的欄位」、以及「未知的 Enum 值」（保留原字串，不崩）。
    - ``audit`` 從第一天就是可擴充的軌跡 ``history[]``（who / when / action / detail），
      **不是**單一時間戳。形狀對齊既有 ``operation_journal.py`` 的 step（at/action/payload），
      但兩者用途不同、並存不互斥（journal = 暫態當機復原；audit = 每筆記錄的永久軌跡）。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Optional, Type, TypeVar, Union

SCHEMA_VERSION = "0.2"


# --------------------------------------------------------------------------- #
# Enums（固定取值；JSON 內以中文 value 表示）
# --------------------------------------------------------------------------- #
class Status(str, Enum):
    DRAFT = "草稿"
    PARTIAL = "待補"
    COMPLETE = "完整"


class Scenario(str, Enum):
    NORMAL = "normal"
    GROUP = "group"


class Origin(str, Enum):
    EXISTING = "existing"  # 既有焊口重焊
    NEW = "new"            # 全新焊口


class Op(str, Enum):
    CUT = "裁切"
    EXTEND = "加長"
    SHORTEN = "縮短"


class Role(str, Enum):
    BEFORE = "before"  # 問題長怎樣
    AFTER = "after"    # 修好的證明


class JointType(str, Enum):
    """接點種類。注意：與 ``Spec.weld_type``（銲接型式，如 BW/SW）是兩回事。"""

    WELD = "焊口"
    THREAD = "管牙"


class SpecSource(str, Enum):
    LOOKED_UP = "looked_up"  # 從管制表帶
    MANUAL = "manual"        # 手填（多為 new）


_E = TypeVar("_E", bound=Enum)


def _now_iso() -> str:
    """ISO 時間（秒），對齊 operation_journal._now_iso 的格式。"""
    return datetime.now().isoformat(timespec="seconds")


def _enum_value(value: Any) -> Any:
    """序列化：Enum → 其 value；其餘原樣（含已被容忍保留的原字串、None）。"""
    return value.value if isinstance(value, Enum) else value


def _coerce_enum(enum_cls: Type[_E], value: Any) -> Any:
    """反序列化：value → Enum 成員；未知值**容忍保留原字串**（前向相容），不崩。"""
    if value is None or isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(value)
    except ValueError:
        return value


# --------------------------------------------------------------------------- #
# 巢狀結構
# --------------------------------------------------------------------------- #
@dataclass
class Spec:
    """焊口規格。"""

    size: Optional[str] = None
    sch: Optional[str] = None
    material: Optional[str] = None
    weld_type: Optional[str] = None  # 銲接型式（BW/SW/RF…），≠ WeldEvent.joint_type

    def to_dict(self) -> dict[str, Any]:
        return {"size": self.size, "sch": self.sch,
                "material": self.material, "weld_type": self.weld_type}

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "Spec":
        data = data or {}
        return cls(
            size=data.get("size"),
            sch=data.get("sch"),
            material=data.get("material"),
            weld_type=data.get("weld_type"),
        )


@dataclass
class WeldEvent:
    """焊口事件——每一口是一個**事件**，不是一個號碼。"""

    joint_type: Union[JointType, str] = JointType.WELD
    origin: Union[Origin, str, None] = None
    base: Optional[str] = None              # 原始焊口號（existing 用；new 為空）
    op: Union[Op, str, None] = None
    rework_index: Optional[int] = None      # 第幾次重工（→ a/b/c…）；Task 3 才算
    code: Optional[str] = None              # 算出的案場碼（2a、1001）；Task 3 才產
    spec: Spec = field(default_factory=Spec)
    spec_source: Union[SpecSource, str, None] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "joint_type": _enum_value(self.joint_type),
            "origin": _enum_value(self.origin),
            "base": self.base,
            "op": _enum_value(self.op),
            "rework_index": self.rework_index,
            "code": self.code,
            "spec": self.spec.to_dict(),
            "spec_source": _enum_value(self.spec_source),
        }

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "WeldEvent":
        data = data or {}
        return cls(
            joint_type=_coerce_enum(JointType, data.get("joint_type", JointType.WELD)),
            origin=_coerce_enum(Origin, data.get("origin")),
            base=data.get("base"),
            op=_coerce_enum(Op, data.get("op")),
            rework_index=data.get("rework_index"),
            code=data.get("code"),
            spec=Spec.from_dict(data.get("spec")),
            spec_source=_coerce_enum(SpecSource, data.get("spec_source")),
        )


@dataclass
class Photo:
    role: Union[Role, str, None] = None
    file: Optional[str] = None
    weld_ref: Optional[str] = None   # 對應哪一口（選填；預設綁整張單）
    annotations: Any = None          # 圖上標註（選填，自由形）

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": _enum_value(self.role),
            "file": self.file,
            "weld_ref": self.weld_ref,
            "annotations": self.annotations,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "Photo":
        data = data or {}
        return cls(
            role=_coerce_enum(Role, data.get("role")),
            file=data.get("file"),
            weld_ref=data.get("weld_ref"),
            annotations=data.get("annotations"),
        )


@dataclass
class DrawingPdf:
    file: Optional[str] = None
    annotations: Any = None  # 在圖上圈位置；內容由結構化欄位提供，不重複輸入

    def to_dict(self) -> dict[str, Any]:
        return {"file": self.file, "annotations": self.annotations}

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "DrawingPdf":
        data = data or {}
        return cls(file=data.get("file"), annotations=data.get("annotations"))


@dataclass
class Material:
    """結構化材料（沿用現精靈 Step6 欄位）。"""

    component: Optional[str] = None
    component_id: Optional[str] = None
    size: Optional[str] = None
    schedule: Optional[str] = None
    material: Optional[str] = None
    qty: Any = None  # 數量；保留原樣（字串或數字）以求 round-trip 穩定
    unit: Optional[str] = None
    remark: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "component_id": self.component_id,
            "size": self.size,
            "schedule": self.schedule,
            "material": self.material,
            "qty": self.qty,
            "unit": self.unit,
            "remark": self.remark,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "Material":
        data = data or {}
        return cls(
            component=data.get("component"),
            component_id=data.get("component_id"),
            size=data.get("size"),
            schedule=data.get("schedule"),
            material=data.get("material"),
            qty=data.get("qty"),
            unit=data.get("unit"),
            remark=data.get("remark"),
        )


@dataclass
class Authorization:
    """業主簽認（選填）。"""

    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    evidence: Any = None  # 簽認過的表單 / 圖之照片或掃描（檔名或清單）

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "Authorization":
        data = data or {}
        return cls(
            approved_by=data.get("approved_by"),
            approved_at=data.get("approved_at"),
            evidence=data.get("evidence"),
        )


@dataclass
class AuditEntry:
    """稽核軌跡的一筆。形狀對齊 operation_journal 的 step。"""

    who: Optional[str] = None
    when: Optional[str] = None  # ISO 秒
    action: Optional[str] = None
    detail: Any = None

    @classmethod
    def make(cls, action: str, who: Optional[str] = None, detail: Any = None) -> "AuditEntry":
        """建一筆並蓋上現在時間。"""
        return cls(who=who, when=_now_iso(), action=action, detail=detail)

    def to_dict(self) -> dict[str, Any]:
        return {"who": self.who, "when": self.when,
                "action": self.action, "detail": self.detail}

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "AuditEntry":
        data = data or {}
        return cls(
            who=data.get("who"),
            when=data.get("when"),
            action=data.get("action"),
            detail=data.get("detail"),
        )


@dataclass
class Audit:
    """稽核軌跡——可累加的 history[]，不是單一時間戳。"""

    history: list[AuditEntry] = field(default_factory=list)

    def record(self, action: str, who: Optional[str] = None, detail: Any = None) -> AuditEntry:
        """新增一筆軌跡並回傳。"""
        entry = AuditEntry.make(action, who=who, detail=detail)
        self.history.append(entry)
        return entry

    def to_dict(self) -> dict[str, Any]:
        return {"history": [e.to_dict() for e in self.history]}

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "Audit":
        data = data or {}
        raw = data.get("history") or []
        return cls(history=[AuditEntry.from_dict(e) for e in raw])


# --------------------------------------------------------------------------- #
# 主結構
# --------------------------------------------------------------------------- #
@dataclass
class ChangeOrder:
    """一張修改單（canonical 記錄）。"""

    schema_version: str = SCHEMA_VERSION
    id: Optional[str] = None
    status: Union[Status, str, None] = Status.DRAFT
    date: Optional[str] = None              # 報告日期 YYYYMMDD
    series: Optional[str] = None            # 流水號（圖號唯一短碼）
    dwg_no: Optional[str] = None            # 圖號（由 series 帶出）
    scenario: Union[Scenario, str] = Scenario.NORMAL
    welds: list[WeldEvent] = field(default_factory=list)
    photos: list[Photo] = field(default_factory=list)
    drawing_pdf: Optional[DrawingPdf] = None
    reason: Optional[str] = None
    materials: list[Material] = field(default_factory=list)
    authorization: Optional[Authorization] = None
    audit: Audit = field(default_factory=Audit)

    # -- 序列化 ---------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version or SCHEMA_VERSION,
            "id": self.id,
            "status": _enum_value(self.status),
            "date": self.date,
            "series": self.series,
            "dwg_no": self.dwg_no,
            "scenario": _enum_value(self.scenario),
            "welds": [w.to_dict() for w in self.welds],
            "photos": [p.to_dict() for p in self.photos],
            "drawing_pdf": self.drawing_pdf.to_dict() if self.drawing_pdf is not None else None,
            "reason": self.reason,
            "materials": [m.to_dict() for m in self.materials],
            "authorization": self.authorization.to_dict() if self.authorization is not None else None,
            "audit": self.audit.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "ChangeOrder":
        """容忍：缺欄位給預設、未知欄位忽略、未知 Enum 值保留原字串。"""
        data = data or {}
        drawing = data.get("drawing_pdf")
        auth = data.get("authorization")
        return cls(
            schema_version=data.get("schema_version", SCHEMA_VERSION),
            id=data.get("id"),
            status=_coerce_enum(Status, data.get("status", Status.DRAFT)),
            date=data.get("date"),
            series=data.get("series"),
            dwg_no=data.get("dwg_no"),
            scenario=_coerce_enum(Scenario, data.get("scenario", Scenario.NORMAL)),
            welds=[WeldEvent.from_dict(w) for w in (data.get("welds") or [])],
            photos=[Photo.from_dict(p) for p in (data.get("photos") or [])],
            drawing_pdf=DrawingPdf.from_dict(drawing) if drawing is not None else None,
            reason=data.get("reason"),
            materials=[Material.from_dict(m) for m in (data.get("materials") or [])],
            authorization=Authorization.from_dict(auth) if auth is not None else None,
            audit=Audit.from_dict(data.get("audit")),
        )

    # -- JSON 檔案 IO ---------------------------------------------------------
    def save_json(self, path: Union[str, Path]) -> None:
        """原子寫入：先寫暫存檔再 rename（對齊 operation_journal 的寫法）。"""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, path)

    @classmethod
    def load_json(cls, path: Union[str, Path]) -> "ChangeOrder":
        with Path(path).open("r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# --------------------------------------------------------------------------- #
# 單號產生
# --------------------------------------------------------------------------- #
def generate_id(series: str, date: str, existing_ids: Optional[Iterable[str]] = None) -> str:
    """產生單號 ``{series}_{date}_{NN}``。

    NN 為當日該流水號的序號（至少兩位、零補）；遇同 series+date 的既有單號遞增。
    純函式：由呼叫端提供 ``existing_ids``，本層不掃描檔案系統。
    """
    prefix = f"{series}_{date}_"
    max_seq = 0
    for existing in (existing_ids or []):
        if isinstance(existing, str) and existing.startswith(prefix):
            suffix = existing[len(prefix):]
            if suffix.isdigit():
                max_seq = max(max_seq, int(suffix))
    return f"{prefix}{max_seq + 1:02d}"
