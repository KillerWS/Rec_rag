# smalltalk_detector.py  (v3)
# -------------------------------------------------
"""
意图检测：
True  → 非柏林Airbnb相关（直接寒暄/道歉）
False → 继续走 RAG / 偏好
"""
from __future__ import annotations
from typing import Literal
import textwrap, json, random
from langchain.prompts import PromptTemplate
from langchain.chains   import LLMChain
from load_llm           import get_llm


_DETECT_PROMPT = PromptTemplate(
    input_variables=["utterance"],
    template=textwrap.dedent("""
    You are an intent classifier for a Berlin-Airbnb chat bot.
    Output **ONE line of JSON** only:

    {{ "label": "<relevant | non_relevant>", "reason": "<brief english reason>" }}

    • relevant      – user likely wants Berlin Airbnb / travel help
    • non_relevant  – greeting / thanks / emoji, or any off-topic question
    """).strip() + "\n\nUSER: {utterance}\nJSON:")




def _classify_llm(text: str) -> Literal["relevant", "non_relevant"]:
    llm   = get_llm()
    chain = LLMChain(llm=llm, prompt=_DETECT_PROMPT)
    raw   = chain.run(utterance=text.strip())
    data  = json.loads(raw)
    return "relevant" if data.get("label") == "relevant" else "non_relevant"


# -------- 对外 API ----------
def is_non_relevant(msg: str) -> bool:
    
    """True → 纯寒暄/跑题；False → 继续业务"""
    # if not msg or not msg.strip():
    #     return True
    try:
        print("is_non_relevant called")
        res = _classify_llm(msg)
        print(res)
        return res == "non_relevant"
    except Exception as e:
        print("intent-detector error:", e)
        return False


# -------- 固定寒暄/道歉 ----------
_GREET_TEMPLATES = [
    "Hi there! 👋 Ask me anything about staying/accommodation in Berlin.",
    "Hello! Need help choosing a neighbourhood or price range?",
    "Hey! I can help you find the right Airbnb in Berlin—just let me know what matters most.",
    "Sorry, I only answer Berlin-Airbnb questions. Feel free to ask about listings, prices or areas!"
]

def gen_small_talk_reply() -> str:
    return {"answer": random.choice(_GREET_TEMPLATES)}
