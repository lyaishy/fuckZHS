#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fuckZHS 图形界面 (Tkinter)

独立于 main.py 的界面程序, 不修改任何命令行行为, 也不重新实现协议逻辑,
所有刷课动作都是复用 fucker.Fucker 的原有方法。

启动方式:
    py gui.py            # 或 Windows 上双击 start_gui.bat

新增文件:
    gui.py             本文件
    start_gui.bat      Windows 双击启动器
    gui_settings.json  界面选项的持久化文件 (自动生成, 可删除)
"""

import io
import json
import logging
import os
import queue
import sys
import threading
import time
import traceback

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
    TK_OK = True
except Exception:  # 没有 tkinter 时也要能给出友好提示
    tk = None
    ttk = None
    messagebox = None
    TK_OK = False

def _resolve_root():
    """可写数据目录, 规则与 utils.getDir() 保持一致

    - 源码运行: 本文件所在目录
    - PyInstaller 打包后: exe 所在目录(onefile 的 __file__ 在临时目录, 不能用)
    - exe 目录不可写时退回 %APPDATA%\\fuckZHS
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
        if os.access(base, os.W_OK):
            return base
        fb = os.path.join(
            os.environ.get("APPDATA") or os.path.expanduser("~"), "fuckZHS"
        )
        try:
            os.makedirs(fb, exist_ok=True)
        except OSError:
            pass
        return fb
    return os.path.dirname(os.path.abspath(__file__))


ROOT = _resolve_root()
CONFIG_PATH = os.path.join(ROOT, "config.json")
COOKIES_PATH = os.path.join(ROOT, "cookies.json")
EXEC_LIST = os.path.join(ROOT, "execution.json")
SETTINGS_PATH = os.path.join(ROOT, "gui_settings.json")
AI_COURSES_PATH = os.path.join(ROOT, "ai_courses.json")


def _bundled_dir():
    """随包发布的资源所在目录

    - 源码运行: 本文件所在目录
    - PyInstaller onefile: sys._MEIPASS (临时解压目录, 只读, 仅用于取模板)
    """
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def _seed_config():
    """首次运行时把随包的 config.json 复制到数据目录

    ROOT 和"随包资源目录"在 exe 下是两个地方, 所以 config.json 不会自己出现。
    只处理 config.json, 且**绝不覆盖**已存在的文件（用户改过的配置不能被冲掉）。
    """
    try:
        if os.path.isfile(CONFIG_PATH):
            return
        # 仓库里 config.json 被 .gitignore 排除（可能含账号密码），
        # 随包发布的是干净模板 config.example.json，优先用它兜底。
        base = _bundled_dir()
        src = os.path.join(base, "config.json")
        if not os.path.isfile(src):
            src = os.path.join(base, "config.example.json")
        if not os.path.isfile(src) or os.path.abspath(src) == os.path.abspath(CONFIG_PATH):
            return
        os.makedirs(ROOT, exist_ok=True)
        with open(src, "rb") as fi, open(CONFIG_PATH, "wb") as fo:
            fo.write(fi.read())
    except Exception:
        pass


_seed_config()

DEFAULT_SETTINGS = {
    "speed": "",
    "limit": 0,
    "threshold": "",
    "tree_view": True,
    "progressbar_view": True,
    "proxy": "",
    "debug": False,
    "verbose": True,
    "ai_use_zhidao": True,
    "ai_no_exam": False,
    "ai_stream": True,
    "ai_api_base": "https://api.openai.com",
    "ai_api_key": "",
    "ai_model": "gpt-4o-mini",
    "last_ai_course": "",
    "last_ai_class": "",
}

# 由 check_env() 填充
Fucker = None
fucker_module = None
logger = None
ObjDict = None
cookie_jar_to_list = None

# 详细日志开关: True 时每次网络请求都打到 INFO, 否则降到 DEBUG
VERBOSE = True

# 项目 logger 只认 debug/info/warning/error/critical, 这里做一次映射
# SUCCESS 走 INFO, 但加一个 "✓ " 前缀, 由 GuiLogHandler 识别成绿色
_LEVEL_MAP = {
    "success": "info",
    "warn": "warning",
    "fatal": "critical",
    "trace": "debug",
}


# --------------------------------------------------------------------------
# 统一日志出口
# 走项目自带的 logger, 于是同一条日志会同时出现在:
#   界面日志区(GuiLogHandler) + logs/info.log + logs/error.log ...
# --------------------------------------------------------------------------
def glog(level, msg, verbose=False):
    """写一条日志。`verbose=True` 表示"细节日志", 由 VERBOSE 开关决定降级与否"""
    try:
        lv = str(level).lower()
        if verbose and not VERBOSE:
            lv = "debug"
        if lv == "success":
            lv = "info"
            # 用 "√"（U+221A）而不是 "✓"（U+2713）：CJK 字体普遍没有后者
            msg = "√ " + str(msg)
        lv = _LEVEL_MAP.get(lv, lv)
        fn = getattr(logger, lv, None) if logger is not None else None
        if callable(fn):
            fn(msg)
    except Exception:
        pass


_SENSITIVE = ("password", "passwd", "pwd", "token", "secret", "key", "cookie")


def _shortUrl(url, limit=96):
    """日志里的 URL 只保留接口路径, 去掉查询串"""
    u = str(url or "").split("?")[0]
    return u if len(u) <= limit else u[:limit] + "…"


def _fmtArgs(args, kwargs, limit=140):
    """把调用参数压成一行日志, 顺手屏蔽敏感字段"""
    parts = []
    for a in args:
        parts.append(repr(a)[:60])
    for k, v in (kwargs or {}).items():
        if any(s in str(k).lower() for s in _SENSITIVE):
            v = "***"
        parts.append(f"{k}={repr(v)[:60]}")
    s = ", ".join(parts)
    return f"({s})" if len(s) <= limit else f"({s[:limit]}…)"



# --------------------------------------------------------------------------
# 环境检查
# --------------------------------------------------------------------------
def check_env():
    """导入并检查运行依赖, 返回缺失项列表 (空列表表示一切正常)"""
    global Fucker, fucker_module, logger, ObjDict, cookie_jar_to_list
    missing = []
    for mod, pkg in (("requests", "requests"),
                     ("Crypto", "pycryptodome"),
                     ("PIL", "Pillow"),
                     ("tiktoken", "tiktoken"),
                     ("openai", "openai")):
        try:
            __import__(mod)
        except Exception:
            missing.append(pkg)
    if missing:
        return missing
    try:
        # ImageTk 单独检查: PIL 装了但没编 Tk 支持时, 二维码会渲染不出来
        from PIL import ImageTk  # noqa: F401
    except Exception as e:
        return [f"PIL.ImageTk 不可用（二维码无法显示）: {e}"]
    try:
        import fucker as _fucker
        from ObjDict import ObjDict as _ObjDict
        from logger import logger as _logger
        from utils import cookie_jar_to_list as _c2l
    except Exception as e:
        return [f"项目模块导入失败: {e}"]
    fucker_module = _fucker
    Fucker = _fucker.Fucker
    ObjDict = _ObjDict
    logger = _logger
    cookie_jar_to_list = _c2l
    return []


# --------------------------------------------------------------------------
# 停止机制
# 不改动 fucker.py, 通过子类 + 模块级钩子实现"点了停止就能停下来"
# --------------------------------------------------------------------------
class StopRequested(BaseException):
    """用户点击停止时抛出

    故意继承 BaseException 而不是 Exception: fucker.py 内部大量使用
    `except Exception` 来跳过失败条目, 继承 Exception 会被这些处理器吞掉。
    """


def make_gui_fucker_class(fucker_cls):
    def _exc(name):
        """延迟解析 fucker 模块里的异常类; 取不到时返回空元组(等价于不捕获)"""
        try:
            return getattr(fucker_module, name)
        except Exception:
            return ()

    class GuiFucker(fucker_cls):
        def __init__(self, *args, stop_event=None, **kwargs):
            super().__init__(*args, **kwargs)
            self._stop_event = stop_event
            # 上一次运行被中断的原因: None / "captcha" / "time_limit"
            #
            # 为什么需要它: 服务端返回 code=-12 时 fucker.py 的 zhidaoQuery 会抛
            # CaptchaException, 但 fuckZhidaoCourse 内部就把它吞掉了(只是 return),
            # 外层拿不到任何异常 —— 于是界面上会把"被验证码打断"显示成"课程完成"。
            # 这里在最底层的 zhidaoQuery 记一笔, 让界面能如实汇报。
            self.last_abort = None
            self._patch_session()

        # ---------------- 停止 ----------------
        def _raise_if_stopped(self):
            if self._stop_event is not None and self._stop_event.is_set():
                raise StopRequested()

        # ---------------- 中断原因记录 ----------------
        def zhidaoQuery(self, *args, **kwargs):
            try:
                return super().zhidaoQuery(*args, **kwargs)
            except _exc("CaptchaException"):
                self.last_abort = "captcha"
                raise

        def _patch_session(self):
            """给 session 的每个 HTTP 动作挂上停止检查

            `_qrlogin` 的轮询是直接调 `self.session.get`, 不走 `_apiQuery`,
            只在 `_apiQuery` 上挂钩子的话, 二维码窗口关了以后这个循环还会
            一直转下去。这里直接包住 session 的方法, 让取消能在 0.5 秒内生效。
            """
            session = self.session
            for name in ("request", "get", "post", "put", "delete", "head", "options"):
                orig = getattr(session, name, None)
                if not callable(orig):
                    continue

                def make(o, n):
                    def wrapper(*a, **kw):
                        self._raise_if_stopped()
                        return o(*a, **kw)
                    wrapper.__name__ = n
                    return wrapper

                try:
                    setattr(session, name, make(orig, name))
                except Exception:
                    pass

        # ---------------- 日志 ----------------
        def _apiQuery(self, *args, **kwargs):
            self._raise_if_stopped()
            url = args[0] if args else kwargs.get("url", "")
            method = str(kwargs.get("method", "POST")).upper()
            t0 = time.time()
            try:
                ret = super()._apiQuery(*args, **kwargs)
            except StopRequested:
                raise
            except BaseException as e:
                glog("warning", f"[请求] {method} {_shortUrl(url)} 失败"
                                 f"（{time.time() - t0:.2f}s）：{type(e).__name__}: {e}")
                raise
            code = None
            for attr in ("code", "status"):
                try:
                    code = getattr(ret, attr)
                    break
                except Exception:
                    continue
            glog("info", f"[请求] {method} {_shortUrl(url)} -> code={code}"
                         f"，用时 {time.time() - t0:.2f}s", verbose=True)
            return ret

        def _checkTimeLimit(self, cid):
            self._raise_if_stopped()
            try:
                return super()._checkTimeLimit(cid)
            except _exc("TimeLimitExceeded"):
                self.last_abort = "time_limit"
                raise

    # 顺手给几个高层动作加上"开始/结束/耗时"日志
    for _name in ("login", "getZhidaoList", "getHikeList", "getZhidaoAiList",
                  "fuckCourse", "fuckVideo", "fuckAiCourse", "fuckWhatever"):
        _orig = getattr(GuiFucker, _name, None)
        if not callable(_orig):
            continue

        def _make(o, n):
            def wrapper(self, *a, **kw):
                glog("info", f"[执行] {n} 开始 {_fmtArgs(a, kw)}")
                t0 = time.time()
                try:
                    ret = o(self, *a, **kw)
                except StopRequested:
                    glog("warning", f"[执行] {n} 已中止（{time.time() - t0:.2f}s）")
                    raise
                except BaseException as e:
                    glog("error", f"[执行] {n} 出错（{time.time() - t0:.2f}s）："
                                  f"{type(e).__name__}: {e}")
                    raise
                glog("info", f"[执行] {n} 结束，用时 {time.time() - t0:.2f}s")
                return ret

            wrapper.__name__ = n
            return wrapper

        setattr(GuiFucker, _name, _make(_orig, _name))

    GuiFucker.__name__ = "GuiFucker"
    return GuiFucker


_patch_lock = threading.Lock()
_pb_original = None
_exam_ctx_original = None
_live_exam_ctxs = []


def install_hooks(stop_event):
    """安装停止钩子
    ① progressBar 每秒会被调用一次, 拿它当 tick 检查点
    ② 登记 AI 考试的 ExamCtx, 停止时要把它的心跳线程关掉
    """
    global _pb_original, _exam_ctx_original
    with _patch_lock:
        if _pb_original is None:
            _pb_original = fucker_module.progressBar

            def _progressBar(*a, **kw):
                if stop_event.is_set():
                    raise StopRequested()
                return _pb_original(*a, **kw)

            fucker_module.progressBar = _progressBar

        if _exam_ctx_original is None:
            _exam_ctx_original = fucker_module.ExamCtx

            class _TrackedExamCtx(_exam_ctx_original):
                def __init__(self, *a, **kw):
                    super().__init__(*a, **kw)
                    _live_exam_ctxs.append(self)

            _TrackedExamCtx.__name__ = "ExamCtx"
            fucker_module.ExamCtx = _TrackedExamCtx


def stop_live_exam_threads():
    """停止时让 exam 心跳线程退出, 否则它会一直往服务器发请求"""
    for ctx in list(_live_exam_ctxs):
        try:
            ctx.examStopped = True
        except Exception:
            pass
    _live_exam_ctxs.clear()


# --------------------------------------------------------------------------
# stdout / 日志  ->  界面
# --------------------------------------------------------------------------
class QueueWriter(io.TextIOBase):
    """把 print 输出按行/按回车切分后推给界面

    * `\\n` 结尾 -> ("nl", 文本)  追加到日志区
    * `\\r` 结尾 -> ("cr", 文本)  刷新底部单行状态 (进度条就是靠这个)
    """

    def __init__(self, q):
        self.q = q
        self.buf = ""

    def write(self, s):
        if not isinstance(s, str):
            s = str(s)
        self.buf += s
        while True:
            i_n = self.buf.find("\n")
            i_r = self.buf.find("\r")
            if i_n < 0 and i_r < 0:
                break
            if i_r >= 0 and (i_n < 0 or i_r < i_n):
                seg, self.buf = self.buf[:i_r], self.buf[i_r + 1:]
                self.q.put(("cr", seg))
            else:
                seg, self.buf = self.buf[:i_n], self.buf[i_n + 1:]
                self.q.put(("nl", seg))
        if len(self.buf) > 8192:
            self.q.put(("nl", self.buf))
            self.buf = ""
        return len(s)

    def flush(self):
        pass

    def writable(self):
        return True


class GuiLogHandler(logging.Handler):
    def __init__(self, q):
        super().__init__()
        self.q = q
        self._fmt = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s",
                                      datefmt="%H:%M:%S")

    def emit(self, record):
        try:
            msg = self._fmt.format(record)
        except Exception:
            msg = str(record.msg)
        level = record.levelname
        try:  # glog("success", ...) 会加 "√ " 前缀, 这里还原成绿色级别
            if str(record.msg).startswith("√"):
                level = "SUCCESS"
        except Exception:
            pass
        self.q.put(("log", level, msg))


class GuiFileHandler(logging.FileHandler):
    """把界面 + 脚本的日志按时间顺序合并写到一个文件

    项目自带的 logger 把不同级别拆到 info.log / warning.log / error.log,
    排查问题时一路跟读很别扭, 这里额外落一份 logs/gui.log。
    """

    def __init__(self):
        os.makedirs(os.path.join(ROOT, "logs"), exist_ok=True)
        super().__init__(os.path.join(ROOT, "logs", "gui.log"),
                         mode="w", encoding="utf-8")
        self.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s"))


# --------------------------------------------------------------------------
# 扫码登录窗口
# --------------------------------------------------------------------------
class QrWindow:
    """扫码登录窗口

    两个坑都在这里:
    * 图片标签不能带 `width/height` 的字符单位 —— 一旦 `configure(image=...)`,
      Tk 会把那两个数字当成**像素**, 280x280 的二维码会被裁成 44x20, 等于看不见。
      所以这里建标签时不设尺寸, 显示图片时用自然尺寸。
    * 关闭窗口必须回调 `on_close`。旧实现只 destroy 窗口, App 那边 `busy` 永远
      是 True、`qr_window` 还指着已销毁的窗口, 于是"再点扫码登录没反应"。
    """

    IMG_SIZE = 260
    WIN_W, WIN_H = 360, 470

    def __init__(self, master, on_close=None):
        self.on_close = on_close
        self._closed = False
        self._photo = None

        self.win = tk.Toplevel(master)
        self.win.title("扫码登录")
        self.win.resizable(False, False)
        self.win.transient(master)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.win.bind("<Escape>", lambda e: self.close())

        wrap = ttk.Frame(self.win, padding=14)
        wrap.pack(fill="both", expand=True)

        # 注意: 这里不传 width/height, 让标签自己按内容(文字或图片)定尺寸
        self.img_label = tk.Label(wrap, text="正在获取二维码…", height=12,
                                  background="#FFFFFF", foreground="#5F5E5A",
                                  relief="solid", borderwidth=1)
        self.img_label.pack(fill="both", expand=True)

        self.status = tk.Label(wrap, text="正在连接智慧树服务器…", fg="#185FA5",
                               wraplength=320, justify="center")
        self.status.pack(fill="x", pady=(8, 2))

        tk.Label(wrap, text="请用「知到」App 扫码；关闭本窗口 = 取消登录",
                 fg="#888780", justify="center").pack(fill="x", pady=(2, 6))

        ttk.Button(wrap, text="取消登录", command=self.close).pack(side="right")

        self._placeOver(master)

    # ---------------- 窗口摆放 ----------------
    def _placeOver(self, master):
        """居中到主窗口上方, 并短暂置顶, 避免二维码窗口被主窗口盖住看不见"""
        try:
            try:
                mx, my = master.winfo_rootx(), master.winfo_rooty()
                mw, mh = master.winfo_width(), master.winfo_height()
            except Exception:
                mx = my = mw = mh = 0
            x = max(mx + (mw - self.WIN_W) // 2, 0)
            y = max(my + (mh - self.WIN_H) // 3, 0)
            self.win.geometry(f"{self.WIN_W}x{self.WIN_H}+{x}+{y}")
            self.win.lift()
            self.win.focus_force()
            self.win.attributes("-topmost", True)
            self.win.after(1200, self._dropTopmost)
        except Exception as e:
            glog("debug", f"[登录] 窗口定位失败(不影响使用): {e}")

    def _dropTopmost(self):
        try:
            self.win.attributes("-topmost", False)
        except Exception:
            pass

    # ---------------- 内容 ----------------
    def set_image(self, data):
        try:
            from PIL import Image, ImageTk
            img = Image.open(io.BytesIO(bytes(data)))
            size = (self.IMG_SIZE, self.IMG_SIZE)
            try:
                img = img.resize(size, Image.LANCZOS)
            except Exception:
                img = img.resize(size)
            self._photo = ImageTk.PhotoImage(img)
            # 用像素尺寸显示, 不继承字符单位
            self.img_label.configure(image=self._photo, text="",
                                     width=self.IMG_SIZE, height=self.IMG_SIZE,
                                     relief="flat")
            glog("info", f"[登录] 二维码已显示（{len(data)} 字节，"
                         f"{self.IMG_SIZE}x{self.IMG_SIZE}）")
            return True
        except Exception as e:
            glog("error", f"[登录] 二维码渲染失败: {type(e).__name__}: {e}")
            self.set_status(f"二维码渲染失败：{e}", False)
            try:
                self.img_label.configure(
                    image="", text="二维码显示失败\n详见下方提示与运行日志")
            except Exception:
                pass
            return False

    def set_status(self, text, ok=None):
        color = "#5F5E5A"
        if ok is True:
            color = "#0F6E56"
        elif ok is False:
            color = "#A32D2D"
        try:
            self.status.configure(text=text, fg=color)
        except Exception:
            pass

    def close(self):
        """幂等关闭; 只在第一次真正关闭时回调 on_close"""
        if self._closed:
            return
        self._closed = True
        try:
            self.win.destroy()
        except Exception:
            pass
        try:
            if callable(self.on_close):
                self.on_close()
        except Exception as e:
            glog("error", f"[登录] 关闭回调出错: {type(e).__name__}: {e}")


# --------------------------------------------------------------------------
# 主窗口
# --------------------------------------------------------------------------
class App:
    def __init__(self):
        global VERBOSE
        self.root = tk.Tk()
        self.root.title("fuckZHS 图形界面")
        self.root.geometry("1040x800")
        self.root.minsize(920, 680)
        try:
            self.root.option_add("*Font", ("Microsoft YaHei UI", 9))
        except Exception:
            pass

        self.q = queue.Queue()
        self.stop_event = threading.Event()
        self.busy = False
        self.course_ids = []
        self.log_lines = 0
        self.qr_window = None
        self.ai_scan_items = []
        self._task = None          # 当前正在运行的任务名 (login/fetch/run/ai/load)
        self._login_gen = 0        # 扫码登录的代次, 用来作废过期消息
        self._login_ev = None      # 当前这次登录尝试的取消事件

        self.settings = self._load_settings()
        VERBOSE = bool(self.settings.get("verbose", True))
        self.GuiFucker = make_gui_fucker_class(Fucker)
        install_hooks(self.stop_event)

        self._build_ui()
        self._install_io()
        self._apply_settings()
        self._act("界面已就绪")
        self._act(f"日志目录：{os.path.join(ROOT, 'logs')}"
                  f"（gui.log 为合并日志；info/warning/error/debug.log 按级别拆分）")
        self._act("第一步：点击「扫码登录」（也可直接点「加载已保存的登录状态」）")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._pump)

    # ---------------- 设置持久化 ----------------
    def _load_settings(self):
        data = dict(DEFAULT_SETTINGS)
        try:
            if os.path.isfile(SETTINGS_PATH):
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    data.update(json.load(f) or {})
        except Exception:
            pass
        return data

    def _save_settings(self):
        for key, var in self.vars.items():
            try:
                self.settings[key] = var.get()
            except Exception:
                pass
        try:  # 记住上次填的 AI 课程/班级, 省得每次重填
            self.settings["last_ai_course"] = self.ai_course_var.get()
            self.settings["last_ai_class"] = self.ai_class_var.get()
        except Exception:
            pass
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._log(f"保存界面设置失败: {e}", "WARNING")

    # ---------------- 界面搭建 ----------------
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        ttk.Label(top, text="登录状态：").pack(side="left")
        self.login_var = tk.StringVar(value="未登录")
        self.login_label = tk.Label(top, textvariable=self.login_var, fg="#A32D2D")
        self.login_label.pack(side="left")
        ttk.Button(top, text="扫码登录",
                   command=self._safe("扫码登录", self.on_login)).pack(side="left", padx=(16, 6))
        ttk.Button(top, text="加载已保存的登录状态",
                   command=self._safe("加载已保存的登录状态",
                                      self.on_load_cookies)).pack(side="left", padx=6)
        ttk.Button(top, text="获取课程列表",
                   command=self._safe("获取课程列表", self.on_fetch)).pack(side="left", padx=6)

        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, **pad)
        self.nb = nb

        self._build_course_tab(nb)
        self._build_ai_tab(nb)

        ctrl = ttk.Frame(self.root)
        ctrl.pack(fill="x", **pad)
        self.run_btn = ttk.Button(ctrl, text="开始刷课",
                                  command=self._safe("开始刷课", self.on_run))
        self.run_btn.pack(side="left")
        self.stop_btn = ttk.Button(ctrl, text="停止", state="disabled",
                                   command=self._safe("停止", self.on_stop))
        self.stop_btn.pack(side="left", padx=6)
        ttk.Button(ctrl, text="清空日志",
                   command=self._safe("清空日志", self._clear_log)).pack(side="left", padx=6)
        ttk.Button(ctrl, text="导出日志",
                   command=self._safe("导出日志", self._export_log)).pack(side="left", padx=6)

        self.verbose_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctrl, text="详细日志（每次网络请求）",
                        variable=self.verbose_var,
                        command=self.on_toggle_verbose).pack(side="left", padx=(16, 6))
        self.debug_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(ctrl, text="调试日志（含账号密码，勿外传）",
                        variable=self.debug_var,
                        command=self.on_toggle_debug).pack(side="left", padx=6)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var, foreground="#185FA5",
                  anchor="w").pack(fill="x", padx=8)

        log_frame = ttk.LabelFrame(self.root, text="运行日志")
        log_frame.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self.log = tk.Text(log_frame, height=16, wrap="none", state="disabled",
                           background="#FCFCFC", foreground="#2C2C2A",
                           borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        hsb = ttk.Scrollbar(log_frame, orient="horizontal", command=self.log.xview)
        self.log.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log.tag_config("ERROR", foreground="#A32D2D")
        self.log.tag_config("CRITICAL", foreground="#A32D2D", underline=True)
        self.log.tag_config("WARNING", foreground="#854F0B")
        self.log.tag_config("SUCCESS", foreground="#0F6E56")
        self.log.tag_config("INFO", foreground="#2C2C2A")
        self.log.tag_config("DEBUG", foreground="#888780")

        self.vars = {
            "speed": self.speed_var,
            "limit": self.limit_var,
            "threshold": self.threshold_var,
            "tree_view": self.tree_view_var,
            "progressbar_view": self.progressbar_view_var,
            "proxy": self.proxy_var,
            "debug": self.debug_var,
            "verbose": self.verbose_var,
            "ai_use_zhidao": self.ai_use_zhidao_var,
            "ai_no_exam": self.ai_no_exam_var,
            "ai_stream": self.ai_stream_var,
            "ai_api_base": self.ai_api_base_var,
            "ai_api_key": self.ai_api_key_var,
            "ai_model": self.ai_model_var,
        }

    def _build_course_tab(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="  普通课程  ")

        left = ttk.Frame(outer)
        left.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)

        ttk.Label(left, text="课程列表（不勾选 = 刷全部课程）",
                  foreground="#5F5E5A").pack(anchor="w")
        box = ttk.Frame(left)
        box.pack(fill="both", expand=True)
        self.course_list = tk.Listbox(box, selectmode="extended", activestyle="none",
                                      exportselection=False)
        sb = ttk.Scrollbar(box, orient="vertical", command=self.course_list.yview)
        self.course_list.configure(yscrollcommand=sb.set)
        self.course_list.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=(4, 0))
        ttk.Button(btns, text="全选",
                   command=self._safe("全选", lambda: self.course_list.select_set(0, "end"))
                   ).pack(side="left")
        ttk.Button(btns, text="全不选",
                   command=self._safe("全不选", lambda: self.course_list.select_clear(0, "end"))
                   ).pack(side="left", padx=6)
        ttk.Button(btns, text="反选",
                   command=self._safe("反选", self._invert_selection)).pack(side="left")

        right = ttk.LabelFrame(outer, text="运行选项")
        right.pack(side="right", fill="y", padx=(4, 8), pady=8)

        self.speed_var = tk.StringVar()
        self.limit_var = tk.StringVar()
        self.threshold_var = tk.StringVar()
        self.proxy_var = tk.StringVar()
        self.tree_view_var = tk.BooleanVar(value=True)
        self.progressbar_view_var = tk.BooleanVar(value=True)

        rows = (
            ("播放速度", self.speed_var, "留空 = 网站最大值（1.25 / 1.5）；可手动填任意数值，如 400"),
            ("单课时限（分钟）", self.limit_var, "0 = 不限"),
            ("完成阈值", self.threshold_var, "留空 = 0.91"),
            ("代理", self.proxy_var, "留空 = 系统代理"),
        )
        r = 0
        for label, var, hint in rows:
            ttk.Label(right, text=label).grid(row=r, column=0, sticky="w", padx=10, pady=(10, 0))
            ttk.Entry(right, textvariable=var, width=30).grid(
                row=r + 1, column=0, sticky="we", padx=10)
            ttk.Label(right, text=hint, foreground="#888780").grid(
                row=r + 2, column=0, sticky="w", padx=10)
            r += 3

        ttk.Checkbutton(right, text="显示课程目录",
                        variable=self.tree_view_var).grid(
            row=r, column=0, sticky="w", padx=10, pady=(14, 0))
        ttk.Checkbutton(right, text="显示进度条",
                        variable=self.progressbar_view_var).grid(
            row=r + 1, column=0, sticky="w", padx=10, pady=(4, 0))

        ttk.Separator(right, orient="horizontal").grid(
            row=r + 2, column=0, sticky="we", padx=10, pady=10)
        ttk.Label(right, text="存在 cookies.json 时会自动复用登录状态，\n"
                              "过期了再重新扫码即可。",
                  foreground="#888780", justify="left").grid(
            row=r + 3, column=0, sticky="w", padx=10, pady=(0, 10))

    def _build_ai_tab(self, nb):
        outer = ttk.Frame(nb)
        nb.add(outer, text="  AI 课程  ")

        form = ttk.LabelFrame(outer, text="AI 课程参数")
        form.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)
        form.columnconfigure(1, weight=1)

        self.ai_course_var = tk.StringVar()
        self.ai_class_var = tk.StringVar()
        self.ai_use_zhidao_var = tk.BooleanVar(value=True)
        self.ai_no_exam_var = tk.BooleanVar(value=False)
        self.ai_stream_var = tk.BooleanVar(value=True)
        self.ai_api_base_var = tk.StringVar()
        self.ai_api_key_var = tk.StringVar()
        self.ai_model_var = tk.StringVar()

        ttk.Label(form, text="课程 ID").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(form, textvariable=self.ai_course_var, width=34).grid(
            row=0, column=1, sticky="we", padx=8, pady=6)
        ttk.Label(form, text="班级 ID").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ttk.Entry(form, textvariable=self.ai_class_var, width=34).grid(
            row=1, column=1, sticky="we", padx=8, pady=6)

        ttk.Button(form, text="查询我参加的 AI 课程",
                   command=self._safe("查询 AI 课程", self.on_ai_list)).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 6))

        self.ai_list = tk.Listbox(form, height=6, activestyle="none", exportselection=False)
        self.ai_list.grid(row=3, column=0, columnspan=2, sticky="we", padx=8, pady=(0, 6))
        self.ai_list.bind("<<ListboxSelect>>", self._on_ai_pick)

        ttk.Checkbutton(form, text="跳过考试（只刷课程内容）",
                        variable=self.ai_no_exam_var).grid(
            row=4, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))

        ai_box = ttk.LabelFrame(outer, text="答题用 AI")
        ai_box.pack(side="right", fill="both", expand=True, padx=(4, 8), pady=8)

        ttk.Checkbutton(ai_box, text="使用智慧树自带 AI（推荐，无需密钥）",
                        variable=self.ai_use_zhidao_var,
                        command=self._toggle_ai_fields).pack(anchor="w", padx=10, pady=(10, 4))

        self.ai_openai_widgets = []
        for label, var in (("接口地址", self.ai_api_base_var),
                           ("API Key", self.ai_api_key_var),
                           ("模型名", self.ai_model_var)):
            f = ttk.Frame(ai_box)
            f.pack(fill="x", padx=10, pady=3)
            ttk.Label(f, text=label, width=8).pack(side="left")
            e = ttk.Entry(f, textvariable=var)
            e.pack(side="left", fill="x", expand=True)
            self.ai_openai_widgets.append(e)

        ttk.Checkbutton(ai_box, text="流式返回", variable=self.ai_stream_var).pack(
            anchor="w", padx=10, pady=(10, 4))
        ttk.Label(ai_box, text="取消上一项勾选后，才会使用这里填写的第三方接口。\n"
                               "答案会缓存在 aiexamAnswer/ 目录，下次直接命中。",
                  foreground="#888780", justify="left").pack(anchor="w", padx=10, pady=(8, 10))

        self._toggle_ai_fields()

    def _toggle_ai_fields(self):
        state = "disabled" if self.ai_use_zhidao_var.get() else "normal"
        for w in self.ai_openai_widgets:
            w.configure(state=state)

    def _invert_selection(self):
        selected = set(self.course_list.curselection())
        for i in range(self.course_list.size()):
            if i in selected:
                self.course_list.select_clear(i)
            else:
                self.course_list.select_set(i)

    def _apply_settings(self):
        global VERBOSE
        s = self.settings
        self.speed_var.set(str(s.get("speed", "") or ""))
        self.limit_var.set(str(s.get("limit", 0) or 0))
        self.threshold_var.set(str(s.get("threshold", "") or ""))
        self.proxy_var.set(str(s.get("proxy", "") or ""))
        self.tree_view_var.set(bool(s.get("tree_view", True)))
        self.progressbar_view_var.set(bool(s.get("progressbar_view", True)))
        self.debug_var.set(bool(s.get("debug", False)))
        self.verbose_var.set(bool(s.get("verbose", True)))
        VERBOSE = bool(self.verbose_var.get())
        self.ai_use_zhidao_var.set(bool(s.get("ai_use_zhidao", True)))
        self.ai_no_exam_var.set(bool(s.get("ai_no_exam", False)))
        self.ai_stream_var.set(bool(s.get("ai_stream", True)))
        self.ai_api_base_var.set(str(s.get("ai_api_base", "")))
        self.ai_api_key_var.set(str(s.get("ai_api_key", "")))
        self.ai_model_var.set(str(s.get("ai_model", "gpt-4o-mini")))
        self.ai_course_var.set(str(s.get("last_ai_course", "") or ""))
        self.ai_class_var.set(str(s.get("last_ai_class", "") or ""))
        self._toggle_ai_fields()
        logger.setLevel("DEBUG" if self.debug_var.get() else "INFO")

    # ---------------- IO 接管 ----------------
    def _install_io(self):
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        sys.stdout = QueueWriter(self.q)
        sys.stderr = QueueWriter(self.q)
        self._handler = GuiLogHandler(self.q)
        logger.addHandler(self._handler)
        try:  # 合并日志文件: 界面操作 + 脚本运行 + 网络请求 全在一个文件里
            self._file_handler = GuiFileHandler()
            logger.addHandler(self._file_handler)
        except Exception as e:
            self._file_handler = None
            print(f"*无法创建 logs/gui.log: {e}")
        logger.setLevel("DEBUG" if self.debug_var.get() else "INFO")

    def _uninstall_io(self):
        for h in (getattr(self, "_handler", None), getattr(self, "_file_handler", None)):
            try:
                if h is not None:
                    logger.removeHandler(h)
            except Exception:
                pass
        try:
            if getattr(self, "_file_handler", None) is not None:
                self._file_handler.close()
        except Exception:
            pass
        try:
            sys.stdout = self._old_stdout
            sys.stderr = self._old_stderr
        except Exception:
            pass

    # ---------------- 日志开关 ----------------
    def on_toggle_debug(self):
        logger.setLevel("DEBUG" if self.debug_var.get() else "INFO")
        self._act(f"调试日志：{'开启（账号密码等敏感信息会写入 logs/，请勿分享）' if self.debug_var.get() else '关闭'}",
                  "WARNING" if self.debug_var.get() else "INFO")

    def on_toggle_verbose(self):
        global VERBOSE
        VERBOSE = bool(self.verbose_var.get())
        self._act(f"详细日志（每次网络请求）：{'开启' if VERBOSE else '关闭'}")

    def _export_log(self):
        """把当前日志区的内容另存一份, 方便排查问题时发出来"""
        try:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            out = os.path.join(ROOT, "logs", f"gui-{stamp}.log")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            text = self.log.get("1.0", "end")
            with open(out, "w", encoding="utf-8") as f:
                f.write(text)
            self._act(f"日志已导出：{out}", "SUCCESS")
            try:
                messagebox.showinfo("导出日志", f"已保存到：\n{out}")
            except Exception:
                pass
        except Exception as e:
            logger.exception(e)
            self._act(f"导出日志失败：{e}", "ERROR")

    # ---------------- 操作日志 ----------------
    def _act(self, msg, level="INFO"):
        """记录一次用户操作或关键步骤: 同时进界面日志区和 logs/*.log"""
        glog(level, f"[界面] {msg}")
        if level in ("WARNING", "ERROR"):
            try:
                self.q.put(("cr", str(msg)[:200]))
            except Exception:
                pass

    def _safe(self, name, fn):
        """按钮回调的统一外壳: 记录点击 + 兜住所有异常

        旧代码里任何一个回调抛异常都会让 busy 卡住 True, 之后所有按钮
        都"没反应"。这里保证异常一定被记录并弹出提示。
        """
        def wrapper(*a, **k):
            self._act(f"点击「{name}」")
            try:
                return fn(*a, **k)
            except BaseException as e:
                logger.exception(e)
                self._act(f"「{name}」发生异常：{type(e).__name__}: {e}", "ERROR")
                glog("debug", traceback.format_exc())
                try:
                    messagebox.showerror(name, f"{type(e).__name__}: {e}\n\n详情见运行日志。")
                except Exception:
                    pass
        return wrapper

    # ---------------- 队列泵 ----------------
    def _pump(self):
        try:
            while True:
                item = self.q.get_nowait()
                kind = item[0]
                try:
                    if kind == "nl":
                        self._append(self._stamp(item[1]))
                    elif kind == "cr":
                        self.status_var.set(item[1].strip()[:220] or "就绪")
                    elif kind == "log":
                        self._append(item[2], item[1])
                    elif kind == "login_msg":
                        # 带"代次"的登录消息: 不是当前这次尝试的一律丢弃,
                        # 避免用户取消后旧线程的消息污染界面状态
                        if item[1] == self._login_gen:
                            self._on_login_msg(item[2])
                    elif kind == "login":
                        self._set_login(item[1], item[2])
                    elif kind == "courses":
                        self._fill_courses(item[1])
                    elif kind == "ai_courses":
                        self._fill_ai_courses(item[1])
                    elif kind == "alert":
                        # 后台线程发来的重点提醒（如"被验证码拦住"）在主线程弹窗，
                        # 因为 messagebox 只能在主线程调用
                        try:
                            messagebox.showwarning(item[1], item[2])
                        except Exception:
                            pass
                    elif kind == "done":
                        self._finish(item[1], item[2])
                except Exception as e:
                    self._append(f"[界面] 处理消息 {kind} 时出错: {e}", "ERROR")
                    glog("debug", traceback.format_exc())
        except queue.Empty:
            pass
        except Exception as e:
            try:
                self._append(f"[界面] 界面内部错误: {e}", "ERROR")
            except Exception:
                pass
        try:
            self.root.after(100, self._pump)
        except Exception:
            pass

    def _on_login_msg(self, item):
        """处理扫码登录线程发来的消息 (qr / qr_status / qr_done)"""
        kind = item[0]
        if kind == "qr":
            if self.qr_window is not None:
                self.qr_window.set_image(item[1])
                self.qr_window.set_status("等待扫码…（二维码过期会自动刷新）")
        elif kind == "qr_status":
            if self.qr_window is not None:
                self.qr_window.set_status(item[1], item[2])
        elif kind == "qr_done":
            if self.qr_window is not None:
                self.qr_window.set_status(item[2], item[1])
            self._set_login(item[1], item[2])
            self._set_busy(False)
            if item[1] and self.qr_window is not None:
                win = self.qr_window
                self.qr_window = None
                self._login_gen += 1   # 让这次的 close 回调不再被当成"取消"
                win.close()

    @staticmethod
    def _stamp(text):
        """给 print 出来的普通行补时间戳

        树形图/进度那种以空格或制表符开头的缩进行不加, 免得看不清结构。
        """
        s = "" if text is None else str(text)
        if not s or s[:1] in (" ", "\t", "|", "+", "\\", "-"):
            return s
        return f"{time.strftime('%H:%M:%S')}  {s}"

    def _append(self, text, level="INFO"):
        if text is None or text == "":
            return
        try:
            self.log.configure(state="normal")
            self.log.insert("end", str(text).rstrip("\n") + "\n", level)
            self.log_lines += 1
            if self.log_lines > 4000:
                self.log.delete("1.0", "1000.0")
                self.log_lines -= 999
            self.log.see("end")
            self.log.configure(state="disabled")
        except Exception:
            pass

    def _log(self, text, level="INFO"):
        """兼容旧调用点: 统一走 logger, 保证同一条消息既进界面也进 logs/"""
        glog(level, f"[界面] {text}")

    def _clear_log(self):
        try:
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.configure(state="disabled")
            self.log_lines = 0
        except Exception:
            pass

    # ---------------- 界面状态 ----------------
    def _set_busy(self, busy, stoppable=True):
        self.busy = busy
        try:
            self.run_btn.configure(state="disabled" if busy else "normal")
            self.stop_btn.configure(state="normal" if (busy and stoppable) else "disabled")
        except Exception:
            pass
        if not busy:
            self._task = None

    def _set_login(self, ok, msg):
        if ok:
            self.login_var.set("已登录")
            try:
                self.login_label.configure(fg="#0F6E56")
            except Exception:
                pass
        else:
            self.login_var.set("未登录")
            try:
                self.login_label.configure(fg="#A32D2D")
            except Exception:
                pass
        self._log(msg, "SUCCESS" if ok else "ERROR")

    def _finish(self, ok, msg):
        self._set_busy(False)
        self.status_var.set(msg)
        self._log(msg, "SUCCESS" if ok else "ERROR")
        stop_live_exam_threads()

    # ---------------- Fucker 构造 ----------------
    def _num(self, var, cast, default=None):
        raw = str(var.get()).strip()
        if raw == "":
            return default
        try:
            return cast(raw)
        except ValueError:
            return default

    def _make_fucker(self, stop_event=None):
        proxies = {}
        proxy = self.proxy_var.get().strip()
        if proxy:
            if proxy.lower().startswith("socks5://"):
                proxies["socks5"] = proxy
            else:
                proxies["http"] = proxy
                proxies["https"] = proxy

        pushplus_token = ""
        bark_token = ""
        try:
            cfg = self._read_config()
            pp = cfg.get("pushplus") or {}
            if pp.get("enable") and pp.get("token"):
                pushplus_token = pp.get("token")
            bk = cfg.get("bark") or {}
            if bk.get("enable") and bk.get("token"):
                bark_token = bk.get("token")
        except Exception:
            pass

        return self.GuiFucker(
            proxies=proxies,
            speed=self._num(self.speed_var, float, None),
            end_thre=self._num(self.threshold_var, float, None),
            limit=self._num(self.limit_var, int, 0) or 0,
            pushplus_token=pushplus_token,
            bark_token=bark_token,
            tree_view=self.tree_view_var.get(),
            progressbar_view=self.progressbar_view_var.get(),
            image_path="",
            stop_event=stop_event if stop_event is not None else self.stop_event,
        )

    def _read_config(self):
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="UTF-8") as f:
                return json.load(f) or {}
        return {}

    def _load_cookies(self, f):
        if not os.path.exists(COOKIES_PATH):
            return False
        try:
            with open(COOKIES_PATH, "r", encoding="utf-8") as fp:
                cookies = json.loads(fp.read().strip() or "{}")
            if not cookies:
                return False
            f.cookies = cookies
            return True
        except Exception as e:
            self._log(f"复用已保存的登录状态失败: {e}", "WARNING")
            return False

    def _save_cookies(self, f):
        try:
            with open(COOKIES_PATH, "w", encoding="utf-8") as fp:
                json.dump(cookie_jar_to_list(f.cookies), fp, indent=2, ensure_ascii=False)
        except Exception as e:
            self._log(f"保存登录状态失败: {e}", "WARNING")

    def _build_ai_config(self):
        return {
            "enabled": True,
            "use_zhidao_ai": self.ai_use_zhidao_var.get(),
            "use_stream": bool(self.ai_stream_var.get()),
            "openai": {
                "api_base": self.ai_api_base_var.get().strip() or "https://api.openai.com",
                "api_key": self.ai_api_key_var.get().strip(),
                "model_name": self.ai_model_var.get().strip() or "gpt-4o-mini",
            },
            "ppt_processing": {"provide_to_ai": False},
        }

    # ---------------- 登录 ----------------
    def on_login(self):
        if self.busy:
            self._act(f"当前正在执行「{self._task or '任务'}」，本次扫码登录被忽略"
                      f"（可先点「停止」）", "WARNING")
            return
        self._start_login()

    def _start_login(self):
        """打开二维码窗口并启动登录线程

        整个过程都包在 try 里: 万一建窗口就失败, 也必须恢复 busy,
        否则界面会永久卡住, 表现就是"再点扫码登录没反应"。
        """
        try:
            self.stop_event.clear()
            self._login_gen += 1
            gen = self._login_gen
            self._login_ev = threading.Event()
            self._task = "扫码登录"
            self._act(f"开始扫码登录（第 {gen} 次尝试）")
            self._set_busy(True, stoppable=True)
            self.qr_window = QrWindow(self.root,
                                      on_close=lambda: self._cancel_login(gen))
            self._act("已打开二维码窗口，正在向智慧树请求二维码…")
            threading.Thread(target=self._worker_login, args=(gen, self._login_ev),
                             name=f"login-{gen}", daemon=True).start()
        except BaseException as e:
            logger.exception(e)
            glog("debug", traceback.format_exc())
            self._act(f"启动扫码登录失败：{type(e).__name__}: {e}", "ERROR")
            self.qr_window = None
            self._set_busy(False)
            try:
                messagebox.showerror("扫码登录失败", f"{type(e).__name__}: {e}")
            except Exception:
                pass

    def _cancel_login(self, gen):
        """用户关闭二维码窗口 / 点停止 -> 作废这次登录

        关键点: 光 destroy 窗口是不够的, 还要
          ① 让轮询线程尽快退出(触发取消事件)
          ② 把 busy 复位, 否则所有按钮都点不动
          ③ 递增代次, 让该线程后续消息失效
        """
        if gen != self._login_gen:
            return
        self._login_gen += 1
        try:
            if self._login_ev is not None:
                self._login_ev.set()
        except Exception:
            pass
        self.qr_window = None
        if self._task == "扫码登录":
            self._set_busy(False)
            self.status_var.set("已取消扫码登录")
        self._act("已取消扫码登录（窗口已关闭），可以重新点击「扫码登录」", "WARNING")

    def _worker_login(self, gen, ev):
        def put(item):
            if gen == self._login_gen:
                self.q.put(("login_msg", gen, item))

        try:
            f = self._make_fucker(stop_event=ev)
            glog("info", f"[登录] 请求二维码中…（代理：{f.proxies or '无'}）")
            put(("qr_status", "正在获取二维码…", None))

            def cb(img):
                put(("qr", img))

            f.login(use_qr=True, qr_callback=cb)
            if gen != self._login_gen:
                glog("info", "[登录] 本次登录已被取消，结果作废")
                return
            self._save_cookies(f)
            try:
                glog("info", f"[登录] 会话已写入 {os.path.basename(COOKIES_PATH)}"
                             f"（uuid={f.uuid}）")
            except Exception:
                pass
            put(("qr_done", True, "登录成功，登录状态已保存"))
        except StopRequested:
            glog("warning", "[登录] 已取消")
            put(("qr_done", False, "已取消"))
        except BaseException as e:
            logger.exception(e)
            glog("debug", traceback.format_exc())
            put(("qr_done", False, f"登录失败：{e}"))

    def on_load_cookies(self):
        if self.busy:
            self._act(f"当前正在执行「{self._task or '任务'}」，本次操作被忽略", "WARNING")
            return
        self.stop_event.clear()
        self._task = "加载登录状态"
        self._set_busy(True)
        self._act(f"尝试复用 {os.path.basename(COOKIES_PATH)} 里的登录状态…")
        threading.Thread(target=self._worker_load_cookies, name="load-cookies",
                         daemon=True).start()

    def _worker_load_cookies(self):
        try:
            f = self._make_fucker()
            if not self._load_cookies(f):
                self.q.put(("done", False, "没有可用的登录状态，请先扫码登录"))
                return
            f.getZhidaoList()
            f.getHikeList()
            self.q.put(("login", True, "已复用保存的登录状态"))
            self.q.put(("done", True, "登录状态可用"))
        except StopRequested:
            self.q.put(("done", True, "已手动停止"))
        except BaseException as e:
            logger.exception(e)
            glog("debug", traceback.format_exc())
            self.q.put(("done", False, f"登录状态已失效：{e}"))

    # ---------------- 课程列表 ----------------
    def on_fetch(self):
        if self.busy:
            self._act(f"当前正在执行「{self._task or '任务'}」，本次操作被忽略", "WARNING")
            return
        self.stop_event.clear()
        self._task = "获取课程列表"
        self._set_busy(True)
        self._act("开始获取课程列表…")
        threading.Thread(target=self._worker_fetch, name="fetch", daemon=True).start()

    def _worker_fetch(self):
        try:
            f = self._make_fucker()
            if not self._load_cookies(f):
                raise RuntimeError("未检测到登录状态，请先点击「扫码登录」")
            self._log("正在获取课程列表…")
            out = []
            for c in f.getZhidaoList() or []:
                out.append({"name": c.get("courseName") or "(未命名)",
                            "id": c.get("secret"), "kind": "共享课"})
            for c in f.getHikeList() or []:
                out.append({"name": c.get("courseName") or "(未命名)",
                            "id": str(c.get("courseId")), "kind": "校内课"})
            self.q.put(("courses", out))
            self.q.put(("done", True, f"获取到 {len(out)} 门课程"))
        except StopRequested:
            self.q.put(("done", True, "已手动停止"))
        except BaseException as e:
            logger.exception(e)
            glog("debug", traceback.format_exc())
            self.q.put(("done", False, f"获取课程列表失败：{e}"))

    def _fill_courses(self, items):
        self.course_ids = []
        self.course_list.delete(0, "end")
        for it in items:
            self.course_list.insert(
                "end", f"[{it.get('kind','')}] {it.get('name','')}  ({it.get('id','')})")
            self.course_ids.append(it.get("id"))
        # 同步写入 execution.json, 让命令行模式也能用同一份清单
        try:
            with open(EXEC_LIST, "w", encoding="utf-8") as fp:
                json.dump([{"name": it.get("name"), "id": it.get("id")} for it in items],
                          fp, indent=4, ensure_ascii=False)
        except Exception as e:
            self._log(f"写入 execution.json 失败: {e}", "WARNING")

    # ---------------- AI 课程列表 ----------------
    def on_ai_list(self):
        if self.busy:
            self._act(f"当前正在执行「{self._task or '任务'}」，本次操作被忽略", "WARNING")
            return
        self.stop_event.clear()
        self._task = "查询 AI 课程"
        self._set_busy(True)
        self._act("开始查询我参加的 AI 课程…")
        threading.Thread(target=self._worker_ai_list, name="ai-list", daemon=True).start()

    def _worker_ai_list(self):
        try:
            f = self._make_fucker()
            if not self._load_cookies(f):
                raise RuntimeError("未检测到登录状态，请先点击「扫码登录」")
            data = f.getZhidaoAiList()
            with open(AI_COURSES_PATH, "w", encoding="utf-8") as fp:
                json.dump(data, fp, ensure_ascii=False, indent=2)
            self.q.put(("ai_courses", data))
            self.q.put(("done", True, f"原始数据已写入 {os.path.basename(AI_COURSES_PATH)}"))
        except StopRequested:
            self.q.put(("done", True, "已手动停止"))
        except BaseException as e:
            logger.exception(e)
            glog("debug", traceback.format_exc())
            self.q.put(("done", False, f"查询 AI 课程失败：{e}"))

    def _fill_ai_courses(self, data):
        """尽力从返回数据里识别 课程ID / 班级ID, 识别不出就提示去看文件"""
        items = data if isinstance(data, list) else []
        if not items and isinstance(data, dict):
            for key in ("courseList", "list", "rows", "data", "courseOpenDtos"):
                v = data.get(key)
                if isinstance(v, list):
                    items = v
                    break

        def pick(d, keys):
            for k in keys:
                if isinstance(d, dict) and d.get(k) not in (None, ""):
                    return d.get(k)
            return None

        found = []
        for it in items:
            if not isinstance(it, dict):
                continue
            cid = pick(it, ("courseId", "scCourseId", "id", "course_id"))
            if cid is None:
                continue
            found.append({
                "name": pick(it, ("courseName", "scCourseName", "name", "course_name")) or "(未命名)",
                "course": cid,
                "class": pick(it, ("classId", "classID", "clazzId", "class_id")),
            })

        self.ai_scan_items = found
        self.ai_list.delete(0, "end")
        if not found:
            self.ai_list.insert("end", "未能自动识别，请查看 ai_courses.json")
            return
        for it in found:
            self.ai_list.insert(
                "end", f"{it['name']}  (课程 {it['course']} / 班级 {it['class']})")

    def _on_ai_pick(self, _event=None):
        sel = self.ai_list.curselection()
        if not sel or sel[0] >= len(self.ai_scan_items):
            return
        it = self.ai_scan_items[sel[0]]
        self.ai_course_var.set(str(it.get("course") or ""))
        self.ai_class_var.set(str(it.get("class") or ""))

    # ---------------- 运行 ----------------
    def _selected_ids(self):
        return [self.course_ids[i] for i in self.course_list.curselection()
                if i < len(self.course_ids)]

    def _current_mode(self):
        try:
            return "ai" if self.nb.index(self.nb.select()) == 1 else "courses"
        except Exception:
            return "courses"

    def on_run(self):
        if self.busy:
            self._act(f"当前正在执行「{self._task or '任务'}」，本次操作被忽略", "WARNING")
            return
        mode = self._current_mode()

        # 所有界面变量的读取都放在主线程做完, 线程里只收一个普通 dict,
        # 这样后台线程完全不碰 Tk 对象
        job = {"mode": mode}
        if mode == "ai":
            if not self.ai_course_var.get().strip() or not self.ai_class_var.get().strip():
                self._act("没有填写 AI 课程 ID / 班级 ID，已中止", "WARNING")
                messagebox.showwarning("缺少参数", "请填写 AI 课程的课程 ID 和班级 ID。")
                return
            job["course_id"] = self.ai_course_var.get().strip()
            job["class_id"] = self.ai_class_var.get().strip()
            job["no_exam"] = bool(self.ai_no_exam_var.get())
            job["ai_config"] = self._build_ai_config()
            params = (f"模式=AI课程  课程ID={job['course_id']}  班级ID={job['class_id']}  "
                      f"跳过考试={job['no_exam']}  "
                      f"答题AI={'智慧树自带' if self.ai_use_zhidao_var.get() else self.ai_model_var.get()}")
        else:
            job["ids"] = self._selected_ids()
            job["speed"] = self.speed_var.get().strip()
            params = (f"模式=普通课程  勾选={job['ids'] or '（未勾选 → 刷全部课程）'}  "
                      f"播放速度={job['speed'] or '网站最大值'}  "
                      f"单课时限={self.limit_var.get().strip() or '0'}分钟  "
                      f"完成阈值={self.threshold_var.get().strip() or '0.91'}  "
                      f"代理={self.proxy_var.get().strip() or '系统默认'}")
            self._note_speed(job["speed"])

        self._save_settings()
        self.stop_event.clear()
        _live_exam_ctxs.clear()
        self._task = "刷课"
        self._set_busy(True)
        self.status_var.set("开始运行…")
        self._act(f"开始刷课：{params}")
        threading.Thread(target=self._worker_run, args=(job,), name="run",
                         daemon=True).start()

    def _note_speed(self, raw):
        """只是记录一下本次用的速度。不做任何拦截（速度由用户自行决定）"""
        try:
            sp = float(raw)
            self._act(f"本次播放速度 = {sp:g}", "INFO")
        except Exception:
            self._act("本次播放速度 = 未填写（使用网站最大值）", "INFO")

    @staticmethod
    def _abort_name(kind):
        return {"captcha": "验证码", "time_limit": "单课时限"}.get(kind, str(kind))

    def _abort_help(self, kind, speed_now=None):
        """中断原因的人话解释 + 可执行的恢复办法"""
        if kind == "captcha":
            self._log("服务端要求验证码（接口返回 code=-12），这门课已中断 —— "
                      "从出错的那一节起，视频都没有刷上。", "ERROR")
            self._log("★ 怎么恢复：请到【电脑】上登录智慧树（www.zhihuishu.com），"
                      "打开这门课 → 进入正在刷的那一节的播放页 → 手动播放一会儿，"
                      "把页面上弹出的验证码过掉（滑块/图形/短信等）→ 确认进度条在正常往前走。", "WARNING")
            self._log("★ 过完验证码后，回到本程序再点一次「开始刷课」就能接着刷了。"
                      "（验证码是平台风控，遇到是正常的，不影响账号；"
                      "目前能刷到哪儿就刷到哪儿，不需要从头再来。）", "WARNING")
        elif kind == "time_limit":
            self._log("达到本次设定的单课时限，已按预期退出（不是出错）。"
                      "想一次刷更久，把「单课时限」调大或留空（0 = 不限）。", "WARNING")
        else:
            self._log(f"课程被中断，原因：{kind}", "ERROR")

    def _worker_run(self, job):
        try:
            f = self._make_fucker()
            if not self._load_cookies(f):
                raise RuntimeError("未检测到登录状态，请先点击「扫码登录」")

            if job.get("mode") == "ai":
                course_id = job.get("course_id")
                class_id = job.get("class_id")
                try:
                    # 参考 zd_utils 里抓到的真实请求: courseId 是字符串, classId 是整数
                    class_id = int(class_id)
                except (ValueError, TypeError):
                    pass
                self._log(f"开始刷 AI 课程 {course_id} / 班级 {class_id}")
                f.fuckAiCourse(course_id, class_id,
                               aiConfig=job.get("ai_config"),
                               no_exam=job.get("no_exam", False))
            else:
                ids = job.get("ids") or []
                speed_now = job.get("speed")
                aborts = []

                def report_abort(label, kind, head="=====", tail=""):
                    """如实汇报一次中断: 中断行 + 人话原因 + 恢复办法"""
                    aborts.append((label, kind))
                    self._log(f"{head} 课程 {label} 被{self._abort_name(kind)}中断"
                              f"{tail}（该课程未刷完）=====", "ERROR")
                    self._abort_help(kind, speed_now)
                    if kind == "captcha":
                        # 验证码是唯一需要用户"去电脑上操作一下"的中断，
                        # 光写日志容易错过，这里再弹一个窗明确提醒。
                        self.q.put(("alert", "需要你操作：平台要求验证码",
                                    f"课程 {label} 被平台的验证码拦住了，已经停在这里。\n\n"
                                    "请到【电脑】上登录智慧树（www.zhihuishu.com），"
                                    "打开这门课的播放页，手动播放一会儿，"
                                    "把弹出的验证码过掉。\n\n"
                                    "过完之后回到本程序，再点一次「开始刷课」即可接着刷。\n\n"
                                    "（遇到验证码是平台风控，正常现象；前面已经刷上的进度不会丢。）"))

                if not ids:
                    self._log("未勾选课程，改为刷全部课程…", "WARNING")
                    f.last_abort = None
                    f.fuckWhatever()
                    if f.last_abort:
                        report_abort("(全部课程)", f.last_abort)
                else:
                    total = len(ids)
                    for idx, cid in enumerate(ids, 1):
                        if self.stop_event.is_set():
                            raise StopRequested()
                        self._log(f"===== [{idx}/{total}] 开始课程 {cid} =====")
                        t0 = time.time()
                        f.last_abort = None
                        try:
                            f.fuckCourse(str(cid))
                            used = time.time() - t0
                            if f.last_abort:
                                report_abort(f"{cid}", f.last_abort,
                                             head=f"===== [{idx}/{total}]",
                                             tail=f"，用时 {used:.1f}s")
                            else:
                                self._log(f"===== [{idx}/{total}] 课程 {cid} 完成，"
                                          f"用时 {used:.1f}s =====", "SUCCESS")
                        except StopRequested:
                            raise
                        except BaseException as e:
                            self._log(f"课程 {cid} 出错（{time.time() - t0:.1f}s）："
                                      f"{type(e).__name__}: {e}", "ERROR")
                            logger.exception(e)
                if aborts:
                    names = "、".join(f"{c}" for c, _ in aborts)
                    self.q.put(("done", True,
                                f"任务结束，但有 {len(aborts)} 门课程未刷完：{names}"))
                else:
                    self.q.put(("done", True, "任务完成"))
        except StopRequested:
            self.q.put(("done", True, "已手动停止"))
        except BaseException as e:
            logger.exception(e)
            glog("debug", traceback.format_exc())
            self.q.put(("done", False, f"运行出错：{e}"))

    def on_stop(self):
        if self._task == "扫码登录":
            self._act("停止扫码登录", "WARNING")
            self._cancel_login(self._login_gen)
            return
        self.stop_event.set()
        stop_live_exam_threads()
        self.status_var.set("正在停止…（当前这一节结束后退出）")
        self._log("已发送停止请求", "WARNING")

    # ---------------- 关闭 ----------------
    def _on_close(self):
        if self.busy:
            if not messagebox.askyesno("确认退出", "任务还在运行，确定要退出吗？"):
                return
            self.stop_event.set()
            try:
                if self._login_ev is not None:
                    self._login_ev.set()
            except Exception:
                pass
            stop_live_exam_threads()
            self._act("退出前已请求停止正在运行的任务", "WARNING")
        self._save_settings()
        self._act("关闭界面")
        self._uninstall_io()
        try:
            self.root.destroy()
        except Exception:
            pass


# --------------------------------------------------------------------------
def main(selftest=False):
    if not TK_OK:
        print("当前 Python 没有 tkinter，无法启动图形界面。")
        print("请改用带 tkinter 的 Python（本机可用：py -3.12 gui.py）")
        return 1

    missing = check_env()
    if missing:
        msg = ("缺少运行依赖，请先执行:\n\n"
               "py -3.12 -m pip install -r requirements.txt\n\n"
               "缺失: " + ", ".join(missing))
        try:
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror("缺少依赖", msg)
            r.destroy()
        except Exception:
            print(msg)
        return 1

    app = App()
    if selftest:
        app.root.update_idletasks()
        app.root.update()
        app._uninstall_io()
        app.root.destroy()
        print("SELFTEST OK")
        return 0
    app.root.mainloop()
    return 0


def _ensure_std_streams():
    """打包成无控制台 exe 后 sys.stdout/stderr 为 None, 补一个空实现防止 print 抛错"""
    class _Null(io.TextIOBase):
        def write(self, s):
            return len(s)

        def flush(self):
            pass

    if sys.stdout is None:
        sys.stdout = _Null()
    if sys.stderr is None:
        sys.stderr = _Null()


def _fatal(exc_type, exc, tb):
    """兜底异常处理: 写 crash.log + 弹窗

    打包后没有控制台, 否则用户看到的只是"闪退", 完全不知道发生了什么。
    """
    try:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
    except Exception:
        text = f"{exc_type}: {exc}"
    crash = os.path.join(ROOT, "crash.log")
    try:
        with open(crash, "a", encoding="utf-8") as fp:
            fp.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n{text}\n")
    except Exception:
        crash = "(日志写入失败)"
    try:
        if TK_OK:
            r = tk.Tk()
            r.withdraw()
            messagebox.showerror(
                "程序出错", f"{getattr(exc_type, '__name__', exc_type)}: {exc}\n\n"
                             f"详细信息已写入:\n{crash}"
            )
            r.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    _ensure_std_streams()
    sys.excepthook = _fatal
    try:
        sys.exit(main(selftest="--selftest" in sys.argv))
    except SystemExit:
        raise
    except BaseException:
        _fatal(*sys.exc_info())
        sys.exit(1)
