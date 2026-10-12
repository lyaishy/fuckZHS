#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fuckZHS 安卓版界面（Kivy）

完全独立于桌面版 `gui.py`（Tkinter）—— 桌面版一行未动，两条线互不干扰。
所有业务逻辑都在 `mobile_core.py` 里，本文件只负责「画界面 + 派发消息」。

启动方式:
    py gui_mobile.py          # 电脑上预览（需要 kivy，仅用于调试）

打包 APK:
    buildozer android debug   # 见 buildozer.spec / docker-build.sh

与桌面版共享的数据（同一个数据目录）:
    config.json, cookies.json, gui_settings.json, execution.json, logs/

布局原则（踩过坑，别再改）:
    * 所有控件宽度用 size_hint_x=1 自动铺满，**不写死像素宽度**，
      这样 360dp / 411dp / 480dp 的手机都能正常显示。
    * 需要换行的文本：绑 width -> text_size=(w, None)（标准写法，稳定）。
      **绝对不要**在 texture_size 回调里回写 text_size，会无限重排导致整屏渲染不出来。
    * 高度一律 size_hint_y=None + 显式 height，不用 minimum_height 自动测高。
"""

import os
import sys
import threading
import traceback

# ---- Kivy 环境在 import 之前设置，避免某些后端报错 ----
os.environ.setdefault("KIVY_NO_ARGS", "1")

try:
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.text import LabelBase
    from kivy.graphics import Color, Line, RoundedRectangle
    from kivy.metrics import dp, sp
    from kivy.properties import BooleanProperty, StringProperty
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.checkbox import CheckBox
    from kivy.uix.image import Image as KvImage
    from kivy.uix.label import Label
    from kivy.uix.popup import Popup
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.textinput import TextInput

    KIVY_OK = True
except Exception as _e:  # 没装 kivy 时给出人话提示
    KIVY_OK = False
    _KIVY_ERR = _e

if not KIVY_OK:
    print("当前环境没有安装 Kivy，无法启动移动端界面。")
    print("安装: pip install kivy==2.3.0")
    print("原始错误:", _KIVY_ERR)
    sys.exit(1)

import mobile_core as mc

# --------------------------------------------------------------------------
# 配色（浅色主题）
# --------------------------------------------------------------------------
C_BG        = (0.976, 0.976, 0.980, 1)
C_CARD      = (1, 1, 1, 1)
C_BORDER    = (0.78, 0.78, 0.81, 1)
C_TEXT      = (0.12, 0.12, 0.14, 1)
C_TEXT_DIM  = (0.45, 0.45, 0.50, 1)
C_PRIMARY   = (0.094, 0.373, 0.647, 1)   # #185FA5
C_ACCENT    = (0.847, 0.353, 0.188, 1)   # #D85A30
C_GOOD      = (0.388, 0.600, 0.133, 1)   # #639922
C_BAD       = (0.639, 0.176, 0.176, 1)   # #A32D2D

# 日志级别 -> 颜色
LEVEL_COLORS = {
    "debug": C_TEXT_DIM,
    "info": C_TEXT,
    "success": C_GOOD,
    "warning": C_ACCENT,
    "error": C_BAD,
    "critical": C_BAD,
}

# 中文字体候选（Android 上自带 Noto Sans CJK，Windows 上回落到雅黑）
_FONT_CANDIDATES = [
    "NotoSansCJK-Regular.ttc",
    "/system/fonts/NotoSansCJK-Regular.ttc",
    "/system/fonts/DroidSansFallbackFull.ttf",
    "/system/fonts/NotoSansSC-Regular.otf",
    "/system/fonts/HarmonyOS_Sans_SC_Regular.ttf",
    "/system/fonts/MiSans-Regular.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyh.ttf",
    "msyh.ttf",
]

# 扫描 /system/fonts 时用来判断"这个字体大概认识中文"的线索词。
# 各品牌 ROM 的中文字体名差异很大（华为用 HarmonyOS_Sans / 小米用 MiSans /
# 老机器用 DroidSansFallback），只赌固定路径很容易在某个品牌上满屏方块，
# 所以固定路径都找不到时，再按这些线索扫一遍系统字体目录。
_CJK_HINTS = ("cjk", "fallback", "harmonyos", "misans", "sourcehan",
              "notosanssc", "notosanstc", "notosanshans", "droidsanschinese",
              "hwfonts", "emui", "sourcehansans", "zh", "chinese")

# 安卓上的系统字体目录（ANDROID_ROOT 一般就是 /system）
def _system_font_dirs():
    dirs = ["/system/fonts", "/system/font"]
    root = os.environ.get("ANDROID_ROOT")
    if root:
        dirs.append(os.path.join(root, "fonts"))
    return dirs


def register_cjk_font():
    """注册中文字体，返回可用字体名（实在找不到就用 Kivy 默认）"""
    # ① 先试明确列出的路径
    for path in _FONT_CANDIDATES:
        try:
            if path in ("NotoSansCJK-Regular.ttc", "msyh.ttf"):
                LabelBase.register(name="cjk", fn_regular=path)
                return "cjk"
            if os.path.isfile(path):
                LabelBase.register(name="cjk", fn_regular=path)
                return "cjk"
        except Exception:
            continue

    # ② 再扫系统字体目录，按线索词挑一个中文字体
    for d in _system_font_dirs():
        try:
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                low = fn.lower()
                if not low.endswith((".ttf", ".ttc", ".otf")):
                    continue
                if any(h in low for h in _CJK_HINTS):
                    LabelBase.register(name="cjk", fn_regular=os.path.join(d, fn))
                    return "cjk"
        except Exception:
            continue

    return "Roboto"


FONT = register_cjk_font()


# --------------------------------------------------------------------------
# 小部件
# --------------------------------------------------------------------------
class Card(BoxLayout):
    """白底圆角卡片（高度由调用方给，宽度自动铺满）"""

    def __init__(self, **kw):
        self.bg = kw.pop("bg", C_CARD)
        kw.setdefault("padding", (dp(12), dp(10), dp(12), dp(10)))
        super().__init__(**kw)
        with self.canvas.before:
            self._c = Color(*self.bg)
            self._r = RoundedRectangle(radius=[dp(10)], pos=self.pos, size=self.size)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size


def vlabel(text, size=13, color=None, bold=False, height=None, halign="left",
           valign="middle", **kw):
    """会自动换行的文本标签

    宽度默认铺满父容器（size_hint_x=1）；`width` 只在少数固定宽度场景显式给。
    `text_size` 由 width 绑定驱动 —— 这是 Kivy 的标准写法，安全。
    """
    lbl = Label(text=text, font_name=FONT, font_size=sp(size),
                color=color if color is not None else C_TEXT, bold=bold,
                halign=halign, valign=valign,
                size_hint_y=None, height=height or dp(22), **kw)
    lbl.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
    # 首次布局时补一次，保证一上来就是对的
    Clock.schedule_once(lambda *_: setattr(lbl, "text_size", (lbl.width, None)), 0)
    return lbl


class FlatButton(Button):
    """扁平按钮；kind: primary / accent / plain / danger

    plain（次要按钮）带一圈描边，否则在白色卡片上几乎是隐形的；
    禁用时整体淡化但文字仍可辨认。
    """

    def __init__(self, kind="plain", **kw):
        self.kind = kind
        super().__init__(**kw)
        self.font_name = FONT
        self.font_size = sp(15)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.color = C_TEXT
        self.disabled_color = (0.62, 0.62, 0.65, 1)
        self._border = None
        if kind == "accent":
            self._fill = C_ACCENT
            self.color = (1, 1, 1, 1)
        elif kind == "primary":
            self._fill = C_PRIMARY
            self.color = (1, 1, 1, 1)
        elif kind == "danger":
            self._fill = C_BAD
            self.color = (1, 1, 1, 1)
        else:
            self._fill = (0.955, 0.955, 0.965, 1)
        self.bold = kind in ("primary", "accent", "danger")
        with self.canvas.before:
            self._c = Color(*self._fill)
            self._r = RoundedRectangle(radius=[dp(10)], pos=self.pos, size=self.size)
            if kind == "plain":
                self._bc = Color(*C_BORDER)
                self._border = Line(rounded_rectangle=(
                    self.x, self.y, self.width, self.height, dp(10)), width=1.0)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size
        if self._border is not None:
            self._border.rounded_rectangle = (
                self.x, self.y, self.width, self.height, dp(10))

    def on_disabled(self, *_):
        # 禁用时只把底色调淡，文字保持足够对比度（否则「开始刷课」会看不见字）
        a = 0.6 if self.disabled else 1.0
        self._c.rgba = (self._fill[0], self._fill[1], self._fill[2], a)


def section_title(text):
    return vlabel(text, size=12, color=C_TEXT_DIM, height=dp(22))


# --------------------------------------------------------------------------
# 二维码弹窗
# --------------------------------------------------------------------------
class QrPopup(Popup):
    def __init__(self, on_cancel, **kw):
        super().__init__(**kw)
        self.title = "扫码登录"
        self.title_font = FONT
        self.title_size = sp(16)
        self.size_hint = (0.92, None)
        self.height = dp(430)
        self.auto_dismiss = False
        self.on_cancel = on_cancel

        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(12))
        self.status = Label(text="正在获取二维码…", font_name=FONT, font_size=sp(13),
                            color=C_TEXT_DIM, size_hint_y=None, height=dp(24))
        self.img = KvImage(size_hint=(1, 1))
        cancel = FlatButton(text="取消登录", kind="plain", size_hint_y=None, height=dp(46))
        cancel.bind(on_release=lambda *_: self._cancel())

        root.add_widget(self.status)
        root.add_widget(self.img)
        root.add_widget(cancel)
        self.content = root

    def set_image(self, data):
        """data: PNG 字节"""
        tmp = os.path.join(mc.ROOT or os.getcwd(), ".qr_preview.png")
        try:
            with open(tmp, "wb") as f:
                f.write(data)
            self.img.source = tmp
            self.img.reload()
            self.status.text = "用「知到」App 扫描二维码"
            self.status.color = C_TEXT
        except Exception as e:
            self.status.text = f"二维码显示失败：{e}"
            self.status.color = C_BAD

    def set_status(self, text, ok=None):
        self.status.text = text
        self.status.color = C_GOOD if ok else (C_BAD if ok is False else C_TEXT_DIM)

    def _cancel(self):
        try:
            self.on_cancel()
        finally:
            self.dismiss()


# --------------------------------------------------------------------------
# 提醒弹窗（验证码等需要用户去电脑上操作的情况）
# --------------------------------------------------------------------------
class AlertPopup(Popup):
    def __init__(self, title, text, **kw):
        super().__init__(**kw)
        self.title = title
        self.title_font = FONT
        self.title_size = sp(15)
        self.size_hint = (0.92, None)
        self.height = dp(340)
        self.auto_dismiss = False

        root = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(12))
        body = vlabel(text, size=13, valign="top", height=dp(224))
        ok = FlatButton(text="知道了", kind="primary", size_hint_y=None, height=dp(46))
        ok.bind(on_release=lambda *_: self.dismiss())
        root.add_widget(body)
        root.add_widget(ok)
        self.content = root


# --------------------------------------------------------------------------
# 课程行（勾选框 + 名称）
# --------------------------------------------------------------------------
class CourseRow(BoxLayout):
    def __init__(self, info, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None, height=dp(50),
                         spacing=dp(4), padding=(dp(2), 0, dp(2), 0), **kw)
        self.info = info
        self.cb = CheckBox(active=True, size_hint_x=None, width=dp(34), color=C_PRIMARY)
        body = BoxLayout(orientation="vertical")
        name = vlabel(info["name"], size=14, height=dp(24))
        meta = vlabel(f"{info.get('kind','')} · {info.get('id','')}",
                      size=10, color=C_TEXT_DIM, height=dp(18))
        body.add_widget(name)
        body.add_widget(meta)
        self.add_widget(self.cb)
        self.add_widget(body)


# --------------------------------------------------------------------------
# 主界面
# --------------------------------------------------------------------------
class MainView(BoxLayout):
    login_text = StringProperty("未登录")
    status_text = StringProperty("就绪")
    course_count = StringProperty("我的课程")
    running = BooleanProperty(False)

    def __init__(self, core, **kw):
        super().__init__(orientation="vertical", padding=dp(10), spacing=dp(8), **kw)
        self.core = core
        self.course_rows = []
        self._qr_popup = None
        self._alert_popup = None
        self._log_lock = threading.Lock()

        with self.canvas.before:
            Color(*C_BG)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size)
        self.bind(pos=lambda *_: setattr(self._bg, "pos", self.pos),
                  size=lambda *_: setattr(self._bg, "size", self.size))

        self._build()

    # ---------------- 界面骨架 ----------------
    def _build(self):
        # 1) 登录状态
        top = Card(orientation="horizontal", size_hint_y=None, height=dp(86),
                   spacing=dp(8))
        txt = BoxLayout(orientation="vertical", spacing=dp(2))
        self.login_label = vlabel(self.login_text, size=14, bold=True, height=dp(26))
        # vlabel 只设置了一次 text，属性变化不会自动同步到 Label，必须显式绑定
        self.bind(login_text=lambda _w, v: setattr(self.login_label, "text", v))
        hint = vlabel("扫码登录，或复用上次的登录状态",
                      size=11, color=C_TEXT_DIM, height=dp(34))
        txt.add_widget(self.login_label)
        txt.add_widget(hint)

        btns = BoxLayout(orientation="vertical", size_hint_x=None, width=dp(104),
                         spacing=dp(6))
        self.login_btn = FlatButton(text="扫码登录", kind="primary", font_size=sp(14))
        self.login_btn.bind(on_release=lambda *_: self.on_login())
        self.reuse_btn = FlatButton(text="用上次登录", kind="plain", font_size=sp(11))
        self.reuse_btn.bind(on_release=lambda *_: self.on_reuse())
        btns.add_widget(self.login_btn)
        btns.add_widget(self.reuse_btn)
        top.add_widget(txt)
        top.add_widget(btns)
        self.add_widget(top)

        # 2) 课程列表
        course_card = Card(orientation="vertical", size_hint_y=None, height=dp(186))
        head = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(28))
        self.course_label = vlabel(self.course_count, size=12, color=C_TEXT_DIM,
                                   height=dp(28))
        self.bind(course_count=lambda _w, v: setattr(self.course_label, "text", v))
        refresh = FlatButton(text="刷新", kind="plain", font_size=sp(12),
                             size_hint_x=None, width=dp(58), height=dp(28))
        refresh.bind(on_release=lambda *_: self.on_fetch())
        head.add_widget(self.course_label)
        head.add_widget(refresh)

        self.course_scroll = ScrollView(do_scroll_x=False, bar_width=dp(2),
                                        size_hint_y=None, height=dp(136))
        self.course_box = BoxLayout(orientation="vertical", size_hint_y=None,
                                    spacing=dp(1))
        self.course_box.bind(minimum_height=self.course_box.setter("height"))
        self.course_scroll.add_widget(self.course_box)

        course_card.add_widget(head)
        course_card.add_widget(self.course_scroll)
        self.add_widget(course_card)

        # 3) 播放速度（手动输入，不做安全拦截）
        speed_card = Card(orientation="vertical", size_hint_y=None, height=dp(96))
        row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44),
                        spacing=dp(8))
        row.add_widget(vlabel("播放速度", size=14, bold=True, height=dp(44)))
        self.speed_input = TextInput(
            text=str(self.core.settings.get("speed") or ""),
            hint_text="留空",
            input_filter="float", multiline=False, font_name=FONT, font_size=sp(15),
            size_hint_x=None, width=dp(104), size_hint_y=None, height=dp(40),
            halign="center", padding=(dp(6), dp(10)),
            background_color=(0.97, 0.97, 0.98, 1), foreground_color=C_TEXT,
            cursor_color=C_PRIMARY, hint_text_color=(0.6, 0.6, 0.63, 1))
        row.add_widget(self.speed_input)
        tip = vlabel("留空 = 网站最大值（1.25 / 1.5）；也可手动填任意数值（如 400）",
                     size=10, color=C_TEXT_DIM, height=dp(30))
        speed_card.add_widget(row)
        speed_card.add_widget(tip)
        self.add_widget(speed_card)

        # 4) 状态
        self.progress_card = Card(orientation="vertical", size_hint_y=None,
                                  height=dp(48))
        self.status_label = vlabel(self.status_text, size=13, color=C_PRIMARY,
                                   height=dp(28))
        self.bind(status_text=lambda _w, v: setattr(self.status_label, "text", v))
        self.progress_card.add_widget(self.status_label)
        self.add_widget(self.progress_card)

        # 5) 日志（占满剩余空间）
        self.add_widget(self._build_log_card())

        # 6) 底部操作
        bottom = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(56),
                           spacing=dp(10))
        self.run_btn = FlatButton(text="开始刷课", kind="accent")
        self.run_btn.bind(on_release=lambda *_: self.on_run())
        self.stop_btn = FlatButton(text="停止", kind="plain")
        self.stop_btn.bind(on_release=lambda *_: self.on_stop())
        self.stop_btn.disabled = True
        bottom.add_widget(self.run_btn)
        bottom.add_widget(self.stop_btn)
        self.add_widget(bottom)

    def _build_log_card(self):
        """日志卡片：内部用 ScrollView + 顶部对齐的 BoxLayout

        注意 ScrollView 的子布局必须设 size_hint_y=None + minimum_height 绑定，
        否则内容会被压扁或无法滚动。
        """
        wrapper = BoxLayout(orientation="vertical")
        head = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(28))
        head.add_widget(vlabel("运行日志", size=12, color=C_TEXT_DIM, height=dp(28)))
        clear = FlatButton(text="清空", kind="plain", font_size=sp(12),
                           size_hint_x=None, width=dp(56), height=dp(28))
        clear.bind(on_release=lambda *_: self._clear_log())
        head.add_widget(clear)

        self.log_scroll = ScrollView(do_scroll_x=False, bar_width=dp(2))
        # holder 固定在顶部，不随内容拉伸，保证日志从上方开始排
        holder = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(3))
        holder.bind(minimum_height=holder.setter("height"))
        self.log_box = holder
        self.log_scroll.add_widget(holder)

        wrapper.add_widget(head)
        wrapper.add_widget(self.log_scroll)
        return wrapper

    # ---------------- 交互 ----------------
    def on_login(self):
        self._clear_log()
        self.core.login_qr()
        self._open_qr_popup()

    def _open_qr_popup(self):
        if self._qr_popup is not None:
            return
        self._qr_popup = QrPopup(on_cancel=self._on_qr_cancel)
        self._qr_popup.bind(on_dismiss=lambda *_: setattr(self, "_qr_popup", None))
        self._qr_popup.open()

    def _on_qr_cancel(self):
        self.core.cancel_login()
        self._qr_popup = None

    def on_reuse(self):
        self.core.load_cookies()

    def on_fetch(self):
        self.core.fetch_courses()

    def on_run(self):
        """开始刷课。速度直接取输入框，不做任何安全确认弹窗"""
        speed = self.speed_input.text.strip()
        _ok, msg = self.core.check_speed(speed)
        if msg:
            # 只提示"不是数字，按留空处理"，然后照常开始
            self._append_log(msg, "warning")
            speed = ""
        ids = [r.info["id"] for r in self.course_rows if r.cb.active]
        self.core.settings["speed"] = speed
        self.core.save_settings({"speed": speed})
        self.core.run_courses(ids, speed=speed)

    def on_stop(self):
        self.core.request_stop()

    # ---------------- 消息派发（主线程） ----------------
    def pump(self, *_):
        drained = 0
        while drained < 60:
            try:
                item = self.core.msg_queue.get_nowait()
            except Exception:
                break
            drained += 1
            try:
                self._dispatch(item)
            except Exception:
                traceback.print_exc()

    def _dispatch(self, item):
        kind = item[0]
        if kind == "log":
            self._append_log(item[2], item[1])
        elif kind == "busy":
            self._set_running(bool(item[1]), item[2] if len(item) > 2 else "")
        elif kind == "status":
            self.status_text = str(item[1])
        elif kind == "alert":
            self._show_alert(item[1], item[2])
        elif kind == "done":
            self._set_running(False, "")
            self._append_log(item[2], "success" if item[1] else "error")
        elif kind == "qr":
            if self._qr_popup is None:
                self._open_qr_popup()
            self._qr_popup.set_image(item[1])
        elif kind == "login":
            ok, msg = item[1], item[2]
            self.login_text = ("已登录" if ok else "未登录") + f" · {msg}"
            if self._qr_popup is not None:
                self._qr_popup.set_status(msg, ok)
                if ok:
                    Clock.schedule_once(
                        lambda *_: self._qr_popup and self._qr_popup.dismiss(), 1.2)
        elif kind == "courses":
            self._fill_courses(item[1])

    def _show_alert(self, title, text):
        """验证码等需要用户操作时弹窗提醒（同时也会留在日志里）"""
        try:
            pop = AlertPopup(title, text)
            pop.bind(on_dismiss=lambda *_: setattr(self, "_alert_popup", None))
            self._alert_popup = pop
            pop.open()
        except Exception:
            traceback.print_exc()

    def _set_running(self, running, task=""):
        self.running = running
        self.run_btn.disabled = running
        self.stop_btn.disabled = not running
        self.login_btn.disabled = running
        self.reuse_btn.disabled = running
        self.speed_input.disabled = running
        if running:
            self.status_text = f"正在执行：{task or '任务'}…"
        else:
            self.status_text = "就绪"

    def _fill_courses(self, items):
        self.course_box.clear_widgets()
        self.course_rows = []
        for it in items:
            row = CourseRow(it)
            self.course_rows.append(row)
            self.course_box.add_widget(row)
        self.course_count = f"我的课程 · 共 {len(items)} 门（勾选要刷的）"

    def _clear_log(self):
        self.log_box.clear_widgets()

    def _append_log(self, text, level="info"):
        color = LEVEL_COLORS.get(str(level).lower(), C_TEXT)
        label = vlabel(text, size=11, color=color, height=dp(18))
        self.log_box.add_widget(label)
        Clock.schedule_once(lambda *_: setattr(self.log_scroll, "scroll_y", 0), 0.03)


# --------------------------------------------------------------------------
# Android 保活：拿唤醒锁
# --------------------------------------------------------------------------
def try_keep_awake():
    """尽量阻止系统在刷课期间休眠

    注意：这不是万能的。国产系统（小米/华为/OPPO 等）仍可能冻结后台应用，
    所以界面里也会提示用户「刷课期间保持屏幕常亮、不要切走太久」。
    """
    try:
        from jnius import autoclass, cast  # 仅在 Android 上存在
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        Context = autoclass("android.content.Context")
        PowerManager = autoclass("android.os.PowerManager")
        pm = cast(PowerManager, activity.getSystemService(Context.POWER_SERVICE))
        flags = PowerManager.SCREEN_DIM_WAKE_LOCK | PowerManager.ON_AFTER_RELEASE
        lock = pm.newWakeLock(flags, "fuckZHS:keeping-awake")
        lock.setReferenceCounted(False)
        lock.acquire()
        return lock
    except Exception as e:
        mc.glog("debug", f"获取唤醒锁失败（桌面运行属正常）：{e}")
        return None


# --------------------------------------------------------------------------
class MobileApp(App):
    def build(self):
        self.title = "fuckZHS"
        self.core = mc.Core()
        missing = self.core.setup()
        view = MainView(self.core)
        if missing:
            view._append_log("缺少依赖：" + ", ".join(missing), "error")
        else:
            view._append_log("界面已就绪。第一步：点「扫码登录」。", "info")
            view._append_log(f"数据目录：{mc.ROOT}", "debug")
            if self.core.has_cookies():
                view.login_text = "已登录 · 有保存的登录状态"
        Clock.schedule_interval(view.pump, 0.15)
        self._wake_lock = try_keep_awake()
        return view

    def on_pause(self):
        # 允许后台运行（Android 会调用；返回 True 表示不要销毁应用）
        return True

    def on_resume(self):
        return True


if __name__ == "__main__":
    MobileApp().run()
