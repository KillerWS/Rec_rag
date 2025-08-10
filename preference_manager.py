"""
修复的偏好管理模块 - 完整版
解决LangChain模板变量问题和代码结构问题
"""

import json
import re
import numpy as np
from typing import Dict, List, Optional, Any

# 如果在实际环境中运行，取消注释以下导入
# from langchain.chains import LLMChain
# from langchain.prompts import PromptTemplate
# from load_llm import get_llm
# from db import execute_query

class PreferenceManager:
    """管理用户偏好的累积和更新"""
    
    def __init__(self):
        self.llm_model = None
        # 🎯 根据数据库字段重新设计schema
        self.preference_schema = {
            # 直接映射到数据库字段
            "room_type": None,              # room_type: Entire home/apt, Private room, Shared room, Hotel room
            "price_min": None,              # price字段的最小值
            "price_max": None,              # price字段的最大值
            "neighbourhood_group": None,    # neighbourhood_group (12个大区)
            "neighbourhood": None,          # neighbourhood (138个具体社区)
            "minimum_nights": None,         # minimum_nights 最少住宿天数
            "maximum_nights": None,         # 推导的最大住宿天数
            
            # 基于existing字段的筛选条件
            "min_reviews": None,            # number_of_reviews 最少评论数（热度指标）
            "reviews_per_month_min": None,  # reviews_per_month 月评论数（活跃度）
            "availability_min": None,       # availability_365 可预订天数
            
            # 语义搜索字段（用于评论和描述搜索）
            "amenities_keywords": [],       # 设施相关关键词：["wifi", "air conditioning", "kitchen"]
            "location_keywords": [],        # 位置相关关键词：["near subway", "close to center", "quiet area"]
            "comfort_keywords": [],         # 舒适度关键词：["clean", "comfortable", "spacious"]
            
            # 无法直接映射的偏好
            "missing_dimension": []         # 暂时无法处理的用户偏好
        }
    
    def get_llm(self):
        """获取LLM实例"""
        if self.llm_model is None:
            try:
                from load_llm import get_llm
                self.llm_model = get_llm()
            except ImportError:
                print("警告: 无法导入LLM模块，将使用模拟数据")
                return None
        return self.llm_model

# 🎯 修复的提示模板 - 使用双大括号避免格式化问题
ENHANCED_PREFERENCE_PROMPT = """
You are an AI assistant that extracts structured preferences for Berlin Airbnb listings.

Extract preferences and map them to these exact field names:

DIRECT DATABASE FIELDS:
1. room_type: Must be one of: "Entire home/apt", "Private room", "Shared room", "Hotel room"
2. price_min: Minimum daily price as integer (no currency symbols)
3. price_max: Maximum daily price as integer (no currency symbols)
4. neighbourhood_group: Broader Berlin area
5. neighbourhood: Specific neighborhood within the area
6. minimum_nights: Minimum stay duration in nights
7. maximum_nights: Maximum stay duration in nights
8. min_reviews: Minimum number of reviews (for popularity filtering)
9. reviews_per_month_min: Minimum monthly review rate (for activity level)

SEMANTIC SEARCH KEYWORDS:
10. amenities_keywords: Array of amenity-related terms ["wifi", "kitchen", "parking"]
11. location_keywords: Array of location ["central", "near metro"] - This will be displayed as "Location" in frontend
12. comfort_keywords: Array of comfort/atmosphere terms ["clean", "quiet", "spacious", "modern"]

SPECIAL HANDLING FOR NOISE CONCERNS:
- If user mentions "noisy", "noise", "loud" → add "quiet" to comfort_keywords
- If user mentions "quiet", "peaceful", "silent" → add "quiet" to comfort_keywords
- Noise-related preferences always go to comfort_keywords, not location_keywords

INSTRUCTIONS:
1. Extract ONLY information explicitly mentioned by the user
2. For budget: "under 80€" → {{"price_max": 80}}, "around 100€" → {{"price_min": 90, "price_max": 110}}
3. For room type: Use exact database values
4. For areas: Map to actual Berlin neighborhoods when possible
5. For noise concerns: Always categorize as comfort preference
6. Put completely unmappable preferences in "missing_dimension" array
7. Set unmentioned fields to null
8. Return valid JSON only, no explanations

User Request: {user_query}
Context: {context}
"""

UPDATE_PREFERENCE_PROMPT = """
You are updating existing user preferences with new information.

EXISTING PREFERENCES:
{existing_preferences}

NEW USER MESSAGE:
{user_query}

RULES:
1. Keep all existing non-null values unless explicitly contradicted
2. Only add/update fields if clearly mentioned in the new message
3. If user contradicts previous preference, update it
4. Merge keyword arrays (don't replace): combine amenities_keywords, location_keywords, comfort_keywords
5. Return the complete updated preference object

Return valid JSON only:
"""

def extract_preferences_with_llm(user_query: str, 
                                conversation_context: List[Dict] = None,
                                existing_preferences: Dict = None) -> Dict:
    """
    使用LLM提取偏好信息
    
    Args:
        user_query: 用户当前消息
        conversation_context: 对话历史上下文
        existing_preferences: 已有的偏好信息
    
    Returns:
        提取的偏好字典
    """
    manager = PreferenceManager()
    llm_model = manager.get_llm()
    
    # 如果LLM不可用，使用fallback逻辑
    if llm_model is None:
        print("使用fallback偏好提取逻辑")
        return extract_preferences_fallback(user_query, existing_preferences)

    try:
        # 🔧 修复：导入LangChain组件
        from langchain.chains import LLMChain
        from langchain.prompts import PromptTemplate
        
        # 准备上下文信息
        context = ""
        if conversation_context:
            recent_messages = conversation_context[-3:]  # 最近3条消息
            context = " | ".join([f"{msg.get('sender', 'user')}: {msg.get('text', '')}" 
                                for msg in recent_messages])
        
        if existing_preferences:
            # 更新现有偏好
            prompt = PromptTemplate(
                input_variables=["existing_preferences", "user_query"], 
                template=UPDATE_PREFERENCE_PROMPT
            )
            input_data = {
                "existing_preferences": json.dumps(existing_preferences, indent=2),
                "user_query": user_query
            }
        else:
            # 首次提取
            prompt = PromptTemplate(
                input_variables=["user_query", "context"], 
                template=ENHANCED_PREFERENCE_PROMPT
            )
            input_data = {
                "user_query": user_query,
                "context": context if context else "No previous context"  # 🔧 确保不为空
            }

        extraction_chain = LLMChain(llm=llm_model, prompt=prompt)
        raw_output = extraction_chain.predict(**input_data).strip()

        # 解析JSON响应
        try:
            # 提取JSON部分
            json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                extracted_data = json.loads(json_str)
            else:
                return {"error": f"无法从LLM输出中提取JSON: {raw_output[:200]}"}
        except json.JSONDecodeError as e:
            return {"error": f"JSON解析失败: {str(e)}, 原始输出: {raw_output[:200]}"}

        # 确保必要字段存在
        extracted_data.setdefault("missing_dimension", [])
        
        # 数据清理和验证
        cleaned_data = clean_and_validate_preferences(extracted_data)
        
        return cleaned_data

    except Exception as e:
        print(f"LLM提取失败，使用fallback: {str(e)}")
        return extract_preferences_fallback(user_query, existing_preferences)

def extract_preferences_fallback(user_query: str, existing_preferences: Dict = None) -> Dict:
    """
    Fallback偏好提取逻辑（不依赖LLM）- 修正版
    用于测试和LLM不可用时的情况
    """
    result = existing_preferences.copy() if existing_preferences else {}
    msg_lower = user_query.lower()
    
    # 简单的正则匹配逻辑
    
    # 价格提取
    price_patterns = [
        (r'under (\d+)', lambda m: {"price_max": int(m.group(1))}),
        (r'below (\d+)', lambda m: {"price_max": int(m.group(1))}),
        (r'around (\d+)', lambda m: {"price_min": int(m.group(1)) - 10, "price_max": int(m.group(1)) + 10}),
        (r'(\d+)[-–](\d+)', lambda m: {"price_min": int(m.group(1)), "price_max": int(m.group(2))}),
        (r'maximum (\d+)', lambda m: {"price_max": int(m.group(1))}),
        (r'budget.*?(\d+)', lambda m: {"price_max": int(m.group(1))})
    ]
    
    for pattern, extractor in price_patterns:
        match = re.search(pattern, msg_lower)
        if match:
            result.update(extractor(match))
            break
    
    # 房间类型
    if 'private room' in msg_lower or 'private' in msg_lower:
        result['room_type'] = 'Private room'
    elif 'entire' in msg_lower or 'apartment' in msg_lower:
        result['room_type'] = 'Entire home/apt'
    elif 'shared' in msg_lower:
        result['room_type'] = 'Shared room'
    elif 'hotel' in msg_lower:
        result['room_type'] = 'Hotel room'
    
    # 区域匹配
    berlin_areas = {
        'mitte': ('Mitte', 'Mitte'),
        'kreuzberg': ('Friedrichshain-Kreuzberg', 'Kreuzberg'),
        'friedrichshain': ('Friedrichshain-Kreuzberg', 'Friedrichshain'),
        'prenzlauer': ('Pankow', 'Prenzlauer Berg'),
        'charlottenburg': ('Charlottenburg-Wilmersdorf', 'Charlottenburg'),
        'neukölln': ('Neukölln', 'Neukölln'),
        'tempelhof': ('Tempelhof-Schöneberg', 'Tempelhof'),
        'schöneberg': ('Tempelhof-Schöneberg', 'Schöneberg')
    }
    
    for area_key, (group, neighbourhood) in berlin_areas.items():
        if area_key in msg_lower:
            result['neighbourhood_group'] = group
            result['neighbourhood'] = neighbourhood
            break
    
    # 住宿天数
    days_match = re.search(r'(\d+)[-–](\d+)\s*days?', msg_lower)
    if days_match:
        result['minimum_nights'] = int(days_match.group(1))
        result['maximum_nights'] = int(days_match.group(2))
    elif re.search(r'(\d+)\s*days?', msg_lower):
        days = int(re.search(r'(\d+)\s*days?', msg_lower).group(1))
        result['minimum_nights'] = days
    
    # 🎯 改进的关键词提取 - 按照前端期望的字段分类
    amenities_keywords = []
    location_keywords = []
    comfort_keywords = []  # 重点：舒适度关键词
    
    # 设施相关关键词
    amenity_terms = ['wifi', 'kitchen', 'air conditioning', 'parking', 'balcony', 'garden', 'elevator', 'heating']
    for term in amenity_terms:
        if term in msg_lower:
            amenities_keywords.append(term)
    
    # 位置相关关键词
    location_terms = ['central', 'near metro', 'near subway', 'city center', 'close to', 'walking distance']
    for term in location_terms:
        if term in msg_lower:
            location_keywords.append(term)
    
    # 🎯 舒适度关键词 - 特别处理noise相关
    comfort_terms = {
        'clean': ['clean', 'cleanliness'],
        'comfortable': ['comfortable', 'comfort'],
        'spacious': ['spacious', 'space', 'large'],
        'modern': ['modern', 'contemporary'],
        'cozy': ['cozy', 'cosy'],
        'quiet': ['quiet', 'peaceful', 'silent', 'no noise', 'not noisy'],  # 🎯 重点
        'bright': ['bright', 'natural light', 'sunny'],
    }
    
    # 处理噪音相关的特殊逻辑
    noise_indicators = ['noisy', 'noise', 'loud', 'sound']
    quiet_indicators = ['quiet', 'peaceful', 'silent']
    
    # 检查噪音偏好
    has_noise_concern = any(indicator in msg_lower for indicator in noise_indicators)
    wants_quiet = any(indicator in msg_lower for indicator in quiet_indicators)
    
    if has_noise_concern or wants_quiet:
        # 用户关心噪音问题，添加quiet到舒适度关键词
        comfort_keywords.append('quiet')
        print(f"🔇 检测到噪音关心，添加quiet关键词: {user_query}")
    
    # 处理其他舒适度关键词
    for comfort_key, terms in comfort_terms.items():
        if comfort_key != 'quiet':  # quiet已经在上面处理过了
            for term in terms:
                if term in msg_lower and comfort_key not in comfort_keywords:
                    comfort_keywords.append(comfort_key)
                    break
    
    # 🎯 合并关键词到结果中（使用正确的字段名）
    if amenities_keywords:
        existing_amenities = result.get('amenities_keywords', [])
        result['amenities_keywords'] = list(set(existing_amenities + amenities_keywords))
    
    if location_keywords:
        existing_location = result.get('location_keywords', [])
        result['location_keywords'] = list(set(existing_location + location_keywords))
    
    if comfort_keywords:
        existing_comfort = result.get('comfort_keywords', [])  # 🎯 使用comfort_keywords
        result['comfort_keywords'] = list(set(existing_comfort + comfort_keywords))
    
    # 确保所有list字段存在
    for field in ['amenities_keywords', 'location_keywords', 'comfort_keywords', 'missing_dimension']:
        if field not in result:
            result[field] = []
    
    # 🎯 调试日志
    if comfort_keywords or amenities_keywords or location_keywords:
        print(f"✅ 关键词提取: 设施={amenities_keywords}, 位置={location_keywords}, 舒适度={comfort_keywords}")
    
    return result

def clean_and_validate_preferences(data: Dict) -> Dict:
    """清理和验证提取的偏好数据 - 修正版"""
    
    # 1. 验证房间类型（根据实际数据库值）
    valid_room_types = ['Entire home/apt', 'Private room', 'Shared room', 'Hotel room']
    if data.get('room_type') and data['room_type'] not in valid_room_types:
        # 尝试映射常见变体
        room_type_mapping = {
            'entire': 'Entire home/apt',
            'whole': 'Entire home/apt',
            'apartment': 'Entire home/apt',
            'private': 'Private room',
            'shared': 'Shared room',
            'hotel': 'Hotel room'
        }
        room_lower = data['room_type'].lower()
        for key, value in room_type_mapping.items():
            if key in room_lower:
                data['room_type'] = value
                break
        else:
            data['room_type'] = None
    
    # 2. 验证价格范围
    if data.get('price_min') and data.get('price_max'):
        if data['price_min'] > data['price_max']:
            data['price_min'], data['price_max'] = data['price_max'], data['price_min']
    
    # 3. 确保数值类型正确
    numeric_fields = ['price_min', 'price_max', 'minimum_nights', 'maximum_nights', 
                     'min_reviews', 'reviews_per_month_min', 'availability_min']
    for field in numeric_fields:
        if data.get(field) is not None:
            try:
                data[field] = int(data[field])
            except (ValueError, TypeError):
                data[field] = None
    
    # 4. 🎯 确保关键词字段是列表，并清理重复项
    keyword_fields = ['amenities_keywords', 'location_keywords', 'comfort_keywords']
    for field in keyword_fields:
        if field not in data:
            data[field] = []
        elif data.get(field):
            if not isinstance(data[field], list):
                data[field] = [data[field]] if data[field] else []
            # 清理重复项和空值
            data[field] = list(set([k for k in data[field] if k and k.strip()]))
    
    # 5. 🎯 特殊处理comfort_keywords，合并同义词
    if data.get('comfort_keywords'):
        comfort_synonyms = {
            'not noisy': 'quiet',
            'no noise': 'quiet', 
            'peaceful': 'quiet',
            'calm': 'quiet',
            'silent': 'quiet'
        }
        
        normalized_comfort = []
        for keyword in data['comfort_keywords']:
            normalized = comfort_synonyms.get(keyword.lower(), keyword)
            if normalized not in normalized_comfort:
                normalized_comfort.append(normalized)
        
        data['comfort_keywords'] = normalized_comfort
    
    return data

def merge_preferences(existing: Dict, new: Dict) -> Dict:
    """合并偏好字典，新的覆盖旧的，但保留有用信息"""
    if not existing:
        return new
    
    merged = existing.copy()
    
    for key, value in new.items():
        if value is not None:
            if key in ['amenities_keywords', 'location_keywords', 'comfort_keywords']:
                # 关键词列表：合并去重
                existing_keywords = merged.get(key, [])
                new_keywords = value if isinstance(value, list) else [value]
                merged[key] = list(set(existing_keywords + new_keywords))
            elif key == 'missing_dimension':
                # 未映射维度：累积
                existing_missing = merged.get('missing_dimension', [])
                new_missing = value if isinstance(value, list) else [value]
                merged['missing_dimension'] = list(set(existing_missing + new_missing))
            else:
                # 其他字段：直接覆盖
                merged[key] = value
    
    return merged

def get_preference_completeness_score(preferences: Dict) -> float:
    """计算偏好完整度评分 (0-1) - 修正版"""
    
    # 必需字段（50%权重）
    critical_fields = ['price_min', 'price_max']
    critical_count = sum(1 for field in critical_fields 
                        if preferences.get(field) is not None)
    critical_score = critical_count / max(len(critical_fields), 1)
    
    # 重要字段（30%权重）
    important_fields = ['room_type', 'neighbourhood_group', 'neighbourhood']
    important_count = sum(1 for field in important_fields 
                         if preferences.get(field) is not None)
    important_score = important_count / max(len(important_fields), 1)
    
    # 可选字段（20%权重）
    optional_fields = ['minimum_nights', 'amenities_keywords', 'location_keywords', 'comfort_keywords']
    optional_count = sum(1 for field in optional_fields 
                        if preferences.get(field) and 
                        (not isinstance(preferences[field], list) or len(preferences[field]) > 0))
    optional_score = optional_count / max(len(optional_fields), 1)
    
    # 🎯 如果有comfort_keywords（用户特殊需求），额外加分
    comfort_bonus = 0.1 if (preferences.get('comfort_keywords') and 
                           len(preferences['comfort_keywords']) > 0) else 0
    
    # 总评分
    total_score = critical_score * 0.5 + important_score * 0.3 + optional_score * 0.2 + comfort_bonus
    
    return min(total_score, 1.0)

def test_preference_extraction():
    """测试偏好提取功能"""
    
    test_cases = [
        "I need a private room in Mitte for under 80 euros per night",
        "Looking for entire apartment, budget around 100-120€, 3-5 days",
        "Shared room somewhere central, need wifi and kitchen", 
        "Budget maximum 90 euros, prefer Kreuzberg, need air conditioning",
        "i want a room with good wifi signal and the landlord's should response me fast asap!"  # 🎯 测试案例
    ]
    
    existing_prefs = None
    for i, query in enumerate(test_cases):
        print(f"\n--- Test Case {i+1} ---")
        print(f"Query: {query}")
        
        result = extract_preferences_with_llm(
            user_query=query,
            conversation_context=[],  # 提供空列表
            existing_preferences=existing_prefs
        )
        
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Extracted: {json.dumps(result, indent=2, ensure_ascii=False)}")
            completeness = get_preference_completeness_score(result)
            print(f"Completeness Score: {completeness:.2f}")
            
            # 更新已有偏好以测试累积效果
            existing_prefs = merge_preferences(existing_prefs, result)
            print(f"Merged Preferences: {json.dumps(existing_prefs, indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    test_preference_extraction()