@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PYEXE="
for %%C in ("py -3.12" "py -3" "py" "python" "D:\Python\python.exe") do (
    if not defined PYEXE (
        %%~C -c "import tkinter,requests,Crypto,PIL,tiktoken,openai" >nul 2>nul
        if !errorlevel! equ 0 set "PYEXE=%%~C"
    )
)

if not defined PYEXE (
    echo.
    echo [ERROR] No usable Python found.
    echo Need Python 3.10+ WITH tkinter and packages from requirements.txt
    echo Try:  py -3.12 -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo Launching GUI with: !PYEXE!
!PYEXE! gui.py
if errorlevel 1 (
    echo.
    echo [ERROR] gui.py exited abnormally.
    pause
)
