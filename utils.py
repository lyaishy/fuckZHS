#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import io
import os
import sys
from requests.cookies import RequestsCookieJar, create_cookie
from PIL import Image, ImageOps
from datetime import timedelta


def HMS(*args, **kw):
    return str(timedelta(*args, **kw))

def strToClass(class_name: str, module: str="__main__"):
    return getattr(sys.modules[module], class_name)

def showImage(img, show_in_terminal=False, ensure_unicode=False):
    if show_in_terminal:
        if ensure_unicode:
            terminalShowImage_unicode(img)
        else:
            terminalShowImage_tty(img)
    else:
        import threading
        img = Image.open(io.BytesIO(img))
        threading.Thread(target=img.show).run()
    print("Scan QR code")

def terminalShowImage_unicode(img):
    img = Image.open(io.BytesIO(img))
    qr = img.resize((47,47), Image.Resampling.NEAREST)
    qr = ImageOps.grayscale(qr)
    chars = [bytes((code,)).decode("cp437") for code in (255, 223, 220, 219)]
    new_line = '\n'
    col, row = qr.size
    def getPos(x, y):
        below = (y+1 < row) and qr.getpixel((x, y+1)) < 128
        return (qr.getpixel((x, y)) < 128) + below*2
    qr_str = ""
    for i in range(0, row, 2):
        qr_str += chars[0]
        for j in range(col):
            qr_str += chars[getPos(j, i)]
        qr_str += chars[0] + new_line
    print(chars[0]*49)
    print(qr_str, end='')
    print(chars[0]*49)

def terminalShowImage_tty(img):
    img = Image.open(io.BytesIO(img))
    qr = img.resize((47,47), Image.Resampling.NEAREST)
    qr = ImageOps.grayscale(qr)
    white = '\033[0;37;47m  '
    black = '\033[0;37;40m  '
    new_line = '\033[0m\n'
    col, row = qr.size
    qr_str = white * 49 + new_line
    for i in range(row):
        qr_str += white
        for j in range(col):
            qr_str += white if qr.getpixel((j, i)) > 128 else black
        qr_str += white + new_line
    qr_str += white * 49 + new_line
    print(qr_str)

def _android_data_dir():
    """Android(Kivy/python-for-android)下的可写目录

    - `ANDROID_PRIVATE` 是应用内部私有目录, 卸载才会清, 用来放 config/cookies;
    - 用户能看到的导出文件走 `ANDROID_PUBLIC`(通常是 /sdcard/Android/data/<包名>/files)。
    """
    for key in ("ANDROID_PRIVATE", "ANDROID_APP_PATH"):
        p = os.environ.get(key)
        if p:
            return p
    return None


def getDir():
    """返回"可写数据目录"（config.json / cookies.json / logs / aiexamAnswer 都放这里）

    - 源码运行: 脚本所在目录
    - PyInstaller 打包后: exe 所在目录
      （打包成 onefile 时 __file__ 指向临时解压目录 _MEIxxxx，往那里写的东西
        进程一退出就被删掉，所以必须改指 exe 自身所在目录）
    - Android(APK): 应用私有目录（沙箱内只有这里可写, 且会持久保留）
    - 若目录不可写（例如放在 C:\\Program Files 且无管理员权限），
      退回 %APPDATA%\\fuckZHS，避免写日志/存 cookie 直接崩掉
    """
    if "ANDROID_ARGUMENT" in os.environ or "P4A_BOOTSTRAP" in os.environ:
        d = _android_data_dir()
        if d:
            try:
                os.makedirs(d, exist_ok=True)
            except OSError:
                pass
            return d
    if getattr(sys, "frozen", False) and sys.platform != "android":
        base = os.path.dirname(os.path.abspath(sys.executable))
        if os.access(base, os.W_OK):
            return base
        fallback = os.path.join(
            os.environ.get("APPDATA") or os.path.expanduser("~"), "fuckZHS"
        )
        try:
            os.makedirs(fallback, exist_ok=True)
        except OSError:
            pass
        return fallback
    return os.path.dirname(os.path.realpath(__file__))

def getConfigPath():
    return os.path.join(getDir(), 'config.json')

def getRealPath(path: str):
    path = os.path.expanduser(path)
    path = os.path.expandvars(path)
    path = os.path.normpath(path)
    if path != os.path.abspath(path):
        path = os.path.join(getDir(), path)
    return os.path.realpath(path)

def versionCmp(v1:str, v2:str) -> int:
    v1 = v1.split('.')
    v2 = v2.split('.')
    for i1, i2 in zip(v1, v2):
        dt = int(i1) - int(i2)
        if dt:
            return dt
    return len(v1) - len(v2)

def terminal_width(default: int = 80) -> int:
    """当前终端列数, 拿不到时返回 default

    Android/iOS、nohup、重定向到文件时 `os.get_terminal_size()` 都会抛 OSError,
    统一从这里取值, 避免各处重复写 try。
    """
    try:
        return os.get_terminal_size().columns
    except OSError:  # no terminal (Android, PyCharm, 重定向)
        return default
    except Exception:
        return default


def wipeLine():
    print('\r' + ' ' * terminal_width(), end = '\r', flush=True)

def progressBar (iteration, total, prefix = '', suffix = '', decimals = 1,
                      length = None, fill = '#', progressbar_view:bool = True):
    """
    ### Call in a loop to create terminal progress bar
    * `iteration`   - Required  : current iteration (Int)
    * `total`       - Required  : total iterations (Int)
    * `prefix`      - Optional  : prefix string (Str)
    * `suffix`      - Optional  : suffix string (Str)
    * `decimals`    - Optional  : positive number of decimals in percent complete (Int)
    * `length`      - Optional  : character length of bar (Int)
    * `fill`        - Optional  : bar fill character (Str)
    """
    if not progressbar_view:
        return False
    if not length:
        length = terminal_width() - 4
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    prefix = f"{prefix} |"
    suffix = f"| {percent}% {suffix}"
    bar_len = length - len(prefix) - len(suffix)
    filled_len = int(bar_len * iteration // total)
    bar = fill * filled_len + ' ' * (bar_len - filled_len)
    print(f"\r{prefix}{bar}{suffix}", end = '\r')
    if iteration >= total:
        wipeLine()

# Converting requests.cookies.RequestCookieJar to list
def cookie_jar_to_list(cookie_jar: RequestsCookieJar):
    cookies_list = []
    for cookie in cookie_jar:
        cookie_dict = {
            'name': cookie.name,
            'value': cookie.value,
            'domain': cookie.domain,
            'port': cookie.port,
            'path': cookie.path,
            'expires': cookie.expires,
            'secure': cookie.secure,
            'rest': cookie.__dict__.get('_rest', {}),
            'version': cookie.version,
            'comment': cookie.comment,
            'comment_url': cookie.comment_url,
            'rfc2109': cookie.rfc2109,
            'discard': cookie.discard,
        }
        cookies_list.append(cookie_dict)
    return cookies_list

# Converting list to requests.cookies.RequestCookieJar
def list_to_cookie_jar(cookies_list: list[dict]):
    cookie_jar = RequestsCookieJar()
    for cookie_dict in cookies_list:
        cookie = create_cookie(
            name=cookie_dict['name'],
            value=cookie_dict['value'],
            domain=cookie_dict.get('domain', ''),
            port=cookie_dict.get('port', None),
            path=cookie_dict.get('path', '/'),
            expires=cookie_dict.get('expires', None),
            secure=cookie_dict.get('secure', False),
            rest=cookie_dict.get('rest', {'HttpOnly': None}),
            version=cookie_dict.get('version', 0),
            comment=cookie_dict.get('comment', None),
            comment_url=cookie_dict.get('comment_url', None),
            rfc2109=cookie_dict.get('rfc2109', False),
            discard=cookie_dict.get('discard', True),
        )
        cookie_jar.set_cookie(cookie)
    return cookie_jar