# Opus 校準結果 — Checkpoint D（非 COM PDF 與現場輸出）

對應請求：`22_Opus校準請求_CheckpointD_非COM_PDF與現場輸出.md`
審查日期：2026-06-17
審查方式：直接讀 `workbook_pdf_converter.py`（最高部署風險點）、capabilities/preflight，並對照前導書 §3 的 PDF overlay 設計。

---

## 0. 總評

方向對，地基穩，**現在停在進 `pdf_overlay` 之前是正確判斷**。
LibreOffice 轉檔的關鍵細節做對了——**每次轉檔用獨立 `UserInstallation` 暫存 profile**（行 57），這是最多人做錯、會在「使用者已開著 LibreOffice」時鎖死或互相干擾的地雷，你避開了。returncode + 輸出存在雙檢、原子 replace、pypdf 回讀也都有。
但有**一個程式 P0**（轉檔 timeout/例外沒接 → 原始 traceback + 可能殘留 soffice.bin）與**一個方向 P0**（LibreOffice 部署策略未定，PDF 還只是「我的機器能跑」）。其餘是 P1 與該延後的。

---

## 1. P0 必修（不改會造成公司部署或輸出事故）

### P0-1　轉檔的 timeout / 例外未處理 → 原始 traceback + 殭屍 soffice.bin
`workbook_pdf_converter.convert_workbook_to_pdf`：`subprocess.run(..., timeout=timeout_seconds)`（行 64-73）**外層沒有 try/except**。後果：

- **timeout** → 丟出 `subprocess.TimeoutExpired`，不會變成你設計好的 `_failure(...)` dict，而是**原始 traceback 往上炸**到 GUI/CLI。
- **soffice 卡住被 timeout** → `subprocess.run` 殺掉的是啟動器；LibreOffice 常另起 `soffice.bin` 子程序，**可能殘留殭屍**，公司共用機器累積後拖垮。
- 同理 `FileNotFoundError`（detect 後 soffice 被移走）、`PermissionError`、`OSError` 都會變 traceback。

修法：把 `subprocess.run` 包 try/except（`TimeoutExpired`、`OSError`）→ 一律轉成 `_failure("libreoffice_timeout"/"libreoffice_spawn_failed", …)`；timeout 時確保**整個程序樹被殺**（用 `Popen` + 平台 process-group / `proc.kill()` 收子程序），避免殘留 soffice.bin。這是「公司級穩定」的硬需求，不是體驗問題。

### P0-2　LibreOffice 部署策略未定 → 非 COM PDF 仍是「我的機器能跑」
你自己列的未完成 #1/#2。**在策略定下來之前，PDF 這條交付通道在部署上等於還沒成立**。三選一要寫進決策紀錄：

- (a) 要求公司電腦安裝 LibreOffice（最省事，但要 IT 配合、版本/字型不一）。
- (b) 打包附帶 portable LibreOffice（單入口最順，但 exe 變大、要管 portable 路徑）。
- (c) settings 指定 `soffice.exe`（你已支援，當 fallback 最好，當主策略太依賴人工）。

建議：**(b) 為主、(c) 為 fallback、(a) 容忍**。在沒決定前，PDF 一律「能轉就轉、不能就給 xlsx + 人話提示」（你已這樣做，對）。但要明確：**PDF 在策略落地前不可被當成唯一交付物**。

> 註：CJK 路徑（專案在「工務修改單」下）+ soffice，Windows 上偶有 `--outdir`/輸入路徑編碼問題。你把 outdir 放 ASCII 暫存夾（對），但輸入 workbook 仍是 CJK 路徑——請列入 P0-2 的真機測試項。

---

## 2. P1 建議（增加維護成本或使用者困惑，但不一定擋 MVP）

- **P1-1 輸出結果 envelope 不一致**：`render_xlsx_template` / `convert_workbook_to_pdf` / `export_site_statistics` 的回傳 dict 形狀略不同（例如 converter 失敗時 `input:""`、成功時 `input:set`，keys 也不一致）。要讓 UI/AI/批次「接管」，應收斂成**單一結果契約**：`{ ok, outputs:[{kind,path}], issues:[{severity,code,message}], capabilities:{} }`。這跟 field-path 目錄是同一個精神——一個契約。（回答 Q3：目前「夠用但不齊」，統一後才穩。）
- **P1-2 PDF 驗證只到 pages>0**（你的未完成 #3）：對固定公司表單，渲染成空白/亂碼/錯頁數的 PDF 仍會「通過」。MVA 可接受，但至少加：**頁面尺寸符合預期** + 內容串流非空。完整視覺比對延後到 overlay 階段。
- **P1-3 失敗/preflight 的人話與前置提示**：保留「轉不出就開 xlsx + warning」這個降級（對），但 warning 要人話（「PDF 需要 LibreOffice，已開 Excel 檔；要 PDF 請到設定指定 soffice」）。並把 `output_capabilities` 的結果**在使用者按產出前**就顯示（綠/灰），不要等失敗才知道。（回答 Q2：現行降級 OK，補前置指示即可；**完整「輸出狀態面板」先別做**，會過度設計。）
- **P1-4 Demo smoke 只有 happy path**：產品價值在抓**不happy**的情況。demo 應擴成小矩陣：缺 after 圖、材料未定價、表格超 `max_rows`、多頁照片、note still placeholder、查無價目。這些正是 dry-run/overflow/completeness 存在的理由——smoke 要證明它們**真的被抓到**。（回答 Q6：目前足以當「跑得起來」的入口，不足以當「驗收抓錯能力」的入口。）
- **P1-5 先鎖 `pdf_overlay` schema 規格（寫成文件），再寫 renderer**（見第 4 節 Q5）。

---

## 3. 可延後（現在做會過度設計）

- 真・像素級 PDF 視覺驗證（先 pages+尺寸+內容非空就好）。
- 完整「輸出狀態儀表板」（先 preflight 指示 + 降級提示）。
- PDF overlay 的「拉框設計器 GUI」（作者工具，等 renderer + schema 穩了再說）。
- portable LibreOffice 的打包自動化（先把策略 P0-2 拍板，再自動化）。
- 每轉一檔開一次 soffice 的批次效能優化（MVA 階段可接受冷啟動）。

---

## 4. 回答 Q5：`pdf_overlay` 的 schema 如何與 `xlsx_template` 三原語對齊（最關鍵）

**核心原則：PDF 不是另一個世界，是同一條管線換一個後端。** 具體：

1. **同三原語、同 field-path 目錄**：`text` / `image` / `table` 不變；引用的路徑一樣只能來自 `canonical_fields`。差別**只有落點**：xlsx 用 `cell`/`anchor`/`start_cell`；pdf 用 `rect_norm`/`region_norm` + `page` + `page_size_pt`。
2. **mapping / 驗證 / dry-run 層不動**：`validate_template_mapping`、`template_dry_run` 維持 renderer-neutral，照樣驗 source、報 unmapped/overflow/missing。只有「落點欄位」由各 renderer 自己的 schema 檢查。
3. **不准加第 4 種原語**：FreeText 就是 `text`；**紅框是設計時 `debug:true` 的裝飾，不是資料欄位**——它絕不可進輸出、也絕不可進目錄。把紅框當成 field 是未來最容易爆的設計錯誤。
4. **座標系統現在就鎖死**（前導書 §3.4）：存**正規化、頁面相對**座標 + 設計時 `page_size_pt`；renderer 轉成 PDF point（左下原點翻轉）。這是 overlay 最會爆的一點，規格先寫死，換底圖 DPI/尺寸才不會跑位。
5. **同一條 pipeline 契約**：validate → dry-run → render → post-validate。PDF 的 post-validate 不能回讀 cell，改成**輸出「overlay manifest」**（哪個欄位畫在哪頁哪框），對照 dry-run 預期。
6. **溢出規則沿用 C1**：table 超 `rows_per_page` → 續頁；**沒處理就是 ERROR，不可靜默畫過界**（Excel 版已立此規矩，PDF 必須繼承）。

這樣才守得住「**AI 只新增模板、核心不動**」——而且是跨 Excel 與 PDF 都成立。

---

## 5. 下一個 3 步開發順序

**Step 1 — 把已建的非 COM PDF 變「安全且可部署」（不碰 overlay）**
- 修 P0-1（converter timeout/例外/殭屍）。
- 拍板 P0-2（LibreOffice 部署策略）寫進決策紀錄。
- 補 P0-2 的 CJK 路徑真機測試 + 一次真 LibreOffice 視覺抽查（你目前本機沒裝，是最大的未驗區）。
- 順手收 P1-1（統一結果 envelope）。

**Step 2 — 鎖資料與 schema 契約（對應 Q4 的 E，且為 overlay 鋪路，但先不寫 renderer）**
- 複查 CanonicalReport 欄位 + 完整度 + field-path 目錄，凍結為 `report.v1`。
- **寫出 `pdf_overlay` schema 規格文件**（第 4 節那六條），擴充 `validate_template` 接受 PDF 落點欄位（但 renderer 還沒做）。
- 擴 demo smoke 成 edge 矩陣（P1-4），當 Step 3 的測試床。

**Step 3 — 才做 `pdf_overlay` renderer**
- 對著凍結的 schema 實作，沿用 validate→dry-run→render→post(manifest)。
- 「真 PDF 驗證」（P1-2 升級）併入它的驗收。

> 對應 Q4 的優先序：**A（部署策略）+ 修 converter = Step 1 最高**；**E（鎖契約）= Step 2**；**C（overlay）= Step 3**；B（視覺驗證）折進 Step 3 驗收；D（輸出狀態面板）降為 P1 的「前置指示」即可，完整面板延後。

---

## 6. 方向有沒有錯？

**沒有錯，維持。** 唯一要嚴防的是：別讓 `pdf_overlay` 長成**平行的第二套輸出系統**。一旦 PDF 有自己的目錄、自己的原語、自己的 dry-run，你前面建立的「單一核心、可替換模板」就破功。第 4 節的六條就是防這件事。

一個小替代選項（非改方向，是多一條路）：若**某些公司的表單本身是可填式 PDF（AcroForm）**，直接「填 PDF 表單欄位」會比座標 overlay 簡單穩定。建議 overlay 當通用解，但保留「AcroForm 填值」當特例後端——同樣掛在 registry 的一個 `kind`，不影響核心。不要假設每家公司都得用座標 overlay。

---

## 7. 一句話

非 COM PDF 的地基蓋對了，profile 隔離這個關鍵細節也對。
進 overlay 前先做兩件：**把 converter 的 timeout/殭屍補掉 + 把 LibreOffice 部署策略拍板**（讓你已經建好的 PDF 真的能在公司機器上活），然後**先鎖 schema 再寫 renderer**——別讓 PDF 變成第二個世界。
