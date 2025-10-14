import json
from typing import List, Dict
from langchain_core.messages import HumanMessage, AIMessage
from load_llm import get_llm
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

SUPPORTED_DIMENSIONS = ["price", "room_type", "location", "social"]


def format_history(history: List[Dict]) -> str:
    """格式化最近对话记录（最多6轮）"""
    turns = []
    for turn in history[-6:]:
        role = "User" if turn["type"] == "human" else "Assistant"
        turns.append(f"{role}: {turn['data']}")
    return "\n".join(turns)

def build_prompt(user_input: str, history: List[Dict]) -> str:
    dialogue = format_history(history)

    return f"""
You are an AI assistant that helps maintain a structured user preference list for a conversational recommendation system.

Your task is to analyze the most recent user message (within full dialogue history), and return:
1. Their intent — one of: preference_update, recommendation, qa, chart_request, preference_confirm, unknown.
2. A dictionary of slot updates — such as price_min, price_max, room_type, location, keywords, or social_flag.
3. A preference_modification type — one of: add, overwrite, remove, none.

✅ Output MUST be a JSON object and NOTHING else.
✅ Think carefully — does the user want to add, change, or confirm a preference?

---
Here are some examples:

Example 1:
User: I want something quiet in Kreuzberg under 100 euros.
→
{{
  "intent": "qa",
  "slots": {{
    "price_max": 100,
    "neighbourhood": "Kreuzberg",
    "keywords": ["quiet"],
    "social_flag": true
  }},
  "preference_modification": "add"
}}

Example 2:
User: Please change the budget to 150–200.
→
{{
  "intent": "preference_update",
  "slots": {{
    "price_min": 150,
    "price_max": 200
  }},
  "preference_modification": "overwrite"
}}

Example 3:
User: I want to see some recommendations.
→
{{
  "intent": "recommendation",
  "slots": {{}},
  "preference_modification": "none"
}}

Now analyze the following dialogue and return only the result in JSON:

Dialogue:
{dialogue}
User: {user_input}
""".strip()

FLEXIBLE_PREFERENCE_PROMPT = """
You are an AI assistant tasked with extracting structured preferences for Airbnb listings from a user's chat log.

Here are the only fields you should map the user's preferences to:

1. room_type: the type of listing ("Entire home/apt" or "Private room").

2. budget: the user's daily budget/price. Normalize budget language into operators:
   - "under / less than / up to / at most / no more than / max / cap N" → "<= N"
   - "over / at least / minimum / from N" → ">= N"
   - "around / about / roughly / approximately / near / N-ish / give or take" with a single number N and no direction → encode a two-sided range as ">= floor(0.9*N) & <= ceil(1.1*N)".
   - If a single bare number N is mentioned with no cue, default to "<= N".
   - If a numeric range is stated (e.g., N to M), encode as ">= N & <= M".
   - Ignore currency symbols and "per night" text; treat €/$ as the same.
   - If only qualitative terms appear (e.g., "cheap", "tight budget", "student budget", "mid-range", "luxury") without numbers, set budget to null and include that qualitative phrase in "missing_dimension".
   - If multiple budgets are mentioned, always choose the last numeric constraint from the latest user message and override earlier mentions.
   - **After rounding (using floor/ceil as specified above), clamp all numeric values to the inclusive range [0, 11000]. Values < 0 become 0; values > 11000 become 11000. Apply clamping to both ends of ranges.**

3. minimum_stay: the minimum number of days the user plans to stay.

4. maximum_stay: the maximum number of days the user plans to stay.

5. location: whether the user is interested in listings in the same area (true or false). If the text names a specific district/neighbourhood instead of expressing “same area”, leave this field as null and put the named location into "missing_dimension".

6. social_dimension: whether the user is interested in other users' reviews (true or false)

7. keywords: phrases that users care about in guest reviews / dimensions that users care about when seeking advice and getting recommendations (e.g., cleanliness, noise, safety, parking, host responsiveness, etc.).

Instructions:

1. Read the user's request carefully and map any stated preferences or requirements (if applicable) to the above field names. Prefer the most recent user statement when conflicts exist.
2. Combine all identified preferences into a JSON object with keys and values exactly the same as the above field names.
3. For unmatched entries in the above fields, assign null.
4. If the identified user preference cannot be mapped to any of the above fields, put it in an array called "missing_dimension".
5. The output must be valid JSON, containing only two parts:
   - The fields from the schema with their values.
   - A "missing_dimension" field containing an array of user preferences that are not mapped to the schema (this field must be present).

No additional text, comments or explanations are included. Only the final JSON format is returned.

Note: You receive multi-turn chat text; resolve contradictions by prioritizing the latest user message.
User history message record:
{user_query}

"""

SELF_ITERATION_PROMPT = """
Previously extracted preferences:
{existing_preferences}

Re-analyze the user's original request to reduce null values if possible, but:
1. Do not guess or fabricate information.
2. Only update null fields if clearly supported by the user’s original request.
3. Keep existing non-null values intact unless explicitly contradicted by the original request.
4. Apply the same budget normalization rules as in the initial extraction:
   - Map “under/less than/up to/at most/no more than/max/cap N” → “<= N”
   - Map “over/at least/minimum/from N” → “>= N”
   - For “around/about/roughly/approximately/near/N-ish/give or take N” with no direction, encode a two-sided range “>= floor(0.9*N) & <= ceil(1.1*N)”
   - Single bare number N with no cue → “<= N”
   - Numeric ranges → “>= N & <= M”
   - If only qualitative budget terms exist with no numbers, keep budget as null and add the phrase to "missing_dimension".
   - **After rounding (using floor/ceil as specified above), clamp all numeric values to the inclusive range [0, 11000]. Values < 0 become 0; values > 11000 become 11000. Apply clamping to both ends of ranges.**
    -"Keep existing non-null values unless explicitly contradicted by the latest user message."
5. Prefer the most recent user statement when conflicts exist.

User Original Request:
{user_query}
"""


def extract_preferences(user_query, existing_preferences=None):
    """调用 LLM 提取用户租房偏好"""
    
    #llm_model = get_llm()  # 🔹 获取 LLM 实例
    
    llm_model = get_llm()

    if llm_model is None:
        return {"error": "LLM 未正确加载"}

    try:
        if existing_preferences is None:
            prompt = PromptTemplate(input_variables=["user_query"], template=FLEXIBLE_PREFERENCE_PROMPT)
            input_data = {"user_query": user_query}
        else:
            prompt = PromptTemplate(input_variables=["existing_preferences", "user_query"], template=SELF_ITERATION_PROMPT)
            existing_pref_json = json.dumps(existing_preferences, indent=2)
            input_data = {"existing_preferences": existing_pref_json, "user_query": user_query}

        extraction_chain = LLMChain(llm=llm_model, prompt=prompt, output_key="preferences")
        extracted_preferences_json = extraction_chain.run(**input_data)

        # 确保 JSON 格式正确
        extracted_data = json.loads(extracted_preferences_json)

        # 确保 "missing_dimension" 存在
        if "missing_dimension" not in extracted_data:
            extracted_data["missing_dimension"] = []

        return extracted_data

    except json.JSONDecodeError:
        return {"error": "LLM 生成的 JSON 无法解析"}
    except Exception as e:
        return {"error": f"LLM 解析失败: {str(e)}"}

def iterative_extraction_pipeline(user_query, iterations=2):
    """执行多轮次偏好提取"""
    preferences = extract_preferences(user_query)

    for _ in range(iterations - 1):
        # 🔹 避免无效的 `null` 结果进入下一轮
        if preferences.get("error") or all(value is None for value in preferences.values()):
            break  
        preferences = extract_preferences(user_query, preferences)
        
    return preferences

def flatten_history(history: List[Dict]) -> str:
    """将多轮消息拼接为自然语言"""
    turns = []
    for turn in history:
        role = "User" if turn["type"] == "human" else "ai"
        turns.append(f"{role}: {turn['data']}")
    return "\n".join(turns)

import re
import math

def normalize_budget_from_text(latest_text: str) -> str | None:
    """
    仅解析“当前用户这句话”的预算，并归一化为字符串：
    - <= N / >= N / >= A & <= B
    - 匹配 under/less than/up to/no more than/max/cap N → <= N
    - over/at least/minimum/from N → >= N
    - around/about/roughly/approximately/near/N-ish/give or take N → 两侧 ±10%
    - bare number N → <= N
    - 显式范围 N to M / between N and M → >= N & <= M
    - 忽略货币符号和 “per night” 等
    """
    if not latest_text:
        return None

    txt = latest_text.lower()
    # 通用取数
    num = lambda s: float(re.findall(r"\d+(?:\.\d+)?", s)[0]) if re.findall(r"\d+(?:\.\d+)?", s) else None

    # 显式区间
    m = re.search(r"(?:between\s+)?(\d+(?:\.\d+)?)\s*(?:to|and|-|~)\s*(\d+(?:\.\d+)?)", txt)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if a > b: a, b = b, a
        return f">= {math.floor(a)} & <= {math.ceil(b)}"

    # 上限类
    m = re.search(r"(?:under|less than|up to|at most|no more than|max|cap)\s+(\d+(?:\.\d+)?)", txt)
    if m:
        n = float(m.group(1))
        return f"<= {math.ceil(n)}"

    # 下限类
    m = re.search(r"(?:over|at least|minimum|from)\s+(\d+(?:\.\d+)?)", txt)
    if m:
        n = float(m.group(1))
        return f">= {math.floor(n)}"

    # “around/roughly/give or take”等
    m = re.search(r"(?:around|about|roughly|approximately|near|give or take|\b(\d+)\s*-?\s*ish\b)\s*(\d+(?:\.\d+)?)", txt)
    if m:
        n = float(m.group(2))
        lo = math.floor(0.9 * n)
        hi = math.ceil(1.1 * n)
        return f">= {lo} & <= {hi}"

    # bare number → 默认上限
    m = re.search(r"\b(\d+(?:\.\d+)?)\b", txt)
    if m:
        n = float(m.group(1))
        return f"<= {math.ceil(n)}"

    return None

def get_latest_human_text(history: List[Dict]) -> str:
    for turn in reversed(history):
        if turn["type"] == "human":
            return turn["data"]
    return ""

def budget_to_min_max(budget: str):
    if not budget:
        return (None, None)
    s = budget.replace(" ", "")
    if "&<=" in s or "&>=" in s:  # ">= A & <= B"
        parts = [p.strip() for p in s.split("&")]
        lo = next((float(p.split(">=")[1]) for p in parts if ">=" in p), None)
        hi = next((float(p.split("<=")[1]) for p in parts if "<=" in p), None)
        return (int(lo) if lo is not None else None, int(hi) if hi is not None else None)
    if s.startswith("<="):
        return (0, int(float(s[2:])))
    if s.startswith(">="):
        return (int(float(s[2:])), None)
    return (None, None)

def extract_budget_change_from_text(text: str, existing_budget: str = None) -> Dict:
    """
    从用户消息中提取预算变更信息，用于 price_coverage_delta 图表
    
    Args:
        text: 用户消息
        existing_budget: 当前预算（从对话历史中获取）
    
    Returns:
        Dict with base_budget, new_budget, and change_type
    """
    if not text:
        return {}
    
    text_lower = text.lower()
    
    # 检测预算变更关键词
    change_keywords = [
        "increase budget", "decrease budget", "raise budget", "lower budget",
        "budget to", "budget of", "what if", "if i", "change budget",
        "预算增加到", "预算减少到", "预算改为", "如果预算", "预算变化"
    ]
    
    has_change_intent = any(keyword in text_lower for keyword in change_keywords)
    
    if not has_change_intent:
        return {}
    
    # 提取新预算数字
    import re
    budget_match = re.search(r'\b(\d+(?:\.\d+)?)\b', text)
    if not budget_match:
        return {}
    
    new_budget = int(float(budget_match.group(1)))
    
    # 确定变更类型
    is_increase = any(word in text_lower for word in ["increase", "raise", "higher", "more", "增加", "提高", "更高"])
    is_decrease = any(word in text_lower for word in ["decrease", "lower", "less", "减少", "降低", "更低"])
    
    # 尝试从现有预算推断基础预算
    base_budget = None
    if existing_budget:
        try:
            # 解析现有预算
            if existing_budget.startswith("<="):
                base_budget = int(float(existing_budget[2:]))
            elif existing_budget.startswith(">="):
                base_budget = int(float(existing_budget[2:]))
            elif "&<=" in existing_budget:
                # 范围预算，取上限作为基础
                parts = existing_budget.split("&")
                for part in parts:
                    if "<=" in part:
                        base_budget = int(float(part.split("<=")[1]))
                        break
        except:
            pass
    
    # 如果无法从现有预算推断，使用启发式方法
    if base_budget is None:
        if is_increase:
            # 假设增加，基础预算比新预算小
            base_budget = max(50, new_budget - 100)  # 至少50，或新预算-100
        elif is_decrease:
            # 假设减少，基础预算比新预算大
            base_budget = new_budget + 100
        else:
            # 默认情况，假设是从某个合理的基础预算变化
            base_budget = max(50, new_budget - 50)
    
    return {
        "base_budget": base_budget,
        "new_budget": new_budget,
        "change_type": "increase" if is_increase else "decrease" if is_decrease else "change",
        "has_budget_change": True
    }


def analyze_user_intent(user_input: str, history: List[Dict]) -> Dict:
    # 1) 拼出完整历史（便于你记录/调试）
    full_history = history + [{"type": "human", "data": user_input}]
    
    # 2) ✅ 只用"最新的人类消息"做抽取输入（关键改动）
    latest_human_text = get_latest_human_text(full_history)
    if not latest_human_text:
        return {"intent": "unknown", "slots": {}, "preference_modification": "none"}

    # 3) 偏好抽取：改为只对 latest_human_text 做两轮迭代（而不是 full_text）
    preferences = iterative_extraction_pipeline(latest_human_text, iterations=2)

    # 4) 预算归一：基于最新人类消息再做一次硬覆盖兜底
    latest_budget = normalize_budget_from_text(latest_human_text)
    if latest_budget:
        preferences["budget"] = latest_budget

        # —— 同步为 min/max，避免 0–75 残留 ——
        lo, hi = budget_to_min_max(latest_budget)  # 见下方小函数
        preferences["price_min"] = lo
        preferences["price_max"] = hi

    # 5) 🎯 新增：检测预算变更意图，用于 price_coverage_delta 图表
    # 从历史中获取现有预算
    existing_budget = None
    for turn in reversed(history):
        if turn.get("type") == "human" and "budget" in turn.get("data", "").lower():
            # 简单提取历史中的预算信息
            existing_budget = normalize_budget_from_text(turn["data"])
            break
    
    # 检测预算变更
    budget_change = extract_budget_change_from_text(latest_human_text, existing_budget)
    if budget_change.get("has_budget_change"):
        preferences.update(budget_change)
        print(f"🎯 检测到预算变更: {budget_change['base_budget']} -> {budget_change['new_budget']} ({budget_change['change_type']})")

    try:
        print(preferences)
        return preferences
    except Exception as e:
        print(f"[Intent Parser] Failed to parse LLM response: {e}\nRaw: {e}")
        return {
            "intent": "unknown",
            "slots": {},
            "preference_modification": "none"
        }
