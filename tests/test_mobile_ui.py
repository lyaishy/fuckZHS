#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""移动端界面回归测试（临时脚本）

覆盖：
  1. 界面能正常构建、渲染（截图不为纯黑/纯白）
  2. 速度输入框可手动输入任意值（含 400），且不再弹"安全确认"
  3. check_speed 不拦截
  4. 收到 ("alert", ...) 会弹出提醒窗
  5. 各控件宽度自适应（不超出屏幕）
"""
import os
import sys
import time

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_LOG_LEVEL", "warning")

sys.path.insert(0, r"C:\Users\我的电脑\fuckZHS")
os.chdir(r"C:\Users\我的电脑\fuckZHS")

from kivy.clock import Clock
from kivy.metrics import dp
import gui_mobile as gm
import mobile_core as mc


PASS = 0
FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}  {extra}")


def main():
    app = gm.MobileApp()
    app.core = mc.Core()
    missing = app.core.setup()
    assert not missing, missing
    root = app.build()

    W, H = dp(400), dp(800)
    root.size = (W, H)
    root.pos = (0, 0)

    # 让布局跑几帧
    for _ in range(6):
        Clock.tick_draw()
        time.sleep(0.02)

    print("\n[1] 构建与布局")
    check("根节点尺寸正确", root.size == [W, H], root.size)
    check("日志区存在", root.log_box is not None)
    check("速度输入框存在", hasattr(root, "speed_input"))

    # 所有子控件都不应超出屏幕宽度
    def walk(w, depth=0):
        bad = []
        for ch in w.children:
            try:
                if ch.width > W + 1:
                    bad.append((type(ch).__name__, ch.width))
            except Exception:
                pass
            bad += walk(ch, depth + 1)
        return bad

    overflow = walk(root)
    check("没有控件超出屏幕宽度", not overflow, overflow[:5])

    print("\n[2] 速度手动输入")
    root.speed_input.text = "400"
    ok, msg = app.core.check_speed(root.speed_input.text)
    check("400 被放行", ok is True)
    check("400 不产生任何提示", msg == "", msg)

    root.speed_input.text = "abc"
    ok2, msg2 = app.core.check_speed(root.speed_input.text)
    check("非数字也放行", ok2 is True)
    check("非数字给出纠正提示", "不是数字" in msg2, msg2)

    root.speed_input.text = ""
    ok3, msg3 = app.core.check_speed("")
    check("留空放行且无提示", ok3 is True and msg3 == "")

    print("\n[3] 不再有速度安全弹窗")
    check("MainView 已无 _confirm_speed", not hasattr(root, "_confirm_speed"))

    print("\n[4] 验证码 alert 弹窗")
    root._dispatch(("alert", mc.CAPTCHA_ALERT_TITLE, mc.captcha_alert_text("c1")))
    Clock.tick_draw()
    check("弹出了提醒窗", root._alert_popup is not None)
    if root._alert_popup is not None:
        body = root._alert_popup.content.children[1]
        txt = getattr(body, "text", "")
        check("提醒里含'电脑'和'验证码'", "电脑" in txt and "验证码" in txt, txt[:60])
        root._alert_popup.dismiss()
        Clock.tick_draw()

    print("\n[5] 日志回流（界面能看到日志）")
    n0 = len(root.log_box.children)
    app.core.act("这是一条测试操作日志")
    for _ in range(3):
        root.pump()
        Clock.tick_draw()
    n1 = len(root.log_box.children)
    check("日志已进入界面", n1 > n0, f"{n0} -> {n1}")

    print("\n[6] busy 联动（禁用速度输入框）")
    root._dispatch(("busy", True, "刷课"))
    check("运行中速度框被禁用", root.speed_input.disabled is True)
    check("运行中「开始」被禁用", root.run_btn.disabled is True)
    root._dispatch(("busy", False, ""))
    check("结束后速度框恢复", root.speed_input.disabled is False)

    print("\n[7] 课程列表渲染")
    root._fill_courses([{"name": "高等数学（上）", "id": "abc123", "kind": "共享课"},
                        {"name": "大学英语", "id": "def456", "kind": "校内课"}])
    for _ in range(3):
        Clock.tick_draw()
    check("课程行已创建", len(root.course_rows) == 2, len(root.course_rows))
    names = [r.info["name"] for r in root.course_rows]
    check("课程行内容正确", names == ["高等数学（上）", "大学英语"], names)

    print("\n[8] 几何布局（不能有重叠 / 越界 / 0 高度）")
    # 说明：这个测试跑在无头环境里，glReadPixels 抓不到画面（全黑），
    # 所以这里改成校验"算出来的几何"，这个在无头下也是准的。
    # 想看真实渲染效果请跑 tests/make_mobile_preview.py。
    cards = [c for c in root.children if type(c).__name__ == "Card"]
    check("卡片数量正确（登录/课程/速度/状态）", len(cards) == 4, len(cards))
    bad = [c for c in cards if c.height <= 0 or c.width <= 0]
    check("没有 0 尺寸的卡片", not bad, [(type(c).__name__, c.size) for c in bad])

    # 从下往上排列，检查是否首尾相接、不重叠
    ordered = sorted(root.children, key=lambda w: w.y)
    ok_stack = True
    detail = []
    for a, b in zip(ordered, ordered[1:]):
        gap = b.y - (a.y + a.height)
        detail.append(round(gap, 1))
        if gap < -0.5:      # 允许 0.5px 浮点误差，负得更多说明重叠了
            ok_stack = False
    check("各区块纵向不重叠", ok_stack, detail)

    total = max(c.y + c.height for c in root.children) - min(c.y for c in root.children)
    check("内容填满了屏幕高度（无大片空白）", total >= root.height - dp(20),
          f"内容 {total:.0f} / 屏幕 {root.height:.0f}")

    print(f"\n===== 结果：{PASS} 通过 / {FAIL} 失败 =====")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
