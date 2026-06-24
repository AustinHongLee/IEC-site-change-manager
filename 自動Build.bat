@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set "STRICT=0"
set "SKIP_DEPS=0"
set "NO_PAUSE=0"
set "USER_ARGS="

:parse_args
if "%~1"=="" goto :after_parse
if /i "%~1"=="--help" goto :show_help
if /i "%~1"=="-h" goto :show_help
if /i "%~1"=="--strict" (
    set "STRICT=1"
    shift
    goto :parse_args
)
if /i "%~1"=="--skip-deps" (
    set "SKIP_DEPS=1"
    shift
    goto :parse_args
)
if /i "%~1"=="--no-pause" (
    set "NO_PAUSE=1"
    shift
    goto :parse_args
)
set USER_ARGS=!USER_ARGS! "%~1"
shift
goto :parse_args

:after_parse
if not exist "logs" mkdir "logs"
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%T"
set "LOG=logs\release_build_!STAMP!.log"

echo ==================================================
echo  工務修改單 - 自動 Build
echo ==================================================
echo [INFO] 工作目錄: %CD%
echo [INFO] Log: %CD%\!LOG!

set "PY=.venv\Scripts\python.exe"
if exist "!PY!" (
    "!PY!" --version >nul 2>&1
    if !errorlevel! equ 0 goto :python_ready
)

set "REQUIRED_VER="
if exist ".python-version" set /p REQUIRED_VER=<.python-version
if not defined REQUIRED_VER set "REQUIRED_VER=3.12"

echo [INFO] 找不到可用 .venv，建立 Python !REQUIRED_VER! 虛擬環境...
py -!REQUIRED_VER! -m venv .venv >nul 2>&1
if !errorlevel! neq 0 (
    echo [WARN] py -!REQUIRED_VER! 建立失敗，改用 PATH 上的 python...
    python -m venv .venv
    if !errorlevel! neq 0 goto :venv_failed
)

:python_ready
echo [INFO] Python:
"!PY!" --version

if "!SKIP_DEPS!"=="1" (
    echo [INFO] 已指定 --skip-deps，略過依賴安裝。
    goto :check_pyinstaller
)

echo [INFO] 安裝 / 更新 requirements.txt 依賴...
"!PY!" -m pip install -r requirements.txt
if !errorlevel! neq 0 goto :deps_failed

:check_pyinstaller
"!PY!" -c "import PyInstaller" >nul 2>&1
if !errorlevel! neq 0 (
    echo [INFO] requirements.txt 未含 PyInstaller，正在補安裝...
    "!PY!" -m pip install PyInstaller
    if !errorlevel! neq 0 goto :deps_failed
)

set "DIRTY_ARG="
git status --porcelain > "%TEMP%\iec_build_dirty.txt" 2>nul
for %%A in ("%TEMP%\iec_build_dirty.txt") do set "DIRTY_SIZE=%%~zA"
if not "!DIRTY_SIZE!"=="0" (
    if "!STRICT!"=="1" (
        echo [INFO] --strict 模式：工作樹 dirty 仍交給 release gate 擋。
    ) else (
        set "DIRTY_ARG=--allow-dirty"
        echo [WARN] 工作樹不是乾淨狀態，這次會用 --allow-dirty 完成本機 build。
        echo [WARN] 這種包只適合本機測試；正式交付請整理工作樹後改跑: 自動Build.bat --strict
    )
)
del "%TEMP%\iec_build_dirty.txt" >nul 2>&1

echo.
echo [INFO] 開始 build_release.py...
echo [INFO] 指令: "!PY!" tools\build_release.py --archive !DIRTY_ARG! !USER_ARGS!
echo.

"!PY!" tools\build_release.py --archive !DIRTY_ARG! !USER_ARGS! > "!LOG!" 2>&1
set "BUILD_RC=!errorlevel!"
type "!LOG!"

echo.
if !BUILD_RC! equ 0 (
    echo [OK] Build 完成。
    echo [OK] onedir: dist\IEC-site-change-manager
    echo [OK] archive/checksum: dist\releases
) else (
    echo [ERROR] Build 失敗，錯誤碼: !BUILD_RC!
    echo [ERROR] 請查看 log: %CD%\!LOG!
)
echo.
if not "!NO_PAUSE!"=="1" pause
exit /b !BUILD_RC!

:venv_failed
echo [ERROR] 建立 .venv 失敗。
if not "!NO_PAUSE!"=="1" pause
exit /b 1

:deps_failed
echo [ERROR] 依賴安裝失敗。
if not "!NO_PAUSE!"=="1" pause
exit /b 1

:show_help
echo 用法:
echo   自動Build.bat [選項] [build_release.py 選項]
echo.
echo 常用:
echo   自動Build.bat
echo       本機自動 build + release gate + zip/sha256；dirty 工作樹會自動加 --allow-dirty。
echo.
echo   自動Build.bat --strict
echo       正式交付模式；dirty 工作樹不放行。
echo.
echo   自動Build.bat --skip-deps --no-cli-smoke
echo       快速 build；略過 pip install，且跳過打包後 CLI 真輸出冒煙。
echo.
echo bat 專用選項:
echo   --strict       不自動加 --allow-dirty，正式交付用。
echo   --skip-deps    略過 requirements/PyInstaller 安裝檢查。
echo   --no-pause     結束時不 pause，給自動化或測試用。
echo   --help, -h     顯示此說明。
echo.
echo 其餘參數會原樣轉交給 tools\build_release.py，例如:
echo   --skip-build --no-health-check --no-cli-smoke --cli-smoke-with-pdf
echo.
exit /b 0
