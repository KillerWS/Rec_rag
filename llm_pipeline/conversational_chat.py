from load_llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from chat_router import ConversationState, get_conversation_state  # 添加导入
from rag_module.follow_up.preference_follow_up import generate_single_followup  # 添加导入
import json # 添加导入

# 用于存储活跃的聊天会话历史
active_chats = {}

def con_chat_with_memory(message: str, history, pref: dict):
    print("执行con_chat_with_memory 自然对话")
    
    # 获取用户ID，如果没有则使用默认ID
    user_id = pref.get("user_id", "default_user")
    session_id = pref.get("session_id", user_id)  # 使用session_id获取对话状态
    
    # 获取对话状态，用于智能追问
    conv_state = get_conversation_state(session_id)
    
    # 获取 LangChain 兼容的 LLM
    llm = get_llm()
    
    # 检查是否为新会话
    is_new_session = user_id not in active_chats
    
    if is_new_session:
        print("创建新的聊天会话")
        # 定义改进的system prompt，包含已知偏好信息
        system_prompt = _build_system_prompt_with_preferences(conv_state)
        
        # 创建新的聊天会话历史，包含系统指令
        chat_history = [SystemMessage(content=system_prompt)]
        
        # 存储聊天会话历史
        active_chats[user_id] = chat_history
    else:
        print("继续现有聊天会话")
        chat_history = active_chats[user_id]
    
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
        
        # 检查是否需要使用智能追问而不是自由对话
        if conv_state.get_preference_count() > 0 and conv_state.get_completeness_score() < 0.8:
            print("使用智能追问模式而不是自由对话")
            # 使用generate_single_followup生成追问
            followup_result = generate_single_followup(conv_state, message)
            response_text = followup_result.get("question")
            
            # 将追问回复添加到历史中
            chat_history.append(AIMessage(content=response_text))
            active_chats[user_id] = chat_history
            
            return response_text
            
        # 如果完整度高或没有收集到偏好，使用LLM进行自由对话
        print("使用LLM自由对话模式")
        # 更新LLM的系统提示，包含最新偏好信息
        if len(chat_history) > 0 and isinstance(chat_history[0], SystemMessage):
            chat_history[0] = SystemMessage(content=_build_system_prompt_with_preferences(conv_state))
            
        # 使用 LangChain 的 invoke 方法发送整个对话历史并获取回复
        response = llm.invoke(chat_history)
        response_text = response.content.strip()
        
        # 将 AI 回复添加到历史中
        chat_history.append(AIMessage(content=response_text))
        
        # 更新存储的会话历史
        active_chats[user_id] = chat_history
        
        print(f"response: {response_text}")
        return response_text
        
    except Exception as e:
        print(f"LLM对话失败: {e}")
        return "Sorry, I'm having trouble understanding your request. Could you please try again?"

def _build_system_prompt_with_preferences(conv_state: ConversationState) -> str:
    """构建更专注的系统提示，将关键维度状态直接传递给LLM"""
    
    # 基础提示词
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
    )
    
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
    
    # 添加到提示词中
    system_prompt += f"\n\nCRITICAL DIMENSIONS STATUS: {json.dumps(critical_status, indent=2)}"
    
    # 直接告诉LLM下一步行动
    missing = [dim for dim, info in critical_status.items() if not info["filled"]]
    if missing:
        system_prompt += f"\n\nNEXT ACTION: Ask ONLY about the {missing[0]} dimension."
    else:
        system_prompt += "\n\nALL CRITICAL DIMENSIONS COLLECTED. Ready for recommendations."
    
    return system_prompt

def clear_chat_session(user_id="default_user"):
    """清除指定用户的聊天会话"""
    if user_id in active_chats:
        del active_chats[user_id]
        return True
    return False