"""百度资讯搜索（中文），按时间排序抓取结果页。页面改版或触发验证时返回空列表。"""
import html
import re

from .common import Article, http_get


def fetch(core_zh, max_records=30, timeout=20):
    out, seen = [], set()
    for kw in (core_zh or ["也门"])[:2]:
        try:
            page = http_get("https://www.baidu.com/s", timeout=timeout,
                            params={"tn": "news", "word": kw, "rtt": "4"}).text
        except Exception:
            continue
        items = re.findall(r'<h3[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S)
        for href, raw in items[:max_records]:
            title = re.sub(r"<[^>]+>", "", raw)
            title = html.unescape(re.sub(r"\s+", " ", title)).strip()
            href = html.unescape(href)
            if title and href.startswith("http") and href not in seen:
                seen.add(href)
                out.append(Article(title=title, url=href, source="百度资讯",
                                   channel="baidu", lang="zh"))
    return out
