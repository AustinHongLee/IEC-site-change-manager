# 下一步計畫書：輸出中心閉環與 EXE 產品化

日期：2026-06-18

## 目前狀態

本專案已從原本成熟的現場修改單工具，往公司級產品化方向推進出一條可驗證主線：

- 啟動守門、健康檢查、單寫者鎖、原子寫入、操作 journal 已建立基礎安全層。
- 材料價目、請款批次、稽核紀錄已有第一階段資料層與 UI。
- `CanonicalReportSet` 已成為現場資料核心，能統一收集 records、attachments、焊口、用料、照片、問題提醒。
- 非 COM 輸出路線已建立，包括 xlsx template、LibreOffice PDF converter、pdf overlay renderer。
- `Site Output Center` 已成為正式輸出中心，能輸出統計 Excel、summary PDF、照片 PDF、資料 JSON。
- 輸出中心結果頁已能分組、定位修改單、解除篩選、處理資料提醒。
- `note` 可在程式內編輯，`before/after` 缺照提醒可直接接入加圖流程。

目前最重要的方向不是再堆更多輸出格式，而是把「發現問題 → 修資料 → 重新輸出 → 確認交付」做成閉環。

## 近期主線

### A. 輸出中心修正閉環

目標：讓輸出中心成為現場資料的工作台，而不只是產檔按鈕。

下一步：

1. 修完 `note` 或照片後，提示使用者重新跑輸出中心。
2. 保留上一次輸出 scope/content/output_dir，讓「重新輸出」不用重選。
3. 結果頁顯示修正後仍存在的提醒數量。
4. 對 `weld_or_material` 提供更明確入口：定位修改單後切到焊口/材料 tab。
5. 對 `parse_error` 提供更明確的人話提示，指出要檢查資料夾名稱、`GroupWeld.txt` 或 `materials.txt`。

驗收：

- 使用者從結果頁處理完 note/照片後，可以一鍵重新輸出。
- 重新輸出後，同一筆 issue 不應再出現。
- focused 與 full tests 持續通過。

### B. attachments 測試資料入庫策略

目標：處理目前 health audit 的既有 warning：兩個 attachments 測試資料夾尚未寫入 `records.json`。

選項：

1. 保留為 showcase 測試資料，並在 audit 中提供「這是測試資料」的白名單或說明。
2. 提供安全入庫工具，將 attachments-only 資料轉成 records 草稿。
3. 在輸出中心中清楚標示「未產出 / 尚未入庫」而不是只當 warning。

建議：

- 先做「attachments-only 入庫草稿」工具。
- 不自動寫 records，先 dry-run 顯示會新增哪些紀錄。
- 使用者確認後才寫入 records，並留下 journal。

驗收：

- health audit 可區分「真的孤兒附件」與「刻意保留的展示資料」。
- 入庫流程不覆蓋既有 records。

### C. EXE 產品化

目標：公司使用者只需要一個 EXE，放進專案資料夾後即可啟動。

下一步：

1. 定義 EXE 啟動路徑規則：以 EXE 所在資料夾作為專案根目錄。
2. 啟動時檢查必要資料夾與檔案：
   - `attachments/`
   - `records/`
   - `output/`
   - `pdf/`
   - `staging/`
   - `logs/`
   - `settings.json`
3. 對第一次開檔、誤刪、跑錯資料夾給不同提示。
4. 建立 PyInstaller spec。
5. 決定 LibreOffice 策略：
   - 短期：settings 指定本機或 portable path。
   - 中期：隨產品包提供 portable LibreOffice。
6. 建立 release smoke：
   - EXE 可啟動。
   - 健康檢查可跑。
   - 輸出中心可用測試資料產出 Excel/PDF。

驗收：

- 空白資料夾第一次啟動能初始化。
- 缺空資料夾能修復。
- 壞 JSON 不自動覆蓋。
- 第二個程式不可重複寫入。
- EXE smoke 有固定測試步驟。

### D. 多格式輸出產品化

目標：支援不同公司不同表單，但核心資料保持同一份。

下一步：

1. 建立 template registry UI。
2. 把目前 demo/pdf overlay template 分成：
   - 內建測試模板
   - 專案模板
   - 公司模板
3. 針對 PDF overlay 加上可視化 template debug output。
4. 針對純 Excel 貼照片格式，補 xlsx template 實務範例。
5. 針對可填式 PDF 表單，另開 AcroForm renderer spike，不和座標 overlay 混在一起。

驗收：

- 同一份 `CanonicalReportSet` 可輸出至少兩種模板。
- 模板 dry-run 能在產檔前指出缺欄位、缺照片、表格超列。

### E. 材料與請款第二階段

目標：不要讓材料/請款拖住現場主線，但保留可請款的資料基礎。

下一步：

1. 材料登記 UI 簡化成現場可填的最小欄位：
   - 零件
   - 尺寸
   - SCH
   - 材質
   - 數量
   - 單位
2. 價目表維持完整追溯，但現場登記不要被複雜欄位壓垮。
3. 請款批次補「待請 / 已送 / 已核 / 已收 / 退回」看板。
4. 請款匯出與輸出中心共用結果 envelope。

驗收：

- 未配價材料不能靜默變 0 元。
- 已請款資料不可被重跑覆蓋。
- 批次狀態異動都有 audit。

## Opus 下一次校準建議

建議等以下任一條件達成後再請 Opus 進場：

- 輸出中心修正閉環完成。
- attachments-only 入庫草稿完成。
- EXE 啟動守門 smoke 完成。

校準題目建議：

```text
請審查目前 IEC Site Change Manager 的產品化路線。
重點檢查：
1. 輸出中心是否已從產檔工具進化成現場資料修正閉環。
2. attachments-only 資料入庫策略是否安全，不會污染 records。
3. EXE 啟動守門是否足以支援公司多人專案使用。
4. 多格式輸出是否維持 CanonicalReport 單一資料核心，而不是重新分裂。
5. 材料/請款是否有被過度設計，或仍缺不可少的稽核邊界。

請列 P0/P1/P2 風險與下一步 3 個最值得做的工程項目。
```

## 目前上傳 GitHub 前建議驗證

每次重要上傳前至少跑：

```powershell
python -m pytest -s .\tests
python .\control\main.py --health-check
git diff --check
```

目前最近驗證結果：

- full tests：337 passed
- health-check：healthy
- audit：error=0，warning=1
- warning：兩個 attachments 測試資料夾尚未寫入 `records.json`
- `git diff --check`：無 whitespace error，只有既有 CRLF 提示

---

# 【Opus 校準意見｜2026-06-22】

> 本節由 Opus 加註，是我的意見與批判，不是原計畫書作者的結論。原計畫書上半部維持不動。風格依使用者要求：不客氣、吹毛求疵。

## 0. 先處理：已修掉的現行傷害（CRLF 地雷）

事實（用 git 指令查證，非臆測）：

- 進場時整個工作區 41 個被改檔呈現 `N 增 = N 刪` 的對稱 diff，合計 36937/36937。
- `git diff HEAD --ignore-all-space` ＝ 零。代表內容一字未改，這 41 檔 100% 只是行尾被整檔從 LF 改成 CRLF。
- repo 沒有 `.gitattributes`，所以沒有任何東西在擋這件事。
- 過程中還撞到一顆 stale `.git/index.lock`（前一個 git 程序崩潰殘留），以及一次 index 損壞。

我做了什麼：

- 加 `.gitattributes`（鎖 LF、`.bat/.cmd/.ps1` 保 CRLF、影像/PDF/xlsx 視為二進位），commit `07bfb3d`。
- 把工作區行尾正規化回 LF，幻影 diff 歸零，`git status` 乾淨，251 檔追蹤。
- 過程中我自己也踩到 index 損壞、誤產一個空樹 commit；已安全 `reset --hard` 回好 commit `4156009`，零資料遺失。這恰好證明下面要講的事：**這個 repo 現在連基本 git 操作都不穩，任何 agent 進來都容易出事。**

為什麼這是「Codex 做奇怪的事」的本質：它（或它叫起來的格式化工具／編輯器）會整檔重存——改行尾、重排版、動 import 順序——把雜訊和真改動混進同一坨，讓你永遠看不出它到底動了哪一行。這不是小事，是會讓 review 與回滾整個失效的系統性風險。

## 1. 專案現況體檢

### 1.1 Git 紀律崩壞 — P0，最高優先

整個 repo 只有 2 個 commit，卻塞進 21+ 模組、337 測試、輸出中心、材料/請款。等於「一個 commit ＝ 一整座城市」。無法逐項 review、無法 `git bisect`、無法回滾單一功能。沒有 `.gitattributes`（已補）、沒有 pre-commit、沒有 CI，完全靠 agent 自律。結論：在補上「機械護欄」之前，叫 Codex 做任何事都是在沒有安全網下走鋼索。

### 1.2 UI 結構性問題 — 你的直覺是對的

證據：

- 巨石檔：`gui_panels.py` 4725 行、`wizard.py` 3322 行、`gui_dialogs.py` 2813 行。單檔破 4000 行 ＝ agent 一改就誤傷遠處。
- 「輸出中心」概念 vs 實作嚴重不符：計畫書把它講成「現場資料的工作台／閉環核心」，實作卻只是 `RecordManagerPanel` 裡一顆按鈕（變數名還停在舊概念 `btn_photo_grid_pdf`），按下去跳一個 `QDialog`。**工作台被做成了彈窗。**
- 命名債：`_export_real_attachments_showcase = _export_site_output_center`（別名疊別名）；按鈕文字寫「輸出中心」變數卻叫 `photo_grid_pdf`。概念換過三輪（showcase → 現場輸出 → 輸出中心），舊名字沒清。Codex 會被殘留名字誤導，繼續長出第四個名字。
- 資訊架構錯位：6 個 tab（產出報告／紀錄管理／材料價目／請款追蹤／設定／健康）是按「資料表」分，不是按「現場工作流」分。但你要的閉環（記錄 → 焊口/材料 → 輸出 → 提醒 → 回記錄）是橫切的，UI 卻逼使用者在 tab 與彈窗間跳。這就是你說「概念上不適合」的根。

### 1.3 計畫書 53 自身會誘導發散

5 條平行主線（A 輸出閉環／B 入庫／C EXE／D 多格式／E 材料請款）同時開。對 Codex 來說平行 ＝ 它會在主線間亂跳，每條做一半。更嚴重的是它跟你自己的 roadmap 紀律打架：核心原則寫「Phase 0–1 只止血，不加材料/請款新功能」，但 53 的 E 段直接加請款看板（待請/已送/已核/已收/退回），D 段又要 template registry UI ＋ AcroForm spike。**計畫書自己就破了戒。**

## 2. 新方案：Codex 護欄（讓它不要做奇怪的事）

核心思路：不要靠 Codex 自律，要用工具擋 ＋ 用契約鎖。

### 2.1 機械護欄（寫進 repo，讓工具擋）

1. `.gitattributes`（已完成）——永久消滅行尾雜訊。
2. 加 `.editorconfig`：LF、UTF-8、Python 4 空格、不自動重排——編輯器層再擋一次。
3. 加 pre-commit hook（本機即可，不需 CI）：擋單一 commit 超過門檻（例如 >15 檔或 >800 行就拒絕）、跑 `git diff --check`、擋「改了 `control/*.py` 卻沒有對應 `tests/` 改動」。
4. 規定：**一個任務 ＝ 一個 commit**，訊息用 `type(scope): 動詞+對象`。禁止整檔重存。

### 2.2 任務契約（每次叫 Codex 前必貼）

每個任務都要含：範圍鎖（只准改哪些檔）、硬禁區（不准重排 import／改行尾／改無關名稱／順手重構）、驗收（pytest 維持 337 passed、health-check 維持 healthy）、交付方式（先給 `git diff --stat`，同意才寫）、單一焦點（一次只給一條主線的一小步）。可直接複製的模板見第 5 節。

### 2.3 主線重排：把 5 條平行收斂成 1 條有序的線

- **P0 地基（做完才准往下）**：git 護欄（已起步）＋ UI 安全網（先補輸出中心/主面板的煙霧測試，讓之後動 UI 有保護）。
- **P1**：輸出中心閉環（53 的 A）——但先把它從「彈窗」升級成「正式分頁」，否則閉環是做在彈窗裡，越做越歪。
- **P2**：EXE 啟動守門（53 的 C）。
- **P3**：attachments 入庫草稿（53 的 B）。
- **凍結到 Phase 2（明確禁止現在碰）**：D 多格式 registry、E 請款看板。寫進計畫書，Codex 才不會自己去開。

## 3. 新延伸方案

1. **輸出中心 → 現場交付中心**：把彈窗扶正為主畫面，不只是產檔，而是「本次交付清單」——哪些修改單已輸出/缺照/缺 note/未入庫，一頁看完並一鍵跳去修。直接打中 UI 痛點。
2. **AI 改動黑盒記錄器**：每次 Codex 跑完，自動把 `git diff --stat` ＋ 測試/health 摘要存到 `ai_sessions/`。事後能追「哪次改壞的」。低成本高保險。
3. **健檢從「警告」升級成「待辦」**：現在 health audit 給 warning（兩個孤兒附件）。改成可勾選處理的待辦清單，接到入庫草稿工具。
4. **模板 dry-run 前移到 UI**：你已有 `template_dry_run.py` 但只在 CLI。搬到產檔前的預檢面板，缺欄位/缺照/超列在產檔前就講。
5. **雲端「誰在編輯」狀態列**：記憶裡最危險地雷是多人無聲覆蓋。UI 上做一條「目前鎖持有者 ＋ 心跳時間」狀態列，讓現場看得到。

## 4. UI 更新方案（能做，但要排序）

先講老實話：你的紀律是「先止血再美化」。大改 UI（拆巨石、重排資訊架構）是高風險動作，**不該在 git 護欄都還沒立、輸出閉環還沒收的此刻整碗端掉**。但「能不能做」的答案是：可以，但切成安全小步，而且先補測試網。順序如下：

- **第 0 步（立刻、低風險）命名收斂**：把 `btn_photo_grid_pdf`、`_export_real_attachments_showcase` 等殘留舊名清成單一概念名。純改名、有測試保護，Codex 最不容易出包。
- **第 1 步 資訊架構**：把「輸出中心」從 `RecordManagerPanel` 的彈窗，升級成第一級分頁（和「產出報告」平級），做成常駐工作區。
- **第 2 步 工作流導向 tab**：現在 6 個 tab 是「資料表導向」。改成「工作流導向」四區——① 現場填單 ② 交付中心（輸出＋閉環） ③ 管理（紀錄/材料/請款收進次選單） ④ 系統（設定/健康）。最常走的路徑放最前。
- **第 3 步 巨石拆分**：`gui_panels.py` 4725 行拆成 `record_panel / material_panel / billing_panel / health_panel / output_center_panel` 各自獨立檔。**拆之前必須先有 UI 煙霧測試**，否則就是讓 Codex 在 4700 行裡裸奔。

## 5. 可直接貼給 Codex 的任務契約模板

```text
任務：<一句話，一條主線的一小步>

範圍鎖（只准改這些檔）：
- <file A>
- <file B>

硬禁區：
- 不准改任何其他檔，包含「只是格式化/排版/行尾」。
- 不准重排 import、不准改無關函式/變數名、不准順手重構。
- 不准整檔重存；只動需要動的行。

驗收（改完要自己跑並貼結果）：
- python -m pytest -s tests        → 維持 337 passed
- python control/main.py --health-check → healthy
- git diff --check                 → 無 whitespace error
- git diff --stat                  → 檔數/行數應與「範圍鎖」相符

交付方式：
- 先只給我 git diff --stat 與變更摘要，我同意後才寫入。
- 一個任務 = 一個 commit，訊息格式 type(scope): 動詞+對象。
```
