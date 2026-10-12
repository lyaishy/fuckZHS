@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo   fuckZHS 安卓 APK 构建
echo ============================================================
echo.

docker --version >nul 2>nul
if errorlevel 1 (
    echo [错误] 没有找到 docker 命令。
    echo        请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop/
    echo        装好后启动它, 等托盘图标变成绿色再运行本脚本。
    echo.
    pause
    exit /b 1
)

docker info >nul 2>nul
if errorlevel 1 (
    echo [错误] Docker 没有运行，请先启动 Docker Desktop。
    echo.
    pause
    exit /b 1
)

echo [1/2] 构建构建镜像（首次约 5 分钟）...
docker build -t fuckzhs-builder .
if errorlevel 1 (
    echo [错误] 镜像构建失败。
    pause
    exit /b 1
)

echo.
echo [2/2] 开始打包 APK（首次需下载 Android SDK，可能 30~60 分钟）...
echo       这一步很占时间和磁盘，请不要关窗口。
echo.

if not exist ".buildozer_cache" mkdir ".buildozer_cache"

docker run --rm -it ^
    -v "%cd%":/home/user/hostcwd ^
    -v fuckzhs-buildozer:/home/user/.buildozer ^
    -v "%cd%\.buildozer_cache":/home/user/.cache ^
    fuckzhs-builder ^
    buildozer android debug
if errorlevel 1 (
    echo.
    echo [错误] 打包失败，请把上面的报错信息发我。
    pause
    exit /b 1
)

echo.
if exist "bin\*.apk" (
    echo ============================================================
    echo   打包成功！APK 在 bin\ 目录：
    dir /b bin\*.apk
    echo.
    echo   装到手机：
    echo     1) 把 APK 传到手机，用文件管理器点击安装
    echo        （需在「设置-安全」里允许「安装未知来源应用」）
    echo     2) 或数据线 + adb install -r bin\xxx.apk
    echo ============================================================
) else (
    echo [错误] 没有找到 APK。
)
echo.
pause
