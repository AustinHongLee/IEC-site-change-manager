# AI Session：EXE diagnostics and release preflight

日期：2026-06-22
角色：工程實作

## 本次目標

補齊公司級 EXE 交付前的診斷、版本辨識與 release preflight

## 主要變更摘要

- 新增支援診斷包，可由 control/main.py --diagnostics 或 tools/collect_support_bundle.py 產生 zip
- 新增 tools/build_release.py，串接 PyInstaller build 與 release package gate
- 新增 Windows EXE version resource，讓檔案屬性可讀 ProductVersion/FileVersion

## 驗證紀錄

- python tools/build_release.py：成功，build returncode=0，package_check OK
- packaged exe --diagnostics：成功產出 support_bundle，啟動判斷 initialize
- Windows VersionInfo：ProductName=IEC Site Change Manager，ProductVersion=0.1.0-alpha，FileVersion=0.1.0-alpha
- python -m pytest -s .\tests：370 items collected, exit 0

## 風險與注意事項

- 目前仍是 PyInstaller onedir，簽章、安裝包、onefile/portable 部署策略尚未完成
- PyInstaller 仍收進較多第三方依賴，後續需要瘦身與乾淨機驗證

## 下一步

- 建立可交付 zip/archive 與 checksums
- 建立 GUI 診斷/關於入口，讓非工程使用者不用打命令

## Git Snapshot

### Branch Status

```text
## main...origin/main
```

### HEAD

```text
c840cb7
```

### Recent Log

```text
c840cb7 build(exe): add Windows version resource
de6681c build(release): add release build preflight
58b6c06 feat(support): add diagnostics bundle
3783c11 feat(app): add shared version identity
1912b56 docs(ai): record exe packaging session
```

### Working Tree Diff Stat

```text
<no working tree diff>
```
