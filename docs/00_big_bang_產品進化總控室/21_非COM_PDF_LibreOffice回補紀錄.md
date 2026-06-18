# 非 COM PDF 路線回補紀錄：LibreOffice Headless

日期：2026-06-17

## 背景

Opus 在 `19_Opus再校準結果_C5_Registry.md` 指出，即使 COM 退出啟動期，如果主要 PDF 交付物仍只能靠 Excel COM，無 Office 機器仍會「能開但不能完成主要輸出」。因此下一個 MVA 是非 COM 的 Excel→PDF 路線。

## 本次範圍

本次建立能力探測與 converter，並接入 `xlsx_template` CLI 與現場統計單的可選 PDF 輸出；不改舊 COM 報表、不切換舊產出預設路線。

## 實作

### `control/capabilities.py`

- 新增 `detect_libreoffice()`：
  - 搜尋 `soffice` / `libreoffice`。
  - Windows 會檢查常見 LibreOffice 安裝路徑。
  - 可用 `--version` 做版本探測。
  - 回傳 `CapabilityResult(name="libreoffice", executable=...)`。
- 新增 `format_libreoffice_unavailable()`，輸出人話不可用訊息。

### `control/workbook_pdf_converter.py`

- 新增 `convert_workbook_to_pdf()`：
  - 支援 `.xlsx` / `.xlsm` / `.ods`。
  - 未明確傳入 `soffice_path` 時，會先讀 `settings.json` 的 `paths.soffice_path`，再交給 capability probe 自動搜尋。
  - 使用 `soffice --headless --convert-to pdf --outdir ...`。
  - 使用暫存 LibreOffice profile，降低和使用者開著的 LibreOffice/Office 狀態互相干擾。
  - timeout 會回傳 `libreoffice_timeout` failure dict，並嘗試停止整個 LibreOffice 程序樹。
  - 啟動失敗、權限問題或 soffice 被移走會回傳 `libreoffice_spawn_failed`，不讓 traceback 直接炸到 GUI/CLI。
  - 轉檔後用 `pypdf` 回讀 PDF，確認至少 1 頁。
  - 寫出採暫存檔再 `os.replace()`，避免半成品覆蓋目標 PDF。

### 部署策略

- 採 portable LibreOffice 隨公司版打包為主策略。
- `settings.json` 的 `paths.soffice_path` 作為 fallback。
- 公司電腦已安裝 LibreOffice 時可容忍自動搜尋或指定路徑。
- portable 打包與真機驗證完成前，PDF 不可被視為唯一交付物；仍需保留 xlsx 產出與人話降級提示。
- 真機驗收需包含 CJK 專案路徑、CJK 檔名、使用者已開 LibreOffice、缺 LibreOffice、timeout、PDF 可讀與版面抽查。

### `tools/convert_workbook_pdf.py`

- 新增 CLI：
  - `python tools/convert_workbook_pdf.py input.xlsx output.pdf`
  - `--soffice` 可指定 LibreOffice 執行檔。
  - `--json` 可給 UI/AI 讀取結果。

### `tools/render_xlsx_template.py`

- 新增可選參數：
  - `--pdf-output output.pdf`
  - `--soffice C:\...\soffice.exe`
  - `--pdf-timeout 120`
- 流程：
  - 先完成 `xlsx_template` workbook 渲染與輸出後校驗。
  - workbook 成功後才呼叫 LibreOffice 轉 PDF。
  - PDF 轉檔失敗時保留已成功產出的 `.xlsx`，整體 CLI 回傳非 0，JSON 會帶 `pdf_conversion` 與明確 issue。

### `tools/export_site_statistics.py`

- 新增可選參數：
  - `--pdf-output output.pdf`
  - `--soffice C:\...\soffice.exe`
  - `--pdf-timeout 120`
  - `--json`
- JSON 模式會延後載入 `site_statistics_exporter`，並把 app 啟動日誌導到 stderr，保持 stdout 可被 UI/AI 直接解析。

### `control/gui_panels.py`

- 紀錄管理面板新增「統計PDF」入口。
- 流程：
  - 先匯出現場統計單 `.xlsx`。
  - 再用 LibreOffice 轉 `.pdf`。
  - 若 LibreOffice 不可用，會開啟已成功產出的 `.xlsx`，並以 warning 說明 PDF 失敗原因。

### `settings.json` / 設定面板

- 新增 `paths.soffice_path`，可記住公司電腦上的 `soffice.exe`。
- 設定面板的「執行選項 / 報告產出」新增 LibreOffice 路徑欄位：
  - 留空時自動搜尋。
  - 可瀏覽指定 `soffice.exe`。
  - 可按「測試」做版本探測。

### `control/output_capabilities.py`

- 新增輸出能力 preflight：
  - `site_statistics_xlsx`
  - `xlsx_template`
  - `workbook_pdf_libreoffice`
  - `legacy_xlsx_com`
- 預設不啟動 Excel COM，也不強制執行 LibreOffice 版本探測。
- 會回傳 `summary`、`capabilities` 與 `recommendations`，供 CLI/UI/AI 讀取。

### `tools/check_output_capabilities.py`

- 新增 CLI：
  - `python tools/check_output_capabilities.py`
  - `--json`
  - `--probe-com`
  - `--probe-libreoffice`

### 設定面板輸出能力檢查

- 設定面板的 LibreOffice PDF 區新增「輸出能力檢查」。
- 以人話列出目前 Excel 統計單、xlsx_template、非 COM PDF 與舊 COM 的可用狀態。

## 測試

- `tests/test_capabilities.py`
  - 無 LibreOffice 時回 unavailable。
  - 假版本探測成功時回 available 與 executable。
- `tests/test_workbook_pdf_converter.py`
  - fake soffice 產出有效 PDF，converter 可回讀頁數。
  - LibreOffice 不可用時回 `libreoffice_unavailable`。
  - 未明確傳 `soffice_path` 時會使用 settings 中設定的路徑。
  - LibreOffice timeout 會回 `libreoffice_timeout`。
  - soffice 啟動失敗會回 `libreoffice_spawn_failed`。
  - CLI 指定不存在 soffice 時可回 JSON 失敗。
- `tests/test_settings_manager.py`
  - 舊設定檔 merge 後會有 `soffice_path`，並可儲存。
- `tests/test_render_xlsx_template_tool.py`
  - `--pdf-output` 指定不存在 soffice 時，xlsx 仍產生、PDF 不產生、CLI 回非 0 並在 JSON 回報 `libreoffice_unavailable`。
- `tests/test_export_site_statistics_tool.py`
  - `--pdf-output` 指定不存在 soffice 時，現場統計單 xlsx 仍產生、PDF 不產生、CLI 回非 0 並保持 stdout 為純 JSON。
- `tests/test_import_guard.py`
  - 納入 `workbook_pdf_converter`，確保 PDF converter import 期不碰 COM。
- `tests/test_output_capabilities.py`
  - 能力報告列出核心輸出與 LibreOffice 建議。
  - settings 中的 `soffice_path` 會被能力報告使用。
- `tests/test_check_output_capabilities_tool.py`
  - CLI 可輸出 JSON，且包含四個輸出能力 key。
- `tests/test_gui_settings_output_capability_format.py`
  - 設定面板可把能力報告格式化成人話摘要。

## 未完成

- 尚未把 portable LibreOffice 實際接入打包流程。
- 尚未做真 LibreOffice 轉出 PDF 的視覺渲染比對。
