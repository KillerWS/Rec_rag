# intent_parser.py
from __future__ import annotations
import json, re, textwrap, ast
from typing import List, Dict
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from load_llm import get_llm

INTENT_LABELS = [
    "recommend",          # 主动要看房源
    "preference_update",  # 修改/新增约束
    "qa",                 # 咨询具体问题（噪音、安全…）
    "chart_request",      # 需要图表
    "preference_confirm", # 确认现有偏好 “looks good”
    "chitchat"            # 与任务无关
]

# ---------------- rule 基础 ----------------
RULE_KEYWORDS = {
    "recommend": [
        r"\b(show|give|recommend|suggest)( me)? (some )?(listing|option)s?\b",
        r"\b(any|some) (suggestion|recommendation)s?\b"
    ],
    "preference_update": [
        r"\b(change|update|set|raise|lower)\b.*\b(price|budget|room|area|type)\b",
        r"\b(no longer|don't) (want|need)\b"
    ],
}

def rule_intent(msg: str, hist: str | None = None) -> str | None:
    """keyword + 简易上下文规则"""
    msg_low = msg.lower()
    for intent, patts in RULE_KEYWORDS.items():
        for p in patts:
            if re.search(p, msg_low, flags=re.I):
                return intent

    # 简单上下文：上一轮 ask-recommend，本轮 “yes/ok/please”
    if hist and re.search(r"\b(recommend|show).+?\?\s*$", hist, re.I):
        if re.match(r"^\s*(yes|yeah|sure|ok|okay|please)\b", msg_low):
            return "recommend"
    return None


# --------------- LLM 提示词 ---------------
FEW_SHOT = textwrap.dedent("""
<EXAMPLES>
User: I'd like a private room below 100 euros.
Assistant: {{
    "intent": "preference_update",
    "confidence": 0.92
}}
---
User: Could you recommend me something in Kreuzberg?
Assistant: {{
    "intent": "recommend",
    "confidence": 0.91
}}
---
User: How noisy is that area at night?
Assistant: {{
    "intent": "qa",
    "confidence": 0.88
}}
---
User: Show me the price distribution instead.
Assistant: {{
    "intent": "chart_request",
    "confidence": 0.86
}}
---
User: Great, keep it like that.
Assistant: {{
    "intent": "preference_confirm",
    "confidence": 0.83
}}
---
User: By the way, what's your favourite food?
Assistant: {{
    "intent": "chitchat",
    "confidence": 0.80
}}
</EXAMPLES>
""").strip()

LM_PROMPT = PromptTemplate(
    input_variables=["labels", "dialogue", "user_msg"],
    template=textwrap.dedent("""
    You are an AI that classifies the user's CURRENT message into one of the intents: {labels}.

    ## Intent definition
    * recommend – user explicitly asks to see / get listings.
    * preference_update – user adds/changes constraints (price, location...).
    * qa – user asks factual question about listings/area/reviews.
    * chart_request – user wants plots/statistics.
    * preference_confirm – user confirms current filters are OK.
    * chitchat – off-topic or small talk.

    ## Dialogue history (max 6 turns)
    {dialogue}

    ## Current user message
    {user_msg}

    {fewshot}

    Return ONLY a JSON, e.g.:
    {{"intent":"recommend","confidence":0.93}}
    """).strip().replace("{fewshot}", FEW_SHOT)  # 插入 few-shot
)

def llm_intent(msg: str, history: List[Dict]) -> Dict:
    llm = get_llm()
    dialogue = []
    for t in history[-6:]:
        role = "User" if t["type"] == "human" else "Assistant"
        dialogue.append(f"{role}: {t['data']}")
    dlg = "\n".join(dialogue)

    chain = LLMChain(llm=llm, prompt=LM_PROMPT)
    raw = chain.run(labels=", ".join(INTENT_LABELS),
                    dialogue=dlg,
                    user_msg=msg)
    print(">>> LLM raw output:", raw)     # 👈 加这一行
    try:
        return json.loads(raw)
    except Exception:
        # 尝试用 ast 解析 / 正则兜底
        try:
            return ast.literal_eval(raw.strip())
        except Exception:
            return {"intent": "unknown", "confidence": 0.0}


# --------------- 对外主函数 ----------------
def parse_intent(message: str, history: List[Dict]) -> Dict:
    # 1. 规则
    intent = rule_intent(message, hist=history[-1]["data"] if history else None)
    if intent:
        return {"intent": intent, "confidence": 0.9}

    # 2. LLM
    res = llm_intent(message, history)
    if res.get("confidence", 0) < .5 or res.get("intent") not in INTENT_LABELS:
        return {"intent": "unknown", "confidence": res.get("confidence", 0)}
    return res
