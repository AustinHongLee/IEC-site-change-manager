# Checkpoint H 校準結果：RC0 交付前審查

> 校準者：Opus｜日期：2026-06-23｜以本機檔案與 git 實況為準，非文件敘述
> 風格：挑毛病、找交付風險、驗證證據鏈。此文件刻意不提交，待人類 review。

## 證據鏈（實況）

- `git rev-parse HEAD` == `git rev-parse origin/main` == `6ee4addc777bc3b76c6bf5cf646835bf2d374bd7`（與 Codex 自述一致）。
- `dist/IEC-site-change-manager/_internal/build_info.json`：`git_commit` = `6ee4add…`（== HEAD）、`source_dirty` = `false`、`app_version` = `0.1.0-alpha`。→ **這份 dist 可溯源到一個乾淨 commit**，不是黑盒。
- 工作樹：只有我前幾輪的未追蹤 docs（74 / 79 / 80 / inbox glass mockup）為 `??`；程式碼本身乾淨。
- 我在 Linux 沙箱**無法 build/run Windows、無法跑 Excel COM**，且這台 mount 會餵過時/截斷檔給 shell；以下結論一律以 Read 工具（真實檔）+ git 為證，凡需實機執行處我都標明。

## 1. 這輪 Codex 修法是否正確？破口？

整體：**正確、有測試、commit 粒度好，沒有做奇怪的事。** 逐項：

- P0-1 資源路徑（`control/resources.py`）：`resolve_resource_dir()` frozen 走 `sys._MEIPASS`、dev 走 repo 根，`config.py:33-34` 用 `resource_path()`。正確。
- Excel 硬需求（`main.py:119-120, 147-152`）：正常啟動才強制，`detect_excel_com()` 不可用就清楚報錯 `exit(4)`。正確。
- build_info gate（`tools/check_release_package.py:97-137`）：驗 schema / app_version / `git_commit == HEAD`。正確。
- 白名單（`project_guard.py:42-50, 322-335`）：需 runtime artifact 在場才放行 distribution 檔。正確但脆（見 §4）。
- 診斷 probe + logs（`diagnostics.py:39-68, 71-91, 143-172`）：opt-in、預設 False、`_collect_log_excerpts` 唯讀截斷。正確。

破口（按嚴重度）：

- **B1（信任假象）`source_dirty` 只記 warning，且偵測漏 untracked。** `check_release_package.py:133-134` 把 `source_dirty: true` 列為 warning，`has_errors` 不含 warning（line 430）→ **髒工作樹建出的包仍 `ok: true` 過 gate**。而 `build_release.py:63-65` 的 `_source_dirty()` 用 `git diff-index --quiet HEAD --`，**不偵測未追蹤新檔**。所以「build_info.commit == HEAD」可以為真，但實際建置位元 ≠ 該 commit。
- **B2（UX/穩定）深度診斷阻塞 GUI thread。** `gui_panels.py:3457-3465` 的 `create_support_bundle(probe=True)` 直接在 UI thread 同步呼叫 `collect_support_bundle(..., probe_com_application=True)`，**無 QThread、無 wait cursor、無禁用按鈕**。探測會啟動 Excel COM，期間視窗凍結（Not Responding）；若 Excel 跳 modal（啟用/修復對話框），`excel.Quit()`（`capabilities.py:124`）可能久卡。
- **B3（脆）白名單是硬編碼名單。** `project_guard.py:42-50` 只認 `README.md/txt`、`使用說明.md/txt`、`啟動工務修改單.bat/cmd`、`LibreOffice`。換名字（`操作手冊.pdf`、`start.bat`、`LibreOfficePortable/`）就會誤觸 `possible_wrong_folder` 擋住第一次啟動。
- **B4（已知限制）provenance 只在有 git 的機器可驗。** `check_release_package.py:81-94, 123-126`：`_current_git_commit()` 在 `_ROOT` 跑 `git rev-parse HEAD`；交付到無 git 的客戶機，gate 無法自驗（這是預期的「出廠前檢查」，但要知道 zip 本身不自證）。

## 2. build_info gate 真能解決「交付包能不能信」？

**大致能，但不是密碼學級保證。** 能信的部分有測試背書：`tests/test_check_release_package_tool.py:90-101` 用 `git_commit="deadbeef"` 證明 commit 不符會 `returncode==1` + `build_info_git_commit_mismatch`；`:77-87` 證明缺 build_info 會擋。`--skip-build` 不會重生 build_info（`build_release.py:205-207` 只在非 skip 分支呼叫 `_write_build_info`），所以 HEAD 一前進、舊包就 mismatch 變紅 → 防 stale。

**不能信的部分**：B1 的髒樹/未追蹤漏洞——gate 會說「對應 commit X」，但不保證位元就是 X 的乾淨狀態（只給 warning）。所以準確說法是：**gate 保證「這包宣稱對應某 commit，且乾淨度有自述」，不保證「位元 = 該 commit 的乾淨建置」。** 對封閉內測夠用；對外發佈前要把 B1 收掉。

## 3. --skip-build / --archive / 乾淨 rebuild 還有假綠嗎？

- **stale 假綠：已關閉**（理由同 §2）。
- **殘留假綠**：(a) 髒工作樹 → 仍 `ok`（B1）；(b) 未追蹤新檔 → `source_dirty` 偵測不到（B1）；(c) **顯式關閉**：`--no-cli-smoke`（`build_release.py:287-292`）或 `--no-health-check`（`:278`）會跳過真輸出冒煙 / 版本 / 資源探測，這是人為選項但會產生「結構綠、行為未驗」的包。
- 注意正面證據：`build_release.py:183` `run_cli_smoke` 預設 **True**，且 `check_release_package` 在 `--skip-build` 路徑仍會被呼叫（`:219-228`）→ **預設情況下，連 `--skip-build --archive` 都會跑真輸出冒煙 + provenance + 資源路徑探測**。這是相對紮實的 gate。

## 4. project_guard 白名單過寬或過窄？

- **不過寬**：`_looks_empty_project_root`（`project_guard.py:322-335`）只有在 `has_runtime_artifact`（exe/`_internal` 在場）時才放行 distribution 名單；隨機非空資料夾不會被誤判成 distribution。`tests/test_check_release_package_tool.py:117-127` 證明頂層放 `records/` 仍被擋（`top_level_extra`）。
- **過窄/脆**：硬編碼名單，換名字就誤擋（B3）。`tests/test_check_release_package_tool.py:130-143` 只測了那幾個精確名稱會過。
- 建議：改 **sentinel 檔**策略——交付包頂層放一個 `.iec_distribution` 標記檔，存在時放行任何附帶說明/啟動檔；或改副檔名白名單（`.pdf/.txt/.bat`）。比硬編碼名單耐用。

## 5. 深度診斷會誤觸 Excel / 卡 GUI / 擋到支援命令？

- **支援命令不被 Excel 硬需求擋：正確。** `_requires_excel_runtime`（`main.py:137-144`）放行 `health_check / audit_integrity / diagnostics / diagnostics_probe`。無 Excel 機**可以**跑 `--diagnostics-probe` 查為什麼。
- **不漏 Excel process：正確。** `capabilities.py:86-126` `excel=None` 初始化、`finally` 守 `if excel is not None` + try/except 包 `Quit()`，且結果有快取（`:25, 47-48, 252`），每 process 只探一次。
- **但會卡 GUI：是（B2）。** 桌面按「深度診斷包」期間 UI thread 凍結。這是這輪唯一明顯的使用者可感缺陷。

## 6. 最新 zip 是否足以進入封閉內測？

**可以——進「1-2 台確定有 Excel 的受控機器」封閉測試（doc 78 範圍），無新增程式碼 P0 阻擋。** 依據：可溯源（build_info commit==HEAD、dirty=false）、gate 預設跑真輸出 cli_smoke + 版本 + 資源路徑探測 + health、且這些都有測試背書。

**前提（必須留證）**：我無法在此實機驗證那顆 zip，所以「可進」成立的條件是——**該 zip 確實由 `build_release.py`（未加 `--no-cli-smoke`/`--no-health-check`）完整產出且 gate 全綠**。請保留當次 `python tools/build_release.py --archive --json` 的輸出（其中 `package_check.ok == true`、`cli_smoke.ok == true`、`build_info.ok == true`）作為交付證據。

**不阻擋封閉測試、但擴大前要收**：B2（深度診斷凍結）、B1（dirty 軟 + untracked 漏）、B3（白名單脆）。

## 7. 下一步 P0 / P1 / P2

- **P0（進封閉內測前）**：無新增程式碼 P0。唯一硬要求＝**保存交付 zip 的 `build_release --json` 全綠輸出**（證明它走過完整 gate，而非 `--no-cli-smoke`）。
- **P1（擴大內測前必收）**：
  1. B1：`source_dirty` 改為 gate 失敗（或要 `--allow-dirty` 才放行）；`_source_dirty()` 改用 `git status --porcelain`（含 untracked）。
  2. B2：深度診斷改非阻塞（QThread + wait cursor + 禁用按鈕 + 探測 timeout）。
  3. B3：白名單改 sentinel 檔或副檔名策略。
- **P2（產品成熟度）**：深度診斷加 LibreOffice/Excel 探測超時保護；provenance 在無 git 機的對照自驗；`scipy`（≈68MB）瘦身；installer / 簽章 / portable LibreOffice。

## 8. 給 Codex 的任務契約（P1-1：provenance 收緊，最高價值）

```text
任務：讓 release gate 對「不乾淨建置」真的擋下，而不是只記 warning。

範圍鎖（只准改這些檔）：
- tools/build_release.py
- tools/check_release_package.py
- tests/test_build_release_tool.py
- tests/test_check_release_package_tool.py

要做：
1. build_release.py：_source_dirty() 改用 `git status --porcelain`（包含 untracked），
   任何非空輸出即視為 dirty。
2. check_release_package.py：build_info 的 source_dirty == true 從 warning 升為 error
   （code: build_info_source_dirty），讓 has_errors=True、gate 變紅；
   另加 CLI 旗標 --allow-dirty 時才降級為 warning。
3. 測試：新增「dirty 包預設被擋」「--allow-dirty 才放行」「untracked 新檔會被判 dirty」。

硬禁區：
- 不准改資源路徑/Excel/診斷邏輯；不准動 GUI；不准順手重構或改行尾。
- 不准放寬既有任何檢查。

驗收（自己跑並貼結果）：
- python -m pytest -s tests/test_check_release_package_tool.py tests/test_build_release_tool.py
- 故意改一個 tracked 檔不 commit → python tools/build_release.py --skip-build --json
  → package_check.ok == false、issues 含 build_info_source_dirty
- 加 --allow-dirty → 同情境變回可過但保留 warning

交付：先給 git diff --stat 與測試輸出，我同意才算完成；一任務一 commit，
訊息 feat(release): fail gate on dirty/untracked build provenance。
```

接續契約（不在本次範圍，但排 P1）：B2 深度診斷非阻塞、B3 白名單 sentinel 化。
