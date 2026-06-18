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
