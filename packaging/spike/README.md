# pywebview Packaging Spike

這個 spike 只驗證「pywebview + WebView2 + js_api + PyInstaller onedir」能不能在 Windows frozen 狀態穩定啟動。它不載入主 GUI、不碰真資料，也不代表正式 spec 已完成。

## 先在開發機跑

```powershell
python packaging\spike\pywebview_smoke_app.py --health-check
python packaging\spike\pywebview_smoke_app.py
```

通過標準：

- `--health-check` 回傳 JSON，`ok` 為 `true`。
- 視窗開啟後，畫面顯示 `pong`，且 `frozen` 在原始碼模式為 `false`。

## 打包 spike

```powershell
python -m PyInstaller --noconfirm --clean packaging\spike\pywebview_smoke.spec
dist\pywebview-smoke\pywebview-smoke.exe --health-check
dist\pywebview-smoke\pywebview-smoke.exe
```

通過標準：

- 打包後 `--health-check` 回傳 JSON，`ok` 為 `true`，`frozen` 為 `true`。
- 打包後視窗開啟，畫面顯示 `pong`，且 `frozen` 為 `true`。
- 將整個 `dist\pywebview-smoke` 複製到沒有開發環境的 Windows 電腦仍可開窗。

## 常見失敗判讀

- `ModuleNotFoundError: webview`：沒有安裝 `requirements.txt`。
- `ModuleNotFoundError: clr_loader` 或 pythonnet 相關錯誤：pywebview Windows backend 依賴沒有被打包或沒有安裝完整。
- 視窗白畫面或無法啟動：優先確認 Microsoft Edge WebView2 Runtime 是否存在。
- 原始碼模式可跑，frozen 模式壞：先保留完整 console log，再調整 `hiddenimports` 或 PyInstaller hook。

這片 spike 通過後，才把結論套到正式 `IEC-site-change-manager-web.spec`。
