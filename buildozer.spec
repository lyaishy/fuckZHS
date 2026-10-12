# -*- coding: utf-8 -*-
[app]

title = fuckZHS
package.name = fuckzhs
package.domain = org.fuckzhs

source.dir = .
source.include_exts = py,png,jpg,jpeg,webp,ttf,ttc,json,txt
# 排除目录：构建产物、缓存、测试、以及用不到的素材
source.exclude_dirs = .buildenv, .buildozer, .buildozer_global, .buildozer_cache, .github, .workbuddy, build, dist, bin, tests, .git, __pycache__, logs, aiexamAnswer, images, decrypt
# ⚠ 以下文件**绝对不能**打进 APK（发给别人 = 连同你的个人数据一起送出去）：
#   cookies.json       当前用户的登录会话
#   config.json        可能填过 username / password / pushplus / bark token
#   gui_settings.json  本地运行痕迹（含速度、代理等）
#   execution.json     上次刷课记录
#   随包发布的只有 config.example.json（干净模板，无任何凭据），
#   程序首次运行会由它生成自己的 config.json。
#   说明：buildozer 打的是**工作目录**，不是 git 仓库，
#   所以 .gitignore 不能替代这里的排除。
source.exclude_patterns = *.spec, *.zip, *.exe, *.log, *.pyc, crash.log, .qr_preview.png, *.md, cookies.json, config.json, gui_settings.json, execution.json, ai_courses.json, 发布说明.txt, 安卓打包说明.txt, 在线上打包教程.txt

version = 1.0.0

# 依赖：**每一项都必须能对上 p4a 的配方，或者由别的配方的 python_depends 带进来。**
# **不要钉版本号** —— p4a 的默认组合（CPython 3.14.2 + Kivy 2.3.1）才是官方 CI
# 每天在测的，自己钉一个旧版本反而是没人验证过的组合。
# 而且：写在 requirements 里的 `包==版本` 对「纯 Python 依赖」那条路径是**无效**的
# （实测：p4a 只取包名、版本被丢弃），所以钉版本根本解决不了下面那个问题。
#   python3        p4a 配方 ✓
#   kivy           p4a 配方 ✓，且它的 python_depends 会自动带上
#                  requests / urllib3 / certifi / chardet / idna / filetype
#                  （脚本要用的 requests 就是从这里来的，不用自己列）
#   openssl        p4a 配方 ✓（python3 的依赖）
#   pycryptodome   p4a 配方 ✓（zd_utils.py 里的 AES 加密要靠它）
# 注意**不要**写 pillow：p4a 没有它的配方，只能 pip 装到安卓目标上，
# 而它是 C 扩展，在安卓上装很容易失败。本项目手机端用不到 PIL
# （结论见 utils.py 顶部：PIL 只用于终端里用字符画显示二维码）。
#
# ⚠⚠ 在线打包失败的真正原因（已定位到根因，别再往依赖里钉版本了）：
#
#   p4a (master) 安装「纯 Python 依赖」分两个阶段，两个阶段的参数**不对称**：
#     ① 解析阶段：
#          pip install <包名> --dry-run ... --only-binary=:all: --report ...
#              --platform=android_{ndk-api}_{abi} --python-version 3.14.2
#        → 带着平台标签去挑，优先命中**安卓专用轮**
#     ② 安装阶段：
#          venv/bin/pip install -v --target '...' --no-deps -r requirements.txt
#        → **没有 --platform**，宿主机 pip 不认 android_* 标签，于是整个构建挂在
#          ERROR: charset_normalizer-3.5.2-cp314-cp314-android_24_arm64_v8a.whl
#                 is not a supported wheel on this platform
#
#   两个阶段唯一都认的是 `py3-none-any` 通用轮。所以要修的不是版本，而是
#   **让①根本匹配不到安卓专用轮** —— 把平台标签从 android_24_* 挪开即可。
#   标签里的 24 = ctx.ndk_api；buildozer 在 android.ndk_api 未设置时让它取
#   android.minapi，所以把 android.minapi 从 24 改成 21 就够了（见文件下方）。
#   21 是 p4a 官方支持的下限（recommendations.MIN_NDK_API = 21），不报错。
#
#   为什么偏偏是 charset-normalizer 中招：它不在我们的依赖里，是 kivy 配方
#   的 python_depends → requests → charset-normalizer 自动带进来的；而它
#   **从 3.5.x 才开始发布 android_24_* 专用轮**，另外七个（certifi/chardet/
#   filetype/idna/requests/six/urllib3）从来只发 py3-none-any，所以一直没事。
#   平台标签变成 android_21_* 后，它也只会落到 py3-none-any —— 纯 Python 包，
#   装在安卓上与装在任何地方等价，性能差异可忽略。
requirements = python3,kivy,openssl,pycryptodome

# 首次运行会联网下载需要的库（sh 文件会指名 fork 源码）
android.permissions = INTERNET, ACCESS_NETWORK_STATE, WAKE_LOCK, POST_NOTIFICATIONS

# 自动化/CI 打包必须自动接受 SDK 许可，否则会卡在交互式许可确认上
android.accept_sdk_license = True

android.api = 34
# ⚠ 必须保持 21，不要改成 24：它经 buildozer 推导出 p4a 的 --ndk-api，
#   而 --ndk-api 直接决定 pip 解析安卓轮时用的平台标签（android_{api}_{abi}）。
#   改成 24 会让 charset-normalizer 命中 android_24_* 专用轮，从而踩中 p4a
#   两个阶段参数不对称的 bug（完整解释见上方 requirements 处的大段注释）。
#   21 是 p4a 的 MIN_NDK_API，官方支持；副作用仅是 APK 的可安装下限变成
#   Android 5.0（API 21），对功能没有影响。
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = True

android.presplash_color = #FFFFFF
# android.presplash = presplash.png

# 保活：长任务需要尽量阻止系统休眠（见 gui_mobile.py 的 try_keep_awake）
android.entrypoint = org.kivy.android.PythonActivity

orientation = portrait

# 图标：buildozer 会自动缩放 icon512 生成各密度版本
# 注意 images/ 被排除在 App 内容之外 —— 图标是在**打包阶段**从磁盘读取的，
# 与打进去的私有目录无关，所以这里不会冲突。
icon.filename = %(source.dir)s/images/icon512.png

fullscreen = 0

# Python 入口固定为应用目录下的 main.py（p4a 不支持改名）。
# 本项目 main.py 顶部做了环境分发：安卓下直接启动 Kivy 界面，桌面下仍是命令行。
# 详见 main.py 开头的「安卓入口分发」注释。

[buildozer]

log_level = 2
warn_on_root = 1
