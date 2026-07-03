@echo off
cd /d "%~dp0..\.."
title CO Manager - Change Order Wizard (Desktop)

rem Launch the native change-order wizard window (pywebview + real bridge)
python control\co_wizard_app.py
if errorlevel 1 (
  echo.
  echo [Launch failed] See the message above.
  echo  - Missing pywebview?   run:  pip install pywebview
  echo  - Missing WebView2 Runtime? download "Evergreen WebView2 Runtime" from Microsoft
  echo.
  pause
)
