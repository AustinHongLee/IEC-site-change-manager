# PyInstaller Onedir Spec 回補紀錄

日期：2026-06-22

## 背景

EXE 產品化已補上啟動守門、release smoke、以及 frozen 狀態下以 EXE 所在資料夾作為專案根。下一步需要可重複的 PyInstaller spec。

## 本次新增

- `packaging/IEC-site-change-manager.spec`
  - 入口：`control/main.py`
  - 模式：onedir
  - console：保留，方便看啟動守門與 smoke 訊息
  - 依賴與打包資產放在 PyInstaller 預設 `_internal/`
  - 打包資產：
    - `template/`
    - `control/image/`
    - `control/wizard_data.json`
    - `material_pricebook_seed.json`
- `packaging/README.md`
- `.gitignore`
  - 忽略 `build/`
  - 忽略 `dist/`
- `tests/test_packaging_spec.py`
  - 檢查 spec 入口與必要資產。
  - 檢查 PyInstaller 輸出已被 gitignore 排除。

## 建置指令

```powershell
python -m PyInstaller --noconfirm --clean packaging\IEC-site-change-manager.spec
```

## 注意

這不是最終公司部署包。`onefile`、簽章、安裝包、portable LibreOffice 都還沒落地。這一步的目標是先讓打包規格可版本控制、可 review、可 smoke。

## 2026-06-22 修正

第一次 build smoke 發現：若把所有依賴攤在 exe 同層，啟動守門會把 dist 目錄判成「可能跑錯資料夾」。因此 spec 改回 PyInstaller 預設 `_internal/`，並由 `project_guard` 忽略本工具 exe 與 `_internal/`。
