# 管線修改單產出系統

## 功能說明
自動化產出管線修改單報告（XLSM + PDF），支援：
- 單一焊口模式（6-slot 模板）
- 群組焊口模式（27-slot 模板）
- 自動偵測變更並略過未修改項目
- 附件 PDF 自動合併

## 產品化文件
公司級產品化、Big Bang 前導書、多 AI 討論規則與 Phase 0 落地任務，請從：

- [docs/README.md](docs/README.md)
- [docs/00_big_bang_產品進化總控室/README.md](docs/00_big_bang_產品進化總控室/README.md)

## 新增功能 (v2.1)
- **🔍 資料夾驗證** - 檢查必要檔案是否齊全
- **🖼️ 圖片預處理** - 自動調整尺寸、校正旋轉
- **✨ 建立精靈** - 步驟式引導建立報告資料夾
- **📋 子資料夾選擇** - 可選擇特定資料夾處理

## 安裝
```bash
pip install -r requirements.txt
```

## 使用方式

### GUI 模式（推薦）
```bash
cd control
python main.py
```
或直接雙擊執行 `啟動GUI.bat`

### GUI 新功能
- **🔍 驗證資料夾** - 檢查選擇的資料夾是否有缺少檔案
- **✨ 建立新資料夾** - 步驟式精靈協助建立正確格式的資料夾
- **🖼️ 預處理圖片** - 調整圖片尺寸以符合模板（需要 Pillow）
- **📋 選擇子資料夾** - 勾選要處理的特定資料夾

### CLI 模式
```bash
# 處理全部
python main.py --cli

# 只處理指定日期
python main.py --date 20260112 20260108

# 重試失敗項目
python main.py --retry

# 強制重新產出（忽略指紋）
python main.py --cli --force

# 不匯出 PDF
python main.py --cli --no-pdf
```

## 資料夾結構
```
工務修改單/
├── attachments/          # 輸入：附件資料夾
│   └── YYYYMMDD/         # 日期資料夾
│       ├── 234_15r1/     # 單一模式
│       └── 101_AG/       # 群組模式（需 GroupWeld.txt）
├── output/               # 輸出：XLSM 檔案
├── pdf/                  # 輸出：PDF 檔案
├── template/             # 模板檔案
├── control/              # 程式碼
│   ├── main.py           # 主程式入口
│   ├── gui.py            # GUI 介面
│   ├── config.py         # 設定
│   ├── parsers.py        # 解析器
│   ├── utils.py          # 工具函數
│   ├── excel_handler.py  # Excel 操作
│   ├── record_manager.py # 紀錄管理
│   ├── validator.py      # 防呆驗證（NEW）
│   ├── image_processor.py # 圖片預處理（NEW）
│   └── wizard.py         # 建立精靈（NEW）
└── 管線修改紀錄清單.xlsx   # 紀錄檔案
```

## 附件資料夾格式

### 單一模式
資料夾名稱：`{series_no}_{weld1}_{weld2}...`
例：`234_15r1_12r1_10a2`

**必要檔案：**
- `before.jpg` - 修改前照片
- `after.jpg` - 修改後照片

### 群組模式
資料夾名稱：`{series_no}_{group}G`
例：`101_AG`

**必要檔案：**
- `GroupWeld.txt` - 焊口清單
- `before_1.jpg`, `after_1.jpg` - 第一組照片
- `before_2.jpg`, `after_2.jpg` - 第二組照片（選用）

### GroupWeld.txt 格式
每行一個焊口：
```
15a0.5
12r1
9b2
```

### 可選檔案
- `note.txt` - 說明文字
- `materials.txt` - 材料清單
- `*.pdf` - 附件 PDF（會自動合併至報告第二頁）

## 照片建議
- **比例**：橫向照片效果最佳（模板區域為橫向）
- **尺寸**：建議 1600x1200 左右，太大會佔用過多記憶體
- **格式**：JPG 格式
- **預處理**：可使用「🖼️ 預處理圖片」功能自動調整

## 作者
GL-05 工務組
