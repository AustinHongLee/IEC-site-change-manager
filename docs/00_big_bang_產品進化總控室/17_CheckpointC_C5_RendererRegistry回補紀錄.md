# Checkpoint C C5 回補紀錄：Renderer Registry

日期：2026-06-17

## 問題

C5 P0 已把 Excel COM 從 GUI import chain 切開，但輸出後端仍缺一個正式分派層。若未來每個 CLI/UI 自己判斷 `xlsx_template`、`xlsx_com`、`pdf_overlay`，多公司格式會重新變成 if 樹。

## 本次範圍

建立 renderer registry 與 kind 分派，讓新 template renderer 先走共同入口。這次仍不重寫舊 COM 報表版面，也不把舊 COM 立即改吃 CanonicalReport。

## 實作

- 新增 `control/renderer_registry.py`
  - `list_renderers()`：列出已知輸出後端。
  - `get_renderer_descriptor(kind)`：取得指定後端狀態。
  - `render_with_template(report, template, output_path)`：依 `template.kind` 分派。
- 新增 `tools/list_renderers.py`
  - 可列出 renderer 清單。
  - `--json` 供 UI/AI 讀取。
  - `--probe-com` 才實際啟動 Excel 探測 COM；預設只做輕量狀態。
- `tools/render_xlsx_template.py`
  - 改走 `renderer_registry.render_with_template()`，不再直接呼叫 `xlsx_template_renderer`。

## Renderer 狀態

### `xlsx_template`

- 狀態：ready
- 契約：CanonicalReport
- 特性：COM-free、template-driven
- 已支援：text / image / table、dry-run、layout validation、post validation

### `xlsx_com`

- 狀態：legacy optional
- 契約：目前仍是 `legacy_folder_args`，標記 `CanonicalReport adapter pending`
- 特性：不再是 import 期硬依賴；若透過 registry 被選到，會先回友善錯誤，不會繞過 canonical/template 閘門直出。

## 自動測試

- `tests/test_renderer_registry.py`
  - registry 能列出 `xlsx_template` 與 `xlsx_com`。
  - 封鎖 `pythoncom/win32com` 時，`xlsx_com` 回 unavailable，不崩潰。
  - `render_with_template()` 可實際分派並產出 `xlsx_template` workbook。
  - `xlsx_com` 在 canonical adapter 未完成前會回 `renderer_not_canonical_ready`。
  - unknown kind 會回 `renderer_unknown`。
- `tests/test_list_renderers_tool.py`
  - `tools/list_renderers.py --json` 可被機器讀取。

## 已達成

- 新 renderer 入口開始集中化。
- `template.kind` 開始有實際分派意義。
- COM 後端被登錄為 legacy optional，但仍被擋在 registry 的安全邊界外。

## 未完成

- GUI 舊產出入口尚未全面改用 renderer registry。
- `xlsx_com` 尚未完成 CanonicalReport adapter。
- `pdf_overlay` 與 `photo_sheet` 尚未進 registry。
- Excel→PDF / LibreOffice 能力探測尚未納入 `capabilities.py`。
