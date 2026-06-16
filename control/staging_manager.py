# -*- coding: utf-8 -*-
"""
staging_manager.py — 前置區（照片/PDF 收件匣）管理模組

工作流：
1. 工程師把現場拍的所有照片 + PDF 丟進 staging/ 資料夾
2. GUI 讀取 staging/ 中所有檔案，提取 EXIF 時間排序
3. 工程師在 GUI 上逐批標記（圖號、焊口、before/after）
4. 點「分派」→ 自動搬移到 attachments/日期/圖號_焊口/ 並正確命名
"""

import os
import re
import shutil
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple, Dict
from pathlib import Path

try:
    from PIL import Image, ExifTags
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


# ────────── 資料結構 ──────────

@dataclass
class StagingFile:
    """staging 資料夾中的一個檔案"""
    path: str                             # 完整路徑
    filename: str                         # 檔名
    file_type: str                        # "image" | "pdf"
    size_kb: float                        # 檔案大小 KB
    exif_time: Optional[datetime] = None  # EXIF 拍攝時間
    mtime: Optional[datetime] = None      # 檔案修改時間
    width: int = 0
    height: int = 0

    @property
    def sort_time(self) -> datetime:
        """排序用時間：優先 EXIF → 檔案修改時間 → epoch"""
        return self.exif_time or self.mtime or datetime(2000, 1, 1)

    @property
    def time_label(self) -> str:
        t = self.exif_time or self.mtime
        if t:
            return t.strftime("%Y-%m-%d %H:%M:%S")
        return "(無時間資訊)"

    @property
    def exif_source(self) -> str:
        if self.exif_time:
            return "EXIF"
        if self.mtime:
            return "檔案時間"
        return "無"


@dataclass
class FileAssignment:
    """一個檔案的分派指令"""
    source_path: str        # staging 中的來源路徑
    date_folder: str        # "20250818"
    series_no: str          # "243"
    suffix_combo: str       # "12a1_12b1" 或 "AG"
    role: str               # "before", "after", "before_1", "after_1", "pdf"

    @property
    def target_filename(self) -> str:
        """產出目標檔名"""
        ext = os.path.splitext(self.source_path)[1].lower()
        if self.role == "pdf":
            # PDF 保留原檔名（工程師可能需要辨識）
            return os.path.basename(self.source_path)
        # before.jpg / after.jpg / before_1.jpg / after_1.jpg ...
        return f"{self.role}{ext}"

    @property
    def folder_name(self) -> str:
        """目標子資料夾名稱，如 243_12a1_12b1"""
        return f"{self.series_no}_{self.suffix_combo}"


@dataclass
class DispatchResult:
    """分派結果"""
    assignment: FileAssignment
    success: bool
    target_path: str = ""
    error: str = ""


# ────────── EXIF 讀取 ──────────

EXIF_DATETIME_TAGS = ['DateTimeOriginal', 'DateTimeDigitized', 'DateTime']
EXIF_DATETIME_FMT = "%Y:%m:%d %H:%M:%S"


def _read_exif_time(filepath: str) -> Optional[datetime]:
    """從圖片讀取 EXIF 拍攝時間"""
    if not PILLOW_AVAILABLE:
        return None
    try:
        with Image.open(filepath) as img:
            exif_data = img._getexif()
            if not exif_data:
                return None
            # 建立 tag name → value 對照
            tag_map = {}
            for tag_id, value in exif_data.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                tag_map[tag_name] = value
            # 依優先順序嘗試
            for tag in EXIF_DATETIME_TAGS:
                val = tag_map.get(tag)
                if val and isinstance(val, str):
                    try:
                        return datetime.strptime(val.strip(), EXIF_DATETIME_FMT)
                    except ValueError:
                        continue
    except Exception:
        pass
    return None


def _read_image_dimensions(filepath: str) -> Tuple[int, int]:
    """讀取圖片寬高"""
    if not PILLOW_AVAILABLE:
        return (0, 0)
    try:
        with Image.open(filepath) as img:
            return img.size  # (width, height)
    except Exception:
        return (0, 0)


def _get_mtime(filepath: str) -> Optional[datetime]:
    """取得檔案修改時間"""
    try:
        ts = os.path.getmtime(filepath)
        return datetime.fromtimestamp(ts)
    except Exception:
        return None


# ────────── 掃描 staging ──────────

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.heic', '.webp'}
PDF_EXTS = {'.pdf'}
ALL_EXTS = IMAGE_EXTS | PDF_EXTS


def scan_staging(staging_dir: str) -> List[StagingFile]:
    """
    掃描 staging 資料夾，回傳所有可處理的檔案清單（按時間排序）。

    Args:
        staging_dir: staging 資料夾路徑

    Returns:
        StagingFile 清單，依 sort_time 排序
    """
    if not os.path.isdir(staging_dir):
        return []

    results: List[StagingFile] = []

    for fname in os.listdir(staging_dir):
        fpath = os.path.join(staging_dir, fname)
        if not os.path.isfile(fpath):
            continue

        ext = os.path.splitext(fname)[1].lower()
        if ext not in ALL_EXTS:
            continue

        file_type = "image" if ext in IMAGE_EXTS else "pdf"
        size_kb = os.path.getsize(fpath) / 1024.0
        mtime = _get_mtime(fpath)

        exif_time = None
        width, height = 0, 0
        if file_type == "image":
            exif_time = _read_exif_time(fpath)
            width, height = _read_image_dimensions(fpath)

        results.append(StagingFile(
            path=fpath,
            filename=fname,
            file_type=file_type,
            size_kb=size_kb,
            exif_time=exif_time,
            mtime=mtime,
            width=width,
            height=height,
        ))

    results.sort(key=lambda f: f.sort_time)
    return results


# ────────── 時間聚類 ──────────

def group_by_time(
    files: List[StagingFile],
    threshold_minutes: int = 30,
) -> List[List[StagingFile]]:
    """
    依 EXIF / 修改時間將照片聚類。
    同一群組內，任兩張連續照片的時間差 ≤ threshold_minutes。

    Args:
        files: 已排序的 StagingFile 清單
        threshold_minutes: 同群門檻（分鐘）

    Returns:
        [[group1_files], [group2_files], ...]
    """
    if not files:
        return []

    groups: List[List[StagingFile]] = []
    current_group: List[StagingFile] = [files[0]]

    for i in range(1, len(files)):
        prev_time = files[i - 1].sort_time
        curr_time = files[i].sort_time
        diff = (curr_time - prev_time).total_seconds() / 60.0

        if diff <= threshold_minutes:
            current_group.append(files[i])
        else:
            groups.append(current_group)
            current_group = [files[i]]

    if current_group:
        groups.append(current_group)

    return groups


# ────────── 分派（搬移檔案） ──────────

def dispatch_files(
    assignments: List[FileAssignment],
    attachments_root: str,
    move: bool = True,
) -> List[DispatchResult]:
    """
    將 staging 中的檔案搬移（或複製）到正確的 attachments 子資料夾。

    目標路徑：
        {attachments_root}/{date_folder}/{series_no}_{suffix_combo}/{role}.ext

    Args:
        assignments: 分派指令清單
        attachments_root: attachments 根目錄
        move: True=搬移 False=複製

    Returns:
        DispatchResult 清單
    """
    results: List[DispatchResult] = []

    for assign in assignments:
        target_dir = os.path.join(
            attachments_root,
            assign.date_folder,
            assign.folder_name,
        )
        target_path = os.path.join(target_dir, assign.target_filename)

        try:
            # 檢查來源是否存在
            if not os.path.isfile(assign.source_path):
                results.append(DispatchResult(
                    assignment=assign, success=False,
                    error=f"來源不存在: {assign.source_path}"
                ))
                continue

            # 檢查目標是否已存在
            if os.path.exists(target_path):
                results.append(DispatchResult(
                    assignment=assign, success=False,
                    target_path=target_path,
                    error=f"目標已存在: {target_path}"
                ))
                continue

            # 建立目標資料夾
            os.makedirs(target_dir, exist_ok=True)

            # 搬移或複製
            if move:
                shutil.move(assign.source_path, target_path)
            else:
                shutil.copy2(assign.source_path, target_path)

            results.append(DispatchResult(
                assignment=assign, success=True,
                target_path=target_path,
            ))

        except Exception as e:
            results.append(DispatchResult(
                assignment=assign, success=False,
                error=str(e),
            ))

    return results


# ────────── 輔助：產出摘要 ──────────

def dispatch_summary(results: List[DispatchResult]) -> str:
    """產出分派結果摘要文字"""
    ok = [r for r in results if r.success]
    fail = [r for r in results if not r.success]

    lines = [f"分派完成：{len(ok)} 成功，{len(fail)} 失敗"]

    if ok:
        lines.append("\n✓ 成功：")
        for r in ok:
            a = r.assignment
            lines.append(f"  {a.source_path} → {r.target_path}")

    if fail:
        lines.append("\n✗ 失敗：")
        for r in fail:
            a = r.assignment
            lines.append(f"  {os.path.basename(a.source_path)}: {r.error}")

    return "\n".join(lines)


# ────────── 建議：從 EXIF 日期推薦 date_folder ──────────

def suggest_date_folder(sf: StagingFile) -> str:
    """從 EXIF/mtime 建議日期資料夾名稱（YYYYMMDD）"""
    t = sf.exif_time or sf.mtime
    if t:
        return t.strftime("%Y%m%d")
    return datetime.now().strftime("%Y%m%d")


# ────────── 初始化 staging 資料夾 ──────────

def ensure_staging_dir(base_dir: str) -> str:
    """確保 staging 資料夾存在，回傳路徑"""
    staging_dir = os.path.join(base_dir, "staging")
    os.makedirs(staging_dir, exist_ok=True)
    return staging_dir


# ────────── 縮圖快取 ──────────

def make_thumbnail(filepath: str, max_size: int = 200) -> Optional[bytes]:
    """
    產生縮圖 bytes (PNG 格式, 記憶體中)。
    用於 GUI 顯示，不寫入磁碟。

    Args:
        filepath: 圖片路徑
        max_size: 縮圖最大邊長 px

    Returns:
        PNG bytes 或 None
    """
    if not PILLOW_AVAILABLE:
        return None
    try:
        from io import BytesIO
        with Image.open(filepath) as img:
            # 先修正方向
            try:
                from image_processor import fix_orientation
                img = fix_orientation(img)
            except ImportError:
                pass
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
    except Exception:
        return None
