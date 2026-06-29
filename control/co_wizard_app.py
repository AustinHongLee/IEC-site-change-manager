# -*- coding: utf-8 -*-
"""co_wizard_app.py — 新精靈的 pywebview 啟動器（原生桌面視窗，非瀏覽器）

職責很薄：開一個原生視窗、把 `ChangeOrderBridge` 當 js_api 接上、注入原生檔案
對話框、處理 WebView2 缺失等啟動失敗。**所有邏輯都在橋與引擎，這裡不放邏輯。**

跑法（Windows）：
    pip install pywebview
    python control/co_wizard_app.py
需求：Windows 的 WebView2 Runtime（Win11 / 更新過的 Win10 通常已內建；缺的話會給提示）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))  # 讓 co_bridge / change_order... 這些同層裸 import 可用

_INDEX = _HERE / "co_wizard_web" / "index.html"


def _resolve_attachments_root() -> Path:
    """輸出根目錄：優先用專案設定的 ATTACHMENTS_ROOT，否則退到專案下 change_order_records。"""
    try:
        from config import ATTACHMENTS_ROOT  # type: ignore
        return Path(ATTACHMENTS_ROOT)
    except Exception:
        return _HERE.parent / "change_order_records"


def main() -> int:
    try:
        import webview  # pywebview
    except ImportError:
        print("✗ 需要 pywebview：請先 `pip install pywebview`")
        return 2

    if not _INDEX.exists():
        print(f"✗ 找不到前端：{_INDEX}")
        return 4

    from co_bridge import ChangeOrderBridge

    bridge = ChangeOrderBridge(attachments_root=_resolve_attachments_root())

    # 視窗先建、再把「原生檔案對話框」注入橋（closure 抓得到 window）。
    window = webview.create_window(
        "新修改單精靈",
        str(_INDEX),
        js_api=bridge,
        width=980,
        height=680,
        min_size=(720, 520),
    )

    def _pick_file(kind: str):
        if kind == "pdf":
            file_types = ("PDF 檔 (*.pdf)", "所有檔案 (*.*)")
        else:
            file_types = ("圖片 (*.jpg;*.jpeg;*.png)", "所有檔案 (*.*)")
        result = window.create_file_dialog(webview.OPEN_DIALOG, file_types=file_types)
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else result

    bridge._pick_file_fn = _pick_file

    debug = os.environ.get("CO_WIZARD_DEBUG", "0") == "1"  # 預設關 DevTools；開發設 CO_WIZARD_DEBUG=1（WebView2=完整 Chromium）
    try:
        webview.start(debug=debug)
        return 0
    except Exception as exc:  # 多半是缺 WebView2 Runtime
        print(
            "✗ 視窗啟動失敗：" + str(exc) + "\n"
            "  Windows 可能缺 WebView2 Runtime。\n"
            "  解法：到 Microsoft 下載「Evergreen WebView2 Runtime」安裝後再試，\n"
            "       或正式打包時把它的 bootstrapper 一起帶上。"
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
