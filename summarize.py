"""调用 Claude API 生成简报：第一轮做深度总结，第二轮做主题分类。
逐条列表由程序 100% 生成（不消耗 AI 输出 token），确保"要应列尽列"。"""
import os

ANALYSIS_SYSTEM = """你是一名资深中东情报分析员，负责撰写也门局势每日深度分析。

输入是过去12小时内从全球多语种媒体（中文、英文、阿拉伯文）抓取的全部新增新闻条目，
格式为：[编号] (语种/媒体/时间) 标题

请输出以下部分的深度分析（Markdown 格式）：

──────────────────────────────────────
## 一、当日简讯总结
──────────────────────────────────────

撰写 4-6 段连贯的分析性文字（不得使用要点列表），必须覆盖：

1. **重大事件判断** — 过去12小时有没有发生重大事件？若有，详细描述事件经过、涉事方、地点及初步影响。若无重大事件，如实说明"今日相对平静"并描述主要动态。

2. **局势走向分析** — 基于今日全部信息，判断也门局势的短期走向，指出正在酝酿的风险和可能的转折点。

3. **多方立场与叙事差异** — 比较不同消息源（胡塞方媒体、也门政府方、沙特/西方媒体、伊朗媒体等）的叙事差异、各自强调的重点与可信度评估。

4. **值得关注的信号** — 指出当前容易被忽视但可能影响后续局势的关键线索或弱信号。

要求：
- 全部使用简体中文，外文名称保留原文。
- 只依据输入条目归纳，不得编造信息。
- 信息相互矛盾时并列说明并注明各自出处。
- 引用具体条目时使用 [N] 编号标注。"""


CATEGORY_SYSTEM = """你是也门局势分析员。以下是本期新增的全部新闻条目的编号、语种与标题。
请将每个条目归入最合适的主题类别。

输出格式：

──────────────────────────────────────
## 三、主题分类
──────────────────────────────────────

### 1. 胡塞武装（军事行动、声明、内部动态等）
简要说明今日该类别的核心动态（1-3句），然后列出条目编号，如 [1][5][12]...

### 2. 红海与航运安全（袭击、护航、航运影响等）
...

### 3. 也门国内政治（政府、南方过渡委员会、各派系动态等）
...

### 4. 沙特与也门关系（外交、军事、边境等）
...

### 5. 阿曼与也门关系（调停、外交接触等）
...

### 6. 伊朗与也门关系（支持、外交、军事协调等）
...

### 7. 美英与也门（空袭、外交、制裁等）
...

### 8. 人道主义与经济（民生、援助、经济等）
...

### 9. 其他
...

规则：
- 每个条目必须且只能出现在一个类别中。
- 某类别本期无相关报道时标注「（本期无相关报道）」。
- 类别可微调，例如某期某类内容特别多可拆分。"""


def _call_claude(system_prompt, user_content, model, max_tokens,
                 disable_thinking=False):
    import logging
    log = logging.getLogger("houthi")
    from anthropic import Anthropic
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system_prompt,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_content}],
    )
    if disable_thinking:
        kwargs["thinking"] = {"type": "disabled"}
    msg = Anthropic().messages.create(**kwargs)
    blocks = [(b.type, len(b.text) if hasattr(b, 'text') else 0)
              for b in msg.content]
    log.info("Claude 响应: %s, stop=%s, out=%s",
             blocks, getattr(msg, 'stop_reason', '?'),
             getattr(msg, 'usage', {}).output_tokens)
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def summarize(articles, model="claude-sonnet-4-6", max_articles=300, max_tokens=4096):
    """第一轮：深度总结分析。只传入标题（不含URL），节省输入token。"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, "未设置 ANTHROPIC_API_KEY，本期跳过 AI 摘要"
    subset = articles[:max_articles]
    lines = [f"[{i}] ({a.lang}/{a.source}/{a.published}) {a.title[:240]}"
             for i, a in enumerate(subset, 1)]
    body = "\n".join(lines)
    if len(articles) > max_articles:
        body += f"\n（共{len(articles)}条，截取前{max_articles}条）"
    try:
        return _call_claude(ANALYSIS_SYSTEM, body, model, max_tokens), None
    except Exception as e:
        return None, f"AI 摘要失败：{e}"


def summarize_category(articles, model="claude-sonnet-4-6", max_articles=300):
    """第二轮：主题分类。输入简化为编号+语种+标题，输出远小于逐条摘要。"""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, "无 API Key"
    subset = articles[:max_articles]
    lines = [f"[{i}] ({a.lang}) {a.title[:200]}" for i, a in enumerate(subset, 1)]
    body = "\n".join(lines)
    try:
        return _call_claude(CATEGORY_SYSTEM, body, model, 4096,
                            disable_thinking=True), None
    except Exception as e:
        return None, f"分类生成失败：{e}"
