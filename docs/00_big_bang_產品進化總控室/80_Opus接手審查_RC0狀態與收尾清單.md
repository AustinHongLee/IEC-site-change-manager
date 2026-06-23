# Opus 接手審查：RC0 狀態與收尾清單

> 校準者：Opus｜日期：2026-06-22｜情境：使用者請 Opus 接手「把 RC0 與未做完的部分弄一弄」
> 此文件刻意不提交，待人類 review。風格：直接、務實。

## 總評

Codex 在 Checkpoint G（doc 74）之後，已經把三個 P0 **正確地修在原始碼裡**，品質是好的、有測試、有 commit 紀律。RC0 在**原始碼層算 source-complete**。剩下的不是一堆我能在這裡盲打的程式碼，而是：**一次乾淨重建 + 一台第二機器的真人測試（Windows 工作，我做不到）**，外加幾項打磨。

## 先糾正我自己

我在對話中一度說「RC0 交付包是壞的、必須重 build」——**這句講太滿**。我原本的依據是「exe build 時間(04:15)早於資源修正 commit(05:26)」，但這在正常工作流裡不成立：開發是「改碼 → build → 測 → commit」，所以 build 早於 commit 很正常，那顆 exe 很可能已含修正。而且 doc 78 的 gate 自報「診斷探測資源路徑指向 `_internal`、packaged CLI smoke 真的產出 XLSM」，反而是 binary 已含修正的證據。

準確說法：**我在 Linux 沙箱無法獨立驗證那顆 binary 含不含修正**（這台 mount 還會餵過時/截斷的檔給 shell，連跑測試都不可信）。所以結論不是「它壞了」，而是「**它無法溯源，保險起見從 HEAD 乾淨重建一次再測**」。

## Codex 三個 P0 修法逐項審核

- **P0-1 打包資產路徑（`e35fe07`）：正確。** 新增 `control/resources.py`，`resolve_resource_dir()` frozen 時走 `sys._MEIPASS`（onedir 即 `_internal`）、dev 走 repo 根；正確區分「專案資料根 `BASE_DIR`」與「唯讀資產根 `RESOURCE_DIR`」。`config.py` 的 `TEMPLATE_PATH_*` 改用 `resource_path()`，`excel_handler` 開樣板就會到 `_internal/template`。修對了。
- **P0-2 Excel 硬需求（`f0c5c92`）：決策合理、實作正確。** `main.py:_requires_excel_runtime` 放行 health-check / audit / diagnostics，正常使用無 Excel 就以 `_enforce_excel_requirement` 顯示「此電腦不符合使用條件」並 `exit(4)`，GUI 也會跳訊息。對 RC0「內測機要有 Excel」這個前提，這是對的處理。
- **P0-3 真實產出冒煙（`64c4b9c`）+ 版本一致性（`0f5c1fb`）：方向對。** 新增 `tools/run_packaged_cli_smoke.py` 與 gate 整合、packaged exe 版本驗證。比原本「只查結構」前進一大步。

結論：這一輪 Codex 沒有做奇怪的事，是紮實的工程。

## RC0 唯一必做（Windows 上跑，我做不到）

交付包是用 `--skip-build --archive` 產的（doc 78 自述），代表打包當下**沒有重建 exe**，binary 與某個 commit 之間沒有可溯源連結。給同事前，做一次乾淨重建消除所有疑慮：

```powershell
git pull                          # 取最新 HEAD
python -m pytest -s .\tests       # 全綠（含新加的 diagnostics logs 測試）
python .\tools\build_release.py --archive --json   # 注意：不要加 --skip-build
```

gate 全綠後，照 doc 78 的人工步驟，在**第二台有 Excel 的機器**實測一次：解壓 → 第一次開啟 → 兩個 CLI 案例產出 XLSM → 開檔確認照片/欄位 → 跑 `--diagnostics` 回收 support bundle。這一步過了，才算真的可以進封閉內測。

## 本次我直接做的（原始碼）

- **`control/diagnostics.py`**：支援診斷包現在會收最新的 `logs/*.log` 尾段（唯讀、截斷到每檔最後 512KB、最多 3 檔）。理由：Excel 已是硬需求，現場「產不出來」時，dev 端需要實際 log 才能定位；原本 bundle 只有 `diagnostics.json` + `health_check.txt`，看不到 log。
- **`tests/test_diagnostics.py`**：新增 `test_collect_support_bundle_includes_recent_logs`，驗證 log 有被收進 bundle。
- 這兩個改動**未提交、未在我這邊執行**（沙箱不能跑他們的 Windows/Excel 測試）。請在 Windows 跑 `pytest tests/test_diagnostics.py` 確認再 commit。

## 仍未做（附任務契約，給 Codex 或下一輪）

每項都用契約：範圍鎖 + 硬禁區（不准順手重構/改行尾/動無關檔）+ 先給 `git diff --stat` + 一任務一 commit。

1. **build 溯源護欄（最值得做，直接解掉「binary 能不能信」這題）。**
   範圍：`tools/build_release.py`（打包時寫入 `build_info.json`：git commit、build time、APP_VERSION 到 `_internal/`）+ `tools/check_release_package.py`（gate 驗證 `build_info` 的 commit == 當前 HEAD、版本一致）。
   驗收：用 `--skip-build` 對舊 dist 打包時，若 commit ≠ HEAD，gate 必須變紅。

2. **診斷探測能力（補完 Q6）。**
   範圍：`control/diagnostics.py` 加參數讓 bundle 可選擇 `probe_com_application=True / probe_libreoffice_version=True`；`main.py` 加 `--diagnostics-probe` 旗標、GUI 加「深度診斷」。
   理由：預設不探測（避免每次啟動 Excel），但要回報「Excel/LibreOffice 到底能不能用」時可開。
   驗收：`--diagnostics-probe` 時 bundle 的 `output_capabilities` 反映真實可用性。

3. **啟動守門頂層白名單（P1）。**
   範圍：`control/project_guard.py` 的 `_looks_empty_project_root` / `RUNTIME_ARTIFACT_NAMES` 改為可設定，放行交付附帶檔（README、啟動捷徑、未來 portable LibreOffice 資料夾）；`tools/check_release_package.py` 的 `ALLOWED_TOP_LEVEL` 同步。
   驗收：package 頂層多一個 `LibreOffice/` 或 `使用說明.txt` 仍能判 initialize、gate 仍綠。

4. **PyInstaller 再瘦身（P1）。**
   `_internal` 仍含 `scipy`（≈48MB）+ `scipy.libs`（≈20MB），本工具幾乎不可能直接用到。先證明無用途，再加進 `excluded_modules`，並對核心輸出路徑重跑 packaged smoke 確認沒拔錯。

5. **（決策題，非工程）部署是 SMB 還是延遲同步雲端？** 決定單寫者鎖在多機是否安全（OneDrive/GDrive 不安全）。這題不解，多人內測的鎖就只是「看起來安全」。

## 為什麼我不在這裡直接把上面全部改掉

老實講：這台沙箱不能 build/run Windows、不能跑 Excel COM，連 mount 都會餵過時檔讓我無法在本地跑測試。在一個 Codex 正在 commit、我又無法執行驗證的 repo 上盲改一堆碼，正是「製造奇怪東西」的最佳溫床。所以我只做了一塊**自包覆、讀碼即可確認正確、不啟動 Excel** 的補強（diagnostics 收 logs），其餘給精確契約，讓有能力 build/test 的一方執行。
