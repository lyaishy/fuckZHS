# ZHS Fucker 食用指北

## NEWS

我总觉得有一天这个脚本会被 `404` ，没想到以这种形式实现了，感谢各位对鸽鸽的支持。
<img style="width: 100px;" src="https://github.com/VermiIIi0n/fuckZHS/assets/104612478/7a285df5-7ffb-4272-b26a-cfa4f079d506">

---

在 TG 上出现了倒卖开源代码的家伙, 其谎称有我的授权. [详见此处](https://github.com/VermiIIi0n/fuckZHS/discussions/19#discussioncomment-4168410).

本脚本是为人节约生命的, 不是增加负担的, 况且屎山代码我也不好意思卖, 倒卖就算了别说是我授权的, 丢不起这个脸![dragon](./images/dragon.jpg)

愿意支持的朋友点个 ☆ 就好, 叔叔我承诺本~~屎山~~脚本可能会下架, 但永不会变质.

---

## WTF?

这是一个 _Python3_ 的自动脚本, 用于自动刷智慧树课堂课程, 为您节约有限的生命.

### Features

- 支持校内学分课与知到共享学分课
- 自动回答弹题
- 设定时限
- 射后不管, 无需交互

---

## WHY?

自从智慧树的校内学分课(i.e. hike)播放页面用了个窒息的 _JavaScript_ 混淆之后, 大部分前端的脚本都没法用了.  
因为它会检查 _DevTools_ 是否打开, 如果打开了就无法继续运行, 要分析的话由于混淆, 解读很麻烦.  
于是我打算直接抄家, 入它后端(\*), 之后便有了该脚本. (虽然最后还是被逼着反混淆了前端代码...)

---

## 实用链接

- [版本更新注意事项](https://github.com/VermiIIi0n/fuckZHS/discussions/24)
- [常见问题](https://github.com/VermiIIi0n/fuckZHS/discussions/25)
- [讨论区](https://github.com/VermiIIi0n/fuckZHS/discussions)

---

## 准备工作

您还需要做以下准备:

- _Python3.10_ 及以上版本(或自行改写旧版不兼容的语法)
- 执行 `pip install -r requirements.txt` 安装依赖

---

## 图形界面（不想记命令就用这个）

本副本额外带了一个 Tkinter 界面, 独立于 `main.py`, 所有刷课动作都是复用
`fucker.Fucker` 的原有方法, 协议逻辑没有分叉。

- **Windows**: 双击 `start_gui.bat`
- **其他方式**: `py -3.12 gui.py`（需要一个带 `tkinter` 的 Python）

界面上能做的事:

- 扫码登录 / 复用 `cookies.json` 里保存的登录状态
- 一键拉取课程列表, 在列表里勾选要刷的课（**不勾选 = 刷全部**）
- 常用参数: 播放速度（**手动输入任意数值**）、单课时限、完成阈值、代理、目录视图、进度条
- 实时日志 + 进度条, 以及「停止」按钮（当前这一节跑完就退出）
- 被验证码拦住时会**弹窗提醒**, 并给出「去电脑端过验证码」的恢复步骤
- 「AI 课程」页签: 课程 ID / 班级 ID、跳过考试、答题用 AI 的选择
- 「导出日志」把日志区内容另存一份, 方便排查问题时发出来

界面选项存在 `gui_settings.json`; 拉课程列表时会顺带写好 `execution.json`,
所以**界面和命令行可以混着用**。

### 日志

界面上发生的每一件事都会记日志, 出口有两个:

- **界面日志区**: 操作记录 `[界面]`、脚本动作 `[执行]`、网络请求 `[请求]`、报错
- **日志文件**（都在 `logs/`）:
  - `gui.log` — **合并日志**, 按时间顺序把上面全部内容写在一起, 排查问题看这个最省事
  - `info.log` / `warning.log` / `error.log` / `debug.log` — 项目原本按级别拆分的日志
  - `gui-<时间戳>.log` — 点「导出日志」时另外存的快照

### 关于「播放速度」和 `code=-12`（验证码）

**这里的「播放速度」不是浏览器倍速。** 脚本的主循环是「每 1 秒真实时间, 把
`played_time` 加上 `speed` 秒, 然后每 30 秒把
`playTimes = played_time - last_submit` 上报一次」。所以 `speed=400` 意味着
**每 30 秒向服务器声称看了 400×30 = 12000 秒（3.3 小时）**.

真实浏览器最高只有 `1.25`（校内学分课）/ `1.5`（知到共享课）。这个值填得越高,
服务端越容易判定为异常, 于是 `saveDatabaseIntervalTimeV2` 返回 `code=-12`,
`fucker.py` 会把它转成 `CaptchaException`。

> **关于填多少**：速度**完全由你自己决定**, 界面不做任何拦截。
> 实测 `400` 可以正常刷（速度本身不必然触发风控）。留空 = 用网站最大值。

**这个脚本没有解验证码的能力**, 而且 `fuckZhidaoCourse` 内部就把这个异常吞掉了
直接 `return` —— 也就是说被要求验证码后, **这门课会立刻中断, 后面的视频一个都不会刷**,
并且状态会一直卡着, 反复重跑也没用（每次都停在同一个视频上）.

**被验证码拦住怎么办**（界面会自动弹窗提醒）:

1. 到**电脑**上登录智慧树（`www.zhihuishu.com`）。
2. 打开这门课 → 进入正在刷的那一节的播放页。
3. 手动播放一会儿, 把页面上弹出的验证码过掉（滑块 / 图形 / 短信等）。
4. 确认进度条在正常往前走, 然后回到本程序**再点一次「开始刷课」**, 就能接着刷。
   （已经刷上的进度不会丢, 不需要从头再来。）

界面现在能区分「跑完了」和「被验证码/时限中断」, 不会再把它误报成 `√ 完成`；
被验证码中断时会同时**写日志 + 弹窗提醒**（移动版和桌面版都有）。

日志覆盖的范围:

| 类别 | 内容 | 级别 |
|---|---|---|
| 操作 | 每次按钮点击、勾选的课程、填写的参数 | INFO |
| 执行 | `login` / `fuckCourse` / `fuckVideo` / `fuckAiCourse` / 拉列表 的开始、结束、耗时 | INFO |
| 请求 | 每一次 HTTP 请求的方法、接口、返回 code、耗时；失败则记下异常 | 成功=详细日志 / 失败=WARNING |
| 出错 | 完整异常信息（含 traceback 进 `debug.log`） | ERROR |

两个开关（在按钮行右侧）:

- **详细日志（每次网络请求）**: 默认**开**。关掉后逐条请求日志降到 DEBUG,
  界面上只看得到课程/视频级别的进度, 日志文件里依然完整。
- **调试日志（含账号密码，勿外传）**: 默认关。开启后项目内部所有 DEBUG 日志
  （**包含账号密码、cookie 等敏感信息**）都会写进 `logs/`。

---

## 如何使用

因登陆验证改变**目前仅有二维码登陆可用**

本块分为

0. Ultra Quick Start: 执行 `python main.py`

   - 仅以交互输入信息, 除非开 DEBUG 模式否则不留任何敏感记录

1. `Login`: 输入账号与密码

   - 使用配置文件
   - 使用命令行参数

2. `Fxxking`: 开干

   - 使用命令行参数
   - 拉清单
   - 参数列表

3. `API` 简易文档: 用于单独使用模块

### Login

_\*如果非常用地登入（可能？）会需要短信验证, 您应该先用浏览器登入一次, 以让您的所在地列入白名单。_  
 _\*\*信息优先级: 命令行 > 配置文件 > 交互输入_

### 使用配置文件

配置文件 _config.json_ 中有以下字段:

```JSON
{
  "username": "",
  "password": "",
  "qrlogin": true,
  "save_cookies": true,
  "proxies": {},
  "logLevel": "INFO",
  "tree_view": true,
  "progressbar_view": false,
  "qr_extra": {
      "show_in_terminal": null,
      "ensure_unicode": false
  },
  "image_path": "",
  "pushplus": {
      "enable": false,
      "token": ""
  },
  "bark": {
      "enable": false,
      "token": "https://example.com/xxxxxxxxx"
  },
  "config_version": "1.3.0"
}
```

- `username`: 账号
- `password`: 密码
- `qrlogin`: **目前强制启用**二维码登陆, 方便在服务器上部署, 优先级高于账号密码
- `proxies`: 代理, 可留空, 在 _Windows_ 上还可解决 _Clash_ 等代理造成的证书错误, 详见 [_常见问题_](https://github.com/VermiIIi0n/fuckZHS/discussions/25)
- `logLevel`: 日志等级, 可选 `NOTSET` `DEBUG` `INFO` `WARNING` `ERROR` `CRITICAL`
- `save_cookies`: 保存cookies，*短时间*内可以自动登录。
- `tree_view`: 课程目录结构，关闭后不显示所有课程目录。
- `progressbar_view`: 进度条控制，关闭后不显示当前视频进度。
- `image_path`: 登录二维码保存路径，留空则不保存。
- `qr_extra`: QR 相关配置
  - `show_in_terminal`: 将二维码打印至终端
  - `ensure_unicode`: 仅使用 Unicode 字符打印二维码
- `pushplus`: 基于 [pushplus](https://www.pushplus.plus) 的推送服务
  - `enable`: 启用推送
  - `token`: 推送 token
- `bark`: 基于 [bark](https://github.com/Finb/Bark) 的推送服务
  - `enable`: 启用推送
  - `token`: 推送 token，例如：`https://api.day.app/xxxxxxxxxxxxx`

~~填入账号密码即可无干预自动登入~~ **当前失效**  
 _\*配置文件如果没有的话会在 main.py 执行时自动创建._

### 使用命令行参数登入

```bash
python main.py -u <username> -p <password>
python main.py -q
```

- `-u` `--username`: 账号
- `-p` `--password`: 密码, 要注意密码将会明文留在记录中, 故不推荐使用 `-p` _\*虽然说这破站密码泄漏就泄露吧, 写配置文件里多方便, 俗话说晚泄不如早泄(¿)_
- `-q` `--qrlogin` : 启用二维码登陆

---

### Fxxking

### 命令行指北

**以下假设您已经在配置文件中输入必要信息**  
 _\*信息优先级: 命令行 > 配置文件 > 交互输入_

```bash
cd fuckZHS
python main.py # 如果 execution.json 不存在的话, 刷所有课
# 只刷课程 ID 为 114514 和 1919180 的课
python main.py -c 114514 1919180
# 想秒过可以设个很高的 SPEEEED
python main.py -s 444 # 我就感觉到快, 有种催人ban的感觉
# 又或者可以限制每节课学习25分钟
python main.py -c 114514 -l 25
# 遇到问题想开 debug 模式, 顺带加个代理?
python main.py -c 114514 -d --proxy http://127.0.0.1:2333
# 又比如您想只干某几个视频, 那您可以使用 -v 传入视频 ID
python main.py -c 114514 -v 1989 604
# 刷ai课程，ai课程号为 114514，classId为 4444
python main.py -ai 114514 4444
```

什么？不知道课程 ID 或视频 ID? 进入课程界面就可以在网址里看到了.  
 _\*课程 ID 为网址中的 `courseId`(校内学分课) 或 `recruitAndCourseId`(共享学分课) 参数_  
 _\*\*更多选项请使用 `-h` 查看._

### 拉清单

使用 `--fetch` 参数可从服务器获得所有课程清单, 存储到 _execution.json_ 这个小本本里, 您可以删去不想干的课程  
当该文件存在且没有指定课程 ID 时, 会先看看这个小本本上有没有写着课程 ID  
_\*清单中 `id` 参数是必须的, 想额外拉清单时请注意_  
_\*\*修改时请注意 JSON 语法, 不然 Exceptions 会一下突开到脸上_

```bash
python main.py --fetch
```

清单示例:

```JSON
[
    {
        "name": "中国近现代史",
        "id": "42"
    },
    {
        "name": "思想道德与法治",
        "id": "1919"
    }
]
```

### 命令行参数列表

- `-c`, `--course`: 课程 ID, `courseId` 或 `recruitAndCourseId`, 可输入多个
- `-v`, `--videos`: 视频 ID, `fileId` 或 `videoId`, 可输入多个
- `-u`, `--username`: 账号
- `-p`, `--password`: 密码
- `-q`, `--qrlogin`: 二维码登录，目前**强制开启**
- `-s`, `--speed`: ~~**POWERR AND SPEEEEED!**~~ 指定播放速度, 想要秒过可以设个很高的值(e.g. 644), 但不推荐. 默认为浏览器观看能到的最大值
- `-t`, `--threshold`: 完成时播放百分比, 高于该值视作完成, 想要重复刷课可以使用大于 `1.0` 的值, 例如 `2.0` 则会再刷一遍
- `-l`, `--limit`: 单节课的时限, 如果您看得上内点习惯分就用吧
- `-d`, `--debug`: 调试级日志记录, 会记录请求到日志 **_(可能包含账号密码, 别乱分享, 当心被盒武_**
- `-f`, `--fetch`: 获取课程清单并存入 _execution.json_ 文件
- `--show_in_terminal`: 将二维码打印至终端
- `--proxy`: 代理设置, 本来用来调试的(e.g. <http://127.0.0.1:8080>)
- `--tree_view`: 课程目录结构，关闭后不显示所有课程目录。
- `--progressbar_view`: 进度条控制，关闭后不显示当前视频进度。
- `--image_path`: 登录二维码保存路径，留空则不保存。
- `-ai`, `--aicourse`: AI课程, Input AI Course ID and CLASS ID to fu*k aiCourse
- `-h` `--help`: 显示帮助

运行示例如下:
![运行示例](./images/running.png)

指北就这些啦, ~~代码很少可以自己看~~ 现在不少了().

---

### `API` 简介

详见源码

#### 实例化 `Fucker`

```Python
from fucker import Fucker

fucker = Fucker()
# 或者更进阶一些
fucker = Fucker(speed=1.5, end_thre=0.91)
# 以上控制播放速度以及终止临界值
# speed: 校内学分课播放速度正常最高为1.25, 共享学分课为1.5, 但似乎更高的服务器也接受, 不过怕暴露就谨慎些吧
# end_thre: 智慧树把高于一定百分比的进度视为完成, 0.91 保险一点
# 以上俩参数仅对视频有效, 其他的内容就只有进度0或1
```

### `login` Method

如果您能自己得到 `Cookies` 就可以略过, 直接给 `Fucker` 实例的 `cookies` 属性赋值即可
_Python3_ 登入样例

```Python
fucker.login(username:str, password:str)
fucker.login(username:str, password:str, interactive=False) # 禁用交互, 在账号或密码为空时引发异常

# 如果您不想使用 login
# 也可直接传入符合 requests 库要求的 cookies
fucker.cookies = {key: "Angel Beats!", "inside Uncle's eyes": value}
# 该 cookies 会覆盖原有值, 同时请确保它是完整的智慧树 cookies，因为 uuid 需要从 cookies 中解析
```

### `fuckCourse` Methods Family

```Python
fucker.fuckCourse(course_id:str) # 把整个课程都干了
fucker.fuckCourse(course_id:str, tree_view=False) # 把整个课程都干了, 但不显示树状视图
fucker.fuckZhidaoCourse(recruitAndCourseId) # 点名就要干知到共享学分课
fucker.fuckHikeCourse(courseId) # 点名就要干校内学分课(hike)
```

### `fuckVideo` Methods Family

```Python
fucker.fuckVideo(course_id, video_id) # 指定干某节课里某视频
fucker.fuckZhidaoVideo(recruitAndCourseId, videoId) # 这里的 videoId 是从 网页API响应 中获得的
fucker.fuckHikeVideo(courseId, fileId) # 这俩就在 校内学分课(hike) 网址里
```

### `getContext` Methods Family

```Python
fucker.getZhidaoContext(recruitAndCourseId)
fucker.getHikeContext(courseId)
fucker.getHikeContext(courseId, force=True) # 强制更新context并重置课程学习时间(本地记录)
'''
自动在 `fuck*Course` `fuck*Video` 中被调用
返回一个 `dict`, 内含该 ID 对应课程的必要信息以及实例运行后学习该课的总时间, 必要信息没有的话会向服务器请求
该 `dict` 结构请见源码
'''
```

### `hike` API

```Python
# 自动添加时间戳和签名, 并检查返回代码
def hikeQuery(self, url:str, data:dict,sig:bool=False, ok_code:int=200, setTimeStamp:bool=True, method:str="GET")...
# 以下为与网页接口同名的 API, 只返回响应中的 "rt" 部分
def queryResourceMenuTree(self, course_id)...
def stuViewFile(self, course_id, file_id)...
def saveStuStudyRecord(self, course_id, file_id, played_time, prev_time, start_date)...
```

### `zhidao` API

```Python
# 自动添加时间戳和加密, 并检查返回代码
def zhidaoQuery(self, url:str, data:dict, encrypt:bool=True, ok_code:int=0, setTimeStamp:bool=True, method:str="POST", key=VIDEO_KEY)...
# 以下为与网页接口同名的 API, 只返回响应中的 "data" 部分
def gologin(self, RAC_id)...
def queryCourse(self, RAC_id)...
def videoList(self, RAC_id)...
def queryStudyReadBefore(self, course_id, recruit_id)...
def queryStudyInfo(self, lesson_ids:list, video_ids:list, recruit_id)...
def queryUserRecruitIdLastVideoId(self, recruit_id)...
def prelearningNote(self, RAC_id, video_id)...
def loadVideoPointerInfo(self, RAC_id, video_id)...
def lessonPopoupExam(self, RAC_id, video_id, question_ids:list)...
def saveLessonPopupExamSaveAnswer(self, RAC_id, video_id, question_id, answer_ids:str)...
def saveDatabaseIntervalTime(self, RAC_id, video_id, played_time, last_submit, watch_point, token_id=None)...
def saveCacheIntervalTime(self, RAC_id, video_id, played_time, last_submit, watch_point, token_id=None)
```

---

## 结构介绍

### 文件结构

- main.py: 命令行主函数
- sign.py: 负责生成 hike API 所需的 `signature` 参数
- utils.py: 一些常用工具
- logger.py: 日志工具, 将不同等级的日志写入不同文件
- fucker.py: `Fucker` 类定义, 所有核心代码全塞一起了, 莫在意
- ObjDict.py: `ObjDict` 类定义, 继承自 `dict`, 可以 `object` 属性形式访问 `dict`
- zd_utils.py: 知到 API 所需的工具, 如生成 `ev` 和 `secretStr`
- config.json: 还能是啥, 没有的话初次运行 _main.py_ 时将生成
- meta.json: 包含版本和分支等信息, 也用于更新检查
- decrypt: 非必要的文件夹, 内含逆向源代码的工具及源码打包

### Fucker Class Structure

```Python
class Fucker:
    def __init__(self, cookies: dict = None,
                 headers: dict = None,
                 proxies: dict = None,
                 limit: int = 0,
                 speed: float = None,
                 end_thre: float = None)...

    @property # cannot directly manipulate _cookies property, we need to parse uuid from cookies
    def cookies(self)...
    @cookies.setter
    def cookies(self, cookies: dict|requests.cookies.RequestsCookieJar)...

    def login(self, username: str=None, password: str=None, interactive: bool=True)...
    def fuckCourse(self, course_id:str, tree_view:bool=True)...
    def fuckVideo(self, course_id, video_id:str)...
############################################
# for some fucking reasons
# there are 2 sets of completely different API for hike.zhihuishu.com and studyservice-api.zhihuishu.com
# so we need to use different methods for different API
#############################################
# following are methods for studyservice-api.zhihuishu.com API
    def getZhidaoContext(self, RAC_id:str, force:bool=False)...
    def fuckZhidaoCourse(self, RAC_id:str, tree_view:bool=True)...
    def fuckZhidaoVideo(self, RAC_id, video_id)...
    def answerZhidao(self, q:dict)...
    def _zhidaoQuery(self, url:str, data:dict, encrypt:bool=True, ok_code:int=0,
               setTimeStamp:bool=True, method:str="POST")...
# end of zhidao methods
#############################################
# following are methods for hike API
    def getHikeContext(self, course_id:str, force:bool=False)...
    def fuckHikeCourse(self, course_id:str, tree_view:bool=True)...
    def fuckHikeVideo(self, course_id, file_id, prev_time=0)...
    def fuckFile(self, course_id, file_id)...
    def _traverse(self,course_id, node: ObjDict, depth=0, tree_view=True)...
    def _hikeQuery(self, url:str, data:dict,sig:bool=False, ok_code:int=200,
                   setTimeStamp:bool=True, method:str="GET")...
# end of hike methods
#######################################
# shared private methods
    def _watchVideo(self, video_id)... # it's probably unnecessary but let's keep it to fool those idiots
    def _apiQuery(self, url:str, data:dict, method:str="POST")...
    def _checkCookies(self)...
    def _checkTimeLimit(self, cid)...
    def _sessionReady(self, ctx:dict=None)...
```

我的很大, 你忍一下(指类定义)

---

## 后记

这一段算是授之以渔吧, 毕竟网站以后更新可能会改内容, 我又没时间更新, 就先把思路写在这. 但要注意, 下文提到的混淆肯定引入了随机量, 不可完全照搬该思路.  
过程中用到的文件样本大多都在 _decrypt_ 目录下压缩档里.

**_以下内容仅针对校内学分课的 `API` ("hike" 开头的域名)_**

### Chapter 0: Too Young Too Naive

本以为从后端入手会很轻松, 目前绝大部分的脚本是在前端实现刷智慧树自动化(有例外但那些都不是对付校内学分课的), 这样做不仅鲁棒性很差而且过于复杂, 本脚本则直接绕后, 甩开前端, 可以做到不变应万变...吧?

#### 捉包

总之先捉个包看看前端怎么和服务器交流, 没想到一开浏览器开发者模式就遇到了问题.  
一旦监测到 _DevTools_, 网页界面就立即停止响应.  
但这还不简单, 手动把相关 _JavaScript_ 无脑删不就行, 源码都在我手上有什么好怕的.

紧接着一看源码:

![WTF](./images/wtf.png)
_好家伙《乱码 1/2》_

不过这也没什么, 我本来就只是想抓个包, 用别的工具就是了.

抓包得到页面向服务器报告进度的甜言蜜语:  
`Headers`:
![headers](./images/headers.png)

`Params`:
![params](./images/params.png)
_\*敏感信息被替换了_  
您看看这些人多不专业, 拿 `GET` 干 `POST` 的活, 而且那个 `uuid` 根本就不是真的 UUID, 七八个随机字符而已.

#### 模拟请求

不过我们一路顺风, 成功就在眼前(flag++).  
这时可以看到一个正常的响应是:

```JSON
{
  "status": 200,
  "message": "OK",
  "rt": 202
}
```

`rt` 是服务器返回的观看进度.

包里大部分参数都很直接, 我们照搬便是.  
`courseId` 我们可以从浏览器链接里得知,  
`fileId` 每个章节的都不一样, 可以从“<https://studyresources.zhihuishu.com/studyResources/stuResouce/queryResourceMenuTree>” 中获取的 JSON 中得到, 源码里有, 不再赘述.

剩下只有 `signature` 不明, 不过大概是个防止多次提交的随机字符串罢了, 毕竟这群人取名似乎一直不太准确.

然后一试

```JSON
{
  "status": 200,
  "message": "OK",
  "rt": null
}
```

**???**  
为何就返回个 `null`, 为了解决这个问题我快把浏览器内核用 _Python_ 实现了, 一直以为就是个 `Headers` 或者 `Cookie☆` 的问题, 我可能缺了什么.  
结果最后才发现问题在 `Params`, 而且就是里面那个该死的 `signature` 造成的.  
这次他们取对名字了, 这真是个签名, 必须和其他内容配套才能被视作合法请求, 并得到 `rt`.  
想要自己生成这个 `MD5` 签名就只能从前端代码里找 salt 等数据.

没办法, 开始人生第一次反混淆 _JavaScript_ 吧...

---

### Chapter 1: At Beginning, It's Just Chaos

下图开头这个站点名就是万恶之源了, 话说为什么叫“加密”, 只是混淆而已, 和加密相差太远了, 只能说连名字都取的很 Obfuscated.

首先得把这些诡异变量重命名一下, 在 [_这个站点_](https://deobfuscate.io) 可以初步反混淆, 去掉一些简单的函数 wrapping 并重命名变量, 新变量名当然是随机的, 只是好读一些.

#### 初步反混淆

![level0](./images/level0.png)
这下好多了, 我们可以看 **_不_** 到开头有一行超大的列表(太长了就只截了前几个), 不过它大概有 1.4k 个**字符串**,  
看起来是 Base64, 解码后是乱码, 是被加密了(真·加密).

再观察一下可以发现一个函数出现的次数很多:
![mapping](./images/mapping.png)
这个 nyko 便是负责解密的函数.

要反混淆 nyko 就需要手动去掉一堆无用的循环和分支, 不然真读不下去.  
恶心的是这个混淆后版本里充斥着各种看起来有意义的字符串, 甚至有些就是混淆前代码里的, 但他们被拿来进行无意义的比较和循环, 这样做可以同时迷惑您和您的 CPU.

总之反混淆出来是这样一个简单的解密程式, 用 _Python_ 重新实现了:

```Python
def decrypt(index:str, key:str):
    index = int(index, 16)
    encrypted = b64dec(table[index])
    key = key.encode()

    mod_sum = 0
    ar = list(range(256))
    for i in range(256):
        mod_sum = (mod_sum + ar[i] + key[i % len(key)]) % 256
        ar[i], ar[mod_sum] = ar[mod_sum], ar[i]
    mod_sum = 0
    n = 0
    decrypted = ""
    encrypted = encrypted.decode()
    for i in range(len(encrypted)):
        n = (n + 1) % 256
        mod_sum = (mod_sum + ar[n]) % 256
        ar[mod_sum], ar[n] = ar[n], ar[mod_sum]
        decrypted += chr(ord(encrypted[i]) ^ ar[(ar[mod_sum] + ar[n]) % 256])
    return decrypted
```

_JavaScript_ 原版其实在 Base64 解码后, 还有个手动把内容 URLEncode 了, 又调用 `decodeURIComponent` 解码的诡异操作.  
一开始我把它删了, 结果竟然生成内容不一样. 似乎是 _JavaScript_ 的 `atob` 似乎会保留非法的内容? 经过看似无意义的 URL Encode&Decode 会把这些字符丢弃掉, 只能说混淆者真是钻研了折磨人的极致了, 好在 _Python_ 的 `b64decode` 默认丢弃这些内容. _\*此部分存疑, 不确定原因是不是这个_

接下来尝试对列表内容解密, 发现还是乱码...

没办法, 只得继续化简开头的函数, 看看会有什么线索.  
接着发现程式开头有一段循环, 把列表开头和结尾的俩无意义的东西扔了, 顺带把这个列表旋转了 138 位, 用 _Python_ 表示就是 `deque.rotate(-138)`  
这个值是好像是固定的, 但保不准以后会变

#### 解读解密后代码

解密并替换内容后的文件:
![level2](./images/level2.png)

解密之后常量已经可以看到了, 但其中仍有很多垃圾信息.  
比如其中有类模式, 就是混淆版本会在一个 `Object` 内包装一堆简单的函数, 比如加减和比较, 然后取个无意义的名字.  
结合那一堆无意义的变量来做比较判断, 以此来表示单个 `Boolean` 值.  
因为嵌套的次数太多所以自动反混淆没能解决它们, 但只要搞清这点可以手动去掉很多无意义的分支.

```JavaScript
var Wtf = {
       RvuT: function (dyo, bie){
       return dyo === bie;
       },
       oPhT: function(Jely, Inp, Stb){
       return Jely(Inp, Stb)
       },
       stEbU: "d0gky", RlVDj: "rk8Eb"
    }
if (Wtf.oPhT(Wtf.RvuT,Wtf.stEbU,Wtf.RlVDj){
    console.log("WTF");
    }

//以上这一大坨， 也就等价于
if (false){
  console.log("who cares what I've logged");
  }

//也就等价于
//do fucking nothing but consuming your CPU, storage, network bandwidth and god damn time

```

---

### Chapter 2: Let There = Light

总算看见曙光了, 但要继续解读的话, 这些乱码的函数名字太难读了, 以功能来重新命名吧, 顺便去掉无用的, 重复的部分:

![level3](./images/level3.png)

怎么说呢, 虽然是很繁琐的一件事, 但看着大批大批代码被删有种莫名的快感, 我当游戏玩了一久.

玩得差不多的时候突然想起来我好像不必把所有代码反混淆, 找到 `MD5` 相关的代码就好啊.  
现在代码也只有一千多行了, 挺好找的才是.  
随手一翻发现:

```JavaScript
function jobany(params) {
      var lennora = kenshin.ADD(kenshin.ADD(
        kenshin.ADD(kenshin.ADD(kenshin.ADD(
          kenshin.ADD(kenshin.ADD(kenshin.ADD(
            kenshin.ADD("o6xpt3b#Qy$Z", params.uuid
          ), params.courseId),  params.fileId
        ), params.studyTotalTime),  params.startDate
      ), params.endDate),  params.endWatchTime
    ), params.startWatchTime),  params.uuid);
      console.log(lennora);
      return kenshin.APPLY($md5, lennora);
    }
```

~~_"Here↘ comes ↗Jobany~"_~~  
诶嘿, 改函数名有效果了, 是**盐**! 它加了**盐**! (顺带特想吐槽下这个自动生成的对象名 `kenshin`，挺中二)

**盐**(bushi):
![Shio](./images/Shiochan.webp)

---

### Chapter 3: small step, Giant Leap

为了个区区 `signature` 废了好大功夫  
不过有了这个我们可以自己签名了, 没想到人都这么大了还靠在自己作业上签名来骗人

```Python
from hashlib import md5
from ObjDict import ObjDict # 这是一个我从 dict 继承后魔改的玩意儿，可以用 JavaScript 风格访问 dict

SALT = "o6xpt3b#Qy$Z"

def sign(p:dict):
    p = ObjDict(p)
    raw = SALT + p.uuid + p.courseId + p.fileId + p.studyTotalTime + \
           p.startDate + p.endDate + p.endWatchTime + p.startWatchTime + p.uuid
    return md5(raw.encode()).hexdigest()
```

我们也算是**努力**的**靠自己**完成作业了

![1000%](./images/1000.png)  
~~_已经 1000%了()_~~

---

给把如此凌乱的内容看到最后您一些安慰吧  
祝您学习像 Anya 一样好, 料理如 Yor 一般出色!
![bonus](./images/bonus.jpg)
(sauce: Pixiv; pid:[97128620](https://www.pixiv.net/en/artworks/97128620)) **_放 GitHub 仓库不能算转载吧?_**

---

## 本副本的改动记录

上游版本 `2.6.3`。以下改动只修明确的逻辑错误, 以及新增图形界面;
**签名算法、AES 密钥、上报节奏等协议逻辑一律未动**。

### 新增

- `gui.py`: Tkinter 图形界面（见上文「图形界面」）
- `start_gui.bat`: Windows 双击启动器
- `gui_settings.json`: 界面选项持久化（自动生成）
- `logs/gui.log`: 界面 + 脚本的合并日志（按时间顺序，自动生成）

### 修复

| 位置 | 问题 | 影响 |
| --- | --- | --- |
| `main.py` | `args.videos` 边遍历边 `remove` | 一门课拥有多个目标视频时, **只会刷第一个**, 其余被静默漏掉 |
| `main.py` | `--tree_view` / `--progressbar_view` 用 `type=bool` | 传 `False` 得到字符串 `"False"`(真值), 开关反而被打开 |
| `main.py` | `tree_view = args.x or config.x` | 命令行传 `False` 会被配置里的 `True` 覆盖, 关不掉 |
| `main.py` | `qrlogin = args.qrlogin or config.qrlogin or True` | 恒为真, 掩盖了「账号密码登录已失效」这一事实; 现在显式固定为二维码并给出提示 |
| `main.py` | `--noexam` 用 `type=bool` | 同 boolean 参数问题, 已统一为 `strToBool` |
| `fucker.py` | `fuckAiCourse` 里 `os.get_terminal_size()` 未兜底 | 输出重定向 / `nohup` 下直接崩溃（其他方法都有 try 兜底） |
| `fucker.py` | `fuckZhidaoVideo` 先读字段再判空 | 视频不存在时抛 KeyError 而不是清晰的 ValueError |
| `fucker.py` | `PptToTxt` 用 URL 路径拼本地下载路径 | 存在路径穿越（URL 里带 `../` 可写到下载目录之外）; 现改为只取 basename + URL 哈希前缀 |
| `push.py` | `http://` 且 content 未做 URL 编码 | 推送内容含 `&` 或中文时参数被截断 / 乱码 |
| `push.py` | bark 用 `quote()` 默认 `safe='/'` | 标题含 `/` 时会把 URL 路径结构撑开 |
| `push.py` | 推送失败会向上抛异常 | 推送失败反而打断刷课主流程, 现已吞掉异常并打印提示 |

### 行为变化（请注意）

- `--tree_view` / `--progressbar_view` 现在**优先级为 命令行 > 配置文件 > 默认值**。
  不带参数时行为与原来一致。
- 推送改用 `https`（pushplus），失败只提示不中断。

### 第二轮：扫码登录两个 bug + 全量日志

| 位置 | 问题 | 影响 |
| --- | --- | --- |
| `gui.py` `QrWindow` | 二维码标签用 `width=44, height=20` 创建（**字符**单位）, 一旦 `configure(image=...)`, Tk 改按**像素**解释这两个值 | 280×280 的二维码被裁成约 44×20 像素, 看起来就是**没有二维码** |
| `gui.py` `QrWindow.close` | 只 `destroy()` 窗口, 不通知主程序 | `busy` 永久为 `True`、`qr_window` 悬空、登录线程仍在后台轮询 → **再点「扫码登录」没有任何反应** |
| `gui.py` `on_login` | 建窗口 / 起线程没有异常兜底 | 任何一步抛异常都会让 `busy` 卡住, 之后所有按钮全部点不动 |
| `gui.py` `_qrlogin` 轮询 | 轮询走 `self.session.get`, 不经 `_apiQuery`, 停止钩子覆盖不到 | 关掉二维码窗口后后台仍会继续请求直到二维码过期 |
| `gui.py` `_worker_run` | 在工作线程里读 `StringVar`/`Listbox` 等 Tk 对象 | 跨线程访问 Tk, 属于隐患（现在改为在主线程取好参数再传进去） |
| `gui.py` | 只有 `Exception` 才会被记到界面 | `StopRequested` 等 `BaseException` 会让线程静默死掉, 界面永远等不到结果 |

修复方式: 二维码标签改为按自然像素尺寸显示（260×260）+ 居中对齐到主窗口并短暂置顶;
关窗改为「作废本次登录」——触发取消事件、复位 `busy`、递增代次丢弃过期消息;
给 `session` 的 HTTP 动词挂停止检查, 使取消能在 0.5 秒内生效;
所有按钮回调统一包一层异常外壳; 所有线程统一捕获 `BaseException` 并记录完整 traceback。

### 实测结果

- 二维码渲染尺寸: 修复前 **48×24 像素** → 修复后 **260×260 像素**
- 关闭窗口 → `busy=False`、登录线程 **0.51 秒**内退出、立刻可以重新扫码登录
- 连续「打开 → 关闭 → 再打开」3 次, 每次都正常出码
- session 停止钩子: 停止状态下请求被拦下; 未停止时不误伤（真实请求正常发出）
- 日志: `logs/gui.log` 按时间顺序记录 界面操作 / 执行动作 / 网络请求 / 报错

### 第三轮：速度手动输入 / 撤掉速度警告 / 验证码提醒 / 日志补全

| 位置 | 改动 | 说明 |
| --- | --- | --- |
| `gui.py` | `_confirm_speed` → `_note_speed` | 删掉「速度偏高」确认弹窗, 改为只记一条日志。**速度不再被拦截**（实测 400 可用） |
| `gui.py` | 速度输入框提示文案 | 改为「留空 = 网站最大值（1.25 / 1.5）；可手动填任意数值，如 400」 |
| `gui.py` | `_abort_help("captcha")` | 重写为「去**电脑**端过的分步指引」, 不再归因于速度 |
| `gui.py` | 新增队列消息 `("alert", title, text)` | 被验证码拦住时在主线程**弹窗提醒**（messagebox 只能在主线程调用） |
| `mobile_core.py` | `SPEED_WARN_ABOVE` / `SPEED_BROWSER_MAX` 删除 | `check_speed()` 只做「非数字 → 按留空处理」, 恒返回 `True` |
| `mobile_core.py` | 新增 `captcha_alert_text()` / `CAPTCHA_ALERT_TITLE` | 验证码提醒文案统一出口 |
| `mobile_core.py` | 新增 `Core.act()` | 与桌面版 `_act` 对齐, 所有按钮点击都留痕 |
| `mobile_core.py` | `glog()` 写文件时补时间戳与级别 | 桌面版与手机版的日志格式统一为 `时间 [级别] 内容` |
| `gui_mobile.py` | `Slider` → `TextInput(input_filter="float")` | 播放速度改为**手动输入**任意数值 |
| `gui_mobile.py` | 新增 `AlertPopup` | 验证码提醒弹窗 |
| `gui_mobile.py` | 布局改为 `size_hint_x=1` 自适应 | 去掉写死的 `dp(306)` / `dp(348)` 宽度; 修复「课程名偏右」、卡片高度不合理 |
| `gui_mobile.py` | `FlatButton` 加描边 + `disabled_color` | 修复「停止」按钮在浅色底上几乎隐形 |
| `gui_mobile.py` | 三个 `StringProperty` 补绑定 | 修复 `登录状态 / 课程数 / 状态栏` **永远不刷新**的 bug（`vlabel` 只写了一次 `text`） |
| `gui.py` + `mobile_core.py` | 成功日志前缀 `✓` → `√` | `✓`(U+2713) 在 CJK 字体里缺字, 手机上显示成方框 |

> 顺带修掉一个一直存在、但没被发现的 bug：`gui_mobile.py` 里
> `login_label` / `course_label` / `status_label` 是用 `vlabel(self.xxx_text, ...)` 建的，
> 而 `vlabel` 只在构造时写一次 `text`，没有绑定 Kivy 属性。
> 于是这三个位置**从头到尾都停在初始值**（"未登录" / "我的课程" / "就绪"），
> 现在都补上了 `self.bind(<prop>, ...)`。

### 实测结果（第三轮）

- `mobile_core` 单测: 速度 `400 / 3.5 / abc / 留空 / None` **全部放行**, `abc` 只给纠正提示
- 移动端界面回归 `tests/test_mobile_ui.py`: **18/18 通过**
  （布局无溢出、速度手动输入、无速度弹窗、alert 弹窗、日志回流、busy 联动、课程渲染）
- 端到端 `tests/test_mobile_e2e.py`: **11/11 通过**
  （`speed=400` 真的传到 fucker、验证码中断触发弹窗、日志含电脑端恢复指引、留空 → `speed=None`）
- 桌面版 `gui.py --selftest` → `SELFTEST OK`; 打包后的 `dist/fuckZHS.exe --selftest` → `SELFTEST OK`
- 界面渲染实测（`tests/make_mobile_preview.py`）: 见 `手机版界面预览.png`


---

## 打包成 exe 发给别人（对方无需安装 Python）

### 一键打包

双击 **`build_exe.bat`**，等 2~5 分钟，产物在 `dist\fuckZHS.exe`（单文件，约 31 MB）。

脚本做的事：
1. 找一个带 tkinter 的 Python 3.10+；
2. 建一个独立环境 `.buildenv`（`--system-site-packages`，继承已装依赖，**不动系统 Python**）；
3. 在里面装 PyInstaller，按 `fuckZHS.spec` 打包。

想手动打包也可以用：
```bat
.buildenv\Scripts\python.exe -m PyInstaller --clean --noconfirm fuckZHS.spec
```

### 打包前必须知道的一个坑

原来的 `utils.getDir()` 和 `gui.py` 的 `ROOT` 都用 `__file__` 定位数据目录。
打成 onefile 后 `__file__` 指向临时解压目录 `_MEIxxxxxx`，往那里写的
`cookies.json` / `logs/` **进程一退出就被删掉**，表现就是"每次打开都要重新扫码"。

现已改为「打包感知」：

| 运行方式 | 可写数据目录 |
| --- | --- |
| 源码运行（`py gui.py`） | 脚本所在目录 |
| exe 运行 | **exe 所在目录** |
| exe 目录不可写（如 `C:\Program Files`） | `%APPDATA%\fuckZHS` |

`utils.getDir()` 与 `gui.py::_resolve_root()` 两处规则保持一致，别只改一处。

### 其他打包相关的改动

- `fucker.py` 的 `tiktoken.encoding_for_model("gpt-4")` 需要 `tiktoken_ext`，
  spec 里用 `collect_all` + PyInstaller 内置 hook 一起收进去了；
  词表文件是**首次使用时联网下载**的，属正常（本工具本来就要联网）。
- `gui.py` 新增 `_ensure_std_streams()`：无控制台模式下 `sys.stdout` 为 `None`，
  不补一个空实现的话 `print` 会直接抛异常。
- `gui.py` 新增 `_fatal()` + `sys.excepthook`：窗口模式下崩溃不再是"闪退"，
  而是弹窗提示 + 写入 `crash.log`。
- spec 里 `excludes` 掉了 numpy/pandas/matplotlib 等用不到的库来瘦身。

### 交付给"电脑小白"

`dist\fuckZHS-发给小白.zip` 里只有两样东西：

- `fuckZHS.exe` —— 双击即用；
- `发布说明.txt` —— 面向零基础用户的图文说明（解压、蓝色弹窗放行、扫码、速度别乱填、看 logs）。

另外提醒：微信/QQ/邮箱常直接拦截 `.exe`，所以发 **zip** 比发裸 exe 更容易成功。
注意**不要**把自己的 `cookies.json` 一起发出去（那是你的登录状态）。

---

## 安卓版（Kivy + Buildozer）

桌面版（`gui.py`）在安卓上**跑不起来**，也**不该**跑：它依赖 Tkinter（python-for-android
的 tkinter 支持基本不可用），而且用了标签页 + 树形列表 + 固定 1040×800 窗口，
在手机上完全不成立。所以安卓版是**单独的一层**，桌面版一行未动。

### 文件分工

| 文件 | 作用 |
| --- | --- |
| `mobile_core.py` | 平台无关的**业务核心**：登录、课程列表、刷课、停止、日志、中断汇报。不导入任何 GUI 库 |
| `gui_mobile.py` | Kivy 界面，只负责「画界面 + 消费消息队列」 |
| `buildozer.spec` | p4a/buildozer 打包配置 |
| `Dockerfile` + `docker-build.sh/.bat` | Linux 构建环境（buildozer 不支持 Windows 原生） |

**关键设计**：业务逻辑全在 `mobile_core.py`，界面通过 `Core.msg_queue` 收消息。
这样逻辑可以**在 Windows 上直接跑测试**，不必先打出 APK 才知道对不对。

### 消息协议

界面按 `item[0]` 分派：

```
("log",     level, text)      日志（含核心/网络层回流的所有日志）
("qr",      png_bytes)        二维码
("login",   ok, msg)          登录结果
("courses", [{name,id,kind}]) 课程列表
("busy",    busy, task)       忙闲状态
("status",  text)             状态栏
("done",    ok, msg)          一次任务结束
```

### 与桌面版共享的数据

两个界面读写**同一批文件**：`config.json`、`cookies.json`、`gui_settings.json`、
`execution.json`、`logs/`。所以电脑上登录过，手机装上就能直接「用上次登录」——
但前提是把这个 `cookies.json` 一起拷过去（**注意：那是你的登录凭证，别随便发给别人**）。

### 安卓适配改动（都在 `utils.py`）

1. **数据目录**：`getDir()` 新增 Android 分支。APK 是沙箱应用，只有应用私有目录可写，
   通过 `ANDROID_ARGUMENT` / `P4A_BOOTSTRAP` 判定，落到 `ANDROID_PRIVATE`。
   卸载才会清空。exe 分支另外加了 `sys.platform != "android"` 守卫。
2. **终端宽度**：新增 `terminal_width(default=80)`。`fucker.py` 里原有 **3 处**
   各自 try/except 的 `os.get_terminal_size()`（视频/文件/AI 三条路径），
   全部改为走这个函数。安卓上没有终端，原写法必然抛异常，而且位置就在刷课主循环里。

### 构建

```bash
# Linux/WSL2
bash docker-build.sh
```
```bat
:: Windows（需先装并启动 Docker Desktop）
docker-build.bat
```

首次会下载 Android SDK/NDK（数 GB，30~60 分钟），之后有缓存。

### ⚠️ 安卓上必须知道的限制

**系统会杀掉长时间后台运行的应用。** 刷完一门课要几小时，安卓的省电策略
（尤其小米/华为/OPPO 等国产系统）可能冻结应用，导致刷到一半无声停止。
对策：

- 界面启动时会申请 `WAKE_LOCK`（阻止休眠）；
- 但仍建议**保持屏幕常亮、不要切走太久**；
- 别指望它像电脑上那样挂一夜。

这不是代码能彻底解决的问题，是安卓的后台限制。
