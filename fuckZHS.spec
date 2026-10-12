# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 —— 生成单文件、无控制台的 fuckZHS.exe

用法(一般不用手敲, 直接双击 build_exe.bat):
    pyinstaller --clean --noconfirm fuckZHS.spec

产物: dist/fuckZHS.exe (单个文件, 双击即用, 目标电脑无需安装 Python)
"""

from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = [], [], []

# config.example.json 必须打进包里：程序启动时会把它"播种"到 exe 所在目录，
# 否则用户第一次运行没有配置文件（push 通知等选项会缺失）。
# 这里**固定只带 config.example.json**（干净模板）：
#   - config.json 可能被用户填过账号密码/pushplus token，绝不能打进 exe
#   - cookies.json 是登录会话，同理
datas += [("config.example.json", ".")]

# tiktoken 带编译扩展 + 数据文件(token 词表), 必须整体收集,
# 否则运行时会报 "Couldn't find encoding ..." 而直接失败。
for _pkg in ("tiktoken", "tiktoken_ext"):
    try:
        _d, _b, _h = collect_all(_pkg)
        datas += _d
        binaries += _b
        hiddenimports += _h
    except Exception:
        pass

# 项目自身的模块: 它们在 gui.py 里是「函数内部 import」, 静态分析容易漏掉
hiddenimports += [
    "fucker", "ObjDict", "logger", "utils", "sign", "zd_utils", "push",
    "Crypto", "Crypto.Cipher", "Crypto.Cipher.AES", "Crypto.Util.Padding",
    "PIL.ImageTk", "PIL._tkinter_finder",
]

a = Analysis(
    ["gui.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 这些库本项目用不到, 排掉可以明显减小体积
    excludes=[
        "numpy", "pandas", "matplotlib", "scipy", "IPython", "jupyter",
        "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
        "pytest", "setuptools", "pip", "wheel",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="fuckZHS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 不弹黑色控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # 想换图标: 把 .ico 放进来并改成 'app.ico'
)
