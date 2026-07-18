import time
from dataclasses import dataclass

import feedparser
import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# 统一忽略环境变量代理：是否走代理只由 config.yaml 的 fetch.proxy 决定，
# 保证 launchd 与终端下行为一致，且国内源始终直连
_session = requests.Session()
_session.trust_env = False


@dataclass
class Article:
    title: str
    url: str
    source: str      # 媒体名
    channel: str     # 采集渠道
    lang: str        # zh / en / ar
    published: str = ""


def http_get(url, timeout=20, params=None, proxy=None):
    proxies = {"http": proxy, "https": proxy} if proxy else None
    resp = _session.get(url, params=params, timeout=timeout,
                        headers={"User-Agent": UA}, proxies=proxies)
    resp.raise_for_status()
    return resp


def fetch_feed(url, timeout=20, proxy=None):
    resp = http_get(url, timeout=timeout, proxy=proxy)
    return feedparser.parse(resp.content)


def entry_time(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return time.strftime("%Y-%m-%d %H:%M", t)
    return entry.get("published", "") or entry.get("updated", "")


def entry_source(entry, default):
    src = entry.get("source")
    if src and src.get("title"):
        return src["title"]
    return default


def text_matches(text, keywords):
    low = (text or "").casefold()
    return any(k.casefold() in low for k in keywords)
