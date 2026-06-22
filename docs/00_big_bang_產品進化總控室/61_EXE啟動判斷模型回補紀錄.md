# EXE 啟動判斷模型回補紀錄

日期：2026-06-22

## 背景

使用者最初目標之一是：單一 EXE 放到專案資料夾後，啟動時能判斷目前資料夾是否完整，並區分第一次開檔、誤刪、跑錯資料夾或其他問題。

`project_guard.py` 已有低階檢查與修復能力，但缺少一個可直接給 EXE/GUI 顯示的啟動決策摘要。

## 本次新增

新增 `StartupDecision` 與 `build_startup_decision(result)`：

- `healthy`
  - 專案狀態正常，可直接啟動。
- `initialize`
  - 空白或僅有基本空結構的資料夾，視為第一次開啟，可自動初始化。
- `repair`
  - 已有部分專案 payload，但缺少可安全補建的資料夾或預設檔，可修復。
- `blocked_wrong_folder`
  - 非空資料夾但不像專案，疑似跑錯位置，禁止自動寫入。
- `blocked_possible_deleted_records`
  - `attachments/` 已有資料但 `records.json` 遺失，疑似誤刪，禁止自動重建空 records 覆蓋語意。
- `blocked`
  - JSON 損壞、pending journal 等其他阻擋性問題。
- `review`
  - 可繼續但需要人工確認的提醒。

`format_guard_report()` 現在會顯示「啟動判斷」。

## 驗收

已執行：

```powershell
python -m pytest -s -q tests/test_project_guard.py
python .\control\main.py --health-check
```

結果：

```text
12 passed
health-check: healthy
```

目前正式專案輸出：

```text
狀態: healthy
啟動判斷: 專案狀態正常
```

## 下一步

EXE 啟動器可使用 `build_startup_decision()` 決定 UI 行為：

- `initialize` / `repair`：提示後修復。
- `blocked_*`：停止啟動並顯示原因。
- `healthy` / `review`：允許進入主程式，但 `review` 應提示到健康檢查。
