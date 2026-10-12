@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   fuckZHS 一键打包脚本
echo   产物:  dist\fuckZHS.exe  (单文件, 双击即用)
echo ============================================================
echo.

REM ---------- 1. 找一个带 tkinter 的 Python 3.10+ ----------
set "PYEXE="
for %%C in ("py -3.12" "py -3" "py" "python" "D:\Python\python.exe") do (
    if not defined PYEXE (
        %%~C -c "import sys,tkinter; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
        if !errorlevel! equ 0 set "PYEXE=%%~C"
    )
)
if not defined PYEXE (
    echo [错误] 没有找到可用的 Python 3.10+（需要带 tkinter）。
    echo        请安装 Python 并在安装时勾选 "tcl/tk and IDLE"。
    echo.
    pause
    exit /b 1
)
echo [1/3] 使用 Python: !PYEXE!
echo.

REM ---------- 2. 准备独立的打包环境（继承已装的依赖, 不动系统 Python） ----------
set "VENV=%~dp0.buildenv"
if not exist "%VENV%\Scripts\python.exe" (
    echo [2/3] 正在创建打包环境 .buildenv ...
    !PYEXE! -m venv --system-site-packages "%VENV%"
    if errorlevel 1 (
        echo [错误] 创建 venv 失败。
        pause
        exit /b 1
    )
) else (
    echo [2/3] 复用已有的打包环境 .buildenv
)

echo       检查/安装 PyInstaller ...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pyinstaller -q
if errorlevel 1 (
    echo [错误] 安装 PyInstaller 失败, 请检查网络。
    pause
    exit /b 1
)
echo.

REM ---------- 3. 打包 ----------
echo [3/3] 开始打包（第一次约 2-5 分钟, 请耐心等待）...
echo.
"%VENV%\Scripts\python.exe" -m PyInstaller --clean --noconfirm fuckZHS.spec
if errorlevel 1 (
    echo.
    echo [错误] 打包失败, 请把上面的报错信息发我。
    pause
    exit /b 1
)

echo.
if exist "dist\fuckZHS.exe" (
    for %%F in ("dist\fuckZHS.exe") do set "SIZE=%%~zF"
    set /a MB=!SIZE!/1048576
    echo ============================================================
    echo   打包成功!
    echo   文件:  %~dp0dist\fuckZHS.exe   ^(约 !MB! MB^)
    echo.
    echo   把这个 exe 单独发给别人即可, 对方不需要安装 Python。
    echo   首次启动会释放文件, 慢几秒属正常。
    echo ============================================================
) else (
    echo [错误] 没有找到 dist\fuckZHS.exe, 请检查上面的输出。
)
echo.
pause
