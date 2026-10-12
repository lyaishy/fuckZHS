#!/usr/bin/env bash
# 在 Docker 里构建 fuckZHS 安卓 APK
#
# 首次运行会下载 Android SDK/NDK（数个 GB），视网络 30~60 分钟；
# 之后有缓存，通常 5~15 分钟。
#
# 用法（在项目根目录）:
#     bash docker-build.sh
#
# 产物: bin/fuckzhs-1.0.0-arm64-v8a_armeabi-v7a-debug.apk

set -e
cd "$(dirname "$0")"

echo "============================================================"
echo "  fuckZHS APK 构建 (Docker)"
echo "============================================================"

if ! command -v docker >/dev/null 2>&1; then
    echo "[错误] 没有找到 docker 命令。请先安装 Docker Desktop 并启动它。"
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "[错误] Docker 没有运行。请启动 Docker Desktop 后重试。"
    exit 1
fi

echo "[1/2] 构建构建镜像 (首次约 5 分钟)…"
docker build -t fuckzhs-builder .

echo
echo "[2/2] 开始打包 APK (首次很慢, 请耐心等待)…"
mkdir -p .buildozer_cache

docker run --rm -it \
    -v "$PWD":/home/user/hostcwd \
    -v fuckzhs-buildozer:/home/user/.buildozer \
    -v "$PWD/.buildozer_cache":/home/user/.cache \
    fuckzhs-builder \
    buildozer android debug

echo
if ls bin/*.apk >/dev/null 2>&1; then
    echo "============================================================"
    echo "  打包成功! APK 在 bin/ 目录:"
    ls -lh bin/*.apk
    echo
    echo "  安装到手机:"
    echo "    1) 把 APK 传到手机, 用文件管理器点击安装"
    echo "       (需要在「设置-安全」里允许「安装未知来源应用」)"
    echo "    2) 或者用数据线 + adb:"
    echo "         adb install -r $(ls bin/*.apk | head -1)"
    echo "============================================================"
else
    echo "[错误] 没有找到 APK，请把上面的报错信息发我。"
    exit 1
fi
