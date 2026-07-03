# -*- coding: utf-8 -*-
"""co_main_app.py — 新版主介面的 pywebview 啟動器（原生桌面視窗，非瀏覽器）

開一個原生視窗載入 `co_main_web/index.html`，並把「主介面橋」(`MainBridge`)
當 js_api 注入——前端 `await pywebview.api.pricebook()` 直呼到橋（非 HTTP）。
目前橋只做唯讀（料表 / 記錄）；寫入 / 產出 / 中央查價等之後逐刀加。

跑法（Windows）：
    pip install pywebview
    python control/co_main_app.py
需求：Windows 的 WebView2 Runtime（Win11 / 更新過的 Win10 通常已內建；缺的話會給提示）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))  # 讓 co_main_bridge 等同層裸 import 可用
_INDEX = _HERE / "co_main_web" / "index.html"


def main() -> int:
    try:
        import webview  # pywebview
    except ImportError:
        print("✗ 需要 pywebview：請先  pip install pywebview")
        return 2

    if not _INDEX.exists():
        print(f"✗ 找不到前端：{_INDEX}")
        return 4

    from co_main_bridge import MainBridge
    bridge = MainBridge(_HERE.parent)  # 專案根目錄，底下有 records/（舊系統資料）

    window = webview.create_window(
        "工務修改單 · 新版 GUI",
        str(_INDEX),
        js_api=bridge,
        width=1280,
        height=820,
        min_size=(980, 640),
    )

    def _pick_file(kind: str):
        if kind == "pdf":
            file_types = ("PDF 檔 (*.pdf)", "所有檔案 (*.*)")
        elif kind == "image":
            file_types = ("圖片 (*.jpg;*.jpeg;*.png)", "所有檔案 (*.*)")
        else:
            file_types = ("Excel (*.xlsx;*.xls)", "所有檔案 (*.*)")
        result = window.create_file_dialog(webview.OPEN_DIALOG, file_types=file_types)
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else result

    bridge._pick_file_fn = _pick_file

    def _save_file(kind: str, default_name: str = ""):
        file_types = ("Excel 檔 (*.xlsx)",) if kind == "excel" else ("所有檔案 (*.*)",)
        result = window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename=default_name, file_types=file_types)
        if not result:
            return None
        return result if isinstance(result, str) else (result[0] if result else None)

    bridge._save_file_fn = _save_file

    def _pick_folder():
        result = window.create_file_dialog(webview.FOLDER_DIALOG)
        if not result:
            return None
        return result if isinstance(result, str) else (result[0] if result else None)

    bridge._pick_folder_fn = _pick_folder

    debug = os.environ.get("CO_MAIN_DEBUG", "0") == "1"  # 開發時設 CO_MAIN_DEBUG=1 可開 DevTools
    try:
        webview.start(debug=debug)
        return 0
    except Exception as exc:  # 多半是缺 WebView2 Runtime
        print(
            "✗ 視窗啟動失敗：" + str(exc) + "\n"
            "  Windows 可能缺 WebView2 Runtime。\n"
            "  解法：到 Microsoft 下載「Evergreen WebView2 Runtime」安裝後再試。"
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
