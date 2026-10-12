@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   把本机代码推送到你自己的 GitHub 仓库
echo   （推完之后，去 GitHub 网页点 Actions 就能在线打包 APK）
echo ============================================================
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo [错误] 没找到 git。请先安装 Git for Windows：https://git-scm.com/download/win
  echo.
  pause
  exit /b 1
)

set /p GHUSER=请输入你的 GitHub 用户名（英文，例如 zhangsan）:
if "%GHUSER%"=="" (
  echo [错误] 用户名不能为空。
  pause
  exit /b 1
)

set /p GHREPO=请输入仓库名（直接回车 = fuckZHS）:
if "%GHREPO%"=="" set "GHREPO=fuckZHS"

set "URL=https://github.com/%GHUSER%/%GHREPO%.git"

echo.
echo ------------------------------------------------------------
echo   目标仓库：%URL%
echo.
echo   请确认：这个仓库必须已经存在（先 Fork 或先新建），
echo   否则推送会失败。
echo ------------------------------------------------------------
echo.
pause

echo.
echo [1/4] 设置远程地址...
git remote set-url origin "%URL%"
if errorlevel 1 git remote add origin "%URL%"

echo.
echo [2/4] 暂存改动...
git add -A

echo.
echo [3/4] 提交...
git commit -m "安卓版：Kivy 界面 + GitHub Actions 在线打包"
echo    （如果提示 nothing to commit，说明没有新改动，不影响）

echo.
echo [4/4] 推送...
git branch -M master
git push -u origin master

if errorlevel 1 (
  echo.
  echo ============================================================
  echo   [失败] 推送没成功。常见原因：
  echo     1. 仓库还没在 GitHub 上创建（先去 Fork 或新建）
  echo     2. 仓库名 / 用户名打错了
  echo     3. 弹出的浏览器授权窗口被关掉了 —— 重新运行本脚本再授权一次
  echo     4. 网络问题（国内访问 GitHub 有时不稳，可多试几次）
  echo ============================================================
) else (
  echo.
  echo ============================================================
  echo   [成功] 代码已经推上去了！
  echo.
  echo   接下来：浏览器打开  %URL:.git=%
  echo             点顶部 Actions   ^>  左侧「在线打包安卓 APK」
  echo             点右侧 Run workflow  ^>  选 arm64-v8a  ^>  运行
  echo.
  echo   详细步骤见同目录的  在线上打包教程.txt
  echo ============================================================
)

echo.
pause
