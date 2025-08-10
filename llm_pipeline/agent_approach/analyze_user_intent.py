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

2. budget: the user's daily budget/price, if the user describes a range, use ">=" or "<=" symbols, without a currency symbol.

3. minimum_stay: the minimum number of days the user plans to stay.

4. maximum_stay: the maximum number of days the user plans to stay.

5. location: whether the user is interested in listings in the same area (true or false)

6. social_dimension: whether the user is interested in other users' reviews (true or false)

7. keywords: phrases that users care about in guest reviews / dimensions that users care about when seeking advice and getting recommendations(e.g. cleanliness, noise, safety, parking, host responsiveness, etc.).

Instructions:

1. Read the user's request carefully and map any stated preferences or requirements (if applicable) to the above field names.

2. Combine all identified preferences into a JSON object with keys and values ​​exactly the same as the above field names.
3. For unmatched entries in the above fields, assign null.
4. If the identified user preference cannot be mapped to any of the above fields, put it in an array called "missing_dimension".
5. The output must be valid JSON, containing only two parts:
- An array of fields from the schema (if mentioned) and their corresponding user preference values.
- A "missing_dimension" field containing an array of user preferences that are not mapped to the schema (this field must be present).

No additional text, comments or explanations are included. Only the final JSON format is returned.


Note that you get a json array containing the conversation between ai and human, pay attention to recognition,User history message record:
{user_query}
"""

SELF_ITERATION_PROMPT = """
Previously extracted preferences:
{existing_preferences}

Re-analyze the user's original request to reduce null values if possible, but:
1. Do not guess or fabricate information.
2. Only update null fields if clearly supported by the user’s original request.
3. Keep existing non-null values intact unless explicitly incorrect.

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

def analyze_user_intent(user_input: str, history: List[Dict]) -> Dict:
    # prompt = build_prompt(user_input, history)
    # llm = get_llm()
    # llm = get_llm()
    # response = llm.invoke(prompt)

    # if llm is None:
    #     return {"error": "LLM 未正确加载"}
    # 包含当前输入
    full_history = history + [{"type": "human", "data": user_input}]
    full_text = flatten_history(full_history)  # 🔥 完整上下文
     # 1️⃣ 解析用户偏好和意图
    preferences = iterative_extraction_pipeline(full_text, iterations=2)

    try:
        # result = json.loads(response)
        print(preferences)
        return preferences
    except Exception as e:
        print(f"[Intent Parser] Failed to parse LLM response: {e}\nRaw: {response}")
        return {
            "intent": "unknown",
            "slots": {},
            "preference_modification": "none"
        }
