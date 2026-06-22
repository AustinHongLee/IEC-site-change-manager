# Release Smoke 回補紀錄

日期：2026-06-22

## 背景

EXE 產品化需要一條可重複的 release smoke：不靠人工打開 GUI，也能確認啟動守門、資料一致性與輸出中心最小產出可跑。

## 本次新增

- `tools/run_release_smoke.py`
  - 檢查 project guard 啟動判斷。
  - 執行 integrity audit。
  - 執行 site output center 最小輸出。
  - 預設不產 PDF，避免 LibreOffice 或 PDF renderer 影響快速 smoke。
  - `--pdf` 可加跑 PDF overlay。
  - `--repair` 可先執行安全修復。
  - `--json` 可輸出機器可讀結果。
- `tests/test_run_release_smoke_tool.py`
  - 驗證暫存 attachments 專案可 `--repair` 後跑輸出中心。
  - 驗證非專案資料夾會被 `blocked_wrong_folder` 擋下。

## 使用方式

目前專案快速 smoke：

```powershell
python tools/run_release_smoke.py --project-root . --output staging/release_smoke --json
```

含 PDF：

```powershell
python tools/run_release_smoke.py --project-root . --output staging/release_smoke --pdf --json
```

## 驗收

手動確認目前專案：

```powershell
python tools/check_startup_guard.py --project-root . --json
python control/main.py --health-check
python tools/run_site_output_center.py --output staging/release_smoke --overwrite --no-pdf --json
```

三者皆 exit code `0`。
