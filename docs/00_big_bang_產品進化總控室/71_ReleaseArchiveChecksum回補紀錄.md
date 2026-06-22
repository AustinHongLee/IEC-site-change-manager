# Release Archive 與 Checksum 回補紀錄

日期：2026-06-22

## 背景

PyInstaller onedir build 會產生一個資料夾。公司內交付時仍需要可傳遞的 zip，以及能確認檔案未損壞的 checksum。

## 本次新增

- `tools/build_release.py --archive`
  - package gate 通過後，建立：
    - `dist/releases/IEC-site-change-manager_0.1.0-alpha_win64_onedir.zip`
    - 同名 `.sha256`
  - zip 內保留頂層資料夾 `IEC-site-change-manager/`。
  - zip 會保留資料夾 entry，避免必要空資料夾在解壓後消失。
  - 若 `archive_dir` 被指定在 package 內，會拒絕執行，避免 zip 把自己打進去。
- `tests/test_build_release_tool.py`
  - 使用小型假 package 驗證 zip 內容與 checksum。

## 使用方式

```powershell
python tools\build_release.py --archive
```

只壓現有 dist：

```powershell
python tools\build_release.py --skip-build --archive
```

## 注意

目前真實 dist 約數百 MB。日常驗證可只跑 `python tools\build_release.py --skip-build`；需要交付給同事時再加 `--archive`。
