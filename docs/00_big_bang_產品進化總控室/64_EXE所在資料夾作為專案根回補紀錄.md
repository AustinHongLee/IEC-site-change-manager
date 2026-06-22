# EXE 所在資料夾作為專案根回補紀錄

日期：2026-06-22

## 背景

使用者的產品目標是「把 EXE 放進專案資料夾，執行後檢查目前資料夾」。因此打包後的 `BASE_DIR` 不應指向 PyInstaller 的 `_internal/control`，而應指向 EXE 所在資料夾。

## 本次調整

更新 `control/config.py`：

- 偵測 `sys.frozen` 時，`resolve_base_dir()` 回傳 `sys.executable` 所在資料夾。
- 非 frozen 狀態維持原本從 `control/` 往上找專案根的行為。

新增 `tests/test_config_paths.py`：

- 模擬 `sys.frozen = True`。
- 確認 `resolve_base_dir()` 使用 EXE 所在資料夾。

## 驗收

需執行：

```powershell
python -m pytest -s -q tests/test_config_paths.py
python -m pytest -s .\tests
```

## 影響

這是 EXE 產品化的前置修正。後續 PyInstaller spec 才能符合「一個入口放在專案資料夾」的部署模型。
