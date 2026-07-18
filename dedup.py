"""SQLite 存储与去重：URL 规范化哈希 + 标题相似度双重判重。"""
import difflib
import hashlib
import os
import re
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DROP_PARAM_PREFIXES = ("utm_", "spm", "from", "fbclid", "gclid", "ocid",
                       "ref", "ved", "ei", "cmpid", "share", "src")


def normalize_url(url):
    try:
        p = urlsplit(url.strip())
    except ValueError:
        return url
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith(DROP_PARAM_PREFIXES)]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(),
                       p.path.rstrip("/"), urlencode(query), ""))


def clean_title(title):
    t = re.sub(r"\s+", " ", title or "").strip()
    t = re.sub(r"\s*[-–—|]\s*[^-–—|]{1,40}$", "", t)  # 去掉尾部“ - 媒体名”
    return t.casefold()


class Store:
    def __init__(self, path, similarity=0.92, compare_days=4):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.similarity = similarity
        self.compare_days = compare_days
        self.conn = sqlite3.connect(path)
        self.conn.execute("""CREATE TABLE IF NOT EXISTS articles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_hash TEXT UNIQUE, url TEXT, title TEXT, clean_title TEXT,
            source TEXT, channel TEXT, lang TEXT,
            published TEXT, fetched_at TEXT)""")
        self.conn.commit()

    def filter_new(self, articles):
        cutoff = (datetime.now() - timedelta(days=self.compare_days)).strftime("%Y-%m-%d %H:%M:%S")
        recent = {}
        for ct, lang in self.conn.execute(
                "SELECT clean_title, lang FROM articles WHERE fetched_at >= ?", (cutoff,)):
            recent.setdefault(lang, []).append(ct)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new = []
        for a in articles:
            if not a.url or not a.title:
                continue
            h = hashlib.sha256(normalize_url(a.url).encode()).hexdigest()
            if self.conn.execute("SELECT 1 FROM articles WHERE url_hash=?", (h,)).fetchone():
                continue
            ct = clean_title(a.title)
            dup = any(difflib.SequenceMatcher(None, ct, t).ratio() >= self.similarity
                      for t in recent.get(a.lang, []))
            self.conn.execute(
                "INSERT OR IGNORE INTO articles(url_hash,url,title,clean_title,source,channel,lang,published,fetched_at) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (h, a.url, a.title, ct, a.source, a.channel, a.lang, a.published, now))
            if not dup:
                recent.setdefault(a.lang, []).append(ct)
                new.append(a)
        self.conn.commit()
        return new
