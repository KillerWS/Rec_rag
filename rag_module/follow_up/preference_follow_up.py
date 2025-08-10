# preference_follow_up.py (新文件)
import json
from typing import Dict, List, Optional
from chat_router import ConversationState
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

def generate_single_followup(conv_state: ConversationState, user_message: str = "") -> Dict:
    """
    根据ConversationState生成单次追问，避免询问已有维度
    
    Args:
        conv_state: 对话状态对象
        user_message: 用户最新消息
        
    Returns:
        Dict: 包含追问问题和目标维度的字典
    """
    # 获取当前偏好
    preferences = conv_state.preferences
    completeness = conv_state.get_completeness_score()
    
    # 获取缺失的关键维度
    missing_dims = []
    
    # 检查必要维度是否缺失
    if not (preferences.get('price_min') or preferences.get('price_max')):
        missing_dims.append("budget")
    
    if not (preferences.get('neighbourhood_group') or preferences.get('neighbourhood')):
        missing_dims.append("location")
    
    if not preferences.get('room_type'):
        missing_dims.append("room_type")
    
    # 次要维度（仅当完整度较高时才询问）
    if completeness >= 0.5:
        if not preferences.get('minimum_nights'):
            missing_dims.append("stay_duration")
        if not preferences.get('min_reviews'):
            missing_dims.append("popularity")
    
    # 如果没有缺失的维度，可以推荐了
    if not missing_dims:
        return {
            "question": "I think I have enough information. Ready to see some great recommendations?",
            "target_dimension": "none",
            "ready_for_recommendation": True
        }
    
    # 选择最重要的缺失维度来询问
    first_missing = missing_dims[0]
    
    # 尝试使用LLM生成自然追问
    llm_question = try_simple_llm_generation(first_missing, user_message, preferences)
    
    if llm_question:
        return {
            "question": llm_question,
            "target_dimension": first_missing,
            "method": "llm",
            "ready_for_recommendation": False
        }
    
    # LLM生成失败，使用模板问题
    template_questions = {
        "budget": "What's your budget range per night? This will help me find the best options for you.",
        "location": "Which area of Berlin would you prefer? Central, trendy, or quieter neighborhoods?",
        "room_type": "Would you like a private room or entire place?",
        "stay_duration": "How long are you planning to stay?",
        "popularity": "Do you prefer popular, well-reviewed places or are you open to newer listings?"
    }
    
    question = template_questions.get(first_missing, "Tell me more about your preferences!")
    
    return {
        "question": question,
        "target_dimension": first_missing,
        "method": "template",
        "ready_for_recommendation": False
    }

def try_simple_llm_generation(dimension: str, user_message: str, preferences: Dict) -> Optional[str]:
    """
    使用LLM为指定维度生成追问，避免询问已有信息
    
    Args:
        dimension: 要询问的维度
        user_message: 用户最近的消息
        preferences: 当前用户偏好字典
        
    Returns:
        Optional[str]: 生成的问题或None（如果生成失败）
    """
    try:
        from load_llm import get_llm
        from langchain.chains import LLMChain
        from langchain.prompts import PromptTemplate
        
        llm = get_llm()
        if not llm:
            return None
        
        # 构建偏好摘要，帮助LLM理解上下文
        preference_summary = []
        if preferences.get('price_min') and preferences.get('price_max'):
            preference_summary.append(f"budget: €{preferences['price_min']}-{preferences['price_max']}")
        elif preferences.get('price_max'):
            preference_summary.append(f"budget: up to €{preferences['price_max']}")
        elif preferences.get('price_min'):
            preference_summary.append(f"budget: from €{preferences['price_min']}")
            
        if preferences.get('neighbourhood'):
            preference_summary.append(f"area: {preferences['neighbourhood']}")
        elif preferences.get('neighbourhood_group'):
            preference_summary.append(f"district: {preferences['neighbourhood_group']}")
            
        if preferences.get('room_type'):
            preference_summary.append(f"room type: {preferences['room_type']}")
            
        if preferences.get('minimum_nights'):
            preference_summary.append(f"stay duration: {preferences['minimum_nights']} nights")
        
        # 改进的LLM提示，明确指示不要询问已有信息
        prompt_template = """You are an assistant helping find accommodation in Berlin.

Current user preferences: {preference_summary}

User's last message: "{user_message}"

Generate ONE natural question asking ONLY about {dimension} for Berlin accommodation.
DO NOT ask about preferences the user has already provided. Be brief and friendly.
Your question must end with a question mark. Maximum 20 words.

Question:"""
        
        prompt = PromptTemplate(
            input_variables=["preference_summary", "user_message", "dimension"],
            template=prompt_template
        )
        
        chain = LLMChain(llm=llm, prompt=prompt)
        
        response = chain.predict(
            preference_summary=", ".join(preference_summary) if preference_summary else "no preferences yet",
            user_message=user_message or "looking for accommodation",
            dimension=dimension
        )
        
        # 简单验证和提取
        response = response.strip()
        if len(response) > 10 and len(response) < 150 and '?' in response:
            # 提取第一个问句
            sentences = response.split('?')
            if sentences:
                question = sentences[0].strip() + '?'
                if 10 < len(question) < 150:
                    print(f"✅ LLM生成追问成功: {question}")
                    return question
        
        print(f"❌ LLM生成质量不佳: {response}")
        return None
        
    except Exception as e:
        print(f"❌ LLM生成失败: {e}")
        return None

def get_unified_followup(conv_state: ConversationState, user_message: str = "", use_intelligent_system: bool = True) -> Dict:
    """
    统一的追问生成函数，可以选择使用简单追问或智能追问系统
    
    Args:
        conv_state: 对话状态
        user_message: 用户消息
        use_intelligent_system: 是否使用更复杂的智能追问系统
        
    Returns:
        Dict: 追问结果
    """
    if use_intelligent_system:
        try:
            # 尝试使用智能追问系统
            from intelligent_followup import analyze_followup_needs, generate_smart_followup
            
            followup_analysis = analyze_followup_needs(conv_state.preferences, conv_state.conversation_history)
            followup_question = generate_smart_followup(followup_analysis, user_message, conv_state.preferences)
            
            return followup_question
        except Exception as e:
            print(f"❌ 智能追问系统失败，回退到简单追问: {e}")
            # 失败时回退到简单追问
    
    # 使用简单追问系统
    return generate_single_followup(conv_state, user_message)