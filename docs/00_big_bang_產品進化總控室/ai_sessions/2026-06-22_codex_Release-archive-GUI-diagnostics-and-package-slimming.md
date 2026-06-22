# AI Session：Release archive GUI diagnostics and package slimming

日期：2026-06-22
角色：工程實作

## 本次目標

補齊使用者可操作診斷入口、release archive/checksum，並降低 PyInstaller onedir 體積

## 主要變更摘要

- 新增 build_release --archive，可產生 zip 與 sha256，並保留空資料夾 entry
- 健康檢查 GUI 新增支援診斷包與版本資訊入口
- PyInstaller spec 排除 pytest、torch、torchvision、tensorflow、tensorboard 等非產品執行期大型套件

## 驗證紀錄

- python -m pytest -s .\tests：372 items collected, exit 0
- python tools\build_release.py：成功，package_check OK
- dist 從 738.30MB / 3611 檔降至 332.68MB / 1191 檔
- packaged exe --diagnostics：成功產生 support bundle，啟動判斷 initialize

## 風險與注意事項

- 目前沒有在乾淨無開發套件機器上實機測過 GUI 啟動與輸出中心完整流程
- archive 會產生數百 MB zip，日常只建議在需要交付時加 --archive

## 下一步

- 下一個高價值點是乾淨機/隔離環境 smoke，或建立更完整的 release checklist

## Git Snapshot

### Branch Status

```text
## main...origin/main
```

### HEAD

```text
872819a
```

### Recent Log

```text
872819a build(exe): exclude unused heavy packages
6cd36d7 feat(ui): add support diagnostics entry
fb1c260 build(release): add archive checksum option
2d822a8 docs(ai): record exe diagnostics session
c840cb7 build(exe): add Windows version resource
```

### Working Tree Diff Stat

```text
<no working tree diff>
```
