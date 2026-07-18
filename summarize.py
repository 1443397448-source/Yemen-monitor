"""调用 Claude API 生成简报：第一轮做深度总结，第二轮做主题分类。"""
import os

ANALYSIS_SYSTEM = """你是一名资深中东情报分析员，负责编写也门局势每日深度中文简报。

输入是过去约12小时内从全球多语种媒体（中文、英文、阿拉伯文）抓取的全部新增新闻条目。
你必须确保对英文和阿拉伯文内容进行同等深度的检索与思考，不得只依赖某一种语言。
外文报道必须吃透原文含义后再翻译归纳，不得臆测。

格式：[编号] (语种/媒体/时间) 标题

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
请将每个条目归入最合适的主题类别。每个类别需做到：

1. 开头用2-3句简述该类别的核心动态
2. 然后按子主题分组列出条目，每组给一行简短说明（含英文/阿拉伯文关键术语翻译）
3. 格式示例：

### 1. 胡塞武装（军事行动、声明、内部动态等）
今日核心动态说明...
- 对沙特袭击：[1][8][9]（胡塞向沙特南部发射导弹和无人机）
- 内部动员与声明：[21][22]（阿卜杜勒-马利克·胡塞发表强硬讲话）
- 军事能力展示：[68][71]（展示新型无人机）

### 2. 红海与航运安全
...

必须覆盖以下类别：
1. 胡塞武装（军事行动、声明、内部动态等）
2. 红海与航运安全（袭击、护航、商船动态等）
3. 也门国内政治（合法政府、南方过渡委员会（STC）、各派系、部落等）
4. 沙特与也门关系（外交、军事、边境冲突等）
5. 阿曼与也门关系（调停、外交接触、人道走廊等）
6. 伊朗与也门关系（军事支持、外交协调、代理人网络等）
7. 美英与也门（空袭、外交、制裁、军事部署等）
8. 国际与地区反应（联合国、欧盟、阿盟、巴基斯坦、以色列等）
9. 人道主义与经济（民生、援助、货币、粮食安全等）
10. 其他

规则：
- 每个条目必须且只能出现在一个类别中。
- 某类别本期无相关报道时标注「（本期无相关报道）」。
- 类别中的子分组说明应简明扼要，外文术语保留原文并括号注明中文。
- 每条条目都要被归入，不得遗漏。"""


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
