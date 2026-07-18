"""URL 解析工具：从搜索引擎跳转 URL 中提取真实文章地址。"""
from urllib.parse import parse_qs, unquote, urlsplit


def unwrap(url):
    """返回真实文章 URL；无法解析时返回原值。"""
    host = (urlsplit(url).netloc or "").lower()

    # Bing apiclick.aspx → 提取 url 参数
    if "bing.com" in host and "apiclick.aspx" in url:
        qs = parse_qs(urlsplit(url).query)
        raw = qs.get("url", [""])[0]
        if raw:
            return unquote(raw)

    # r.search.yahoo.com 跳转 → 提取 RU 参数
    if ("search.yahoo.com" in host or "r.search.yahoo.com" in host) and "RU=" in url:
        import re
        m = re.search(r"[/;.]RU=([^/;.&]+)", url)
        if m:
            return unquote(m.group(1))

    return url
