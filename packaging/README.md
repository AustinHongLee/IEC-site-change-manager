# Packaging

本資料夾保存公司版打包相關檔案。

目前策略：

- 先用 PyInstaller `onedir`。
- 依賴與打包資產放在 PyInstaller 預設 `_internal/`。
- `project_guard` 會忽略本工具的 exe 與 `_internal/`，讓空白資料夾仍可被判定為第一次開啟。
- 先保留 console 視窗，方便看啟動守門與 release smoke 訊息。
- `onefile`、簽章、安裝包與 portable LibreOffice 後續再做。

建置：

```powershell
python -m PyInstaller --noconfirm --clean packaging\IEC-site-change-manager.spec
```

建置加交付前檢查：

```powershell
python tools\build_release.py
```

建置後先跑：

```powershell
dist\IEC-site-change-manager\IEC-site-change-manager.exe --health-check
```
