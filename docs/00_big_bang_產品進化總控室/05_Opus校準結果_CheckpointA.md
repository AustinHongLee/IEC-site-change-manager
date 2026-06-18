# Opus 校準結果 — Checkpoint A（材料價目表 + 價格寫入鏈）

對應檢查點：`04_Opus校準檢查點.md`
審查日期：2026-06-16
審查方式：以挑錯角度直接讀程式碼與資料檔，並實跑核心財務邏輯測試。

## 審查涵蓋的程式與資料

- `control/material_pricebook.py`、`control/billing_calculator.py`
- `control/record_manager.py`（`upsert_materials_rows`、`_preserve_material_price`、`_recalculate_preserved_material_amount`）
- 價格寫入鏈：`gui.py:673-712`、`main.py:391-433`
- 價目表 UI：`gui_panels.py` MaterialPricebookPanel（約 1430-1549）
- 資料檔：`records/material_pricebook.json`、`records/billing.json`、`records/records.json`
- 對照藍圖：前導書 ⑦material／⑧catalog／⑨price_history／⑩billing／⑪batch／⑫item

驗證：`billing_calculator` + `material_pricebook` 共 11 個測試以權威原始碼跑過，全綠（金額計算、帶價、手動價保留邏輯本身正確）。

嚴重度標記：🔴 必修（資料/財務正確性） · 🟠 做請款批次前要補 · 🟡 體驗/穩健性

---

## 結論速覽

整體方向正確：你已經把「材料完全沒料號沒單價」的功能空洞補上，來源標記（`單價來源`/`金額來源`/`價目表ID`）與「手動價不被回沖」的核心也成立。但在進請款批次前，有 **1 個真實資料遺失 bug**、**2 個會回溯改變已請款金額的設計缺口**，以及請款金額規則的數個財務風險，必須先處理。

---

## 1. 材料價目表 schema 是否足夠支撐 合約價／歷史價／手動覆蓋

- 手動覆蓋：✅ 成立。`單價來源="manual"` 在寫入鏈與 `_preserve_material_price` 都有正確處理。
- 專案合約價：🟠 只做了一半。目前用「每專案一份 `material_pricebook.json`」隱含表達合約價，但 item 沒有 `來源`(合約／報價／手動) 欄位，無法在同一份料庫裡區分「合約價」與「一般參考價」。前導書 ⑨ 明確要 `source`。
- 歷史價：🔴 不支援。item 只有單一 `單價`，沒有 `生效日`／版本／append-only。改價就是就地覆蓋，**舊價查不回來**。v1 決策（`02_決策紀錄`）刻意延後「歷史回溯」，可以接受；但風險是改一次價，連「上次合約價多少」都查不到，對帳時會痛。

建議（schema 先對、UI 可後補）：item 加 `來源`(合約/報價/手動) 與 `生效日`；把「改價」改成「新增一列」而非就地覆蓋（UI 仍只顯示最新即可）。這樣日後要做 price_history 不必 migration。

## 2. 單價/金額來源欄位是否足以追溯請款依據

- 已具備：`單價來源`(pricebook/manual)、`金額來源`(calculated/manual)、`價目表ID`。✅ 比藍圖批評的舊狀態前進很多。
- 不足：
  - 🟠 缺「帶價當下的版本/時間」。`價目表ID` 指向料號，但料號的價會被覆蓋（見第 1 點），所以即使存了 ID，回頭也查不到「當時帶的是哪個價」——唯一證據只剩 `records.json` 裡那個數字本身，脆弱。
  - 🟠 缺 `category`(材料/工資/耗材/雜項)。前導書 ⑦ 有。請款常要分「材料線/工資線」，現在全混在一起。
  - 🔴 缺穩定 `id`。材料列主鍵是 `(報告編號,零件類型,尺寸,材質)` 複合字串，不是穩定 id，任何字串改動就斷鏈（見第 3 點 bug）。
- 結論：追溯「這筆錢怎麼算的」（數量×單價＋來源標記）勉強夠；追溯「依據哪份合約價」不夠。

## 3. 「重跑產出不覆蓋歷史單價」是否有遺漏場景 ← 最關鍵

現行 `_preserve_material_price`：existing 已有單價、且 incoming 來源為 `""`/`"pricebook"` 即保留。✅ 正確擋住「價目表回沖手動/歷史價」。但有四個遺漏：

1. 🔴 **空白價回填會回溯改變已請款單。** 凍結條件是「existing 已有單價」。若某材料當初帶價時 pricebook 是空的（單價空白、金額 0），日後 pricebook 補了價，重跑就會把它「補上」價與金額。若這張修改單**已請款/估驗送出**，材料金額會事後悄悄變動——正是前導書點名的財務大忌。凍結的觸發點不該是「有沒有價」，而該是「這張單是否已進入請款」。

2. 🔴 **數量改變會連動改金額，即使單價已凍結。** `_recalculate_preserved_material_amount` 在單價凍結時，仍用「新數量 × 舊單價」重算金額（`數量` 不在保留欄位，重跑會被覆蓋）。所以「快照」其實只凍結單價，數量與金額仍會移動。對已請款單同樣是事後變動。

3. 🔴 **SCH 不在主鍵 → 同品名同尺寸同材質、不同 SCH 的兩列互相覆蓋（資料遺失＋金額算少）。** 這是真實 bug，不是理論：
   - 寫入時 materials_rows 帶了 `SCH`（`gui.py:685`）。
   - 但 upsert 主鍵是 `(報告編號,零件類型,尺寸,材質)`（`record_manager.py:264-269`），**不含 SCH**。
   - 結果 SCH40 與 SCH80 收斂成同一鍵，第二筆覆蓋第一筆 → 少一條材料、金額算少。
   - 諷刺的是 `find_material_price` 會用 SCH 加分配價，等於「配得出價、卻存不進去」。

4. 🟠 **rename `報告編號` → 全部斷鏈。** materials/details/billing 都用 `報告編號` 字串當外鍵，沒有 referential integrity。

建議：凍結改以「請款狀態」為準；主鍵補 `SCH`（或改用穩定 id）；**已請款單的材料列整列鎖定（單價＋數量＋金額全鎖）**。

## 4. 請款面板自動計算＋手動覆蓋規則是否造成財務風險 ← 關鍵

現行 `build_billing_rows`：weld/material 各自「有手填用手填、否則自動彙總」；total「有手填 total 用手填、否則＝有效 weld＋有效 material」。風險：

1. 🔴 **total 可獨立於 weld+material 被手填，且不檢查一致性。** 可以出現 `total ≠ weld+material` 而無任何警示，下游會計拿到「分項加總對不上總額」的單。
2. 🟠 **混合 manual/calc 的幽靈連動。** 手填 weld、material 留自動，則 total＝手填weld＋自動material。日後 pricebook/數量變動使 material 自動值改變，total 跟著悄悄變，即使你以為 weld 已「鎖定」。
3. 🔴 **金額編輯無留痕、無二次確認。** 前導書明確要求金額/單價編輯要留痕＋二次確認。目前 billing 沒有 audit 欄、沒有 who/when，inline 雙擊改金額手一滑沒人知道。你已有 `operation_journal`，接上即可。
4. 🟠 **無進位規則。** `amount_to_text` 保留完整小數（`format 'f'`）。數量×單價可能產生小數分；台幣請款通常進位到整數元，多列加總會和人工四捨五入的發票對不上。需明定逐列 round 還是總額 round。
5. 🟠 **無稅（營業稅 5%）／未稅含稅標記。** 對業主請款幾乎一定要處理。
6. 🟠 **狀態是自由字串、無狀態機。** 前導書要 enum＋不可跳狀態＋不可重複請。現在 status 自由字串，一個空格/同義字就裂開。

建議：total 一律由分項加總（或保留手填但強制顯示「與分項差額」警示）；金額/狀態編輯走二次確認＋寫 journal；定義進位與稅；狀態改 enum。

## 5. 價目表 UI 是否對非工程師夠直覺／是否需防呆與匯入

現況（MaterialPricebookPanel）：有子字串搜尋、新增/複製/刪除、inline 雙擊編輯、單價數字驗證、存檔檢查（缺零件類型、缺有效單價、料號重複）。✅ 基礎防呆有了。不足：

1. 🔴 **配價是「精確正規化字串相等」**（`_normalize` 只去空白、轉小寫、全形逗號轉半形）。零件類型/材質/SCH/單位 任何打字差異（「彎頭」vs「90彎頭」、全形/半形、`M` vs `m`）都會配不到 → 單價**靜默空白** → 金額 0。對非工程師這是最危險的「無聲失敗」。需要受控詞彙下拉或別名表（前導書反覆強調：狀態/分類用 enum，不要中文自由字串）。
2. 🟠 **無匯入。** 現場合約材料價通常是 Excel/報價單；沒有「從 Excel 匯入價目表」就要逐列手敲，量一大就不會維護，價目表形同虛設。建議加 Excel 匯入＋預覽＋重複合併。
3. 🟡 複製產生的料號 `_copy` 易與既有衝突；料號自動＝`comp|size|sch|material`，使用者改了欄位卻沒重算 id 時，id 與內容會脫節。
4. 🟡 配價失敗時 UI 應「明確標紅/提示無價」，不要靜默 0。

## 6. 做請款批次前還缺哪些必要資料欄位

對照前導書 ⑩⑪⑫，缺：

- 🟠 **billing_batch 一級物件**（批次號、狀態、業主、估驗期數、建立人、送審/送出時間、加總）。現在 billing.json 是「每張單一格」，沒有批次；真實請款是一批一批送。
- 🟠 **狀態 enum＋狀態機**（未請款/請款中/部分付款/已付款/退回/作廢；不可跳、不可重複請）。
- 🔴 **防重複請款約束**：一張單同時只能在一個進行中批次。
- 🟠 **部分請款**：`paid_amount` / `ratio`（分期、部分付款）。
- 🟠 **稅、未稅/含稅、幣別**（meta 有 currency，但單據層沒有）。
- 🟠 **category（材料/工資/耗材）、估驗期數 period、業主 client。**
- 🔴 **金額/狀態變更 audit 留痕**（who/when/old→new）。
- 🔴 **穩定 id 與 referential integrity**，取代用中文字串當外鍵。
- 提醒：前導書要求 billing 財務資料「原子＋鎖＋稽核＋備份」四者齊全。目前 原子 ✅、備份 ✅（Phase0 板）、鎖 部分、**稽核 ❌**。

---

## 做請款批次前的「必補最小集合」（建議順序）

1. 🔴 修 SCH 主鍵碰撞（純 bug，資料遺失，最高優先）。
2. 🔴 凍結觸發點改為「請款狀態」而非「有無單價」；已請款單材料列整列鎖（單價＋數量＋金額）。
3. 🔴/🟠 請款金額：total 由分項加總、加進位規則、加稅、狀態改 enum。
4. 🔴 金額/狀態編輯加二次確認＋接 `operation_journal` 留痕。
5. 🔴/🟠 價目表：受控詞彙＋Excel 匯入＋配價失敗明示。
6. 🟠 schema 先把 billing_batch / billing_item / category / period / 穩定 id 設計定下來（即使 v1 UI 不做批次），避免日後 migration。

「暫不校準」清單（PyInstaller 打包、SQLite/PostgreSQL 選型、完整角色權限）維持延後 — 認同，現在開會發散。

---

## 附帶提醒（請本機確認，可能是同步假象）

審查時，沙箱端讀到的 `control/utils.py` 是**被截斷**的（停在 `try: sz = os.path.getsize(ap)`，沒有 `except`，整檔無法編譯）；但 git HEAD 版本完整且可編譯，研判是同步快照造成的假象。不過若你本機的工作目錄檔案真的被截斷，`utils` 一壞，整條 import 鏈（含 atomic 寫入與帶價）會全死。**請跑一次確認**：

```bash
python -c "import ast,io; ast.parse(io.open('control/utils.py', encoding='utf-8').read()); print('utils.py OK')"
```

或直接啟動 GUI 看是否正常 import。若報 SyntaxError，從 git 還原或補回被截斷的尾段即可。
