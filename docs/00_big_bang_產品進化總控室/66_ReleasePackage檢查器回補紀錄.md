# Release Package 檢查器回補紀錄

日期：2026-06-22

## 背景

PyInstaller onedir spec 已可建置出 `dist/IEC-site-change-manager/IEC-site-change-manager.exe`，但交付前仍需要一個可重複的檢查器，確認 package 沒有混入專案資料或漏掉打包資產。

## 本次新增

- `tools/check_release_package.py`
  - 檢查 package 目錄是否存在。
  - 檢查入口 exe 與 `_internal/`。
  - 檢查必要內嵌資產：
    - `template/`
    - `control/image/`
    - `control/wizard_data.json`
    - `material_pricebook_seed.json`
  - 檢查頂層是否只保留 `IEC-site-change-manager.exe` 與 `_internal/`。
  - 使用啟動守門確認乾淨 package 仍判定為第一次開啟。
  - 可選擇執行 `exe --health-check`。
- `tests/test_check_release_package_tool.py`

## 使用方式

```powershell
python tools/check_release_package.py --package-dir dist\IEC-site-change-manager --run-health-check
```

JSON：

```powershell
python tools/check_release_package.py --package-dir dist\IEC-site-change-manager --run-health-check --json
```

## 定位

這個工具是 release gate，不是建置器。建置仍由 PyInstaller spec 負責；本工具負責回答：「這包 onedir 現在能不能拿去交付測試？」
