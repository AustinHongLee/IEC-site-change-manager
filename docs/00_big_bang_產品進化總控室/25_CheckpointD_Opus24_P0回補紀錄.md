# Checkpoint D Opus24 P0 回補紀錄

日期：2026-06-17

## 來源

依 `24_Opus校準結果_CheckpointD.md` 的兩個 P0 回補：

1. P0-1：LibreOffice converter timeout / OSError 需轉成 friendly failure，timeout 時嘗試終止整個程序樹。
2. P0-2：LibreOffice 部署策略需拍板，否則非 COM PDF 還只是「我的機器能跑」。

## P0-1 回補

### `control/workbook_pdf_converter.py`

- 將 `subprocess.run(..., timeout=...)` 改為 `_run_libreoffice_command()`：
  - 使用 `subprocess.Popen()`。
  - Windows 使用 `CREATE_NEW_PROCESS_GROUP`。
  - 非 Windows 使用 `start_new_session=True`。
  - timeout 時呼叫 `_terminate_process_tree()`。
- 新增 `LibreOfficeCommandTimeout`。
- `convert_workbook_to_pdf()` 會捕捉：
  - `LibreOfficeCommandTimeout` → `libreoffice_timeout`
  - `OSError` / `PermissionError` / `FileNotFoundError` → `libreoffice_spawn_failed`
- timeout / spawn failed 都回傳 `_failure(...)` dict，不讓原始 traceback 噴到 CLI/GUI。

## P0-2 決策

新增決策：

- portable LibreOffice 隨公司版打包為主策略。
- `settings.json` 的 `paths.soffice_path` 作為 fallback。
- 公司電腦已安裝 LibreOffice 時可容忍自動搜尋或指定路徑。
- portable 打包與真機驗證落地前，PDF 不可作為唯一交付物；必須保留 xlsx 產出與降級提示。

真機驗收需包含：

- CJK 專案路徑。
- CJK 檔名。
- 使用者已開 LibreOffice。
- 缺 LibreOffice。
- timeout。
- PDF 可讀。
- 版面抽查。

## 測試

- `tests/test_workbook_pdf_converter.py`
  - `libreoffice_timeout`
  - `libreoffice_spawn_failed`
  - 既有成功、不可用、settings 路徑、CLI JSON 失敗測試維持。

## 後續

- P1：統一 output result envelope。
- P1：PDF 驗證升級到頁面尺寸與內容非空。
- Step 2：先寫 `pdf_overlay` schema 規格，再寫 renderer。
