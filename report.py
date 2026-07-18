"""生成 Markdown 简报 + DOCX + 备份到桌面目录。
命名格式：也门X月X日资讯-08时 / 也门X月X日资讯-20时"""
import os
import shutil
from datetime import datetime

LANG_NAMES = {"zh": "中文", "en": "英文", "ar": "阿拉伯文"}


def _report_name(now=None):
    """生成中文报告名：也门7月19日资讯-08时"""
    if now is None:
        now = datetime.now()
    hour_label = "08时" if now.hour < 14 else "20时"
    return f"也门{now.month}月{now.day}日资讯-{hour_label}"


def write_report(report_dir, new_articles, total_count, summary, cat_text, note, channel_stats):
    os.makedirs(report_dir, exist_ok=True)
    now = datetime.now()
    name = _report_name(now)
    md_path = os.path.join(report_dir, f"{name}.md")
    docx_path = os.path.join(report_dir, f"{name}.docx")

    lines = [f"# {name} · {now.strftime('%Y-%m-%d %H:%M')}", ""]
    stats = "、".join(f"{k} {v}条" for k, v in channel_stats.items())
    lines.append(f"本轮共抓取 {total_count} 条，去重后新增 **{len(new_articles)}** 条。（{stats}）")
    lines.append("")

    if summary:
        lines.append(summary)
    elif note:
        lines.append(f"> {note}")
    lines.append("")

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

    if cat_text:
        lines.append("──────────────────────────────────────")
        lines.append(cat_text)
        lines.append("")

    with open(md_path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(lines) + "\n")
    shutil.copyfile(md_path, os.path.join(report_dir, "latest.md"))
    return md_path, docx_path, name
