# Checkpoint G 校準結果

> 校準者：Opus｜日期：2026-06-22｜對象：IEC Site Change Manager（工務修改單）EXE 產品化與交付閉環
> 標準：公司級內部工具交付。風格：直接、挑剔、務實。
> 此文件為校準意見，刻意不提交，待人類 review 後自行 commit。

## 總評

地基（啟動守門、單寫者鎖、release gate 骨架、瘦身、診斷入口）做得紮實而且有紀律；**但因為「打包資產路徑斷裂」「核心修改單輸出仍硬綁 Excel COM」「release gate 從不實際產一張修改單」三件事，目前 onedir 還不能給一般同事內測——只能給「會自己裝 Excel、看得懂 console、願意當白老鼠」的工程同事做封閉測試。先解三個 P0，再開內測。**

---

## 八問逐答

1. **onedir 足以內測嗎？哪裡不適合一般同事？**
   不足。不適合的點：(a) 打包後產修改單很可能找不到樣板（見 P0-1，health-check 驗不出來）；(b) 核心輸出沒裝 Excel 直接拒跑（P0-2）；(c) console 視窗、預設 PyInstaller icon、UPX 容易被防毒/SmartScreen 攔；(d) 任何頂層夾帶檔（說明書、啟動捷徑）會被啟動守門判成「跑錯資料夾」擋住（P1）。結論：可給工程白老鼠，不可給一般同事。

2. **「一個 exe」目標怎麼拆？（明確判斷）**
   - **現在～正式版前：維持 onedir + zip + sha256，不要追 onefile。** onefile 每次啟動解壓到 temp，PyQt6+scipy+pymupdf 會更慢、更容易被 AV 誤判，而且 onefile 的 `sys._MEIPASS` 是 temp 目錄，會直接打爛你「exe 所在資料夾＝專案根」的模型。onedir 對「資料夾即專案」最契合。
   - **正式版：走 installer（Inno Setup 或 MSI），把程式裝到 Program Files，程式與專案資料分離。** 這才是「公司每個專案開檔都能用」的正解：程式裝一份，每個專案資料夾各自存資料。**但前提是先打破現在「BASE_DIR＝exe 資料夾＝專案根」的綁定，改成「選擇／記住專案資料夾」。**
   - **portable app folder：** 只適合單一固定專案或隨身碟，不適合公司多專案（333MB × N 份、更新惡夢）。
   - **明確不建議 onefile 當最終形態。**
   - **公司內部署策略：** 程式（installer 或唯讀共用 onedir）與專案資料（各專案資料夾）分離；一支程式能開多個專案；絕不每個專案複製 333MB。

3. **啟動守門判斷安全嗎？有誤判風險嗎？**
   - first_open / missing dirs / missing settings / damaged / 誤刪 records：分層清楚、保守、不自動覆蓋（`attachments` 有料但缺 `records.json` 會 block，`damaged` 不自動修）——這塊**做得好、安全**。
   - exe + `_internal` 被忽略：正確（`RUNTIME_ARTIFACT_NAMES`，project_guard.py:41）。
   - **誤判風險（P1）：** `possible_wrong_folder` 對「任何頂層夾帶檔」過嚴。`_looks_empty_project_root`（project_guard.py:308-317）只放行 `.git*` 與 exe/`_internal`；只要套件多一個 `使用說明.txt`、`啟動.bat`、或未來的 `portable LibreOffice/` 頂層資料夾，首次啟動就會被判 `possible_wrong_folder` 擋下（project_guard.py:346-354）。`check_release_package` 的 `ALLOWED_TOP_LEVEL`（check_release_package.py:29）也同樣只准 exe+`_internal`——兩邊一起卡死「附說明檔 / 隨包 LibreOffice」。
   - 小瑕疵：`elif first_open or looks_empty and not marker_exists`（project_guard.py:355）運算子優先序（and 先於 or）可讀性差，建議加括號明確化。

4. **release gate 還缺哪些關鍵檢查？**
   有：zip checksum（✓）、diagnostics（✓）、頂層乾淨（✓）、內嵌資產存在（✓）、啟動判斷＝initialize（✓）、exe --health-check（✓）。
   缺：
   - **真實產出冒煙**（最關鍵）：gate 從不用 demo 附件實際產一張修改單並核對輸出檔非空、可開。所以 P0-1、P0-2 都能綠燈過 gate。
   - **版本一致性**：`app_info.APP_VERSION` 與 `windows_version_info.txt` 兩處手維（目前都 0.1.0-alpha），無檢查綁定；archive 命名用 APP_VERSION，可能與 exe 內嵌版本資源不一致而沒人發現。
   - **內嵌資產完整性**：只查「存在」，不查 hash/size，截斷或損壞的樣板會過關。
   - **乾淨機冒煙**：目前只在 build 機跑，抓不到缺 VCRedist / 缺 Excel / 缺 LibreOffice。
   - **COM / LibreOffice 邊界探測**：gate 不報告目標機有沒有可用的 Excel 或 LibreOffice。

5. **PyInstaller 瘦身排除清單危險嗎？**
   目前排除（`torch`/`torchvision`/`tensorflow`/`tensorboard`/`pytest`）**安全且有測試 pin**（test_packaging_spec.py），誤排風險低——這些確實沒被產品執行期用到。
   但方法是**反應式黑名單**，而且漏了大魚：`_internal` 裡 **scipy 48MB + scipy.libs 20MB ≈ 68MB**，本工具幾乎不可能直接用到 scipy，是下一個明顯排除標的（先證明無用途再排）。另外 `cryptography` 10MB、`pydantic_core` 6MB、`lxml` 7MB 來路不明，代表依賴圖沒被稽核過。誤收（不該收卻收）風險明顯高於誤排。

6. **GUI 支援診斷入口夠給非工程同事回報嗎？**
   有入口（✓，HealthCheckPanel:3304，「支援診斷包」按鈕 + 版本資訊）。但對非工程同事**還不夠**：診斷包（diagnostics.py）不收 `logs/`、`probe_com_application=False`、`probe_libreoffice_version=False`、無 settings 快照、無「一鍵開啟資料夾／複製路徑」、無讓使用者填一句「發生什麼事」的欄位。最常見的「PDF 產不出來」正好需要這些才能遠端判斷。

7. **下一階段最值得做的 3~5 件（風險/價值排序）**
   1. 修打包資產解析（P0-1）：加 `resource_path()`／用 `sys._MEIPASS`，或 first-run 從 `_internal` 部署樣板到專案。
   2. release gate 加「真實產出冒煙」（讓 gate 真能擋 P0）。
   3. 釐清 Excel COM 邊界（P0-2）：決定無 Excel 機要不要能產核心修改單，或明確標限制。
   4. 啟動守門/gate 頂層白名單可設定（為 portable LibreOffice 與說明檔預留）。
   5. 版本一致性 gate + 診斷包補 logs/COM/LibreOffice 探測。

8. **P0/P1/P2** — 見下方三節。

---

## 目前最強的地方

- **啟動守門判斷模型**分層清楚、保守、不自動覆蓋：誤刪 records 會 block、`damaged` 不自動修、壞 JSON 不覆蓋。這是公司級資料安全該有的態度。
- **release 骨架完整**：`build_release` → `check_release_package`（頂層乾淨／內嵌資產／啟動判斷＝initialize／exe --health-check）→ `--archive`（zip + sha256），而且 `archive_dir` 不准在 package 內（build_release.py:80）這種細節都顧到了。
- **瘦身有紀律**：738MB→333MB，且有 test pin 排除清單、有回補紀錄。
- **診斷與識別齊**：GUI 診斷入口、`--diagnostics` CLI、Windows 版本資源、`app_info` 單一識別源。
- **上輪建議確實落地**：`.gitattributes`、`.editorconfig`、命名收斂（移除 `_export_real_attachments_showcase` 別名）、AI 改動黑盒記錄器都做了。紀律有在走。

## 最大風險

**打包後的 exe 從未被證明能產出一張真正的修改單。** 三個 P0 疊在一起：資產路徑斷裂（找不到樣板）、核心輸出綁 Excel COM（乾淨機拒跑）、gate 只驗結構不驗產出（綠燈騙人）。三者交集 = 你可能交付一個「能開、能過 health-check、但一按產出就壞」的 exe，而且現在的驗證流程抓不到。

---

## P0 清單（不解不該交付公司內測）

- **P0-1　打包資產路徑斷裂。**
  spec 把 `template/`、`control/image`、`material_pricebook_seed.json`、`wizard_data.json` 打包進 `_internal/`（實測 `dist/IEC-site-change-manager/` 頂層只有 exe + `_internal/`，頂層無 `template/`）。但 `config.py` 算的是 `BASE_DIR/template`（frozen 時 BASE_DIR＝exe 資料夾，不是 `_internal`），`excel_handler.py:250` 就用這個路徑 `Workbooks.Open(tpl["path"])`。**全 repo 零 `sys._MEIPASS`**，沒有任何橋接。health-check / release gate / 372 測試都不載入樣板（測試在 dev 模式跑，dev 的 BASE_DIR 是 repo 根、頂層剛好有 template/），所以全都驗不出來。
  → 修法：加資源解析（read-only 資產走 `sys._MEIPASS`），或 first-run 從 `_internal` 部署一份樣板到專案根。
  → **必做驗證：用 build 出來的 exe，真的產一張修改單，確認 xlsx/pdf 非空可開。**

- **P0-2　核心修改單輸出硬綁 Excel COM。**
  `main.py:235-238`：`detect_excel_com()` 不可用即 `sys.exit(4)`；`excel_handler.py:250` 走 COM `Workbooks.Open`。LibreOffice 路線目前覆蓋的是「輸出中心」統計/summary/photo PDF，不等於能填 `.xlsm` 修改單。→ 沒裝 Microsoft Excel 的乾淨機，核心功能直接拒跑。這跟「一個 exe 給每個同事用」的目標正面衝突。
  → 決策：要嘛內測明文規定「機器要裝 Excel」，要嘛投資 LibreOffice headless 填 xlsx 的非 COM 主線。

- **P0-3　release gate 不做真實產出冒煙。**
  `check_release_package` 只驗：頂層乾淨、`_internal` 資產存在、啟動判斷＝initialize、exe --health-check 回 0。**從不實際產一張修改單。** 所以 P0-1、P0-2 都能過 gate。gate 目前給的是虛假安全感。
  → 修法：gate 內用內建 demo 附件，從 exe 跑一次真實產出，核對輸出檔存在、非空、可開；故意把 `_internal/template` 改名時 gate 必須變紅。

## P1 清單（內測可接受，正式版前應補）

- **啟動守門 / gate 頂層白名單過嚴**：夾帶任何頂層檔（說明書、啟動捷徑、未來 portable LibreOffice 資料夾）會被判 `possible_wrong_folder` 擋住，且 gate 也會擋。需把白名單做成可設定，為交付附件與隨包 LibreOffice 預留。
- **版本一致性無 gate**：`app_info.APP_VERSION` vs `windows_version_info.txt` 兩處手維，無檢查。應在 gate 加「exe 內嵌版本 == APP_VERSION == archive 命名」。
- **雲端共用 + 單寫者鎖在「延遲同步雲端資料夾」不安全**：`O_EXCL` 與 `os.replace` 只在本地原子；跨機 PID 檢查無效（`_windows_process_exists` 只認本機），只能等 30 分鐘心跳逾時（project_guard.py:791-810, 840-866）。SMB 網路磁碟尚可，OneDrive/Google Drive/Dropbox 這類延遲同步資料夾**會讓兩台機器同時搶到鎖**。需先確認部署到底是哪種（見人類決策）。
- **診斷包對非工程同事不足**：不收 `logs/`、不探測 Excel/LibreOffice 是否可用、無 settings 快照、無使用者描述欄、無一鍵開資料夾。
- **scipy ~68MB 殘留**：瘦身下一個明顯標的（先證明無用途）。

## P2 清單（產品成熟度）

- onefile（不建議當最終形態）/ installer（建議）/ 程式碼簽章 / portable LibreOffice 隨包 / 自訂 icon / 關閉 console。
- 依賴圖稽核：釐清 `cryptography`/`pydantic_core`/`lxml` 為何被收，把排除從反應式黑名單改成有依據的白名單。
- 機械護欄補最後一角：pre-commit hook 仍未落地（`.gitattributes`/`.editorconfig` 已有，但 `.git/hooks/pre-commit` 不存在），擋大 commit / 缺測試。
- 乾淨機冒煙自動化（VM / 沙箱）。

---

## 對「一個 exe」目標的決策建議

明確結論，不騎牆：

1. **內測階段就用 onedir + zip + sha256，凍結 onefile。** onefile 會打爛「資料夾即專案」模型、拖慢啟動、加劇 AV 誤判。
2. **正式版走 installer + 程式/資料分離。** 程式裝一份到 Program Files，使用者在每個專案資料夾各自存資料。**這要求先重構「BASE_DIR＝exe 資料夾」為「選擇/記住專案資料夾」**——這是達成「公司每個專案開檔都能用」的關鍵前置，比 onefile 重要得多。
3. **絕不每個專案複製整包 333MB。** portable 只留給隨身碟/單專案特例。
4. UPX 在簽章/AV 場景弊大於利，正式版建議關 UPX 並改為簽章。

一句話：**onefile 不是你的目標，「程式與專案資料分離的可安裝程式」才是。** 先別把力氣花在把 333MB 壓成單一 exe。

## 建議 Codex 下一步 3 件事

每件都用任務契約：範圍鎖 + 硬禁區（不准順手重構/改行尾/動無關檔）+ 先給 `git diff --stat` 才寫 + 一任務一 commit。

1. **修打包資產解析（解 P0-1）。**
   範圍鎖：新增 `control/resources.py`（resource_path：frozen 走 `sys._MEIPASS`，dev 走 BASE_DIR）、改 `config.py` 樣板/seed/image 路徑、`excel_handler.py` 取樣板處。
   驗收：build exe 後用內建 demo 附件產一張修改單成功；`pytest` 維持綠；把 `_internal/template` 改名時要明確報錯而非靜默。

2. **release gate 加真實產出冒煙（解 P0-3）。**
   範圍鎖：`tools/check_release_package.py` + 一個 demo 附件 fixture。
   驗收：gate 會實際從 exe 產一張修改單並核對輸出非空可開；故意移除/改名 `_internal/template`，gate 必須變紅（紅了才算這個檢查有效）。

3. **啟動守門頂層白名單可設定 + 版本一致性檢查（解 P1 兩項）。**
   範圍鎖：`project_guard.py`（白名單）、`check_release_package.py`（版本一致性）、`app_info.py`。
   驗收：在 package 頂層加一個 `LibreOffice/` 資料夾仍能判 initialize；當 exe 版本資源 ≠ APP_VERSION 時 gate 變紅。

## 需要人類決策的問題

1. **部署到底是 SMB 網路磁碟，還是延遲同步雲端（OneDrive/GDrive/Dropbox）？** 直接決定單寫者鎖安不安全、要不要提前上中央伺服器/DB。
2. **乾淨機要不要假設裝了 Microsoft Excel？** 還是要做到「無 Excel 也能產核心修改單」（LibreOffice headless 填 xlsx）？這是最大成本分叉，影響 P0-2 的修法。
3. **「每個專案開檔都能用」走哪條路？** 一支安裝程式開多專案資料夾（需重構 BASE_DIR 綁定，建議），還是每專案一份 onedir（簡單但肥、更新惡夢）？
4. **正式版要不要程式碼簽章？** 不簽，AV/SmartScreen 會擋一般同事；UPX 又加劇誤判。簽章要採購憑證（成本/流程決策）。
5. **console 視窗**：內測留著看訊息可接受，正式版要不要關（關了出事更難查，要搭配診斷包補強）？
