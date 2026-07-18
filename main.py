#!/usr/bin/env python3
"""也门与胡塞武装动态监控：单轮流程入口（代理启停 → 采集 → 去重 → AI 摘要 → 简报）。"""
import logging
import os
import shutil
import sys
from collections import OrderedDict
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

import yaml

from convert import md_to_docx
from dedup import Store
from proxy_ctl import ensure_proxy, stop_proxy
from push import push_serverchan, push_wecom_file
from report import write_report
from sources import baidu, bing_news, gdelt, google_news, media_rss, yahoo_news
from summarize import summarize, summarize_category

log = logging.getLogger("houthi")


def load_env():
    path = os.path.join(BASE, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    load_env()
    with open(os.path.join(BASE, "config.yaml"), encoding="utf-8") as fp:
        cfg = yaml.safe_load(fp)

    core = cfg["keywords"]["core"]
    flt = cfg["keywords"]["filter"]
    fc = cfg["fetch"]
    timeout, look, maxn = fc["timeout"], fc["lookback_hours"], fc["max_per_source"]
    proxy = fc.get("proxy") or None
    proxy_app = fc.get("proxy_app") or None
    enabled = cfg["sources"]

    is_ci = os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS")

    started_by_us = False
    if is_ci:
        log.info("运行环境：GitHub Actions（云端，无需代理）")
        proxy = None  # CI 环境直接访问国际源
    elif proxy and proxy_app:
        try:
            ok, started_by_us = ensure_proxy(proxy, proxy_app)
            if started_by_us:
                log.info("已自动启动代理 App：%s", proxy_app)
            elif ok:
                log.info("代理已在运行，保持原样")
            if not ok:
                log.warning("代理端口未就绪，本轮境外源可能不可用")
        except Exception as e:
            log.warning("代理自动启动失败：%s", e)

    try:
        _run_round(cfg, core, flt, timeout, look, maxn, proxy, enabled)
    finally:
        if started_by_us and fc.get("proxy_autostop", True):
            log.info("运行结束，关闭本程序启动的代理 App：%s", proxy_app)
            stop_proxy(proxy_app)


def _run_round(cfg, core, flt, timeout, look, maxn, proxy, enabled):
    articles, stats = [], OrderedDict()

    def run(name, fn):
        if not enabled.get(name, False):
            return
        try:
            got = fn()
        except Exception as e:
            got = []
            log.warning("%s 抓取失败：%s", name, e)
        stats[name] = len(got)
        articles.extend(got)
        log.info("%s：%d 条", name, len(got))

    run("gdelt", lambda: gdelt.fetch(core, look, maxn, timeout, proxy))
    run("google_news", lambda: google_news.fetch(core, maxn, timeout, proxy))
    run("bing_news", lambda: bing_news.fetch(core, maxn, timeout, proxy))
    run("yahoo_news", lambda: yahoo_news.fetch(core, maxn, timeout, proxy))
    run("baidu", lambda: baidu.fetch(core.get("zh", []), 30, timeout))
    run("media_rss", lambda: media_rss.fetch(cfg.get("media_feeds", []), flt, maxn, timeout, proxy))

    store = Store(os.path.join(BASE, "data", "news.db"),
                  cfg["dedup"]["title_similarity"], cfg["dedup"]["compare_days"])
    new = store.filter_new(articles)
    log.info("共抓取 %d 条，去重后新增 %d 条", len(articles), len(new))

    summary = note = None
    cat_text = None
    sc = cfg["summarize"]
    if sc.get("enabled") and new:
        summary, note = summarize(new, sc["model"],
                                  sc.get("max_articles", 300),
                                  sc.get("max_tokens", 4096))
        if note:
            log.warning(note)
        # 第二轮：主题分类（独立调用，输出短，不受逐条列表 token 限制）
        cat_text, cat_note = summarize_category(new, sc["model"],
                                                sc.get("max_articles", 300))
        log.info("分类返回值 cat_text=%s cat_note=%s",
                 "非空(%d字)" % len(cat_text) if cat_text else "空/None",
                 cat_note or "None")
        if cat_note:
            log.warning("分类错误：%s", cat_note)
        elif cat_text:
            log.info("主题分类生成完成 (%d字)", len(cat_text))

    md_path, docx_path, report_name = write_report(
        os.path.join(BASE, cfg["report"]["dir"]),
        new, len(articles), summary, cat_text, note, stats)
    log.info("简报已生成：%s", md_path)

    # 转换 DOCX
    try:
        md_to_docx(md_path, docx_path)
        log.info("DOCX 已生成：%s", docx_path)
    except Exception as e:
        log.warning("DOCX 转换失败：%s", e)
        docx_path = md_path  # 兜底

    # 备份 DOCX 到桌面
    backup_dir = os.path.expanduser("~/Desktop/科研与竞赛（研）/Yemen-每日资讯")
    try:
        os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, f"{report_name}.docx")
        shutil.copy2(docx_path, backup_path)
        log.info("已备份至桌面：%s", backup_path)
    except Exception as e:
        log.warning("桌面备份失败：%s", e)

    push_cfg = cfg.get("push", {})
    push_title = datetime.now().strftime("也门简报 %m-%d %H:%M")
    if summary:
        push_body = summary
    else:
        push_body = "（本轮无 AI 摘要）\n\n" + "\n".join(
            f"- [{a.title}]({a.url})" for a in new[:20])
    if not new:
        push_body = "本轮无新增动态。"

    # 企业微信群机器人（文件直传，DOCX 格式）
    wecom_key = os.environ.get("WECOM_WEBHOOK_KEY")
    if push_cfg.get("wecom", False) and wecom_key:
        err = push_wecom_file(wecom_key, docx_path,
                              f"# {push_title}（新增{len(new)}条）\n\n{summary or push_body}",
                              timeout=30)
        if err:
            log.warning("企业微信推送: %s", err)
        else:
            log.info("企业微信文件推送成功")

    # Server酱 → 企业微信群（应用专用SendKey）或方糖个人微信（普通SendKey）
    if push_cfg.get("wechat", False):
        # 组装完整简报内容推送
        full_body = push_body
        if new:
            full_body += "\n\n---\n\n" + "\n".join(
                f"[{i}] {a.title[:120]}\n{a.url}"
                for i, a in enumerate(new[:80], 1))
        err = push_serverchan(f"{push_title}（新增{len(new)}条）", full_body)
        if err:
            log.warning(err)
        else:
            log.info("Server酱推送成功")


if __name__ == "__main__":
    main()
