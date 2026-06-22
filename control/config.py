# -*- coding: utf-8 -*-
"""
config.py — 所有設定、常數、路徑配置

集中管理：
- 路徑設定（自動偵測 base_dir）
- 模板配置（6-slot / 27-slot）
- 執行參數（DEBUG、EXPORT_PDF 等）
"""

import os
import sys
from dataclasses import dataclass
from typing import Dict, Any

from resources import resolve_project_dir, resolve_resource_dir, resource_path

# ========= 自動定位 base_dir =========
def resolve_base_dir() -> str:
    """自動定位到「工務修改單」這層資料夾"""
    return resolve_project_dir()


# ========= 路徑常數 =========
BASE_DIR = resolve_base_dir()
RESOURCE_DIR = resolve_resource_dir()
ATTACHMENTS_ROOT = os.path.join(BASE_DIR, 'attachments')
OUTPUT_ROOT = os.path.join(BASE_DIR, 'output')
PDF_OUTPUT_DIR = os.path.join(BASE_DIR, 'pdf')
RECORD_XLSX_PATH = os.path.join(BASE_DIR, '管線修改紀錄清單.xlsx')
LOGS_DIR = os.path.join(BASE_DIR, 'logs')

TEMPLATE_PATH_6 = resource_path('template', 'template_file.xlsm')
TEMPLATE_PATH_27 = resource_path('template', 'template_file_27w.xlsm')


# ========= DWG LIST（從設定管理器取得）=========
# 延遲載入，避免循環 import
_drawing_list_path_cache = None

def get_drawing_list_path() -> str:
    """取得 DWG LIST 路徑（從 settings.json 或自動偵測）"""
    global _drawing_list_path_cache
    if _drawing_list_path_cache is None:
        try:
            from settings_manager import get_drawing_list_path as _get_dwg
            _drawing_list_path_cache = _get_dwg()
        except ImportError:
            _drawing_list_path_cache = ""
    return _drawing_list_path_cache


# 為了向後兼容，保留變數
# 注意：這是在 import 時執行，之後若更改設定需要重新 import
try:
    from settings_manager import get_drawing_list_path as _get_dwg_path
    DRAWING_LIST_PATH = _get_dwg_path()
except ImportError:
    DRAWING_LIST_PATH = ""


# ========= 執行參數 =========
@dataclass
class RuntimeConfig:
    """可在 GUI 中調整的執行參數"""
    debug_mode: bool = False
    export_pdf: bool = True
    skip_unchanged: bool = True
    show_dims_in_desc: bool = False
    
    # 圖片預處理參數
    auto_preprocess_images: bool = True   # 流程中自動預處理圖片
    preprocess_max_edge: int = 1280       # 最大邊像素（保持比例）
    preprocess_quality: int = 85          # JPEG 壓縮品質 (1-95)
    preprocess_backup: bool = True        # 備份原檔為 .orig
    
    # 完整性檢查參數
    integrity_level_default: int = 0  # 0: exist+size; 1: +pdf readable; 2: stronger
    min_xlsm_kb: float = 0.3
    min_pdf_kb: float = 0.5
    max_retries: int = 2
    retry_sleep: float = 0.3


# 全域預設配置（可被 GUI 覆寫）
RUNTIME = RuntimeConfig()


# ========= 模板常數 =========
SHEET_NAME = "template"

# 6-slot（舊模板）
TEMPLATE_6_CONFIG = {
    "path": TEMPLATE_PATH_6,
    "sheet": SHEET_NAME,
    "before_range": "C9:AI23",
    "after_range": "C24:AI38",
    "desc_cell": "G7",
    "line_cell": "G4",
    "dwg_cell": "G5",
    "id_cell": "AD3",
    "date_cell": "AD4",
    "series_cell": "AD5",
    "weld_slots": ['G6', 'I6', 'K6', 'M6', 'O6', 'Q6'],
    "overflow_behavior": "ellipsis_last_cell",
}

# 27-slot（新模板）
TEMPLATE_27_CONFIG = {
    "path": TEMPLATE_PATH_27,
    "sheet": SHEET_NAME,
    "before_ranges": ["C11:AI24", "C25:AI39"],
    "after_ranges": ["C40:AI53", "C54:AI67"],
    "desc_cell": "G9",
    "line_cell": "G4",
    "dwg_cell": "G5",
    "id_cell": "AD3",
    "date_cell": "AD4",
    "series_cell": "AD5",
    "weld_slots_grid": [
        ["G6", "I6", "K6", "M6", "O6", "Q6", "S6", "U6", "W6"],
        ["G7", "I7", "K7", "M7", "O7", "Q7", "S7", "U7", "W7"],
        ["G8", "I8", "K8", "M8", "O8", "Q8", "S8", "U8", "W8"],
    ],
    "overflow_behavior": "ellipsis_last_cell",
}

# 模板索引
TEMPLATE_BY_KEY = {
    "single_6": TEMPLATE_6_CONFIG,
    "single_27w": TEMPLATE_27_CONFIG,
}


# ========= 記錄表頭定義 =========
RECORD_HEADER = [
    "日期", "報告編號", "Series NO", "LINE NUMBER", "DWG NO",
    "變更類型", "焊口清單", "焊口與尺寸", "說明", "材料附加",
    "附件PDF", "資料夾名", "before.jpg", "after.jpg", "內容指紋"
]

DETAIL_HEADER = [
    "項目", "紀錄編號", "修改日期", "修改原因敘述",
    "Series NO", "DWG NO", "焊口編號", "焊口尺寸",
    "係數", "單價/DB", "金額", "備註"
]

MATERIALS_HEADER = [
    "項目", "報告編號", "修改日期", "Series NO",
    "零件類型", "尺寸", "SCH", "材質",
    "數量", "單位", "單價", "金額", "備註"
]


def get_template_for_mode(mode: str, token_count: int) -> Dict[str, Any]:
    """根據模式和焊口數量選擇模板"""
    if mode == "group" or token_count > 6:
        return TEMPLATE_BY_KEY["single_27w"]
    return TEMPLATE_BY_KEY["single_6"]


def use_dual_images(mode: str, token_count: int) -> bool:
    """判斷是否使用雙圖模式"""
    return mode == "group" or token_count > 6


def print_config_info():
    """印出目前設定資訊"""
    print(f"▶ 基準資料夾 base_dir = {BASE_DIR}")
    print(f"▶ 程式資源資料夾       = {RESOURCE_DIR}")
    print(f"▶ 附件資料夾         = {ATTACHMENTS_ROOT}")
    print(f"▶ 模板(6/27)         = {TEMPLATE_PATH_6}")
    print(f"                      {TEMPLATE_PATH_27}")
    print(f"▶ DWG LIST           = {DRAWING_LIST_PATH}")
    print(f"▶ 輸出 output/pdf    = {OUTPUT_ROOT} / {PDF_OUTPUT_DIR}")
    print(f"▶ 記錄清單            = {RECORD_XLSX_PATH}")
