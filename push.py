'''
Author: Vincent Young, jiajiu123
Date: 2023-03-30 00:15:22
LastEditors: Vincent Young
LastEditTime: 2023-03-30 02:40:33
FilePath: /fuckZHS/push.py
Telegram: https://t.me/missuo(Vincent Young)

Copyright © 2023 by Vincent, All Rights Reserved. 
'''
from urllib.parse import quote

import requests


def pushpluser(title: str, content, token: str) -> None:
    """pushplus 推送

    改动说明:
    * 改用 https, 并交给 requests 自动做 URL 编码
      原实现把 content 直接拼进 URL, 推送内容里只要出现 `&` 或中文,
      参数就会被截断或乱码
    * 吞掉网络异常, 推送失败不应反过来打断刷课主流程
    """
    try:
        requests.get(
            "https://www.pushplus.plus/send",
            params={"token": token, "title": title, "content": str(content)},
            timeout=10,
        )
    except Exception as e:
        print(f"*pushplus 推送失败: {e}")


def barkpusher(title: str, content, token: str) -> None:
    """bark 推送, token 形如 https://api.day.app/xxxxxxxxxxxxx

    注意 quote 要用 safe="", 否则 `/` 不会被转义,
    标题里带斜杠时会把这个 URL 的路径结构撑开
    """
    try:
        requests.get(
            f"{str(token).rstrip('/')}/{quote(str(title), safe='')}/{quote(str(content), safe='')}",
            timeout=10,
        )
    except Exception as e:
        print(f"*bark 推送失败: {e}")
