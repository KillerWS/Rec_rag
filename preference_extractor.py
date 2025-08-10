import json
import re
from typing import Dict, List, Optional, Any
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from load_llm import get_llm

# 🎯 根据数据库字段重新设计的偏好Schema
class PreferenceManager:
    """管理用户偏好的累积和更新"""
    
    def __init__(self):
        self.llm_model = None
        # 🔥 根据实际数据库字段设计的偏好结构
        self.preference_schema = {
            # === 可直接映射到数据库字段的偏好 ===
            "room_type": None,              # Entire home/apt, Private room, Shared room, Hotel room
            "price_min": None,              # 对应 price 字段的最小值
            "price_max": None,              # 对应 price 字段的最大值
            "neighbourhood_group": None,    # 对应 neighbourhood_group (12个大区)
            "neighbourhood": None,          # 对应 neighbourhood (138个具体社区)
            "minimum_nights": None,         # 对应 minimum_nights 字段
            "maximum_nights": None,         # 用户最多想住几晚 (可用于筛选)
            
            # === 偏好权重字段 ===
            "popularity_preference": None,   # 基于 reviews_per_month, number_of_reviews
            "host_experience_preference": None, # 基于 calculated_host_listings_count
            
            # === 无法直接映射的偏好 (需要通过评论分析) ===
            "amenities_mentioned": [],      # ["wifi", "kitchen", "air conditioning", "near metro"]
            "location_features": [],        # ["near supermarket", "quiet area", "central location"]
            "room_features": [],           # ["clean", "spacious", "good lighting", "comfortable bed"]
            
            # === 元信息 ===
            "missing_dimensions": []        # 无法分类的用户偏好
        }
    
    def get_llm(self):
        """获取LLM实例"""
        if self.llm_model is None:
            self.llm_model = get_llm()
        return self.llm_model

# 🎯 获取柏林地区层次结构 (从数据库动态获取更好)
def get_berlin_areas_hierarchy():
    """获取柏林地区的层次结构"""
    # 这个理想情况下应该从数据库查询获得
    # SELECT DISTINCT neighbourhood_group, neighbourhood FROM listings
    return {
        "neighbourhood_groups": [
            "Charlottenburg-Wilm.",
            "Friedrichshain-Kreuzberg", 
            "Lichtenberg",
            "Marzahn - Hellersdorf",
            "Mitte",
            "Neukölln",
            "Pankow",
            "Reinickendorf",
            "Spandau",
            "Steglitz-Zehlendorf",
            "Tempelhof - Schöneberg",
            "Treptow - Köpenick"
        ],
        "neighbourhood_mapping": {
            # 常见的社区名映射到标准名称
            "mitte": "Mitte",
            "kreuzberg": "Friedrichshain-Kreuzberg",
            "prenzlauer berg": "Pankow",
            "charlottenburg": "Charlottenburg-Wilm.",
            "neukölln": "Neukölln",
            "friedrichshain": "Friedrichshain-Kreuzberg",
            "tempelhof": "Tempelhof - Schöneberg",
            "schöneberg": "Tempelhof - Schöneberg"
        }
    }

# 🎯 修复后的提示模板
ENHANCED_PREFERENCE_PROMPT = """
You are an AI assistant that extracts structured preferences for Berlin Airbnb listings.

Extract preferences and map them to these EXACT field names:

=== DIRECT DATABASE FIELDS ===
1. room_type: Must be one of: "Entire home/apt", "Private room", "Shared room", "Hotel room"
2. price_min: Minimum daily price as integer (no currency symbols)
3. price_max: Maximum daily price as integer (no currency symbols)  
4. neighbourhood_group: Broader Berlin area (e.g., "Mitte", "Friedrichshain-Kreuzberg")
5. neighbourhood: Specific neighborhood name
6. minimum_nights: Minimum stay requirement as integer
7. maximum_nights: Maximum nights user wants to stay as integer

=== PREFERENCE WEIGHTS ===
8. popularity_preference: "high" if user wants popular/well-reviewed places, null otherwise
9. host_experience_preference: "experienced" if user prefers experienced hosts, null otherwise

=== AMENITIES & FEATURES (arrays) ===
10. amenities_mentioned: ["wifi", "kitchen", "air conditioning", "parking", "elevator"]
11. location_features: ["near metro", "near supermarket", "quiet area", "central", "nightlife"]
12. room_features: ["clean", "spacious", "bright", "comfortable bed", "good view"]

=== UNMAPPED ===
13. missing_dimensions: Array of preferences that don't fit above categories

PARSING RULES:
- "under 80€" → price_max: 80
- "around 100€" → price_min: 90, price_max: 110  
- "3-5 days" → minimum_nights: 3, maximum_nights: 5
- "popular place" → popularity_preference: "high"
- "experienced host" → host_experience_preference: "experienced"
- "need wifi" → amenities_mentioned: ["wifi"]
- "near metro" → location_features: ["near metro"]
- "clean room" → room_features: ["clean"]

Return ONLY valid JSON with these exact field names. Set unmentioned fields to null or empty arrays.

User Request: {user_query}
Context: {context}
"""

UPDATE_PREFERENCE_PROMPT = """
You are updating existing preferences with new information.

EXISTING PREFERENCES:
{existing_preferences}

NEW USER MESSAGE:
{user_query}

RULES:
1. Keep all existing values unless explicitly contradicted
2. MERGE arrays (amenities_mentioned, location_features, room_features) - don't replace
3. Update single values only if clearly mentioned
4. Use exact field names from existing preferences

Return the complete updated JSON object:
"""

def extract_preferences_with_llm(user_query: str, 
                                conversation_context: List[Dict] = None,
                                existing_preferences: Dict = None) -> Dict:
    """
    使用LLM提取偏好信息 - 修复版本
    """
    manager = PreferenceManager()
    llm_model = manager.get_llm()
    
    if llm_model is None:
        return {"error": "LLM 未正确加载"}

    try:
        # 准备上下文
        context = ""
        if conversation_context:
            recent_messages = conversation_context[-3:]
            context = " | ".join([f"{msg.get('sender', 'user')}: {msg.get('text', '')}" 
                                for msg in recent_messages])
        
        # 选择提示模板
        if existing_preferences:
            prompt = PromptTemplate(
                input_variables=["existing_preferences", "user_query"], 
                template=UPDATE_PREFERENCE_PROMPT
            )
            input_data = {
                "existing_preferences": json.dumps(existing_preferences, indent=2),
                "user_query": user_query
            }
        else:
            prompt = PromptTemplate(
                input_variables=["user_query", "context"], 
                template=ENHANCED_PREFERENCE_PROMPT
            )
            input_data = {
                "user_query": user_query,
                "context": context
            }

        # 调用LLM
        extraction_chain = LLMChain(llm=llm_model, prompt=prompt)
        raw_output = extraction_chain.predict(**input_data).strip()
        
        print(f"🔍 LLM Raw Output: {raw_output[:300]}...")  # Debug输出

        # 解析JSON
        try:
            json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                extracted_data = json.loads(json_str)
            else:
                return {"error": f"无法提取JSON: {raw_output[:200]}"}
        except json.JSONDecodeError as e:
            return {"error": f"JSON解析失败: {str(e)}"}

        # 数据清理
        cleaned_data = clean_and_validate_preferences(extracted_data)
        return cleaned_data

    except Exception as e:
        return {"error": f"偏好提取失败: {str(e)}"}

def clean_and_validate_preferences(data: Dict) -> Dict:
    """清理和验证提取的偏好数据"""
    
    # 获取地区信息
    areas = get_berlin_areas_hierarchy()
    
    # 1. 验证房间类型
    valid_room_types = ['Entire home/apt', 'Private room', 'Shared room', 'Hotel room']
    if data.get('room_type') and data['room_type'] not in valid_room_types:
        room_mapping = {
            'entire': 'Entire home/apt',
            'whole': 'Entire home/apt', 
            'apartment': 'Entire home/apt',
            'private': 'Private room',
            'shared': 'Shared room',
            'hotel': 'Hotel room'
        }
        room_lower = data['room_type'].lower()
        for key, value in room_mapping.items():
            if key in room_lower:
                data['room_type'] = value
                break
        else:
            data['room_type'] = None
    
    # 2. 验证地区名称
    if data.get('neighbourhood'):
        neighbourhood_lower = data['neighbourhood'].lower()
        # 先尝试映射到neighbourhood_group
        for mapping_key, group_name in areas['neighbourhood_mapping'].items():
            if mapping_key in neighbourhood_lower:
                data['neighbourhood_group'] = group_name
                break
    
    # 3. 验证数值类型
    numeric_fields = ['price_min', 'price_max', 'minimum_nights', 'maximum_nights']
    for field in numeric_fields:
        if data.get(field) is not None:
            try:
                data[field] = int(data[field])
            except (ValueError, TypeError):
                data[field] = None
    
    # 4. 验证价格逻辑
    if data.get('price_min') and data.get('price_max'):
        if data['price_min'] > data['price_max']:
            data['price_min'], data['price_max'] = data['price_max'], data['price_min']
    
    # 5. 确保数组字段
    array_fields = ['amenities_mentioned', 'location_features', 'room_features', 'missing_dimensions']
    for field in array_fields:
        if field not in data:
            data[field] = []
        elif not isinstance(data[field], list):
            data[field] = [data[field]] if data[field] else []
    
    return data

def merge_preferences(existing: Dict, new: Dict) -> Dict:
    """合并偏好 - 特别处理数组字段"""
    if not existing:
        return new
    
    merged = existing.copy()
    
    for key, value in new.items():
        if value is not None and value != [] and value != "":
            if key in ['amenities_mentioned', 'location_features', 'room_features', 'missing_dimensions']:
                # 数组字段：合并去重
                existing_items = merged.get(key, [])
                new_items = value if isinstance(value, list) else [value]
                merged[key] = list(set(existing_items + new_items))
            else:
                # 单值字段：覆盖
                merged[key] = value
    
    return merged

def get_preference_completeness_score(preferences: Dict) -> float:
    """
    计算偏好完整度评分 - 基于推荐系统需求
    
    评分逻辑：
    - 基础过滤条件 (权重60%): room_type, price_range, location
    - 偏好增强条件 (权重40%): amenities, features, popularity
    """
    
    # 基础过滤条件 (必须有才能有效推荐)
    basic_filters = {
        'room_type': preferences.get('room_type') is not None,
        'price_range': (preferences.get('price_min') is not None or 
                       preferences.get('price_max') is not None),
        'location': (preferences.get('neighbourhood') is not None or 
                    preferences.get('neighbourhood_group') is not None)
    }
    
    # 偏好增强条件 (提升推荐质量)
    enhancement_preferences = {
        'amenities': len(preferences.get('amenities_mentioned', [])) > 0,
        'location_features': len(preferences.get('location_features', [])) > 0,
        'room_features': len(preferences.get('room_features', [])) > 0,
        'popularity': preferences.get('popularity_preference') is not None,
        'stay_duration': (preferences.get('minimum_nights') is not None or 
                         preferences.get('maximum_nights') is not None)
    }
    
    basic_score = sum(basic_filters.values()) / len(basic_filters)
    enhancement_score = sum(enhancement_preferences.values()) / len(enhancement_preferences)
    
    total_score = basic_score * 0.6 + enhancement_score * 0.4
    return round(total_score, 2)

def is_ready_for_recommendation(preferences: Dict) -> bool:
    """判断是否已准备好推荐"""
    # 至少需要价格区间和位置信息
    has_price = (preferences.get('price_min') is not None or 
                preferences.get('price_max') is not None)
    has_location = (preferences.get('neighbourhood') is not None or 
                   preferences.get('neighbourhood_group') is not None)
    
    return has_price and has_location

# 🧪 修复后的测试用例
def test_preference_extraction():
    """测试偏好提取功能"""
    
    test_cases = [
        "I need a private room in Mitte for under 80 euros per night",
        "Looking for entire apartment, budget around 100-120€, 3-5 days, need wifi",
        "Shared room somewhere central, need kitchen and near metro",
        "Hotel room with air conditioning, prefer experienced host, popular area"
    ]
    
    existing_prefs = None
    for i, query in enumerate(test_cases):
        print(f"\n=== Test Case {i+1} ===")
        print(f"Query: {query}")
        
        result = extract_preferences_with_llm(
            user_query=query,
            existing_preferences=existing_prefs
        )
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"✅ Extracted: {json.dumps(result, indent=2, ensure_ascii=False)}")
            completeness = get_preference_completeness_score(result)
            ready = is_ready_for_recommendation(result)
            print(f"📊 Completeness: {completeness:.2f}, Ready for Rec: {ready}")
            
            # 累积偏好
            existing_prefs = merge_preferences(existing_prefs, result)
            print(f"🔄 Accumulated Prefs: {json.dumps(existing_prefs, indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    test_preference_extraction()