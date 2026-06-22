# AI Session：EXE packaging and release package gate

日期：2026-06-22
角色：工程實作

## 本次目標

建立可版本控制的 PyInstaller onedir 打包基準，並補上 release package 交付前檢查器

## 主要變更摘要

- 新增 PyInstaller onedir spec，打包入口為 control/main.py，資產放在預設 _internal/
- 修正啟動守門，讓 exe 與 _internal 不會讓乾淨 package 被誤判為跑錯資料夾
- 新增 check_release_package release gate，可檢查 exe、_internal、必要資產、乾淨頂層與 exe health-check

## 驗證紀錄

- python -m PyInstaller --noconfirm --clean packaging\IEC-site-change-manager.spec：build complete
- dist\IEC-site-change-manager\IEC-site-change-manager.exe --health-check：first_open / 第一次開啟專案
- python tools\check_release_package.py --package-dir dist\IEC-site-change-manager --run-health-check：合格
- python -m pytest -s .\tests：362 items collected, exit 0

## 風險與注意事項

- 目前仍是 onedir，onefile、簽章、安裝包、portable LibreOffice 尚未落地
- PyInstaller 分析仍會收進較多第三方依賴，之後需要瘦身與乾淨機實測

## 下一步

- 建立版本資訊與使用者可見的關於/診斷頁
- 將 release package gate 納入正式打包流程

## Git Snapshot

### Branch Status

```text
## main...origin/main
```

### HEAD

```text
e1fb5a4
```

### Recent Log

```text
e1fb5a4 test(release): add package gate
ca2b7a2 build(exe): add PyInstaller onedir spec
e4b1203 fix(config): use exe folder as project root when frozen
27e310c docs(ai): record startup guard session
ebd4235 test(release): add release smoke runner
```

### Working Tree Diff Stat

```text
<no working tree diff>
```
