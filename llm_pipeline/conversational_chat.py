from load_llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from chat_router import ConversationState, get_conversation_state  # 添加导入
from rag_module.follow_up.preference_follow_up import generate_single_followup  # 添加导入
import json # 添加导入
import re

# 用于存储活跃的聊天会话历史
active_chats = {}

def con_chat_with_memory(message: str, history, pref: dict):
    print("执行con_chat_with_memory 自然对话")
    
    # 统一基于 session_id 管理会话；兼容旧参数
    session_id = pref.get("session_id") or pref.get("user_id") or "default_session"

    # 获取对话状态，用于智能追问
    conv_state = get_conversation_state(session_id)
    
    # 获取 LangChain 兼容的 LLM
    llm = get_llm()
    
    # 检查是否为新会话
    is_new_session = session_id not in active_chats
    
    if is_new_session:
        print("创建新的聊天会话")
        # 定义改进的system prompt，包含已知偏好信息
        system_prompt = _build_system_prompt_with_preferences(conv_state)
        
        # 创建新的聊天会话历史，包含系统指令
        chat_history = [SystemMessage(content=system_prompt)]
        
        # 存储聊天会话历史
        active_chats[session_id] = chat_history
    else:
        print("继续现有聊天会话")
        chat_history = active_chats[session_id]
    
    # 如果有历史记录但是是新会话，需要重建历史记录
    if is_new_session and history and len(history) > 0:
        print(f"重建历史记录 ({len(history)} 条消息)")
        for msg in history:
            if msg["type"] == "user":  # 用户消息
                chat_history.append(HumanMessage(content=msg["data"]))
            elif msg["type"] == "bot":  # 机器人消息
                chat_history.append(AIMessage(content=msg["data"]))
    
    try:
        # 添加当前用户消息到历史
        chat_history.append(HumanMessage(content=message))
        
        # 检查是否需要使用智能追问而不是自由对话（基于关键维度是否齐全）
        essential = conv_state.has_essential_preferences()
        completeness = conv_state.get_completeness_score()
        print(f"智能追问门槛检查: essential_complete={essential['is_complete']}, completeness={completeness:.2f}")
        if not essential["is_complete"]:
            print("使用智能追问模式而不是自由对话（关键维度未齐全）")
            # 使用generate_single_followup生成追问
            followup_result = generate_single_followup(conv_state, message)
            response_text = followup_result.get("question")
            
            # 将追问回复添加到历史中
            chat_history.append(AIMessage(content=response_text))
            active_chats[session_id] = chat_history
            
            return response_text
        else:
            # 关键维度已齐全：如用户为泛化应答（yes/ok/thanks等），直接给探索/评估引导
            if _should_use_guidance(message):
                guidance = _build_post_essentials_guidance(conv_state)
                chat_history.append(AIMessage(content=guidance))
                active_chats[session_id] = chat_history
                return guidance
            
        # 如果完整度高或没有收集到偏好，使用LLM进行自由对话
        print("使用LLM自由对话模式")
        # 更新LLM的系统提示，包含最新偏好信息
        if len(chat_history) > 0 and isinstance(chat_history[0], SystemMessage):
            chat_history[0] = SystemMessage(content=_build_system_prompt_with_preferences(conv_state))
            
        # 使用 LangChain 的 invoke 方法发送整个对话历史并获取回复
        response = llm.invoke(chat_history)
        response_text = response.content.strip()
        # 在返回之前，基于当前偏好对预算表达进行规范化，避免出现诸如 "€4" 的截断
        response_text = _fix_budget_truncation(response_text, conv_state)
        
        # 将 AI 回复添加到历史中
        chat_history.append(AIMessage(content=response_text))
        
        # 更新存储的会话历史
        active_chats[session_id] = chat_history
        
        print(f"response: {response_text}")
        return response_text
        
    except Exception as e:
        print(f"LLM对话失败: {e}")
        return "Sorry, I'm having trouble understanding your request. Could you please try again?"

def _build_system_prompt_with_preferences(conv_state: ConversationState) -> str:
	"""构建更专注的系统提示，将关键维度状态直接传递给LLM"""

	# 提取关键维度状态
	prefs = conv_state.preferences
	critical_status = {
		"location": {
			"filled": bool(prefs.get('neighbourhood') or prefs.get('neighbourhood_group')),
			"value": prefs.get('neighbourhood') or prefs.get('neighbourhood_group') or None,
			"type": "neighbourhood" if prefs.get('neighbourhood') else ("neighbourhood_group" if prefs.get('neighbourhood_group') else None)
		},
		"price": {
			"filled": bool(prefs.get('price_min') or prefs.get('price_max')),
			"min": prefs.get('price_min'),
			"max": prefs.get('price_max')
		},
		"room_type": {
			"filled": bool(prefs.get('room_type')),
			"value": prefs.get('room_type')
		}
	}

	# 判断关键维度是否齐全
	missing = [dim for dim, info in critical_status.items() if not info["filled"]]
	essentials_complete = (len(missing) == 0)

	# 当关键要素未齐全：沿用原有提示词（不改动）
	if not essentials_complete:
		# 基础提示词（原样保留）
		system_prompt = (
			"You are a focused accommodation assistant for Berlin Airbnb. Follow these strict rules:"
			"\n1. Be extremely concise - limit responses to 1-2 sentences"
			"\n2. Focus ONLY on collecting the THREE critical dimensions: location, price range, and room type"
			"\n3. Only ask about ONE missing dimension in each response"
			"\n4. NEVER engage in chitchat or irrelevant conversation"
			"\n5. NEVER ask about dimensions that are already provided"
			"\n6. Use natural, friendly English language appropriate for an international app"
			"\n7. Always prioritize collecting missing critical dimensions before anything else"
			"\n8. Do not provide recommendations until all three critical dimensions are collected"
			"\n9. If the user asks who you are or what you can do, briefly answer: \"I'm your Berlin Airbnb assistant.\" Then immediately follow NEXT ACTION to ask ONLY about the next missing critical dimension."
		)
		# 添加到提示词中
		system_prompt += f"\n\nCRITICAL DIMENSIONS STATUS: {json.dumps(critical_status, indent=2)}"
		# 明确下一步
		system_prompt += f"\n\nNEXT ACTION: Ask ONLY about the {missing[0]} dimension."
		return system_prompt

	# 当关键要素齐全（探索/评估阶段）：使用新的探索阶段提示词
	# 生成 brief_prefs（简要偏好摘要）
	brief_parts = []
	area = prefs.get('neighbourhood') or prefs.get('neighbourhood_group')
	if area:
		brief_parts.append(f"area: {area}")
	if prefs.get('room_type'):
		brief_parts.append(f"room_type: {prefs.get('room_type')}")
	if prefs.get('price_min') is not None and prefs.get('price_max') is not None:
		brief_parts.append(f"budget: €{prefs.get('price_min')}-{prefs.get('price_max')}")
	elif prefs.get('price_min') is not None:
		brief_parts.append(f"budget: from €{prefs.get('price_min')}")
	elif prefs.get('price_max') is not None:
		brief_parts.append(f"budget: up to €{prefs.get('price_max')}")
	brief_prefs = ", ".join(brief_parts) if brief_parts else "(not specified)"

	# UI 状态注入
	has_shown_listings = getattr(conv_state, 'has_shown_listings', False)
	last_visualizations = getattr(conv_state, 'last_visualizations', None)
	if last_visualizations is None:
		last_visualizations_str = "none"
	else:
		try:
			last_visualizations_str = json.dumps(last_visualizations)
		except Exception:
			last_visualizations_str = str(last_visualizations)

	# 新的探索阶段提示词
	system_prompt = (
		"You are the Berlin Airbnb assistant in the EXPLORE stage."
		"\n\nContext:"
		"\n- CRITICAL DIMENSIONS are COMPLETE."
		f"\n- USER PREFERENCES (summarized): {brief_prefs}"
		f"\n- UI STATE: has_shown_listings={str(has_shown_listings).lower()}, last_visualizations={last_visualizations_str}"
		"\n\nRules (strict):"
		"\n1) ANSWER-FIRST: If the user asks a question, give a clear, useful, 1–2 sentence answer."
		"\n2) EVIDENCE NUDGE: After the answer, suggest exactly ONE next step that maps to a concrete artifact:"
		"\n   - chart: price distribution (budget coverage), area comparison, availability trend, room-type split"
		"\n   - map: district/community heatmap"
		"\n   - reviews: open Review Q&A with sources"
		"\n   The nudge must be one line, no menus, no multiple options."
		"\n3) NO REPETITION: Do not repeat the same nudge within 5 minutes or if it was the last visualization shown."
		"\n4) LISTINGS HOOK: If listings are already visible on the left, briefly reference them (\"I’ve updated the left panel\")."
		"\n5) BE Terse & Helpful: 1–2 sentences for the answer + 1 short nudge line. No small talk."
		"\n\nStyle:"
		"\n- Friendly, decision-oriented, concrete. Avoid generic \"Would you like 1/2/3?\" menus."
		"\n\nOutput shape:"
		"\n- Text only (answer + single nudge). Do not list options."
	)
	return system_prompt

def _format_budget_from_prefs(prefs: dict) -> str | None:
    """根据偏好生成标准预算文案。"""
    min_price = prefs.get('price_min')
    max_price = prefs.get('price_max')
    if min_price is not None and max_price is not None:
        return f"€{min_price}-{max_price}"
    if min_price is not None:
        return f"from €{min_price}"
    if max_price is not None:
        return f"up to €{max_price}"
    return None

def _fix_budget_truncation(text: str, conv_state: ConversationState) -> str:
    """修复模型在文案中对预算的截断或不一致表达，不改变其他内容。

    策略：
    1) 如果检测到“within your €...”结构，则用基于偏好的标准预算文案整体替换该片段；
    2) 若未替换且文本包含列表更新的提示（listings/left panel），而标准预算不在文本中，则在末尾补充标准预算。
    """
    try:
        prefs = conv_state.preferences if hasattr(conv_state, 'preferences') else {}
        canonical = _format_budget_from_prefs(prefs)
        if not canonical:
            return text

        # 1) 定位并替换典型片段：within your €<token>
        pattern = re.compile(r"(?i)(within\s+your\s+)€[^\s,.;)]+")
        replaced, n = pattern.subn(rf"\1{canonical}", text)
        if n > 0:
            return replaced

        # 2) 若包含列表更新的典型措辞且未出现标准预算，则在末尾补充标准预算
        lower = text.lower()
        mentions_hook = ("left panel" in lower) or ("updated the listings" in lower) or ("updated the left panel" in lower) or ("listings" in lower)
        if mentions_hook and canonical not in text:
            sep = " " if not text.endswith(('.', '!', '?')) else ""
            return f"{text}{sep} (budget: {canonical})"

        return text
    except Exception:
        # 出现异常不影响主流程
        return text

def _should_use_guidance(message: str) -> bool:
    """当用户是泛化反馈时，触发探索/评估引导而非重复确认。"""
    m = (message or "").strip().lower()
    accept_terms = [
        "yes", "yes!", "ok", "okay", "sure", "sounds good", "great", "perfect",
        "go ahead", "give it to me", "let's see", "fine", "alright"
    ]
    return any(m == term for term in accept_terms)

def _build_post_essentials_guidance(conv_state: ConversationState) -> str:
    """关键维度已齐全后的引导：建议查看口碑/可视化/筛选。"""
    prefs = conv_state.preferences
    area = prefs.get('neighbourhood') or prefs.get('neighbourhood_group') or 'your selected area'
    budget = None
    if prefs.get('price_min') and prefs.get('price_max'):
        budget = f"€{prefs['price_min']}-€{prefs['price_max']}"
    elif prefs.get('price_max'):
        budget = f"up to €{prefs['price_max']}"
    elif prefs.get('price_min'):
        budget = f"from €{prefs['price_min']}"
    rt = (prefs.get('room_type') or '').lower()
    brief = f"{rt} in {area}" if rt else f"in {area}"
    if budget:
        brief += f", budget {budget}"

    return (
        f"Great — I’ve got your essentials ({brief}). Would you like to: "
        f"1) explore review insights, 2) see price and availability charts, or 3) view recommendations now?"
    )

def clear_chat_session(session_id="default_session"):
    """清除指定会话的聊天会话"""
    if session_id in active_chats:
        del active_chats[session_id]
        return True
    return False