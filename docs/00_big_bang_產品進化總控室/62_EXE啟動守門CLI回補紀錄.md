# EXE 啟動守門 CLI 回補紀錄

日期：2026-06-22

## 背景

`project_guard.py` 已能產生啟動判斷，但 EXE 產品化還需要一個不用進 GUI 的 smoke 入口。這樣在打包或測試不同專案資料夾時，可以直接確認「第一次開檔 / 可修復 / 跑錯資料夾 / 阻擋」。

## 本次新增

- `tools/check_startup_guard.py`
  - `--project-root` 指定要檢查的專案資料夾。
  - `--repair` 執行可安全自動修復。
  - `--json` 輸出機器可讀結果。
  - 可繼續啟動時 exit code `0`。
  - 阻擋性問題時 exit code `2`。
- `tests/test_check_startup_guard_tool.py`
  - 驗證空白資料夾回報 `initialize`。
  - 驗證非專案資料夾回報 `blocked_wrong_folder`。
  - 驗證 `--repair` 可初始化空白專案。

## 使用範例

```powershell
python tools/check_startup_guard.py --project-root . --json
```

檢查並修復空白專案：

```powershell
python tools/check_startup_guard.py --project-root C:\Temp\NewProject --repair --json
```

## 下一步

後續 EXE smoke 可先執行此工具的等價流程，再啟動 GUI。這能避免 EXE 一打開就污染錯誤資料夾。
