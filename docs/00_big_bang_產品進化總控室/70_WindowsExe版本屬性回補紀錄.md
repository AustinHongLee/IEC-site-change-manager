# Windows EXE 版本屬性回補紀錄

日期：2026-06-22

## 背景

CLI 已有 `--version`，health-check 也會印出 APP identity。但公司內交付 EXE 時，使用者常會從檔案總管或右鍵內容確認版本，因此 EXE 本身也應寫入 Windows version resource。

## 本次新增

- `packaging/windows_version_info.txt`
  - `CompanyName`: `IEC`
  - `FileDescription`: `IEC Site Change Manager`
  - `FileVersion`: `0.1.0-alpha`
  - `ProductName`: `IEC Site Change Manager`
  - `ProductVersion`: `0.1.0-alpha`
- `packaging/IEC-site-change-manager.spec`
  - `EXE(..., version=...)`
- `tests/test_packaging_spec.py`
  - 檢查 spec 掛上 version resource。
  - 檢查 version info 仍保留目前 APP 顯示版本。

## 驗證方式

```powershell
python tools\build_release.py
(Get-Item .\dist\IEC-site-change-manager\IEC-site-change-manager.exe).VersionInfo
```
