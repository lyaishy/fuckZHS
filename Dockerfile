# 用于构建 fuckZHS 安卓 APK 的镜像
#
# buildozer 不支持 Windows 原生构建，所以走 Docker。
# 用法见 docker-build.sh / docker-build.bat
#
# 基于官方 kivy/buildozer 镜像（已装好 Android SDK / NDK / python-for-android 依赖）

FROM kivy/buildozer:latest

ENV DEBIAN_FRONTEND=noninteractive

# buildozer 需要的补充依赖（apt 源慢时可跳过，官方镜像已包含大部分）
USER root
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
        git zip unzip openjdk-17-jdk-headless autoconf libtool \
        pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
        cmake libffi-dev libssl-dev >/dev/null 2>&1 || true
USER user

WORKDIR /home/user/hostcwd

# 构建缓存：把 SDK/NDK 和 buildozer 全局缓存挂到卷上，避免每次重新下载
ENV BUILDOZER_WARN_ON_ROOT=0
ENV GRADLE_OPTS="-Dorg.gradle.daemon=false"

CMD ["buildozer", "android", "debug"]
