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

# 依赖：Kivy 2.3.0 与 python-for-android 的 CPython 3.11 是已知可用的组合
requirements = python3==3.11.5,kivy==2.3.0,openssl,requests,pycryptodome,pillow,urllib3,chardet,idna,certifi

# 首次运行会联网下载需要的库（sh 文件会指名 fork 源码）
android.permissions = INTERNET, ACCESS_NETWORK_STATE, WAKE_LOCK, POST_NOTIFICATIONS

# 自动化/CI 打包必须自动接受 SDK 许可，否则会卡在交互式许可确认上
android.accept_sdk_license = True

android.api = 34
android.minapi = 24
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
