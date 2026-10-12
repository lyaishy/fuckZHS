#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端：验证「速度手动输入」与「验证码提醒」两条链路真的通了（临时脚本）"""
import os, sys, time

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_LOG_LEVEL", "error")
sys.path.insert(0, r"C:\Users\我的电脑\fuckZHS")
os.chdir(r"C:\Users\我的电脑\fuckZHS")

from kivy.clock import Clock
import gui_mobile as gm
import mobile_core as mc

PASS = FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {extra}")


def main():
    app = gm.MobileApp()
    app.core = mc.Core()
    app.core.setup()

    root = app.build()
    root.size = (800, 1600)     # dp 400x800 @ density 2
    root.pos = (0, 0)

    # ---- 用假 fucker 顶掉真实网络请求 ----
    class FakeFucker:
        instances = []

        def __init__(self, **kw):
            self.kw = kw
            self.last_abort = None
            self.cookies = {}
            FakeFucker.instances.append(self)

        def fuckCourse(self, cid):
            # 模拟：第一门课被验证码中断，第二门正常完成
            if str(cid) == "111":
                self.last_abort = "captcha"
            else:
                self.last_abort = None

        def fuckWhatever(self):
            self.last_abort = None

    class FakeCoreFucker(FakeFucker):
        pass

    app.core.CoreFucker = FakeCoreFucker
    app.core._load_cookies = lambda f: True      # 跳过登录状态检查

    print("\n[1] 速度 400 真的传到了 fucker")
    root.speed_input.text = "400"
    root._fill_courses([{"name": "A", "id": "111", "kind": "共享课"},
                        {"name": "B", "id": "222", "kind": "共享课"}])
    root.on_run()
    # 等后台线程跑完
    for _ in range(120):
        root.pump()
        Clock.tick_draw()
        if not app.core.busy:
            break
        time.sleep(0.03)
    inst = FakeFucker.instances[-1]
    check("speed=400 已传给 fucker", inst.kw.get("speed") == 400.0,
          inst.kw.get("speed"))
    check("设置里也存了 400", app.core.settings.get("speed") == "400",
          app.core.settings.get("speed"))

    print("\n[2] 验证码中断 -> 界面弹提醒 + 日志有恢复指引")
    check("触发了 alert 弹窗", root._alert_popup is not None)
    logs = [c.text for c in root.log_box.children if hasattr(c, "text")]
    joined = "\n".join(logs)
    check("日志里有「电脑」恢复指引", "电脑" in joined)
    check("日志里提到 zhihuishu.com", "zhihuishu.com" in joined, joined[-200:])
    check("日志里说明过完验证码后再点开始刷课", "开始刷课" in joined)

    print("\n[3] 第二门课正常完成（不会误报）")
    # 只看"===== [n/m] 课程 X 被…中断"这种带课程号的汇报行
    interrupt_lines = [l for l in logs if "课程" in l and "中断" in l and "=====" in l]
    check("只有课程 111 被报为中断",
          len(interrupt_lines) == 1 and "111" in interrupt_lines[0], interrupt_lines)
    check("课程 222 没有被误判", not any("222" in l and "中断" in l for l in logs),
          [l for l in logs if "222" in l])
    done_logs = [l for l in logs if "全部课程" in l or "未刷完" in l]
    check("结束时如实汇报未刷完的课程", any("未刷完" in l for l in logs), done_logs)

    print("\n[4] 速度留空 -> 交给网站默认")
    FakeFucker.instances.clear()
    root.speed_input.text = ""
    root._fill_courses([{"name": "B", "id": "222", "kind": "共享课"}])
    root.on_run()
    for _ in range(120):
        root.pump()
        Clock.tick_draw()
        if not app.core.busy:
            break
        time.sleep(0.03)
    inst2 = FakeFucker.instances[-1]
    check("留空时 speed=None（用网站默认）", inst2.kw.get("speed") is None,
          inst2.kw.get("speed"))

    print("\n[5] 速度填非数字 -> 提示并按留空处理，不阻断")
    FakeFucker.instances.clear()
    root.speed_input.text = "fast"
    root._fill_courses([{"name": "B", "id": "222", "kind": "共享课"}])
    root.on_run()
    for _ in range(120):
        root.pump()
        Clock.tick_draw()
        if not app.core.busy:
            break
        time.sleep(0.03)
    inst3 = FakeFucker.instances[-1]
    check("非数字被当成留空", inst3.kw.get("speed") is None, inst3.kw.get("speed"))

    print(f"\n===== 结果：{PASS} 通过 / {FAIL} 失败 =====")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
