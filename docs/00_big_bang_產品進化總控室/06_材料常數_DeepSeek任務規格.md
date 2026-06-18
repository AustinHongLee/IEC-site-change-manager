# 材料常數補齊任務規格（給便宜模型：DeepSeek V4 Pro / Haiku）

這份是「照著做就好」的規格。執行模型不需要懂整個專案，只要嚴格遵守鐵則、
只用受控詞彙、產出能通過 `tools/validate_pricebook.py` 的 JSON。

負責人：李宗鴻　·　驗證閘門：`python tools/validate_pricebook.py <你的輸出>.json`
（0 個 ERROR 才算完成）

---

## 0. 為什麼這件事「看起來無腦、其實有地雷」

材料價目表的配價邏輯是**正規化字串相等**（`control/material_pricebook.py` 的 `_normalize`：
去頭尾空白、轉小寫、全形逗號→半形、移除所有空白後比對）。
零件類型／材質／尺寸／SCH 只要差一個字、少一個括號、全形半形不一致，
帶價就會**靜默落空 → 金額算成 0 → 請款少算錢**。

所以這個任務真正的難點不是「打字」，是「逐字用對字串」。鐵則第 1 條就是為此而生。

---

## 1. 鐵則（違反任一條即不合格）

1. **零件類型／材質／尺寸／SCH 只能逐字使用第 3 節「受控詞彙表」內的字串。**
   含括號、英文、半形引號 `"`、空格都要一模一樣。禁止自創、翻譯、改寫、補字。
2. **單價一律留空 `""`。** 價格是各專案的合約資料，不是常數，**禁止編造或臆測**。
   價由內業/合約另外填。
3. **單位必須給預設值**（見第 4 節對照），不可空白。
4. **同一 `(零件類型, 尺寸, SCH, 材質)` 不可重複**（會被視為同一料，互相覆蓋）。
5. **`id` 必須唯一**；建議用 `零件類型|尺寸|SCH|材質` 組合（留空欄位略過）。
6. **輸出必須是合法 JSON**，結構見第 5 節，且**通過驗證閘門**才算交付。
7. **同一 `(零件類型, 尺寸, SCH, 材質)` 不可重複**；同零件/尺寸/材質但 SCH 不同可以保留。
   Codex 已修正材料寫入主鍵包含 `SCH`，不再因不同壁厚互相覆蓋。

---

## 2. 要產出什麼

材料價目表「骨架」：把這個專案會用到的 `零件類型 × 尺寸 × SCH × 材質` 常見組合
列成價目表列，**單位填好、單價留空**。內業之後只要填價。

範圍建議（可由李宗鴻指定縮小）：
- 先做最常用零件：`Pipe (管)`、`Elbow (彎頭)`、`Tee (三通)`、`Reducer (大小頭)`、
  `Flange (法蘭)`、`Cap (封蓋)`、`Coupling (接頭)`、`Union (活接)`、`Valve (閥)`。
- 尺寸先做 `1/2"`～`12"`。
- SCH：管件常見 `SCH 10 / SCH 40 / SCH 80`；配件可留空。
- 材質：兩種都做（白鐵 / 黑鐵）。

> 不確定某零件該配哪些尺寸/SCH 時，**寧可少列、不要亂列**。少列只是少帶價，亂列會污染詞彙。

---

## 3. 受控詞彙表（唯一合法字串，逐字照抄）

> 此表來源＝ `control/wizard_data.json`，程式端由 `control/material_constants.py` 統一載入。
> 若日後該檔更新，以該檔為準；可隨時用
> `python tools/validate_pricebook.py material_pricebook_seed.json --list-vocab` 重新匯出最新版。

### 零件類型（32 種，照抄括號與英文）
```
Pipe (管)            Elbow (彎頭)          Tee (三通)            Reducer (大小頭)
Flange (法蘭)        Gasket (墊片)         Cap (封蓋)            Coupling (接頭)
Union (活接)         Valve (閥)            Bolt & Nut (螺栓螺帽)  Nipple (短管)
Plug (管塞)          Bushing (異徑接頭)     Cross (四通)          Olet (支管座)
Strainer (過濾器)     Steam Trap (疏水器)    Sight Glass (視鏡)    Expansion Joint (伸縮接頭)
Flexible Hose (軟管)  Pipe Support (管架)   Control Valve (控制閥)  Spectacle Blind (8字盲板)
Thermowell (溫度套管)  Pressure Gauge (壓力表) Weld Pad (焊墊)       Welding Electrode (焊條)
Filler Wire (焊線)    Thread Seal Tape (止洩帶) Flowmeter (流量計)   Other (其他)
```

### 材質（2 種，務必含英文全名）
```
白鐵 (Stainless Steel)
黑鐵 (Carbon Steel)
```
⚠️ 注意：現場 `materials.txt` 曾出現只寫「白鐵」的舊資料。本任務一律用上面完整字串。
別名（白鐵 / SS / 黑鐵 / CS）驗證時只會給 WARNING，不要當正解（詳見第 6 節）。

### 尺寸（18 種，半形引號 `"`）
```
1/2"  3/4"  1"  1-1/4"  1-1/2"  2"  2-1/2"  3"  4"  6"  8"  10"  12"  14"  16"  18"  20"  24"
```

### SCH（7 種，含 `SCH ` 前綴與空格）
```
SCH 5   SCH 10   SCH 20   SCH 40   SCH 80   SCH 160   XXS
```
（配件類若無壁厚概念，SCH 留空 `""`。）

---

## 4. 單位預設對照（單位不可空白）

| 零件類型 | 建議單位 |
|---|---|
| Pipe (管) | M（公尺）|
| Elbow / Tee / Reducer / Cap / Coupling / Union / Cross / Bushing / Nipple / Plug / Olet | 個 |
| Flange (法蘭) / Valve (閥) / Control Valve (控制閥) / Strainer / Steam Trap / Sight Glass / Flowmeter | 個 |
| Gasket (墊片) | 片 |
| Bolt & Nut (螺栓螺帽) | 組 |
| Welding Electrode (焊條) / Filler Wire (焊線) | kg |
| Thread Seal Tape (止洩帶) | 卷 |
| 其他不確定 | 個 |

---

## 5. 輸出 JSON 格式（嚴格）

```json
{
  "items": [
    {
      "id": "Elbow (彎頭)|2\"|SCH 40|白鐵 (Stainless Steel)",
      "零件類型": "Elbow (彎頭)",
      "尺寸": "2\"",
      "SCH": "SCH 40",
      "材質": "白鐵 (Stainless Steel)",
      "單位": "個",
      "單價": "",
      "備註": ""
    }
  ],
  "meta": { "version": "1.0", "currency": "TWD" }
}
```

欄位規則：
- 八個欄位都要在：`id, 零件類型, 尺寸, SCH, 材質, 單位, 單價, 備註`。
- 字串型別；`單價` 一律 `""`；`SCH`/`備註` 可為 `""`。
- 不要加自創欄位。

---

## 6. 已處理與仍需注意

1. **材質字串不一致**：精靈詞彙是「白鐵 (Stainless Steel)」，但舊現場資料可能是「白鐵」。
   本任務一律用完整字串。Codex 已在配價層與驗證層加入 alias 正規化，舊資料如 `白鐵` / `SS`
   可對到正規材質，但新骨架仍不可把別名當正解。
2. **SCH 主鍵碰撞已修正**：`record_manager.upsert_materials_rows` 寫入主鍵已包含 `SCH`。
   因此價目表可保留同零件/尺寸/材質、不同 SCH 的列；驗證閘門只阻擋完全相同的
   `(零件類型, 尺寸, SCH, 材質)` 重複列。
3. **單價＝合約資料**：再次強調，模型不准填價。

---

## 7. 交付與驗收

1. 把輸出存成 `material_pricebook_seed.json`。
2. 在 repo 根目錄執行：
   ```
   python tools/validate_pricebook.py material_pricebook_seed.json
   ```
3. 看到 `✓ 通過驗證閘門`、`ERROR: 0` 才算完成；有 ERROR 全部修掉再交。
   WARNING 要逐條看過、確認是預期內（例如刻意保留的別名/SCH 組合）。
4. 交給李宗鴻/Codex 覆核後，再用安全匯入工具併入 `records/material_pricebook.json`：
   ```
   python tools/import_pricebook_seed.py material_pricebook_seed.json
   python tools/import_pricebook_seed.py material_pricebook_seed.json --apply
   ```
   第一行只 dry-run，會列出既有項目、將新增、已存在略過；第二行才實際寫入。
   一般使用者也可以在「材料價目表」面板按「匯入骨架」，走同一套驗證與二次確認流程。

---

## 附：可選的「物理常數」第二張表（非本次必做）

若日後要做「依管徑自動估重/估量」，可另外做一張**參考表**（不要塞進價目表，
價目表 schema 沒有這些欄位）：管外徑 OD、各 SCH 壁厚、單位重 kg/m。
權威來源：
- 碳鋼（黑鐵 / CS）管尺寸：**ASME B36.10M**
- 不鏽鋼（白鐵 / SS）管尺寸：**ASME B36.19M**
這類是真常數、可逐筆對標準驗證，適合便宜模型草擬 + 人工抽查。但**價格永遠不是常數**。
