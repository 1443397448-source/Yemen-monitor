"""Yahoo News 搜索（英文）。RSS 接口已停用，改为解析搜索结果页 HTML，
并把 Yahoo 跳转链接（RU= 参数）还原成原始文章地址。"""
import html
import re
from urllib.parse import quote, unquote

from .common import Article, http_get
from .url_util import unwrap


def _real_url(href):
    m = re.search(r"[/;]RU=([^/;]+)", href)
    return unquote(m.group(1)) if m else href


def fetch(core_keywords, max_per_source=80, timeout=20, proxy=None):
    kws = core_keywords.get("en") or []
    if not kws:
        return []
    out, seen = [], set()
    for kw in kws[:2]:
        url = f"https://news.search.yahoo.com/search?p={quote(kw)}"
        try:
            page = http_get(url, timeout=timeout, proxy=proxy).text
        except Exception:
            continue
        items = re.findall(
            r'<h4[^>]*s-title[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            page, re.S)
        for href, raw in items[:max_per_source]:
            title = html.unescape(re.sub(r"<[^>]+>", "", raw))
            title = re.sub(r"\s+", " ", title).strip()
            link = unwrap(_real_url(html.unescape(href)))
            if not title or not link.startswith("http") or link in seen:
                continue
            seen.add(link)
            out.append(Article(title=title, url=link, source="Yahoo News",
                               channel="yahoo_news", lang="en"))
    return out
