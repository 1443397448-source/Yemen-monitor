"""固定媒体 RSS 订阅（含中东阿语媒体），用关键词过滤出相关条目。"""
from .common import Article, entry_time, fetch_feed, text_matches


def fetch(feeds, filter_keywords, max_per_source=80, timeout=20, proxy=None):
    all_kws = [k for kws in filter_keywords.values() for k in kws]
    out = []
    for f in feeds:
        try:
            feed = fetch_feed(f["url"], timeout=timeout,
                              proxy=proxy if f.get("proxy", True) else None)
        except Exception:
            continue
        for e in feed.entries[: max_per_source * 3]:
            title = (e.get("title") or "").strip()
            link = e.get("link") or ""
            if not title or not link:
                continue
            text = f"{title} {e.get('summary', '')}"
            if text_matches(text, all_kws):
                out.append(Article(title=title, url=link,
                                   source=f.get("name", "RSS"),
                                   channel="media_rss",
                                   lang=f.get("lang", "en"),
                                   published=entry_time(e)))
    return out
