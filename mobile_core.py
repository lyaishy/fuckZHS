#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""移动端核心逻辑层（Kivy / Android 共用）

设计目标
--------
把「刷课」这件事从界面里彻底剥离出来，做到：

1. **不依赖任何 GUI 库** —— 不 import tkinter / kivy，纯 Python + threading，
   因此可以在 Windows 上直接跑单元测试，不必先打出 APK 才知道对不对；
2. **平台无关** —— 数据目录、终端宽度这些差异都已经收敛在 `utils.py` 里；
3. **与桌面版共享同一份数据文件** —— config.json / cookies.json /
   execution.json / gui_settings.json 的格式完全一致，两个界面可以来回切换；
4. **如实汇报中断** —— 沿用桌面版的做法：服务端返回 code=-12（验证码）时，
   `fucker.fuckZhidaoCourse` 会把它吞掉并提前 return，外层完全感知不到。
   所以在最底层的 `zhidaoQuery` 记一笔 `last_abort`，界面才能区分
   「真跑完了」和「被验证码打断了」。

这个文件不含任何界面代码，界面只负责调用这里的 API 并消费 `Core.msg_queue`。
"""

import json
import logging
import os
import queue
import threading
import time
import traceback

# 说明：这里故意不 import fucker / utils 等重依赖，
# 而是在核心初始化时再导入，方便在没有网络/缺依赖时给出清晰报错。

ROOT = None            # 由 init_paths() 填
CONFIG_PATH = None
COOKIES_PATH = None
SETTINGS_PATH = None
EXEC_LIST = None
LOGS_DIR = None

# 播放速度由用户自行填写，不做任何"安全阈值"拦截。
# （实测 400 可用；被验证码拦住属于平台风控，与速度高低无必然关系）

DEFAULT_SETTINGS = {
    "speed": "",
    "limit": 0,
    "threshold": "",
    "tree_view": False,
    "progressbar_view": False,
    "proxy": "",
    "debug": False,
    "verbose": True,
    "ai_use_zhidao": True,
    "ai_no_exam": False,
    "ai_stream": True,
    "ai_api_base": "https://api.openai.com",
    "ai_api_key": "",
    "ai_model": "gpt-4o-mini",
    "keep_awake": True,
}

# 由 check_env() 填
Fucker = None
fucker_module = None
logger = None
ObjDict = None
cookie_jar_to_list = None

# 详细日志开关：True 时每次网络请求都记到 INFO
VERBOSE = True


# --------------------------------------------------------------------------
# 路径
# --------------------------------------------------------------------------
def _app_source_dir():
    """随程序一起发布的源码目录（找 config.json 用）

    * 源码运行 / Android：就是 mobile_core.py 所在目录
    * PyInstaller onefile：__file__ 指向 _MEIxxxx 临时解压目录，
      但那里进程退出就没了，不适合当"模板来源"读取——不过读一次复制出来没问题。
    """
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def seed_default_files():
    """首次运行时，把随包发布的 config.json 复制到可写的数据目录

    ROOT（可写、持久）和"随包发布的源码目录"在 exe / APK 下是两个地方，
    所以 config.json 不会自动出现在 ROOT 里，必须显式播种一次。
    只处理 config.json，且**绝不覆盖**已存在的文件。
    """
    try:
        base = _app_source_dir()
        # 仓库里 config.json 被 .gitignore 排除（可能含账号密码），
        # 随包发布的是 config.example.json，优先用它兜底。
        src = os.path.join(base, "config.json")
        if not os.path.isfile(src):
            src = os.path.join(base, "config.example.json")
        if os.path.isfile(CONFIG_PATH) or not os.path.isfile(src):
            return
        if os.path.abspath(src) == os.path.abspath(CONFIG_PATH):
            return
        os.makedirs(ROOT, exist_ok=True)
        with open(src, "rb") as fi, open(CONFIG_PATH, "wb") as fo:
            fo.write(fi.read())
        glog("debug", f"已生成默认 {os.path.basename(CONFIG_PATH)}")
    except Exception as e:
        glog("debug", f"生成默认 config.json 失败（不影响使用）：{e}")


def init_paths():
    """确定数据目录。规则统一由 utils.getDir() 决定（源码 / exe / Android 三态）"""
    global ROOT, CONFIG_PATH, COOKIES_PATH, SETTINGS_PATH, EXEC_LIST, LOGS_DIR
    from utils import getDir
    ROOT = getDir()
    CONFIG_PATH = os.path.join(ROOT, "config.json")
    COOKIES_PATH = os.path.join(ROOT, "cookies.json")
    SETTINGS_PATH = os.path.join(ROOT, "gui_settings.json")
    EXEC_LIST = os.path.join(ROOT, "execution.json")
    LOGS_DIR = os.path.join(ROOT, "logs")
    seed_default_files()
    return ROOT


# --------------------------------------------------------------------------
# 日志：统一出口
# 走项目自带的 MonoLogger，于是同一条日志会同时进
#   ① 界面日志区（由界面注册 handler 消费）
#   ② logs/info.log、logs/error.log ...
# --------------------------------------------------------------------------
_LEVEL_MAP = {
    "success": "info",
    "warn": "warning",
    "fatal": "critical",
    "trace": "debug",
}


def glog(level, msg, verbose=False):
    """写一条日志。`verbose=True` 表示"细节日志"，由 VERBOSE 开关决定是否降级"""
    try:
        lv = str(level).lower()
        if verbose and not VERBOSE:
            lv = "debug"
        if lv == "success":
            lv = "info"
            # 用 "√"（U+221A）而不是 "✓"（U+2713）：CJK 字体普遍没有后者，
            # 手机上会显示成一个方框。
            msg = "√ " + str(msg)
        lv = _LEVEL_MAP.get(lv, lv)
        text = str(msg)
        # ① 推给界面（手机上看不到控制台，必须显式回传）
        if _sink is not None:
            try:
                _sink(lv, text)
            except Exception:
                pass
        # ② 写进日志文件：补上时间戳，格式与桌面版 gui.log 保持一致
        if logger is not None:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            fn = getattr(logger, lv, None)
            if callable(fn):
                fn(f"{stamp} [{lv.upper()}] {text}")
    except Exception:
        pass


_sink = None


def set_log_sink(sink):
    """注册日志接收器：`sink(level, text)`。界面用它在页面上显示日志。"""
    global _sink
    _sink = sink


_SENSITIVE = ("password", "passwd", "pwd", "token", "secret", "key", "cookie")


def _fmt_args(args, kwargs, limit=140):
    parts = []
    for a in args:
        parts.append(repr(a)[:60])
    for k, v in (kwargs or {}).items():
        if any(s in str(k).lower() for s in _SENSITIVE):
            parts.append(f"{k}=***")
        else:
            parts.append(f"{k}={repr(v)[:60]}")
    s = ", ".join(parts)
    return s if len(s) <= limit else s[:limit] + "…"


def _short_url(url, limit=96):
    u = str(url or "").split("?")[0]
    return u if len(u) <= limit else u[:limit] + "…"


# --------------------------------------------------------------------------
# 依赖检查
# --------------------------------------------------------------------------
def check_env():
    """导入依赖；返回缺失的**必需**依赖列表（空列表 = 一切正常）

    ⚠ 这里只能列「视频刷课」这条主路真正必需的包，也就是 requests 和
    pycryptodome（AES 加密）。以下三个**必须**当作可选，不能算缺失：

        PIL/Pillow   只在「在终端里用字符画显示二维码」时用（见 utils.py），
                     手机端二维码画在 Kivy 界面上，走不到那里；
                     p4a 没有它的配方，安卓上也装不了。
        tiktoken     只有 AI 课里给文本分词时用；p4a 没有配方（纯 C 扩展）。
        openai      只有 AI 课调用大模型时用；安卓上同样没有。

    把它们算成缺失的后果很严重：APK 装得上，但一打开就提示缺依赖、
    界面直接不可用。所以下面的必需清单里只有两项。
    """
    global Fucker, fucker_module, logger, ObjDict, cookie_jar_to_list
    missing = []
    for mod, pkg in (("requests", "requests"),
                     ("Crypto", "pycryptodome")):
        try:
            __import__(mod)
        except Exception:
            missing.append(pkg)
    if missing:
        return missing
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
# --------------------------------------------------------------------------
class StopRequested(BaseException):
    """用户点击停止时抛出

    故意继承 BaseException：fucker.py 内部大量使用 `except Exception`
    来跳过失败条目，继承 Exception 会被这些处理器吞掉，导致"点了停止停不下来"。
    """


def make_core_fucker_class(fucker_cls):
    """生成带「停止支持 + 中断原因记录 + 关键日志」的 Fucker 子类"""

    def _exc(name):
        """延迟解析 fucker 模块里的异常类；取不到时空元组（等价于不捕获）"""
        try:
            return getattr(fucker_module, name)
        except Exception:
            return ()

    class CoreFucker(fucker_cls):
        def __init__(self, *args, stop_event=None, **kwargs):
            super().__init__(*args, **kwargs)
            self._stop_event = stop_event
            # 上次运行被中断的原因: None / "captcha" / "time_limit"
            self.last_abort = None
            self._patch_session()

        def _raise_if_stopped(self):
            if self._stop_event is not None and self._stop_event.is_set():
                raise StopRequested()

        def zhidaoQuery(self, *args, **kwargs):
            try:
                return super().zhidaoQuery(*args, **kwargs)
            except _exc("CaptchaException"):
                self.last_abort = "captcha"
                raise

        def _patch_session(self):
            """给 session 的每个 HTTP 动作挂停止检查

            `_qrlogin` 的轮询直接调 `self.session.get`，不走 `_apiQuery`，
            只包 `_apiQuery` 的话，关掉扫码界面后这个循环还会一直转。
            包住 session 的方法后，取消能在 0.5 秒内生效。
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
                glog("warning", f"[请求] {method} {_short_url(url)} 失败"
                                 f"（{time.time() - t0:.2f}s）：{type(e).__name__}: {e}")
                raise
            code = None
            for attr in ("code", "status"):
                try:
                    code = getattr(ret, attr)
                    break
                except Exception:
                    continue
            glog("info", f"[请求] {method} {_short_url(url)} -> code={code}"
                         f"，用时 {time.time() - t0:.2f}s", verbose=True)
            return ret

        def _checkTimeLimit(self, cid):
            self._raise_if_stopped()
            try:
                return super()._checkTimeLimit(cid)
            except _exc("TimeLimitExceeded"):
                self.last_abort = "time_limit"
                raise

    # 给几个高层动作加上「开始 / 结束 / 耗时」日志
    for _name in ("login", "getZhidaoList", "getHikeList", "getZhidaoAiList",
                  "fuckCourse", "fuckVideo", "fuckAiCourse", "fuckWhatever"):
        _orig = getattr(CoreFucker, _name, None)
        if not callable(_orig):
            continue

        def _make(o, n):
            def wrapper(self, *a, **kw):
                glog("info", f"[执行] {n} 开始 {_fmt_args(a, kw)}")
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

        setattr(CoreFucker, _name, _make(_orig, _name))

    CoreFucker.__name__ = "CoreFucker"
    return CoreFucker


# --------------------------------------------------------------------------
# 模块级钩子：停止 + AI 考试心跳线程登记
# --------------------------------------------------------------------------
_hook_lock = threading.Lock()
_pb_original = None
_exam_ctx_original = None
_live_exam_ctxs = []


def install_hooks(stop_event):
    """① progressBar 每秒被调一次，拿它当停止检查点
       ② 登记 AI 考试的 ExamCtx，停止时要关掉它的心跳线程
    """
    global _pb_original, _exam_ctx_original
    with _hook_lock:
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
    for ctx in list(_live_exam_ctxs):
        try:
            ctx.examStopped = True
        except Exception:
            pass
    _live_exam_ctxs.clear()


# --------------------------------------------------------------------------
# 中断原因的"人话"解释
# --------------------------------------------------------------------------
def abort_name(kind):
    return {"captcha": "验证码", "time_limit": "单课时限"}.get(kind, str(kind))


# 被验证码拦住时给用户看的提醒（手机上重点提醒：去电脑端过验证码）
CAPTCHA_ALERT_TITLE = "需要你操作：平台要求验证码"


def captcha_alert_text(label="(当前课程)"):
    return (f"课程 {label} 被平台的验证码拦住了，已经停在这里。\n\n"
            "请到【电脑】上登录智慧树（www.zhihuishu.com），打开这门课的播放页，"
            "手动播放一会儿，把弹出的验证码过掉。\n\n"
            "过完之后回到本程序，再点一次「开始刷课」即可接着刷。\n\n"
            "（遇到验证码是平台风控，正常现象；前面已经刷上的进度不会丢。）")


def abort_help(kind, speed_now=None, log=None):
    """输出「恢复建议」；log 为可选的日志函数"""
    say = log or (lambda m, lv="warning": glog(lv, m))
    if kind == "captcha":
        say("服务端要求验证码（接口返回 code=-12），这门课已中断 —— "
            "从出错的那一节起，视频都没有刷上。", "error")
        say("★ 怎么恢复：请到【电脑】上登录智慧树（www.zhihuishu.com），"
            "打开这门课 → 进入正在刷的那一节的播放页 → 手动播放一会儿，"
            "把页面上弹出的验证码过掉（滑块/图形/短信等）→ 确认进度条在正常往前走。",
            "warning")
        say("★ 过完验证码后，回到本程序再点一次「开始刷课」就能接着刷了。"
            "（验证码是平台风控，遇到是正常的，不影响账号；"
            "目前能刷到哪儿就刷到哪儿，不需要从头再来。）", "warning")
    elif kind == "time_limit":
        say("达到本次设定的单课时限，已按预期退出（不是出错）。"
            "想一次刷更久，把「单课时限」调大或留空（0 = 不限）。", "warning")
    else:
        say(f"课程被中断，原因：{kind}", "error")


# --------------------------------------------------------------------------
# 核心：所有耗时操作都在后台线程里跑，主线程只消费 msg_queue
# --------------------------------------------------------------------------
class Core:
    """移动端核心

    消息协议（界面按 item[0] 分派）：
        ("log",   level, text)          日志
        ("qr",    png_bytes)            二维码图片数据（PNG 字节）
        ("login", ok, msg)              登录结果
        ("courses", [{"name","id","kind"}])   课程列表
        ("busy",  busy: bool)           忙闲状态变化
        ("done",  ok, msg)              一次任务结束
        ("status", text)                状态栏文案
        ("alert", title, text)          需要用户操作的重点提醒（如"被验证码拦住"）
    """

    def __init__(self):
        self.msg_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.busy = False
        self.courses = []
        self.CoreFucker = None
        self._task = None
        self._login_gen = 0
        self._login_ev = None
        self.settings = {}
        # 日志回流：核心/网络层的每条日志都投进队列，界面消费后显示。
        # 手机上用户看不到控制台，没有这一步等于"盲跑"。
        set_log_sink(self._on_log)

    # ---------------- 初始化 ----------------
    def setup(self):
        """导入依赖 + 装钩子。返回缺失依赖列表"""
        global VERBOSE
        missing = check_env()
        if missing:
            return missing
        init_paths()
        self.settings = self.load_settings()
        VERBOSE = bool(self.settings.get("verbose", True))
        self.CoreFucker = make_core_fucker_class(Fucker)
        install_hooks(self.stop_event)
        return []

    def put(self, *item):
        self.msg_queue.put(item)

    def _on_log(self, level, text):
        """glog 的接收器：把日志投进消息队列（界面线程消费）"""
        try:
            t = str(text)
            lv = str(level).lower()
            # glog 把 success 收敛成 info + "√ " 前缀，界面上还原成绿色
            if lv == "info" and t.startswith("√"):
                lv = "success"
            self.msg_queue.put(("log", lv, t))
        except Exception:
            pass

    def log(self, text, level="info"):
        glog(level, text)

    def act(self, msg, level="info"):
        """记录一次用户操作或关键步骤（与桌面版 `_act` 对齐）

        界面上任何按钮点击都走这里，确保「我点了什么」一定留下痕迹。
        """
        glog(level, f"[界面] {msg}")

    # ---------------- 设置持久化（与桌面版同一份 gui_settings.json） ----------------
    def load_settings(self):
        try:
            if os.path.isfile(SETTINGS_PATH):
                with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                    s = json.load(f) or {}
                    merged = dict(DEFAULT_SETTINGS)
                    merged.update(s)
                    return merged
        except Exception as e:
            glog("warning", f"读取界面设置失败：{e}")
        return dict(DEFAULT_SETTINGS)

    def save_settings(self, values=None):
        if values:
            self.settings.update(values)
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            glog("warning", f"保存界面设置失败：{e}")

    # ---------------- 配置 / cookie ----------------
    def read_config(self):
        try:
            if os.path.isfile(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="UTF-8") as f:
                    return json.load(f) or {}
        except Exception as e:
            glog("warning", f"读取 config.json 失败：{e}")
        return {}

    def has_cookies(self):
        return os.path.exists(COOKIES_PATH) and os.path.getsize(COOKIES_PATH) > 2

    def _load_cookies(self, f):
        if not self.has_cookies():
            return False
        try:
            with open(COOKIES_PATH, "r", encoding="utf-8") as fp:
                cookies = json.loads(fp.read().strip() or "{}")
            if not cookies:
                return False
            f.cookies = cookies
            return True
        except Exception as e:
            self.log(f"复用已保存的登录状态失败: {e}", "warning")
            return False

    def _save_cookies(self, f):
        try:
            with open(COOKIES_PATH, "w", encoding="utf-8") as fp:
                json.dump(cookie_jar_to_list(f.cookies), fp, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.log(f"保存登录状态失败: {e}", "warning")
            return False

    # ---------------- 构造 fucker ----------------
    @staticmethod
    def _num(raw, cast, default=None):
        """把界面上的字符串安全转成数字；留空/非法 -> default"""
        if raw is None:
            return default
        s = str(raw).strip()
        if not s:
            return default
        try:
            return cast(float(s))
        except Exception:
            try:
                return cast(s)
            except Exception:
                return default

    def make_fucker(self, stop_event=None):
        s = self.settings
        proxies = {}
        proxy = str(s.get("proxy") or "").strip()
        if proxy:
            if proxy.lower().startswith("socks5://"):
                proxies["socks5"] = proxy
            else:
                proxies["http"] = proxy
                proxies["https"] = proxy

        pushplus_token = ""
        bark_token = ""
        try:
            cfg = self.read_config()
            pp = cfg.get("pushplus") or {}
            if pp.get("enable") and pp.get("token"):
                pushplus_token = pp.get("token")
            bk = cfg.get("bark") or {}
            if bk.get("enable") and bk.get("token"):
                bark_token = bk.get("token")
        except Exception:
            pass

        return self.CoreFucker(
            proxies=proxies,
            speed=self._num(s.get("speed"), float, None),
            end_thre=self._num(s.get("threshold"), float, None),
            limit=self._num(s.get("limit"), int, 0) or 0,
            pushplus_token=pushplus_token,
            bark_token=bark_token,
            tree_view=bool(s.get("tree_view", False)),
            progressbar_view=bool(s.get("progressbar_view", False)),
            image_path="",
            stop_event=stop_event if stop_event is not None else self.stop_event,
        )

    def build_ai_config(self):
        s = self.settings
        return {
            "enabled": True,
            "use_zhidao_ai": bool(s.get("ai_use_zhidao", True)),
            "use_stream": bool(s.get("ai_stream", True)),
            "openai": {
                "api_base": str(s.get("ai_api_base") or "").strip() or "https://api.openai.com",
                "api_key": str(s.get("ai_api_key") or "").strip(),
                "model_name": str(s.get("ai_model") or "").strip() or "gpt-4o-mini",
            },
            "ppt_processing": {"provide_to_ai": False},
        }

    # ---------------- 忙闲 / 任务 ----------------
    def _set_busy(self, busy, task=None):
        self.busy = busy
        self._task = task if busy else None
        self.put("busy", busy, self._task or "")

    def _start(self, task, fn, *args):
        """统一的任务启动：清停止事件 + 置忙 + 起后台线程"""
        if self.busy:
            self.log(f"当前正在执行「{self._task or '任务'}」，本次操作被忽略"
                     f"（可先点「停止」）", "warning")
            return False
        self.stop_event.clear()
        _live_exam_ctxs.clear()
        self._set_busy(True, task)
        t = threading.Thread(target=self._guard, args=(fn, args), name=task, daemon=True)
        t.start()
        return True

    def _guard(self, fn, args):
        """后台线程统一外壳：任何异常都记日志并且一定复位忙闲状态

        否则一旦抛异常没被接住，界面会永久卡在"运行中"，用户只能杀进程。
        """
        import time as _t
        t0 = _t.time()
        try:
            fn(*args)
        except StopRequested:
            self.put("done", True, "已手动停止")
        except BaseException as e:
            glog("error", f"[执行] 未预期错误：{type(e).__name__}: {e}")
            glog("debug", traceback.format_exc())
            self.put("done", False, f"出错了：{type(e).__name__}: {e}")
        finally:
            glog("debug", f"[执行] 任务「{self._task or ''}」结束，"
                          f"用时 {_t.time() - t0:.1f}s")
            self._set_busy(False)

    def request_stop(self):
        """请求停止（界面点「停止」时调用）"""
        if not self.busy:
            return
        self.act("点击「停止」，正在等待当前步骤结束…", "warning")
        self.stop_event.set()
        stop_live_exam_threads()
        # 作废正在进行的登录（它会自己退出）
        self._login_gen += 1
        if self._login_ev is not None:
            self._login_ev.set()

    # ---------------- 扫码登录 ----------------
    def login_qr(self):
        """启动扫码登录；二维码通过 ("qr", png_bytes) 消息回传"""
        if self.busy:
            self.log(f"当前正在执行「{self._task or '任务'}」，本次扫码登录被忽略"
                     f"（可先点「停止」）", "warning")
            return
        self._login_gen += 1
        gen = self._login_gen
        ev = threading.Event()
        self._login_ev = ev

        self.stop_event.clear()
        self._set_busy(True, "扫码登录")
        self.act(f"开始扫码登录（第 {gen} 次尝试）")
        self.act("已打开二维码窗口，正在向智慧树请求二维码…")
        self.put("status", "正在获取二维码…")
        threading.Thread(target=self._worker_login, args=(gen, ev),
                         name="login", daemon=True).start()

    def cancel_login(self):
        """作废当前这次登录（关闭二维码界面时调用）"""
        self._login_gen += 1
        if self._login_ev is not None:
            self._login_ev.set()
        self._login_ev = None
        if self.busy and self._task == "扫码登录":
            self.stop_event.set()
            self._set_busy(False)
        self.act("已取消本次扫码登录（窗口已关闭），可以重新点击「扫码登录」",
                 "warning")

    def _worker_login(self, gen, ev):
        """后台登录线程

        注意：`_set_busy(False)` 放在 finally，无论成功失败都要复位，
        否则界面会永远卡住（表现就是"关了窗口再点扫码登录没反应"）。
        """
        try:
            f = self.make_fucker(stop_event=ev)
            self.act(f"请求二维码中…（代理：{f.proxies or '无'}）", "info")

            def cb(img):
                if gen == self._login_gen:
                    self.act(f"二维码已获取（{len(img)} 字节），正在显示…")
                    self.put("qr", img)

            f.login(use_qr=True, qr_callback=cb)
            if gen != self._login_gen:
                self.act("本次登录已被取消，结果作废", "warning")
                return
            self._save_cookies(f)
            try:
                self.act(f"会话已写入 {os.path.basename(COOKIES_PATH)}"
                         f"（uuid={f.uuid}）")
            except Exception:
                pass
            self.put("login", True, "登录成功，登录状态已保存")
            self.put("done", True, "登录成功")
        except StopRequested:
            self.act("已取消登录", "warning")
            self.put("done", True, "已取消登录")
        except BaseException as e:
            logger.exception(e)
            glog("debug", traceback.format_exc())
            self.put("done", False, f"登录失败：{e}")
        finally:
            self._set_busy(False)

    # ---------------- 复用已保存的登录状态 ----------------
    def load_cookies(self):
        self.act(f"尝试复用 {os.path.basename(COOKIES_PATH)} 里的登录状态…")

        def job():
            f = self.make_fucker()
            if not self._load_cookies(f):
                raise RuntimeError("没有找到保存的登录状态，请先扫码登录")
            self.act("正在校验已保存的登录状态…")
            f.getZhidaoList()
            f.getHikeList()
            self.act("登录状态可用", "success")
            self.put("login", True, "已复用保存的登录状态")
        self._start("校验登录状态", job)

    # ---------------- 获取课程列表 ----------------
    def fetch_courses(self):
        self.act("开始获取课程列表…")

        def job():
            f = self.make_fucker()
            if not self._load_cookies(f):
                raise RuntimeError("未检测到登录状态，请先点击「扫码登录」")
            self.log("正在获取课程列表…", "info")
            out = []
            for c in f.getZhidaoList() or []:
                out.append({"name": c.get("courseName") or "(未命名)",
                            "id": c.get("secret"), "kind": "共享课"})
            for c in f.getHikeList() or []:
                out.append({"name": c.get("courseName") or "(未命名)",
                            "id": str(c.get("courseId")), "kind": "校内课"})
            self.courses = out
            self.put("courses", out)
            # 同步写 execution.json，命令行模式可以复用同一份清单
            try:
                with open(EXEC_LIST, "w", encoding="utf-8") as fp:
                    json.dump([{"name": it["name"], "id": it["id"]} for it in out],
                              fp, indent=2, ensure_ascii=False)
                self.log(f"课程清单已写入 {os.path.basename(EXEC_LIST)}")
            except Exception as e:
                self.log(f"写入 execution.json 失败：{e}", "warning")
            self.put("done", True, f"获取到 {len(out)} 门课程")
        self._start("获取课程列表", job)

    # ---------------- 刷课 ----------------
    def check_speed(self, raw):
        """速度校验。

        速度由用户自己填，本函数只负责把非数字纠正为「留空」，
        **不再做任何"安全提示/弹窗确认"**（用户实测 400 可用）。
        返回 (ok, message)，ok 恒为 True。
        """
        s = "" if raw is None else str(raw).strip()
        if s == "":
            return True, ""
        try:
            float(s)
        except Exception:
            return True, f"「{s}」不是数字，已按「留空 = 网站最大值」处理。"
        return True, ""

    def run_courses(self, ids=None, speed=None, force_all=False):
        """开始刷课

        ids: 要刷的课程 id 列表；为空则刷全部课程
        speed: 播放速度（字符串，可空）

        返回 True 表示已启动；False 表示被拒绝（正忙 / 参数问题）。
        """
        if self.busy:
            self.log(f"当前正在执行「{self._task or '任务'}」，本次操作被忽略"
                     f"（可先点「停止」）", "warning")
            return False
        ids = list(ids or [])
        self.save_settings({"speed": "" if speed is None else str(speed)})
        self.act(f"开始刷课：勾选={ids or '（未勾选 → 刷全部课程）'}  "
                 f"播放速度={speed or '网站最大值'}  "
                 f"单课时限={self.settings.get('limit') or '0'}分钟  "
                 f"完成阈值={self.settings.get('threshold') or '0.91'}  "
                 f"代理={self.settings.get('proxy') or '系统默认'}")

        def job():
            f = self.make_fucker()
            if not self._load_cookies(f):
                raise RuntimeError("未检测到登录状态，请先点击「扫码登录」")

            speed_now = speed
            aborts = []

            def report_abort(label, kind, head="=====", tail=""):
                aborts.append((label, kind))
                self.log(f"{head} 课程 {label} 被{abort_name(kind)}中断"
                         f"{tail}（该课程未刷完）=====", "error")
                abort_help(kind, speed_now, log=lambda m, lv="warning": self.log(m, lv))
                if kind == "captcha":
                    # 验证码需要用户去电脑上操作一下，光写日志容易被忽略，
                    # 额外发一条 alert 让界面弹个窗 / 显示醒目提示。
                    self.put("alert", CAPTCHA_ALERT_TITLE, captcha_alert_text(label))

            if not ids:
                self.log("未选择课程，改为刷全部课程…", "warning")
                f.last_abort = None
                f.fuckWhatever()
                if f.last_abort:
                    report_abort("(全部课程)", f.last_abort)
            else:
                total = len(ids)
                for idx, cid in enumerate(ids, 1):
                    if self.stop_event.is_set():
                        raise StopRequested()
                    self.log(f"===== [{idx}/{total}] 开始课程 {cid} =====", "info")
                    self.put("status", f"正在刷第 {idx}/{total} 门课程")
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
                            self.log(f"===== [{idx}/{total}] 课程 {cid} 完成，"
                                     f"用时 {used:.1f}s =====", "success")
                    except StopRequested:
                        raise
                    except BaseException as e:
                        self.log(f"课程 {cid} 出错（{time.time() - t0:.1f}s）："
                                 f"{type(e).__name__}: {e}", "error")
                        logger.exception(e)

            if aborts:
                names = "、".join(str(c) for c, _ in aborts)
                self.put("done", True,
                         f"任务结束，但有 {len(aborts)} 门课程未刷完：{names}")
            else:
                self.put("done", True, "全部课程已处理完毕")

        return self._start("刷课", job)

    # ---------------- AI 课程 ----------------
    def run_ai_course(self, course_id, class_id, no_exam=False):
        course_id = str(course_id or "").strip()
        class_id = str(class_id or "").strip()
        if not course_id or not class_id:
            self.log("没有填写 AI 课程 ID / 班级 ID，已中止", "warning")
            return False
        try:
            class_id_val = int(class_id)
        except (ValueError, TypeError):
            class_id_val = class_id

        def job():
            f = self.make_fucker()
            if not self._load_cookies(f):
                raise RuntimeError("未检测到登录状态，请先点击「扫码登录」")
            self.act(f"开始刷 AI 课程 {course_id} / 班级 {class_id_val}"
                     f"（跳过考试={bool(no_exam)}）")
            f.fuckAiCourse(course_id, class_id_val,
                           aiConfig=self.build_ai_config(), no_exam=bool(no_exam))
            self.put("done", True, "AI 课程已处理完毕")

        self._start("刷 AI 课程", job)
        return True
