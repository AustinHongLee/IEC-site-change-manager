# PyInstaller 大型非必要套件排除回補紀錄

日期：2026-06-22

## 背景

目前 onedir dist 約 738MB，PyInstaller build log 顯示收進 `torch`、`torchvision`、`pytest` 等套件。這些不是本工具執行現場修改單、輸出中心、診斷包所需的產品執行期依賴。

## 本次調整

- `packaging/IEC-site-change-manager.spec`
  - 新增 `excluded_modules`
  - 排除：
    - `pytest`
    - `tensorboard`
    - `tensorflow`
    - `torch`
    - `torchvision`
- `tests/test_packaging_spec.py`
  - 檢查 spec 保留排除清單。

## 驗證重點

排除後必須重新建置並跑：

```powershell
python tools\build_release.py
python tools\check_release_package.py --package-dir dist\IEC-site-change-manager --run-health-check
dist\IEC-site-change-manager\IEC-site-change-manager.exe --diagnostics --diagnostics-output staging\support_bundle_exe
```

若後續某個功能真的需要這些套件，必須先證明用途，再從排除清單移除。

## 本次實測結果

- 排除前：`738.30 MB`，`3611` 個檔案。
- 排除後：`332.68 MB`，`1191` 個檔案。
- `python tools\build_release.py`：成功。
- `tools\check_release_package.py --run-health-check`：合格。
- packaged exe `--diagnostics`：成功產生支援診斷包，啟動判斷 `initialize`。
