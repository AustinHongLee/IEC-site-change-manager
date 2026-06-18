# -*- coding: utf-8 -*-
"""
settings_manager.py — 用戶設定管理器

功能：
- JSON 持久化儲存用戶設定
- 記住上次使用的路徑
- 自動載入/儲存
"""

import os
import json
from typing import Any
from datetime import datetime


# 設定檔路徑（放在專案資料夾內）
def _get_settings_path() -> str:
    """取得 settings.json 的路徑"""
    here = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(here, os.pardir))
    return os.path.join(base_dir, "settings.json")


def _atomic_write_json(path: str, data: dict):
    """原子性儲存設定檔，避免寫到一半中斷造成 settings.json 損壞。"""
    tmp = path + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


# 預設設定
DEFAULT_SETTINGS = {
    # 路徑設定
    "paths": {
        "drawing_list": "",           # DWG LIST 檔案路徑
        "attachments_root": "",       # 附件根目錄（通常不需要改）
        "output_root": "",            # 輸出根目錄
        "pdf_output": "",             # PDF 輸出目錄
        "last_browse_dir": "",        # 上次瀏覽的目錄
        "weld_control_table": "",     # 焊口管制表路徑（必填）
        "prefab_drawing_dir": "",     # 預製圖 PDF 來源目錄
        "soffice_path": "",           # LibreOffice soffice.exe 路徑（非 COM PDF）
    },
    
    # 焊口管制表設定
    "weld_control": {
        "sheet_name": "焊口編號明細",      # 工作表名稱
        "col_serial": "流水號",            # 流水號欄位名稱（主鍵1）
        "col_weld_no": "焊口編號",         # 焊口編號欄位名稱（主鍵2）
        "serial_format": "raw",            # 流水號格式: "raw"=原始, "pad4"=補零4位
        "auto_sync": True,                 # 自動同步新增焊口
        "check_duplicate": True,           # 檢查重複焊口
        # 動態欄位配置：可自定義要同步的欄位
        "dynamic_columns": [
            {"name": "LINE NO", "source": "line_no", "required": False},
            {"name": "SIZE", "source": "size", "required": False},
            {"name": "SCH", "source": "sch", "required": False},
            {"name": "DWG NO", "source": "dwg_no", "required": False},
            {"name": "登錄日期", "source": "auto_date", "required": False},
            {"name": "修改單編號", "source": "report_id", "required": False},
            {"name": "備註", "source": "remark", "required": False},
        ],
    },
    
    # DWG LIST 設定
    "dwg_list": {
        "sheet_name": "DRAWING LIST",      # 工作表名稱
        "col_serial": "NO",                # 流水號欄位名稱（主鍵）
        "serial_format": "raw",            # 流水號格式: "raw"=原始, "pad4"=補零4位
        "enabled": True,                   # 是否啟用 DWG LIST 查詢
        # 動態欄位配置：定義要從 DWG LIST 取得的欄位
        "dynamic_columns": [
            {"name": "DWG NO", "target": "dwg_no"},
            {"name": "DWG名稱", "target": "dwg_name"},
            {"name": "REV", "target": "rev"},
        ],
    },
    
    # 執行設定
    "runtime": {
        "export_pdf": True,
        "skip_unchanged": True,
        "debug_mode": False,
        "auto_preprocess_images": True,
        "preprocess_max_edge": 1280,
        "preprocess_quality": 85,
    },
    
    # 記錄
    "meta": {
        "last_modified": "",
        "version": "1.3",
    }
}


class SettingsManager:
    """設定管理器（單例）"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._settings_path = _get_settings_path()
        self._settings = {}
        self._load()
        self._initialized = True
    
    def _load(self):
        """載入設定"""
        if os.path.exists(self._settings_path):
            try:
                with open(self._settings_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                # 合併預設值（處理新增的設定項目）
                self._settings = self._merge_defaults(loaded)
            except Exception as e:
                print(f"⚠️ 載入設定失敗: {e}，使用預設值")
                self._settings = DEFAULT_SETTINGS.copy()
        else:
            self._settings = DEFAULT_SETTINGS.copy()
    
    def _merge_defaults(self, loaded: dict) -> dict:
        """合併載入的設定與預設值（確保新設定項不會遺失）"""
        result = {}
        for key, default_value in DEFAULT_SETTINGS.items():
            if key not in loaded:
                result[key] = default_value
            elif isinstance(default_value, dict):
                result[key] = {**default_value, **loaded.get(key, {})}
            else:
                result[key] = loaded[key]
        return result
    
    def save(self):
        """儲存設定"""
        self._settings["meta"]["last_modified"] = datetime.now().isoformat()
        try:
            _atomic_write_json(self._settings_path, self._settings)
        except Exception as e:
            print(f"⚠️ 儲存設定失敗: {e}")
    
    def get(self, section: str, key: str, default: Any = None) -> Any:
        """取得設定值"""
        return self._settings.get(section, {}).get(key, default)
    
    def set(self, section: str, key: str, value: Any, auto_save: bool = True):
        """設定值"""
        if section not in self._settings:
            self._settings[section] = {}
        self._settings[section][key] = value
        if auto_save:
            self.save()
    
    def get_path(self, key: str) -> str:
        """取得路徑設定（便捷方法）"""
        return self.get("paths", key, "")
    
    def set_path(self, key: str, value: str, auto_save: bool = True):
        """設定路徑（便捷方法）"""
        self.set("paths", key, value, auto_save)
    
    def get_runtime(self, key: str, default: Any = None) -> Any:
        """取得執行設定"""
        return self.get("runtime", key, default)
    
    def set_runtime(self, key: str, value: Any, auto_save: bool = True):
        """設定執行設定"""
        self.set("runtime", key, value, auto_save)
    
    @property
    def all_settings(self) -> dict:
        """取得所有設定（唯讀）"""
        return self._settings.copy()


# 全域實例
_settings_manager = None

def get_settings() -> SettingsManager:
    """取得設定管理器"""
    global _settings_manager
    if _settings_manager is None:
        _settings_manager = SettingsManager()
    return _settings_manager


# ========= 便捷函數 =========

def get_drawing_list_path() -> str:
    """
    取得 DWG LIST 路徑
    優先順序：
    1. settings.json 中的設定
    2. 自動搜尋最新版本
    3. 寫死的預設路徑
    """
    import glob
    import re
    
    sm = get_settings()
    saved_path = sm.get_path("drawing_list")
    
    # 1. 如果有儲存的路徑且檔案存在，使用它
    if saved_path and os.path.exists(saved_path):
        return saved_path
    
    # 2. 自動搜尋
    here = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.abspath(os.path.join(here, os.pardir))
    gl05_dir = os.path.dirname(base_dir)
    
    pattern = os.path.join(gl05_dir, "可寧衛_DRAWING LIST*.xlsm")
    matches = glob.glob(pattern)
    
    if matches:
        # 依日期排序
        def extract_date(path):
            filename = os.path.basename(path)
            m = re.search(r'(\d{2,3})\.(\d{2})\.(\d{2})', filename)
            if m:
                y, mon, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return y * 10000 + mon * 100 + d
            return os.path.getmtime(path)
        
        matches.sort(key=extract_date, reverse=True)
        found_path = matches[0]
        
        # 自動儲存找到的路徑
        sm.set_path("drawing_list", found_path)
        return found_path
    
    # 3. 沒找到就留空，交由使用者在設定頁選擇
    return ""


def remember_browse_directory(path: str):
    """記住上次瀏覽的目錄"""
    if os.path.isfile(path):
        path = os.path.dirname(path)
    get_settings().set_path("last_browse_dir", path)


def get_last_browse_directory() -> str:
    """取得上次瀏覽的目錄"""
    return get_settings().get_path("last_browse_dir") or ""


def get_weld_control_table_path() -> str:
    """取得焊口管制表路徑"""
    return get_settings().get_path("weld_control_table") or ""


def set_weld_control_table_path(path: str):
    """設定焊口管制表路徑"""
    get_settings().set_path("weld_control_table", path)


def get_weld_control_config() -> dict:
    """取得焊口管制表設定"""
    sm = get_settings()
    config = {
        "file_path": get_weld_control_table_path(),
        "sheet_name": sm.get("weld_control", "sheet_name", "焊口編號明細"),
        "col_serial": sm.get("weld_control", "col_serial", "流水號"),
        "col_weld_no": sm.get("weld_control", "col_weld_no", "焊口編號"),
        "auto_sync": sm.get("weld_control", "auto_sync", True),
        "check_duplicate": sm.get("weld_control", "check_duplicate", True),
        "dynamic_columns": sm.get("weld_control", "dynamic_columns", []),
    }
    return config


def set_weld_control_config(config: dict):
    """設定焊口管制表設定"""
    sm = get_settings()
    for key, value in config.items():
        if key != "file_path":  # file_path 存在 paths 區
            sm.set("weld_control", key, value, auto_save=False)
    sm.save()


def get_weld_dynamic_columns() -> list:
    """取得焊口管制表的動態欄位配置"""
    sm = get_settings()
    return sm.get("weld_control", "dynamic_columns", [])


def set_weld_dynamic_columns(columns: list):
    """設定焊口管制表的動態欄位配置"""
    sm = get_settings()
    sm.set("weld_control", "dynamic_columns", columns)


def is_weld_control_configured() -> bool:
    """檢查焊口管制表是否已設定"""
    path = get_weld_control_table_path()
    return bool(path) and os.path.exists(path)


# ========= DWG LIST 相關函數 =========

def get_dwg_list_config() -> dict:
    """取得 DWG LIST 設定"""
    sm = get_settings()
    return {
        "file_path": get_drawing_list_path(),
        "sheet_name": sm.get("dwg_list", "sheet_name", "DRAWING LIST"),
        "col_serial": sm.get("dwg_list", "col_serial", "NO"),
        "serial_format": sm.get("dwg_list", "serial_format", "raw"),
        "enabled": sm.get("dwg_list", "enabled", True),
        "dynamic_columns": sm.get("dwg_list", "dynamic_columns", []),
    }


def set_dwg_list_config(config: dict):
    """設定 DWG LIST 設定"""
    sm = get_settings()
    for key, value in config.items():
        if key != "file_path":  # file_path 存在 paths 區
            sm.set("dwg_list", key, value, auto_save=False)
    sm.save()


def get_dwg_dynamic_columns() -> list:
    """取得 DWG LIST 的動態欄位配置"""
    sm = get_settings()
    return sm.get("dwg_list", "dynamic_columns", [])


def set_dwg_dynamic_columns(columns: list):
    """設定 DWG LIST 的動態欄位配置"""
    sm = get_settings()
    sm.set("dwg_list", "dynamic_columns", columns)


def set_drawing_list_path(path: str):
    """設定 DWG LIST 路徑"""
    get_settings().set_path("drawing_list", path)


# ========= 預製圖路徑相關函數 =========

def get_prefab_drawing_dir() -> str:
    """取得預製圖 PDF 來源目錄"""
    return get_settings().get_path("prefab_drawing_dir") or ""


def set_prefab_drawing_dir(path: str):
    """設定預製圖 PDF 來源目錄"""
    get_settings().set_path("prefab_drawing_dir", path)


def get_soffice_path() -> str:
    """取得 LibreOffice soffice.exe 路徑。"""
    return get_settings().get_path("soffice_path") or ""


def set_soffice_path(path: str):
    """設定 LibreOffice soffice.exe 路徑。"""
    get_settings().set_path("soffice_path", path)


if __name__ == "__main__":
    # 測試
    print("=== 設定管理器測試 ===")
    sm = get_settings()
    print(f"設定檔: {sm._settings_path}")
    print(f"DWG LIST: {get_drawing_list_path()}")
    print(f"所有設定: {json.dumps(sm.all_settings, ensure_ascii=False, indent=2)}")
