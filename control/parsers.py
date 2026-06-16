# -*- coding: utf-8 -*-
"""
parsers.py — 資料解析模組

包含：
- 資料夾名稱解析（single/group 模式偵測）
- GroupWeld.txt 解析
- note.txt / materials.txt 解析
- 焊口代碼解析
"""

import os
import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


# ========= 正規表達式 =========
GROUP_FOLDER_RE = re.compile(r'^(\d+)_([A-Za-z])G$')   # 101_AG
SINGLE_FOLDER_RE = re.compile(r'^(\d+?)_(.+)$')        # 234_15r1_12r1

# GroupWeld.txt 格式
GROUP_WELD_LINE_RE_NEW = re.compile(r'^\s*(\d+)([A-Za-z])(\d+(?:\.\d+)?)\s*$')
GROUP_WELD_LINE_RE_OLD = re.compile(r'^\s*([A-Za-z0-9\.]+)\s*_\s*([0-9]+(?:\.[0-9]+)?)\s*$')


# ========= 資料結構 =========
@dataclass
class WeldToken:
    """焊口資訊"""
    raw: str
    weld_no: Optional[str] = None
    tag: Optional[str] = None
    size: Optional[float] = None
    is_cut: bool = False
    
    @property
    def code(self) -> str:
        """取得焊口代碼（如 15a）"""
        if self.weld_no and self.tag:
            return f"{self.weld_no}{self.tag}"
        return self.raw or ""
    
    def to_dict(self) -> Dict:
        """轉為 dict（向後相容）"""
        return {
            'raw': self.raw,
            'weld_no': self.weld_no,
            'tag': self.tag,
            'size': self.size,
            'is_cut': self.is_cut,
        }


@dataclass
class FolderInfo:
    """資料夾解析結果"""
    folder_name: str
    folder_path: str
    mode: str  # "single" or "group"
    series_no: str
    extra: str  # suffix_combo for single, group_tag for group
    tokens: List[WeldToken] = None
    note_text: str = ""
    materials_text: str = ""
    
    def __post_init__(self):
        if self.tokens is None:
            self.tokens = []


# ========= 資料夾解析 =========
def detect_mode(folder_name: str) -> Tuple[str, str, str]:
    """
    解析資料夾名稱
    
    Returns:
        (mode, series_no, extra)
        - mode: "group" 或 "single"
        - series_no: 4位數的系列號
        - extra: 群組標籤(如"A") 或 suffix_combo(如"15r1_12r1")
    
    Raises:
        ValueError: 無法辨識的資料夾名稱
    """
    m = GROUP_FOLDER_RE.match(folder_name)
    if m:
        return ("group", m.group(1).zfill(4), m.group(2).upper())
    
    m = SINGLE_FOLDER_RE.match(folder_name)
    if m:
        return ("single", m.group(1).zfill(4), m.group(2))
    
    raise ValueError(f"Unsupported folder name: {folder_name}")


# ========= 焊口解析 =========
def parse_weld_code_basic(code: str) -> Dict:
    """解析基本焊口代碼"""
    s = code.strip()
    m = re.match(r'^(\d+)(.*)$', s)
    if not m:
        return {"raw": s, "weld_no": s, "tag": "", "is_cut": False}
    
    weld_no = m.group(1)
    tail = (m.group(2) or "").lower()
    tag = ""
    if re.match(r'^[a-z]', tail):
        tag = tail[0]
    is_cut = 'r' in tail
    return {"raw": s, "weld_no": weld_no, "tag": tag, "is_cut": is_cut}


def parse_suffix_combo(suffix_combo: str) -> List[WeldToken]:
    """
    解析 single 模式的 suffix（如 "15r1_12r1_10a2"）
    """
    tokens = []
    for tok in suffix_combo.split('_'):
        tok = tok.strip()
        if not tok:
            continue
        
        m = re.fullmatch(r'(?P<weld>\d+)(?P<tag>[A-Za-z])(?P<size>\d+(?:\.\d+)?)?', tok)
        if m:
            weld = m.group('weld')
            tag = m.group('tag')
            size_str = m.group('size')
            size = float(size_str) if size_str else None
            is_cut = tag.lower() == 'r'
            tokens.append(WeldToken(
                raw=tok, weld_no=weld, tag=tag, size=size, is_cut=is_cut
            ))
        else:
            m2 = re.fullmatch(r'(?P<weld>\d+)', tok)
            if m2:
                tokens.append(WeldToken(
                    raw=tok, weld_no=m2.group('weld'), tag='', size=None, is_cut=False
                ))
            else:
                tokens.append(WeldToken(
                    raw=tok, weld_no=None, tag=None, size=None, is_cut=False
                ))
    return tokens


def read_groupweld_txt(folder_path: str) -> List[WeldToken]:
    """
    讀取 GroupWeld.txt
    
    支援格式：
      1) 新式：<weldNo><tag><size>   例如：15a0.5、12r1、9b2
      2) 舊式：<code>_<size>         例如：15a0.5_0.5、12r1_1
    
    Raises:
        FileNotFoundError: 找不到 GroupWeld.txt
        ValueError: 格式錯誤
    """
    txt_path = os.path.join(folder_path, "GroupWeld.txt")
    if not os.path.exists(txt_path):
        raise FileNotFoundError(f"GroupWeld.txt not found in {folder_path}")
    
    tokens: List[WeldToken] = []
    with open(txt_path, "r", encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            
            # 新式格式
            m = GROUP_WELD_LINE_RE_NEW.match(s)
            if m:
                weld_no, tag, size_str = m.groups()
                try:
                    size_val = float(size_str)
                except ValueError:
                    size_val = None
                tokens.append(WeldToken(
                    raw=s,
                    weld_no=weld_no,
                    tag=tag,
                    size=size_val,
                    is_cut=tag.lower() == "r",
                ))
                continue
            
            # 舊式格式
            m2 = GROUP_WELD_LINE_RE_OLD.match(s)
            if m2:
                code, size_str = m2.groups()
                base = parse_weld_code_basic(code)
                try:
                    size_val = float(size_str)
                except ValueError:
                    size_val = None
                tokens.append(WeldToken(
                    raw=s,
                    weld_no=base["weld_no"],
                    tag=base["tag"],
                    size=size_val,
                    is_cut=base["is_cut"],
                ))
                continue
            
            raise ValueError(f"Invalid GroupWeld format at line {ln}: {s}")
    
    return tokens


# ========= note / materials 解析 =========
def read_note_and_materials(folder_path: str) -> Tuple[str, str]:
    """
    讀取 note.txt 和 materials.txt
    
    Returns:
        (note_text, materials_text)
    """
    note_path = os.path.join(folder_path, 'note.txt')
    materials_path = os.path.join(folder_path, 'materials.txt')
    
    note_text = ""
    materials_lines: List[str] = []
    
    if os.path.exists(note_path):
        with open(note_path, 'r', encoding='utf-8') as f:
            lines = [ln.rstrip() for ln in f.readlines()]
        for ln in lines:
            if re.match(r'^\s*材料\s*[:：]', ln):
                materials_lines.append(re.sub(r'^\s*材料\s*[:：]\s*', '', ln).strip())
            else:
                note_text += (ln + '\n')
        note_text = note_text.strip()
    
    if os.path.exists(materials_path):
        with open(materials_path, 'r', encoding='utf-8') as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    materials_lines.append(ln)
    
    materials_text = "；".join(materials_lines) if materials_lines else ""
    return note_text, materials_text


def parse_materials_txt(folder_path: str) -> List[Dict[str, str]]:
    """解析 materials.txt 檔案，回傳結構化材料清單

    支援格式：
      6 欄（新版）：零件, 尺寸, SCH, 材質, 數量 單位, 備註
      4 欄（舊版）：零件, 尺寸, 材質, 數量 單位
    """
    materials: List[Dict[str, str]] = []
    mat_path = os.path.join(folder_path, "materials.txt")

    if not os.path.exists(mat_path):
        return materials

    try:
        with open(mat_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('-'):
                continue

            parts = [p.strip() for p in line.split(',')]

            if len(parts) >= 6:
                component, size, schedule, material = parts[0], parts[1], parts[2], parts[3]
                qty_unit, remark = parts[4], parts[5]
            elif len(parts) >= 4:
                component, size, material = parts[0], parts[1], parts[2]
                schedule, qty_unit, remark = "", parts[3], ""
            else:
                continue

            qty_match = re.match(r'^(\d+(?:\.\d+)?)\s*(.*)$', qty_unit)
            if qty_match:
                qty = qty_match.group(1)
                unit = qty_match.group(2) or "個"
            else:
                qty = qty_unit
                unit = "個"

            materials.append({
                "零件類型": component,
                "尺寸": size,
                "SCH": schedule,
                "材質": material,
                "數量": qty,
                "單位": unit,
                "備註": remark,
            })
    except Exception as e:
        print(f"⚠️ 解析 materials.txt 失敗：{e}")

    return materials


# ========= 說明文字建構 =========
def weld_code_list(tokens: List[WeldToken]) -> List[str]:
    """取得焊口代碼列表"""
    return [t.code for t in tokens if t.code]


def build_auto_description(
    tokens: List[WeldToken],
    note_text: str,
    show_dims: bool = False
) -> str:
    """建構自動說明文字"""
    codes = weld_code_list(tokens)
    codes_str = '、'.join([c for c in codes if c])
    
    dims = [f"{t.weld_no}{t.tag}={t.size}"
            for t in tokens if t.weld_no and t.tag and t.size is not None]
    dims_str = '；'.join(dims)
    
    if note_text:
        desc = note_text.strip()
        if codes_str:
            if not desc.endswith(('。', '！', '!', '.')):
                desc += "。"
            desc += f"\n新增焊口：{codes_str}"
        if show_dims and dims:
            desc += f"\n尺寸：{dims_str}"
        return desc
    
    # 無 note 時自動產生
    if tokens and all(t.is_cut for t in tokens):
        desc = f"原管線過長，故裁切後重新銲接，新增焊口：{codes_str}"
    else:
        desc = f"原管線長度不足，故加長處理，新增焊口：{codes_str}"
    
    if show_dims and dims:
        desc += f"\n尺寸：{dims_str}"
    return desc


# ========= 完整資料夾解析 =========
def parse_folder(folder_path: str) -> FolderInfo:
    """
    完整解析一個資料夾
    
    Returns:
        FolderInfo 物件，包含所有解析結果
    
    Raises:
        ValueError: 資料夾名稱無法辨識
        FileNotFoundError: group 模式找不到 GroupWeld.txt
    """
    folder_name = os.path.basename(folder_path)
    mode, series_no, extra = detect_mode(folder_name)
    
    # 解析焊口
    if mode == "group":
        tokens = read_groupweld_txt(folder_path)
    else:
        tokens = parse_suffix_combo(extra)
    
    # 讀取 note/materials
    note_text, materials_text = read_note_and_materials(folder_path)
    
    return FolderInfo(
        folder_name=folder_name,
        folder_path=folder_path,
        mode=mode,
        series_no=series_no,
        extra=extra,
        tokens=tokens,
        note_text=note_text,
        materials_text=materials_text,
    )
