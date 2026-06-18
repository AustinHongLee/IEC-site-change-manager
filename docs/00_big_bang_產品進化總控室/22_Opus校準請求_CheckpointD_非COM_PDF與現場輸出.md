# Opus 校準請求：Checkpoint D 非 COM PDF 與現場輸出

日期：2026-06-17

## 請 Opus 扮演的角色

請以「公司級工程工具產品架構審查」角度校準，重點不是稱讚，而是找出還會在部署、現場使用、輸出交付、模板維護或多人協作時爆炸的地方。

## 背景

本專案的產品方向已從單純產出修改單，逐步轉成：

1. 以 `CanonicalReport / CanonicalReportSet` 作為現場資料核心。
2. 記錄現場修改、焊口統計、照片、用料。
3. 讓不同公司格式透過 renderer/template 輸出，而不是改核心資料。
4. 舊 Excel COM 降級為 optional legacy backend，不可成為 app 啟動或核心輸出的硬依賴。
5. 公司級部署目標仍是讓使用者點一個入口就能工作，長期可能走單一 exe 或類似單入口包裝。

## 本輪已完成

### 非 COM PDF 能力

- `control/capabilities.py`
  - 新增 `detect_libreoffice()`。
  - 支援搜尋 `soffice/libreoffice` 與 Windows 常見安裝路徑。
  - 回傳 `CapabilityResult(name="libreoffice", executable=...)`。
- `control/workbook_pdf_converter.py`
  - 新增 `convert_workbook_to_pdf()`。
  - 支援 `.xlsx/.xlsm/.ods`。
  - 使用 LibreOffice headless profile 隔離轉檔。
  - 轉檔後用 `pypdf` 回讀 PDF，至少確認頁數大於 0。
  - 採暫存檔再 `os.replace()`，避免半成品覆蓋 PDF。
- `tools/convert_workbook_pdf.py`
  - 獨立 workbook→PDF CLI。
- `settings.json`
  - 新增 `paths.soffice_path`。
  - 未明確傳 `--soffice` 時，converter 會先讀 settings，再自動搜尋。
- `control/gui_settings.py`
  - 設定面板可瀏覽、測試 LibreOffice `soffice.exe`。

### xlsx_template 接入 PDF 後處理

- `tools/render_xlsx_template.py`
  - 新增 `--pdf-output`、`--soffice`、`--pdf-timeout`。
  - 先完成 workbook render、layout validation、post validation。
  - workbook 成功後才轉 PDF。
  - PDF 失敗時保留 `.xlsx`，CLI 回傳非 0，JSON 帶 `pdf_conversion` issue。

### 現場統計單接入 PDF 後處理

- `tools/export_site_statistics.py`
  - 新增 `--pdf-output`、`--soffice`、`--pdf-timeout`、`--json`。
  - JSON 模式會延後載入 `site_statistics_exporter`，避免 app 啟動日誌污染 stdout。
- `control/gui_panels.py`
  - 紀錄管理面板新增「統計PDF」。
  - 點擊後先匯出現場統計單 `.xlsx`，再嘗試 LibreOffice 轉 PDF。
  - 若 LibreOffice 不可用，會開啟已成功的 `.xlsx`，並以 warning 顯示 PDF 失敗原因。

### 輸出能力 preflight

- `control/output_capabilities.py`
  - 統一回報：
    - `site_statistics_xlsx`
    - `xlsx_template`
    - `workbook_pdf_libreoffice`
    - `legacy_xlsx_com`
  - 預設不啟動 Excel，不強制執行 LibreOffice 版本探測。
  - 回傳 `summary / capabilities / recommendations`。
- `tools/check_output_capabilities.py`
  - 可用 `--json` 給 UI/AI/批次流程讀。
  - 可用 `--probe-com` 與 `--probe-libreoffice` 做深探測。
- 設定面板新增「輸出能力檢查」。

### Demo smoke / 人工測試入口

- `control/demo_smoke.py`
  - 建立安全 demo 專案資料夾。
  - 產生 demo attachments、before/after 圖、附件 PDF。
  - 產生 `demo_canonical_report_set.json`。
  - 產生 `demo_field_report.template.json`。
  - 產出 `demo_field_report.xlsx` 與 `demo_site_statistics.xlsx`。
  - 可選擇嘗試 LibreOffice PDF。
- `tools/run_demo_output_smoke.py`
  - 預設輸出到 `staging/demo_output`。
  - 只有資料夾帶 `.iec_demo_project` marker 時才允許 overwrite，避免覆寫正式資料夾。
- `23_DemoSmoke_人工測試入口.md`
  - 記錄人工測試指令與檢查項目。

### import / COM 邊界

- `tests/test_import_guard.py`
  - 封鎖 `pythoncom/win32com` 後 import 核心與 GUI 啟動集合。
  - `workbook_pdf_converter`、`output_capabilities`、`demo_smoke` 與 GUI 新增 PDF 匯入後仍通過，代表非 COM PDF 與 smoke 工具沒把 COM 拉回啟動期。

## 驗證結果

- Focused tests：
  - `tests/test_export_site_statistics_tool.py`
  - `tests/test_render_xlsx_template_tool.py`
  - `tests/test_workbook_pdf_converter.py`
  - `tests/test_capabilities.py`
  - `tests/test_import_guard.py`
  - `tests/test_output_capabilities.py`
  - `tests/test_check_output_capabilities_tool.py`
  - `tests/test_demo_smoke.py`
  - `tests/test_run_demo_output_smoke_tool.py`
- Full tests：
  - `python -m pytest -s tests`
  - 目前 284 passed。
- 健康檢查：
  - `python control/main.py --health-check`
  - 狀態 healthy。
- 資料稽核：
  - `python _audit_data.py`
  - error=0, warning=1。
  - warning 是既有的 2 個 attachments 子資料夾尚未寫入 records。
- `git diff --check`
  - 無 whitespace error。
  - 僅既有 LF→CRLF warning。

## 已知未完成

1. 本機目前沒有 LibreOffice，因此尚未做真 LibreOffice PDF 視覺渲染比對。
2. 尚未決定 LibreOffice 的公司部署策略：
   - 要求公司電腦安裝 LibreOffice。
   - 由打包流程附帶 portable LibreOffice。
   - 或在 settings 裡指定 `soffice.exe`。
3. PDF 驗證目前只確認可讀與頁數，不確認版面、圖片是否完整、頁面尺寸是否符合公司表單。
4. 尚未做 PDF overlay / FreeText / 紅框欄位 template renderer。
5. 現場統計單雖可轉 PDF，但本質仍是 workbook 版面轉出，不是專門設計的 PDF 表單版面。
6. `xlsx_template` 的資料覆蓋報告目前會把未使用欄位列為 info，尚未整理成模板作者更好讀的 UX。

## 為什麼現在該進 Opus

目前已經補完「自己可驗證」的地基：

1. CanonicalReport 資料核心。
2. xlsx_template renderer。
3. 現場統計單。
4. 非 COM PDF 後處理。
5. LibreOffice 路徑設定。
6. 輸出能力 preflight。
7. Demo smoke 與人工測試入口。

下一個大步若直接做 `pdf_overlay`，會開始定義：

- PDF 座標系統。
- FreeText / 紅框 / 圖片框 schema。
- PDF template 與 xlsx_template 的共用原語。
- 多頁照片表與溢出策略。
- 驗證方式：只檢查欄位？還是 render PDF 後做視覺/文字/圖片檢查？

這些會影響長期多公司格式支援，屬於高風險架構分岔，因此適合讓 Opus 進場挑錯。

## 請 Opus 校準的問題

1. 非 COM PDF 採「workbook 先產出，再用 LibreOffice headless 轉 PDF」是否適合作為公司級 MVA？
2. PDF 轉檔失敗時，目前策略是保留並開啟 `.xlsx`、提示 PDF 失敗。這對現場/內勤使用者是否夠清楚，還是應該導入「輸出狀態面板」？
3. `render_xlsx_template.py --json` 與 `export_site_statistics.py --json` 都回傳結構化 result。這是否足以讓 UI/AI/批次流程接管？
4. 下一個最該補的風險是否是：
   - A. LibreOffice 安裝/打包/路徑設定策略。
   - B. 真 PDF 視覺驗證。
   - C. PDF overlay template renderer。
   - D. 現場統計單 UI 的輸出狀態與重新開檔流程。
   - E. 先回頭整理 CanonicalReport 欄位與照片/焊口/材料完整度。
5. 如果長期支援「每家公司不同格式」，PDF overlay 的 template schema 應該如何和既有 `xlsx_template` 三原語對齊？
6. Demo smoke 目前是否足以作為 MVP 人工驗收入口？還是應再補更多真實案例，例如缺 after 圖、材料未定價、表格溢出、多頁照片？

## 請輸出格式

請用以下格式回覆：

1. P0 必修問題：不改會造成公司部署或資料/輸出事故。
2. P1 建議問題：會造成維護成本或使用者困惑，但不一定擋 MVP。
3. 可延後事項：現在做會過度設計。
4. 下一個 3 步開發順序。
5. 若你認為目前方向錯，請直接指出替代架構。
