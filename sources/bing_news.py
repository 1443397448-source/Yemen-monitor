"""Bing News RSS 搜索：美国英文、中国中文、沙特阿语三个市场。
Bing 的 RSS 接口不支持带引号的 OR 复合查询，因此按关键词逐个简单查询后合并。"""
from urllib.parse import quote

from .common import Article, entry_source, entry_time, fetch_feed
from .url_util import unwrap

MARKETS = {"en": "en-US", "zh": "zh-CN", "ar": "ar-SA"}
MAX_KEYWORDS_PER_LANG = 3


def fetch(core_keywords, max_per_source=80, timeout=20, proxy=None):
    out, seen = [], set()
    for lang, mkt in MARKETS.items():
        for kw in (core_keywords.get(lang) or [])[:MAX_KEYWORDS_PER_LANG]:
            url = (f"https://www.bing.com/news/search?q={quote(kw)}"
                   f"&format=RSS&setmkt={mkt}")
            try:
                feed = fetch_feed(url, timeout=timeout, proxy=proxy)
            except Exception:
                continue
            for e in feed.entries[:max_per_source]:
                title = (e.get("title") or "").strip()
                link = e.get("link") or ""
                if not title or not link or link in seen:
                    continue
                seen.add(link)
                real_url = unwrap(link)
                out.append(Article(title=title, url=real_url,
                                   source=entry_source(e, "Bing News"),
                                   channel="bing_news", lang=lang,
                                   published=entry_time(e)))
    return out
