# Opus 再校準結果 — C5 COM 邊界 + Renderer Registry

對應請求：`18_Opus再校準請求_C5_Registry.md`、回補紀錄 `17_CheckpointC_C5_RendererRegistry回補紀錄.md`、原審查 `11_Opus校準結果_C5_COM邊界.md`。
審查日期：2026-06-16
審查方式：讀 import 邊界與 registry 路由；並在**無 win32com 沙箱**實跑 import-guard、`list_renderers`、`render_with_template` 路由。

---

## 0. 結論：**可繼續**（架構方向正確，無需回改）

我把 C5 的核心地基——「COM 退出啟動期」——在無 pywin32 環境實測確認成立：

- `capabilities` + `renderer_registry` **import 期不碰 COM**（`sys.modules` 無 win32com/pythoncom）。
- `list_renderers()` 預設**不啟動 Excel**。
- `render_with_template(kind="xlsx_com")` 在無 COM 時回 `renderer_unavailable`、`ok:False`、**不崩、不繞過閘門**；未知 kind 回 `renderer_unknown`。
- 讀碼確認：`excel_handler` 的 `import win32com` 已移進方法（行 33）、`gui.py` 只在函式內 import `excel_handler`（行 521）。

我原審查（`11`）的 P0 #1/#2/#4 都落地了。**唯一真正的待補不是程式，是一道鎖**：把上面這個 import-guard 變成**正式自動測試**，否則哪天有人又在某模組頂層 `import excel_handler`，啟動期 COM 依賴會無聲復活，而 Windows 上有 Excel 所以測試照樣全綠、沒人發現。

---

## 1. 回答你的七個問題

### Q1. C5 是否已可稱「COM 從核心與啟動期降級」？
**可以這樣稱，但有一個證據缺口。** 架構上成立、我也在無 COM 環境驗了核心/registry/capabilities。
缺口：**「GUI 在無 Office 機器能啟動」目前是靠讀碼推論 + 核心模組 COM-free 佐證，沒有一個會在無 pywin32 環境跑的測試去證明它。** Codex 的 267 passed / health-check 都在**有** pywin32 的 Windows 上跑，證明不了無 Office 的情況。補上 import-guard 測試（Q6）才算「證明」而非「相信」。

### Q2. `xlsx_com` 登錄為 legacy optional、adapter pending、回友善錯誤——安全嗎？
**安全，而且是對的過渡。** 它**拒絕**而不是直出，所以不會繞過 canonical/template 閘門。
一個必須講清楚的雙重身分：現在有兩個 COM-ish 東西——
(a) **真正在用的舊 GUI 產出**（`generate_report()`，COM、folder-args、走 gui.py:521 的 guarded 入口）；
(b) **registry 裡的 `xlsx_com`**（會拒絕、adapter pending，是個佔位）。
只要舊產出**維持走自己的 guarded 入口**、不被導進會拒絕的 registry 條目，就安全。風險只在於有人誤以為「registry 選 xlsx_com = 跑舊報表」——它不是。文件講明即可。

### Q3. `list_renderers` 預設 unprobed、`--probe-com` 才完整探測——符合公司級 UX/效能嗎？
**預設正確。** 列清單就啟動 Excel 會慢、會生程序、可能留殭屍，絕不能當預設。
UX 微調：GUI 端不要把 `unprobed` 永遠顯示成「不可用」，否則裝了 Excel 的人會以為壞了。建議**第一次真的要用 COM 輸出時，才當場 `probe_application=True` 探測一次並快取**。即：清單用便宜的 unprobed；實際啟用用「按需探測 + 快取」。UI 把 `unprobed`（顯示「需要時再檢查」）與 `unavailable`（灰掉＋原因）分開。

### Q4. GUI 舊產出下一步：先接 registry，還是先做 CanonicalReport adapter？
**先接 registry（A），且建議「不要」做 xlsx_com 的 canonical adapter（B）。**
理由：把 GUI 的「輸出選項」改成讀 registry descriptor，低風險、讓 UI 有單一真相、又是 MVA 的前置。
反之，幫 `xlsx_com` 做 CanonicalReport adapter，是**把力氣投在一條你打算淘汰的路**上——長期目標是用非 COM（openpyxl/PDF）renderer **取代** COM 報表，不是把 COM 報表細心搬上 canonical。B 投資方向錯了。

### Q5. `render_with_template` 對 `xlsx_com` 回 `renderer_not_canonical_ready`——正確防線，還是該允許 legacy direct render？
**正確防線，維持。** 不要讓 legacy 直出穿過 canonical registry——那會在「凡走 `render_with_template` 必經 canonical+template 閘門」這個不變量上打洞。
舊報表保留它**自己的 guarded 入口**即可，不必、也不該進 registry 的 canonical 路由。registry 拒絕＝守住不變量，是對的。

### Q6. 還有哪些 P0 風險會讓「單一 exe、無 Office 仍可啟動並使用非 COM 功能」不成立？
1. **沒有自動 import-guard 測試**：未來某模組頂層 `import excel_handler` 就讓啟動期 COM 復活，而有 Excel 的開發機測不出來。**最高優先。**
2. **「無 Office 啟動」未被會在無 pywin32 跑的測試覆蓋**：需要一個 startup-import 煙霧測試（至少涵蓋啟動會 import 的非 GUI 模組集合；GUI 殼若需 PyQt，至少把它的 import 來源集合納入 guard）。
3. **PyInstaller 打包假設**：build 的 hiddenimports/collect 若硬把 pywin32 當必要、或啟動路徑假設 Excel 存在，exe 在無 Office 機器仍會掛。打包時要驗「無 Office 乾淨機」能啟動。
4. **非 COM 的 PDF 產出尚不存在**：若唯一 PDF 路是 COM，無 Office 機器雖能「啟動」，卻**做不出主要交付物（PDF）**。不是啟動崩潰，是「能開不能用」——對公司級而言接近 P0，由 Q7-D 解。
5. 能力快取 staleness：探測後才裝 Excel／COM 中途壞掉，快取要能 `force_refresh`（給一個「重新偵測」動作）。次要。

### Q7. 下一個 MVA 排序（A 全面讀 registry / B xlsx_com adapter / C photo_sheet / D LibreOffice 替代）
**建議：先補 import-guard 測試（Q6#1，最高），再 A → D → C；B 擱置或永不做。**

1. **A（GUI 讀 registry 顯示輸出選項）**：前置、低風險、UI 單一真相，就是 MVA 本身。
2. **D（LibreOffice / 非 COM Excel→PDF）**：這才是讓 COM「實務上」可選的關鍵——沒有非 COM 的 PDF 路，COM 仍是主要交付物的承重牆，無 Office 機器產不出 PDF。**而且 D 完全不用動舊 COM 報表程式碼**，符合你的限制。
3. **C（photo_sheet renderer）**：純 openpyxl，補「只把照片貼進去」這個真實現場需求，擴大非 COM 輸出面。
4. **B（xlsx_com canonical adapter）**：**最後或永不。** 把淘汰中的 COM 路搬上 canonical 是反方向投資。讓它凍結在 guarded 入口，等非 COM 取代後直接刪。

---

## 2. P0 / P1 / P2

**P0（穩定性/方向，必做）**
1. **Import-guard 自動測試**：強制 win32com 不可用後，斷言 `capabilities / renderer_registry / canonical_* / template_* / xlsx_template_renderer / site_statistics_exporter / record_manager / project_guard` 與 GUI 啟動 import 集合都能 import，且 `sys.modules` 不含 win32com。（CI 用非 Windows runner 天然無 pywin32＝天然守門。）
2. **GUI 讀 registry（Q7-A）**：輸出選項由 registry descriptor 驅動；舊報表執行仍走自己的 guarded 入口。

**P1（過渡安全/可用）**
3. 非 COM 的 Excel→PDF（LibreOffice headless）能力 + 探測（Q7-D），不動舊 COM 報表碼。
4. GUI：COM 選項按需探測一次＋快取；`unprobed` 與 `unavailable` 顯示分開、給人話。
5. COM 程序衛生：產出中止/崩潰不留殭屍 EXCEL.EXE，且只在 COM 路徑被觸發。
6. 能力 `force_refresh`／「重新偵測」入口。

**P2（長期收斂）**
7. `photo_sheet` renderer（Q7-C，純 openpyxl）。
8. 用非 COM 模板做出等價的每張修改單輸出 → golden 比對一致 → 切預設 → 舊 COM 標 legacy 最終刪除。**（取代，不是 adapter）**

---

## 3. 需要的測試

**自動**
1. Import-guard（如上 P0#1）。我已在無 win32com 沙箱跑過原型，全綠，直接收成正式測試即可。
2. `list_renderers()` 預設不 import win32com、不啟動 Excel。
3. `render_with_template`：`xlsx_com` 無 COM→`renderer_unavailable`、`ok:False`、不崩；未知 kind→`renderer_unknown`。
4. `detect_excel_com(probe_application=False)` 在無 pywin32 回 `available=False`＋reason，不丟例外。

**人工（Windows）**
1. 無 Office 機 / PyInstaller exe：能啟動；health-check、統計單、xlsx_template、dry-run、validate 全可用；COM 選項灰掉有訊息。
2. 有 Office 機：首次用 COM 觸發一次探測（Excel 開一次即關、無殭屍）；舊報表輸出與改版前**視覺一致**（golden）。
3. 產出中途強制關 Excel→無殭屍、回友善錯誤。
4. 探測失敗後才裝 Excel→「重新偵測」可刷新能力。

---

## 4. 對「不要一次重寫舊 COM 報表」限制下的下一步

1. **先鎖 import-guard 測試**（半天工，防止啟動期 COM 無聲復活）。
2. **A：GUI 讀 registry**（不碰舊報表執行碼，只改 UI 取選項的來源）。
3. **D：非 COM 的 PDF 路**（LibreOffice 或 pdf_overlay），讓無 Office 機也能產主要交付物——**全程不動舊 COM 報表**。
4. 舊 COM 報表：**凍結在 guarded 入口、別投資 adapter**；等非 COM 取代後再刪。這正是「不重寫」的最務實解——不是改它，是讓它停在原地、最後被取代。

---

## 5. 一句話

地基對了：COM 真的退出啟動期，我在無 COM 環境驗證過。
**現在唯一會讓它倒退的是「沒有鎖」——把 import-guard 收成正式測試，C5 的核心就封住了。**
接著 GUI 讀 registry、做非 COM 的 PDF 路；別為要淘汰的 `xlsx_com` 做 canonical adapter。
