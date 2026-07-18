"""Google News RSS 搜索：英文版、中文版、阿拉伯语版三个地区版本。"""
from urllib.parse import quote

from .common import Article, entry_source, entry_time, fetch_feed

EDITIONS = {
    "en": "hl=en-US&gl=US&ceid=US:en",
    "zh": "hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    "ar": "hl=ar&gl=SA&ceid=SA:ar",
}


def fetch(core_keywords, max_per_source=80, timeout=20, proxy=None):
    out = []
    for lang, edition in EDITIONS.items():
        kws = core_keywords.get(lang) or []
        if not kws:
            continue
        q = quote(" OR ".join(f'"{k}"' for k in kws) + " when:1d")
        url = f"https://news.google.com/rss/search?q={q}&{edition}"
        try:
            feed = fetch_feed(url, timeout=timeout, proxy=proxy)
        except Exception:
            continue
        for e in feed.entries[:max_per_source]:
            title = (e.get("title") or "").strip()
            link = e.get("link") or ""
            if title and link:
                out.append(Article(title=title, url=link,
                                   source=entry_source(e, "Google News"),
                                   channel="google_news", lang=lang,
                                   published=entry_time(e)))
    return out
