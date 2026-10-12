#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用真实窗口渲染一次并截图（临时脚本）

注意：App.run() 会自己 build() 出 root，所以演示数据必须在窗口起来之后再注入。
"""
import os, sys

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_LOG_LEVEL", "error")
sys.path.insert(0, r"C:\Users\我的电脑\fuckZHS")
os.chdir(r"C:\Users\我的电脑\fuckZHS")

from kivy.clock import Clock
from kivy.core.window import Window
import gui_mobile as gm
import mobile_core as mc

Window.size = (400, 800)

app = gm.MobileApp()
app.core = mc.Core()
app.core.setup()

state = {"n": 0, "filled": False}


def fill(view):
    view._clear_log()
    view._append_log("界面已就绪。第一步：点「扫码登录」。", "info")
    view._fill_courses([
        {"name": "高等数学（上）", "id": "a1b2c3d4", "kind": "共享课"},
        {"name": "大学英语读写", "id": "e5f6g7h8", "kind": "共享课"},
        {"name": "中国近现代史纲要", "id": "i9j0k1l2", "kind": "校内课"},
    ])
    view._append_log("√ 获取到 3 门课程", "success")
    view._append_log("开始刷课：勾选=3 门  播放速度=400  代理=系统默认", "info")
    view._append_log("===== [1/3] 开始课程 高等数学（上） =====", "info")
    view._append_log("===== [1/3] 课程完成，用时 128.4s =====", "success")
    view._append_log("===== [2/3] 开始课程 大学英语读写 =====", "info")
    view.login_text = "已登录 · 有保存的登录状态"
    view.status_text = "正在刷第 2/3 门课程"
    view.speed_input.text = "400"
    view._set_running(True, "刷课")


def tick(dt):
    state["n"] += 1
    view = app.root
    if view is None:
        return
    if not state["filled"]:
        fill(view)
        state["filled"] = True
        return
    if state["n"] < 16:
        return
    try:
        Window.screenshot(name="_dev_preview.png")
    except Exception as e:
        print("shot err:", e)
    Clock.schedule_once(lambda *_: app.stop(), 0.8)


Clock.schedule_interval(tick, 0.15)
app.run()
print("done")
