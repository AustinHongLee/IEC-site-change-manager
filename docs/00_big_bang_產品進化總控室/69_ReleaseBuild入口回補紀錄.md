# Release Build 入口回補紀錄

日期：2026-06-22

## 背景

目前已有 PyInstaller spec、release package gate、版本資訊與支援診斷包。下一步需要一個標準入口，把「建置」與「交付前檢查」串起來，避免每次人工漏步。

## 本次新增

- `tools/build_release.py`
  - 預設執行 PyInstaller onedir build。
  - build 成功後執行 `check_release_package`。
  - 預設會讓 package gate 執行 `exe --health-check`。
  - 支援 `--skip-build`，方便只檢查現有 dist。
  - 支援 `--json`，方便 CI 或其他 AI 讀取。
- `tests/test_build_release_tool.py`
  - 測試 `--skip-build` 可以跑 package gate。
  - 測試 package gate 失敗時整體 release build 會失敗。
- `packaging/README.md`
  - 補上 `python tools\build_release.py` 作為建置加檢查入口。

## 使用方式

完整建置：

```powershell
python tools\build_release.py
```

只檢查現有 dist：

```powershell
python tools\build_release.py --skip-build
```

JSON：

```powershell
python tools\build_release.py --skip-build --json
```
