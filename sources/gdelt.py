"""GDELT DOC 2.0 API：免费的全球媒体全文库，按英/中/阿三种源语言分路查询。
官方限频：每5秒最多1次请求，因此各语种查询之间强制间隔。"""
import time

from .common import Article, http_get

API = "https://api.gdeltproject.org/api/v2/doc/doc"
SOURCELANG = {"en": "eng", "zh": "zho", "ar": "ara"}


def _fmt(seendate):
    if len(seendate) >= 13 and "T" in seendate:
        d, t = seendate.split("T", 1)
        return f"{d[0:4]}-{d[4:6]}-{d[6:8]} {t[0:2]}:{t[2:4]} UTC"
    return seendate


def fetch(core_keywords, lookback_hours=18, max_records=80, timeout=20, proxy=None):
    out = []
    first = True
    for lang, code in SOURCELANG.items():
        kws = core_keywords.get(lang) or []
        if not kws:
            continue
        if not first:
            time.sleep(6)
        first = False
        terms = " OR ".join(f'"{k}"' for k in kws)
        params = {
            "query": f"({terms}) sourcelang:{code}",
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(max_records),
            "timespan": f"{lookback_hours}h",
            "sort": "DateDesc",
        }
        data = None
        for attempt in range(2):
            try:
                data = http_get(API, timeout=timeout, params=params, proxy=proxy).json()
                break
            except Exception:
                if attempt == 0:
                    time.sleep(8)
        if not data:
            continue
        for a in data.get("articles", []):
            title = (a.get("title") or "").strip()
            url = a.get("url") or ""
            if title and url:
                out.append(Article(title=title, url=url,
                                   source=a.get("domain", "GDELT"),
                                   channel="gdelt", lang=lang,
                                   published=_fmt(a.get("seendate", ""))))
    return out
