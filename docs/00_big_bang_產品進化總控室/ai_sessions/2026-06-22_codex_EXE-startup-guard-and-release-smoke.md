# AI Session：EXE startup guard and release smoke

日期：2026-06-22
角色：工程實作

## 本次目標

把單一 EXE 產品化前需要的啟動判斷與 release smoke 變成可測工具

## 主要變更摘要

- 新增 StartupDecision 啟動判斷模型
- 新增 check_startup_guard CLI，可輸出 JSON action
- 新增 run_release_smoke，串接 startup guard、integrity audit、site output center

## 驗證紀錄

- python -m pytest -s .\tests：355 items collected, exit 0
- python .\control\main.py --health-check：healthy，啟動判斷為專案狀態正常
- python tools/run_release_smoke.py --project-root . --output staging/release_smoke --json：ok true

## 風險與注意事項

- integrity audit 仍保留 attachments_without_records warning，這是既有測試資料狀態

## 下一步

- 可進入 EXE 打包 spec 與 release smoke 文件化
- 輸出中心正式分頁仍需逐步設計，不應一次大改

## Git Snapshot

### Branch Status

```text
## main...origin/main
```

### HEAD

```text
ebd4235
```

### Recent Log

```text
ebd4235 test(release): add release smoke runner
0b115d7 test(guard): add startup check CLI
8bd7176 feat(guard): classify startup decisions
85a175a test(ui): cover main window output center path
c7ef4f9 refactor(ui): remove legacy output center aliases
```

### Working Tree Diff Stat

```text
<no working tree diff>
```
