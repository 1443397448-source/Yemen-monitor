"""生成 Markdown 简报：AI 深度总结 + 程序逐条列尽 + AI 主题分类。"""
import os
import shutil
from datetime import datetime

LANG_NAMES = {"zh": "中文", "en": "英文", "ar": "阿拉伯文"}


def write_report(report_dir, new_articles, total_count, summary, cat_text, note, channel_stats):
    os.makedirs(report_dir, exist_ok=True)
    now = datetime.now()
    path = os.path.join(report_dir, now.strftime("%Y-%m-%d_%H%M") + ".md")

    lines = [f"# 也门局势深度简报 · {now.strftime('%Y-%m-%d %H:%M')}", ""]
    stats = "、".join(f"{k} {v}条" for k, v in channel_stats.items())
    lines.append(f"本轮共抓取 {total_count} 条，去重后新增 **{len(new_articles)}** 条。（{stats}）")
    lines.append("")

    # 第一部分：AI 深度总结
    if summary:
        lines.append(summary)
    elif note:
        lines.append(f"> {note}")
    lines.append("")

    # 第二部分：程序生成 100% 逐条列表
    lines.append("──────────────────────────────────────")
    lines.append("## 二、逐条列表")
    lines.append("──────────────────────────────────────")
    lines.append("")

    if not new_articles:
        lines.append("（本时段无新增条目。）")
    else:
        langs = ["zh", "en", "ar"] + sorted({a.lang for a in new_articles} - {"zh", "en", "ar"})
        idx = 0
        for lang in langs:
            group = [a for a in new_articles if a.lang == lang]
            if not group:
                continue
            lines.append(f"### {LANG_NAMES.get(lang, lang)}（{len(group)}条）")
            lines.append("")
            for a in group:
                idx += 1
                meta = []
                if a.source:
                    meta.append(f"来源：{a.source}")
                if a.published:
                    meta.append(f"时间：{a.published}")
                lines.append(f"**[{idx}] {a.title}**  ")
                lines.append(f"{' | '.join(meta)}  ")
                lines.append(f"链接：[{a.source or a.channel}]({a.url})  ")
                lines.append("")
            lines.append("")

    # 第三部分：AI 主题分类
    if cat_text:
        lines.append("──────────────────────────────────────")
        lines.append(cat_text)
        lines.append("")

    with open(path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")
    shutil.copyfile(path, os.path.join(report_dir, "latest.md"))
    return path
