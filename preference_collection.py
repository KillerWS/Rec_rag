# preference_collection.py
import re
from typing import Dict, List, Optional

def handle_preference_collection(user_message: str, intent_result: Dict, current_prefs: Dict = None, slot_result: Dict = None) -> str:
    """
    处理偏好收集阶段的对话
    
    参数:
    - user_message: 用户输入的消息
    - intent_result: 意图识别结果 {"intent": "preference_update", "confidence": 0.9}
    - current_prefs: 当前已收集的用户偏好
    - slot_result: 槽位提取结果（可选）
    
    返回:
    - 对用户的回复消息
    """
    
    if current_prefs is None:
        current_prefs = {}
    
    # 1. 分析用户提供了什么新信息
    provided_info = analyze_provided_information(user_message, intent_result, slot_result)
    
    # 2. 确认收到的信息
    confirmation = generate_confirmation(provided_info)
    
    # 3. 检查还缺少什么关键信息
    missing_info = check_missing_critical_info(current_prefs, provided_info)
    
    # 4. 生成引导问题
    guidance = generate_guidance_question(missing_info, current_prefs)
    
    # 5. 组合最终回复
    return combine_response(confirmation, guidance, missing_info)

def analyze_provided_information(user_message: str, intent_result: Dict, slot_result: Dict = None) -> Dict:
    """
    分析用户在这轮对话中提供了什么信息
    """
    provided = {
        "price_info": False,
        "location_info": False, 
        "room_type_info": False,
        "duration_info": False,
        "guest_count_info": False,
        "specific_values": {}
    }
    
    msg_lower = user_message.lower()
    
    # 方法1: 从slot_result获取信息（如果有的话）
    if slot_result and slot_result.get("slots"):
        extracted_slots = slot_result["slots"]
        
        if any(key in extracted_slots for key in ["price_min", "price_max"]):
            provided["price_info"] = True
            provided["specific_values"]["price"] = {
                "min": extracted_slots.get("price_min"),
                "max": extracted_slots.get("price_max")
            }
            
        if "neighbourhood" in extracted_slots:
            provided["location_info"] = True
            provided["specific_values"]["location"] = extracted_slots["neighbourhood"]
            
        if "room_type" in extracted_slots:
            provided["room_type_info"] = True
            provided["specific_values"]["room_type"] = extracted_slots["room_type"]
            
        if "duration_nights" in extracted_slots:
            provided["duration_info"] = True
            provided["specific_values"]["duration"] = extracted_slots["duration_nights"]
            
        if "guest_count" in extracted_slots:
            provided["guest_count_info"] = True
            provided["specific_values"]["guest_count"] = extracted_slots["guest_count"]
    
    # 方法2: 简单规则检测（兜底）
    else:
        # 检测价格相关词汇
        if any(word in msg_lower for word in ["budget", "price", "euro", "€", "cost", "expensive", "cheap"]):
            provided["price_info"] = True
            
        # 检测地点相关词汇
        berlin_areas = ["mitte", "kreuzberg", "prenzlauer", "friedrichshain", "charlottenburg", "central", "center"]
        if any(area in msg_lower for area in berlin_areas):
            provided["location_info"] = True
            
        # 检测房间类型
        if any(room in msg_lower for room in ["private", "shared", "entire", "apartment", "room"]):
            provided["room_type_info"] = True
    
    return provided

def generate_confirmation(provided_info: Dict) -> str:
    """
    生成对用户提供信息的确认
    """
    confirmations = []
    specific_values = provided_info.get("specific_values", {})
    
    # 确认价格信息
    if provided_info["price_info"]:
        if "price" in specific_values:
            price_info = specific_values["price"]
            if price_info["min"] and price_info["max"]:
                confirmations.append(f"budget {price_info['min']}-{price_info['max']}€")
            elif price_info["max"]:
                confirmations.append(f"budget up to {price_info['max']}€")
            elif price_info["min"]:
                confirmations.append(f"budget from {price_info['min']}€")
        else:
            confirmations.append("budget preference")
    
    # 确认地点信息
    if provided_info["location_info"]:
        if "location" in specific_values:
            confirmations.append(f"{specific_values['location']} area")
        else:
            confirmations.append("location preference")
    
    # 确认房间类型
    if provided_info["room_type_info"]:
        if "room_type" in specific_values:
            confirmations.append(f"{specific_values['room_type'].lower()}")
        else:
            confirmations.append("room type preference")
    
    # 确认住宿时长
    if provided_info["duration_info"]:
        if "duration" in specific_values:
            nights = specific_values['duration']
            confirmations.append(f"{nights} night{'s' if nights > 1 else ''}")
        else:
            confirmations.append("duration")
    
    # 确认住客数量
    if provided_info["guest_count_info"]:
        if "guest_count" in specific_values:
            count = specific_values['guest_count']
            confirmations.append(f"for {count} guest{'s' if count > 1 else ''}")
        else:
            confirmations.append("guest count")
    
    # 生成确认文本
    if confirmations:
        if len(confirmations) == 1:
            return f"Got it! I've noted your {confirmations[0]}."
        elif len(confirmations) == 2:
            return f"Perfect! I've noted: {confirmations[0]} and {confirmations[1]}."
        else:
            confirmation_list = ", ".join(confirmations[:-1]) + f", and {confirmations[-1]}"
            return f"Excellent! I've noted: {confirmation_list}."
    else:
        return "Thanks for the information!"

def check_missing_critical_info(current_prefs: Dict, provided_info: Dict) -> List[str]:
    """
    检查还缺少哪些关键信息
    """
    # 定义关键信息的优先级
    critical_info = ["price_max", "neighbourhood"]  # 最关键的
    important_info = ["room_type"]  # 重要但可以有默认值
    
    missing = []
    
    # 检查价格信息
    has_price = (current_prefs.get("price_max") is not None or 
                 current_prefs.get("price_min") is not None or 
                 provided_info["price_info"])
    if not has_price:
        missing.append("budget")
    
    # 检查地点信息
    has_location = (current_prefs.get("neighbourhood") is not None or 
                   provided_info["location_info"])
    if not has_location:
        missing.append("area")
    
    # 检查房间类型（不太关键，可以有默认值）
    has_room_type = (current_prefs.get("room_type") is not None or 
                    provided_info["room_type_info"])
    if not has_room_type:
        missing.append("room_type")
    
    return missing

def generate_guidance_question(missing_info: List[str], current_prefs: Dict) -> str:
    """
    基于缺失信息生成引导问题
    """
    if not missing_info:
        # 所有关键信息都有了，可以进入推荐阶段
        return "Ready to see some listings?"
    
    # 优先询问最重要的缺失信息
    if "budget" in missing_info and "area" in missing_info:
        return "What's your budget range and which Berlin area would you prefer?"
    
    elif "budget" in missing_info:
        return "What's your budget range per night?"
    
    elif "area" in missing_info:
        return "Which area of Berlin interests you most? (Mitte, Kreuzberg, Prenzlauer Berg, etc.)"
    
    elif "room_type" in missing_info:
        return "Would you prefer a private room, shared room, or entire apartment?"
    
    else:
        # 有其他缺失信息
        return "Any other preferences for your Berlin stay?"

def combine_response(confirmation: str, guidance: str, missing_info: List[str]) -> str:
    """
    组合确认和引导问题成为最终回复
    """
    if not missing_info:
        # 信息收集完毕，准备推荐
        return f"{confirmation} {guidance}"
    
    else:
        # 还需要收集更多信息
        return f"{confirmation} {guidance}"

# 增强版本：考虑对话上下文
def handle_preference_collection_contextual(
    user_message: str, 
    intent_result: Dict, 
    current_prefs: Dict,
    slot_result: Dict,
    conversation_history: List[Dict]
) -> Dict:
    """
    考虑对话上下文的偏好收集处理
    
    返回:
    {
        "response": "回复文本",
        "next_stage": "preference_collection" | "ready_for_recommendations",
        "updated_prefs": {...},
        "collection_progress": 0.8  # 0-1之间，表示收集完成度
    }
    """
    
    # 1. 分析提供的信息
    provided_info = analyze_provided_information(user_message, intent_result, slot_result)
    
    # 2. 更新偏好
    updated_prefs = update_preferences_from_provided_info(current_prefs, provided_info, slot_result)
    
    # 3. 计算收集进度
    progress = calculate_collection_progress(updated_prefs)
    
    # 4. 生成回复
    confirmation = generate_confirmation(provided_info)
    missing_info = check_missing_critical_info(updated_prefs, provided_info)
    guidance = generate_guidance_question(missing_info, updated_prefs)
    
    response = combine_response(confirmation, guidance, missing_info)
    
    # 5. 决定下一阶段
    next_stage = "ready_for_recommendations" if progress >= 0.8 else "preference_collection"
    
    return {
        "response": response,
        "next_stage": next_stage,
        "updated_prefs": updated_prefs,
        "collection_progress": progress,
        "missing_info": missing_info
    }

def update_preferences_from_provided_info(current_prefs: Dict, provided_info: Dict, slot_result: Dict) -> Dict:
    """从提供的信息更新偏好"""
    updated = current_prefs.copy()
    
    if slot_result and slot_result.get("slots"):
        for key, value in slot_result["slots"].items():
            if value is not None:
                updated[key] = value
    
    return updated

def calculate_collection_progress(prefs: Dict) -> float:
    """计算偏好收集进度 (0-1)"""
    required_fields = ["price_max", "neighbourhood"]
    optional_fields = ["room_type", "guest_count"]
    
    required_score = sum(1 for field in required_fields if prefs.get(field) is not None)
    optional_score = sum(0.5 for field in optional_fields if prefs.get(field) is not None)
    
    max_score = len(required_fields) + len(optional_fields) * 0.5
    current_score = required_score + optional_score
    
    return min(1.0, current_score / max_score)

# 测试示例
def test_preference_collection():
    """测试偏好收集功能"""
    
    test_cases = [
        {
            "message": "My budget is around 150 euros",
            "intent": {"intent": "preference_update", "confidence": 0.9},
            "current_prefs": {},
            "slot_result": {"slots": {"price_min": 130, "price_max": 170}}
        },
        {
            "message": "I want something in Kreuzberg",
            "intent": {"intent": "preference_update", "confidence": 0.85},
            "current_prefs": {"price_max": 170},
            "slot_result": {"slots": {"neighbourhood": "Kreuzberg"}}
        },
        {
            "message": "Private room please",
            "intent": {"intent": "preference_update", "confidence": 0.8},
            "current_prefs": {"price_max": 170, "neighbourhood": "Kreuzberg"},
            "slot_result": {"slots": {"room_type": "Private room"}}
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n=== 测试案例 {i} ===")
        print(f"用户消息: {case['message']}")
        print(f"当前偏好: {case['current_prefs']}")
        
        result = handle_preference_collection_contextual(
            case["message"], 
            case["intent"], 
            case["current_prefs"],
            case["slot_result"],
            []
        )
        
        print(f"回复: {result['response']}")
        print(f"更新后偏好: {result['updated_prefs']}")
        print(f"收集进度: {result['collection_progress']:.1%}")
        print(f"下一阶段: {result['next_stage']}")

# if __name__ == "__main__":
#     test_preference_collection()