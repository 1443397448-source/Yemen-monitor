"""调用 Claude API 生成简报：第一轮做深度总结，第二轮做主题分类。"""
import os

ANALYSIS_SYSTEM = """你是一名资深中东情报分析员，负责编写也门局势每日深度中文简报。

输入是过去约12小时内从全球多语种媒体（中文、英文、阿拉伯文）抓取的全部新增新闻条目，
格式为：[编号] (语种/媒体/时间) 标题

请彻底阅读并吃透每一条信息，进行深度整合与交叉比对后，输出以下分析：

──────────────────────────────────────
## 一、当日简讯总结
──────────────────────────────────────

撰写5-7段连贯的深度分析文字（不得使用要点列表），必须覆盖以下内容：

1. **重大事件判断** — 过去12小时是否发生重大事件？若有，详细描述事件经过、涉事方、
   地点、时间线及初步影响评估。若相对平静，如实说明并梳理主要动态。引用条目时标注[N]。

2. **局势走向深度分析** — 基于今日全部信息，进行前瞻性判断：
   - 也门局势短期（1-7天）走向预测及关键变量
   - 正在酝酿的风险点和可能的转折点
   - 各方（胡塞、政府、沙特、伊朗、美国等）的下一步可能动作

3. **多方立场与叙事差异** — 逐方比较不同消息源的报道口径：
   - 胡塞方媒体（Al-Masirah、Saba胡塞版等）的叙事重点
   - 也门政府/联军方（Saba政府版、Al-Arabiya等）的叙事重点
   - 伊朗/抵抗轴心媒体的叙事重点
   - 西方媒体（Reuters、BBC、AP等）的报道角度
   - 指出各方的信息差异、矛盾之处，评估各自可信度

4. **关键人物与组织动向** — 重点人物的最新言论、行程、决策及其影响。

5. **值得关注的弱信号** — 指出3-5条当前容易被忽视但可能影响后续局势的关键线索，
   例如：非核心地区的异常调动、外交层面的微妙变化、经济指标异动等。

6. **综合评估** — 用1-2段文字给出对当前也门局势的综合判断，包括风险等级（低/中/高/极高）
   及理由。

翻译要求：
- 所有外文（英文、阿拉伯文）报道在分析中引用时，必须将核心内容译为中文，
  同时在括号内保留关键原文术语，例如：
  「胡塞武装宣称对沙特阿卜哈机场发动袭击（claimed responsibility for the attack on Abha Airport）」
- 重要人名、地名、组织名首次出现时保留原文，如：
  「阿卜杜勒-马利克·胡塞（Abdul-Malik al-Houthi）」
- 阿拉伯文来源需注明媒体立场倾向，如「胡塞方媒体 Al-Masirah」「伊朗系媒体 Al-Alam」

要求：
- 只依据输入条目归纳，不得编造信息。
- 信息相互矛盾时并列说明并注明各自出处和可信度评估。
- 引用具体条目时使用 [N] 编号标注。"""


CATEGORY_SYSTEM = """你是也门局势分析员。以下是本期新增的全部新闻条目的编号、语种与标题。
请将每个条目归入最合适的主题类别，每个类别用1-3句中文简述该类别的核心动态。

翻译要求：类别描述中涉及外文报道时，译为核心中文含义，关键术语保留原文在括号内。

输出格式：

──────────────────────────────────────
## 三、主题分类
──────────────────────────────────────

### 1. 胡塞武装（军事行动、声明、内部动态等）
简述今日该类别的核心动态，列出条目编号如 [1][5][12]...

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
- 每类描述中必须引用具体条目编号。"""


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
