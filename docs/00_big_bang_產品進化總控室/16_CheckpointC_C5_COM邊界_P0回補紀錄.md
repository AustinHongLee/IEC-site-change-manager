# Checkpoint C C5 回補紀錄：舊 Excel COM 邊界 P0

日期：2026-06-17

## 問題

Opus C5 校準指出，真正的高風險不是舊 COM 報表尚未重寫，而是 GUI 啟動鏈在 import 期硬依賴 COM：

- `gui.py` 頂層 import `excel_handler`
- `excel_handler.py` 頂層 import `win32com`

因此在沒有 Office/pywin32 的機器上，App 可能連啟動都失敗。這不符合公司級單一 exe 的部署目標。

## 本次範圍

本次只做 P0 import 邊界與能力探測，不重寫舊報表、不改舊 Excel/PDF 版面。

## 實作

- 新增 `control/capabilities.py`
  - `detect_excel_com()`：集中探測 `pythoncom`、`win32com` 與 Excel Application 是否可啟動。
  - `format_excel_com_unavailable()`：把不可用原因轉成人話訊息。
- `control/excel_handler.py`
  - 移除頂層 `win32com` import。
  - 只有 `ExcelManager._start_excel()` 真的要啟動 Excel 時才 lazy import COM。
  - COM 不可用時回傳清楚錯誤，不讓 traceback 漏到使用者流程。
- `control/gui.py`
  - 移除頂層 `excel_handler` import。
  - GUI 建立後先探測舊 COM 產出能力；不可用時停用「開始執行 / 重試失敗」舊產出入口。
  - 背景產出執行緒內才 lazy import `pythoncom` 與 `excel_handler`。
- `control/main.py`
  - CLI 舊產出前先探測 Excel COM；不可用時印出人話訊息並以非 0 exit 停止。

## 自動測試

- `tests/test_capabilities.py`
  - 封鎖 `pythoncom/win32com` 時，`detect_excel_com()` 回傳 unavailable，不丟例外。
  - 封鎖 COM import 時，`excel_handler` 與 `gui` 仍可 import，且不把 `win32com/pythoncom` 帶進 `sys.modules`。

## 已達成

- 無 pywin32/Excel 的環境不應再因 import `excel_handler` 而讓 GUI 啟動失敗。
- 新核心、現場統計單、template validate/dry-run/xlsx renderer 仍保持 COM-free。
- 舊版修改單產出仍保留原 COM 行為；有 COM 的機器上應維持既有輸出版面。

## 未完成

- 尚未建立正式 renderer registry。
- 舊 COM renderer 尚未改吃 CanonicalReport。
- Excel 轉 PDF 預設仍未切到 LibreOffice。
- 舊 COM 輸出尚未 golden-file 視覺比對。
