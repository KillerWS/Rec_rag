"""
修正的偏好提取模块 - 基于实际数据库字段
"""
import json
import re
from typing import Dict, List, Optional, Any
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from load_llm import get_llm

class PreferenceManager:
    """管理用户偏好的累积和更新"""
    
    def __init__(self):
        self.llm_model = None
        # 🎯 基于实际数据库字段重新设计偏好结构
        self.preference_schema = {
            # === 直接映射到listings表字段 ===
            "room_type": None,              # 'Entire home/apt', 'Private room', 'Shared room', 'Hotel room'
            "price_min": None,              # 最低价格
            "price_max": None,              # 最高价格
            "neighbourhood_group": None,    # 大区域（12个）
            "neighbourhood": None,          # 具体社区（138个）
            "minimum_nights": None,         # 最少停留天数
            "maximum_nights": None,         # 最多停留天数（灵活性）
            
            # === 基于数值字段的筛选条件 ===
            "min_reviews": None,            # number_of_reviews >= X
            "reviews_per_month_min": None,  # reviews_per_month >= X (热度)
            "availability_min": None,       # availability_365 >= X
            
            # === 语义搜索字段（用于RAG检索评论）===
            "amenities_keywords": [],       # 设施需求：wifi, kitchen, parking等
            "location_keywords": [],        # 位置需求：near metro, quiet, central等
            "experience_keywords": [],      # 体验需求：clean, spacious, friendly等
            "semantic_query": ""            # 完整语义查询，用于RAG
        }
    
    def get_llm(self):
        """获取LLM实例"""
        if self.llm_model is None:
            self.llm_model = get_llm()
        return self.llm_model

# 🎯 优化的LLM提示模板
ENHANCED_PREFERENCE_PROMPT = """
You are an AI assistant extracting preferences for Berlin Airbnb search.

Extract information and map to these EXACT field names:

DIRECT DATABASE FIELDS:
1. room_type: Must be exactly one of: 'Entire home/apt', 'Private room', 'Shared room', 'Hotel room'
2. price_min: Minimum daily price (integer, no currency)
3. price_max: Maximum daily price (integer, no currency)  
4. neighbourhood_group: Berlin major districts (like 'Mitte', 'Friedrichshain-Kreuzberg')
5. neighbourhood: Specific Berlin neighborhoods
6. minimum_nights: User's planned stay duration (integer)
7. maximum_nights: Maximum acceptable stay (integer)

FILTER FIELDS:
8. min_reviews: Minimum review count required (integer)
9. reviews_per_month_min: Minimum monthly reviews (float)
10. availability_min: Minimum available days (integer)

SEMANTIC SEARCH FIELDS:
11. amenities_keywords: Array of facility needs ["wifi", "kitchen", "parking"]
12. location_keywords: Array of location needs ["near metro", "quiet", "central"]
13. experience_keywords: Array of experience needs ["clean", "spacious", "friendly"]
14. semantic_query: Full user query for RAG search

EXTRACTION RULES:
- Extract ONLY explicitly mentioned information
- For "X days" or "X-day trip", set minimum_nights to X
- For "under X€", set price_max to X  
- For "around X€", set price_min to X-15, price_max to X+15
- For "X to Y euros", set price_min to X, price_max to Y
- Put facility mentions (wifi, kitchen, etc.) in amenities_keywords
- Put location descriptions (near metro, quiet) in location_keywords  
- Put quality/experience words (clean, spacious) in experience_keywords
- Store original query in semantic_query for RAG retrieval
- Set unmentioned fields to null
- Return valid JSON only

BERLIN AREA MAPPING:
- "Mitte" → neighbourhood_group: "Mitte"
- "Kreuzberg" or "Friedrichshain" → neighbourhood_group: "Friedrichshain-Kreuzberg"
- "Prenzlauer Berg" → neighbourhood_group: "Pankow"
- "Charlottenburg" → neighbourhood_group: "Charlottenburg-Wilm."

User Message: {user_query}
Previous Context: {context}

Return JSON:
"""

UPDATE_PREFERENCE_PROMPT = """
Update existing preferences with new user information.

CURRENT PREFERENCES:
{existing_preferences}

NEW USER MESSAGE:  
{user_query}

UPDATE RULES:
1. Keep existing values unless explicitly contradicted
2. Only change fields clearly mentioned in new message
3. For keyword arrays, ADD new items to existing (don't replace)
4. For budget changes, completely replace if new values given
5. If user changes mind about room type/area, update those fields
6. Always update semantic_query with the new user message
7. Return complete updated preference object as valid JSON

EXAMPLES:
- If existing price_max: 100, user says "actually under 80€" → price_max: 80
- If existing amenities_keywords: ["wifi"], user says "also need kitchen" → amenities_keywords: ["wifi", "kitchen"]
- User says "3 days" → minimum_nights: 3
- User says "Mitte area" → neighbourhood_group: "Mitte"

Return complete JSON:
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
    
    if llm_model is None:
        return {"error": "LLM 未正确加载"}

    try:
        # 准备上下文信息
        context = ""
        if conversation_context:
            recent_messages = conversation_context[-4:]  # 最近4条消息
            context = " | ".join([f"{msg.get('sender', 'user')}: {msg.get('text', '')}" 
                                for msg in recent_messages])
        
        if existing_preferences and any(v for v in existing_preferences.values() if v):
            # 更新现有偏好
            prompt = PromptTemplate(
                input_variables=["existing_preferences", "user_query"], 
                template=UPDATE_PREFERENCE_PROMPT
            )
            input_data = {
                "existing_preferences": json.dumps(existing_preferences, indent=2, ensure_ascii=False),
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
                "context": context or ""
            }

        extraction_chain = LLMChain(llm=llm_model, prompt=prompt)
        raw_output = extraction_chain.predict(**input_data).strip()

        print(f"LLM原始输出: {raw_output}")

        # 解析JSON响应
        try:
            # 提取JSON部分
            json_match = re.search(r'\{.*\}', raw_output, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                extracted_data = json.loads(json_str)
            else:
                return {"error": f"无法从LLM输出中提取JSON: {raw_output[:300]}"}
        except json.JSONDecodeError as e:
            return {"error": f"JSON解析失败: {str(e)}, 原始输出: {raw_output[:300]}"}

        # 数据清理和验证
        cleaned_data = clean_and_validate_preferences(extracted_data)
        
        print(f"清理后的偏好: {cleaned_data}")
        
        return cleaned_data

    except Exception as e:
        print(f"LLM偏好提取异常: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"偏好提取失败: {str(e)}"}

def clean_and_validate_preferences(data: Dict) -> Dict:
    """清理和验证提取的偏好数据"""
    
    # 🎯 验证房间类型 - 严格匹配数据库值
    valid_room_types = ['Entire home/apt', 'Private room', 'Shared room', 'Hotel room']
    if data.get('room_type') and data['room_type'] not in valid_room_types:
        # 尝试映射常见变体
        room_type_mapping = {
            'entire': 'Entire home/apt',
            'whole': 'Entire home/apt', 
            'apartment': 'Entire home/apt',
            'entire home': 'Entire home/apt',
            'entire place': 'Entire home/apt',
            'private': 'Private room',
            'shared': 'Shared room',
            'hotel': 'Hotel room'
        }
        room_lower = data['room_type'].lower()
        mapped = False
        for key, value in room_type_mapping.items():
            if key in room_lower:
                data['room_type'] = value
                mapped = True
                break
        if not mapped:
            print(f"无效房间类型: {data['room_type']}, 设为None")
            data['room_type'] = None
    
    # 🎯 验证和修正价格范围
    if data.get('price_min') and data.get('price_max'):
        if data['price_min'] > data['price_max']:
            data['price_min'], data['price_max'] = data['price_max'], data['price_min']
    
    # 🎯 确保数值类型正确
    numeric_fields = ['price_min', 'price_max', 'minimum_nights', 'maximum_nights', 
                     'min_reviews', 'reviews_per_month_min', 'availability_min']
    for field in numeric_fields:
        if data.get(field) is not None:
            try:
                if field == 'reviews_per_month_min':
                    data[field] = float(data[field])  # 月评论数可以是小数
                else:
                    data[field] = int(data[field])
                    
                # 合理性检查
                if field in ['price_min', 'price_max'] and data[field] < 0:
                    data[field] = None
                elif field in ['minimum_nights', 'maximum_nights'] and data[field] < 1:
                    data[field] = None
                elif field == 'min_reviews' and data[field] < 0:
                    data[field] = None
                    
            except (ValueError, TypeError):
                print(f"数值字段 {field} 转换失败: {data[field]}")
                data[field] = None
    
    # 🎯 确保关键词字段是列表且去重
    keyword_fields = ['amenities_keywords', 'location_keywords', 'experience_keywords']
    for field in keyword_fields:
        if data.get(field):
            if not isinstance(data[field], list):
                data[field] = [data[field]] if data[field] else []
            # 去重并保持顺序
            data[field] = list(dict.fromkeys(data[field]))
        else:
            data[field] = []
    
    # 🎯 处理语义查询
    if not data.get('semantic_query'):
        data['semantic_query'] = ""
    
    # 🎯 柏林地区名称标准化（可以扩展）
    berlin_area_mapping = {
        'mitte': 'Mitte',
        'kreuzberg': 'Friedrichshain-Kreuzberg',
        'friedrichshain': 'Friedrichshain-Kreuzberg', 
        'prenzlauer berg': 'Pankow',
        'charlottenburg': 'Charlottenburg-Wilm.',
        'neukölln': 'Neukölln',
        'tempelhof': 'Tempelhof - Schöneberg',
        'schöneberg': 'Tempelhof - Schöneberg'
    }
    
    for field in ['neighbourhood_group', 'neighbourhood']:
        if data.get(field):
            area_lower = data[field].lower()
            if area_lower in berlin_area_mapping:
                data[field] = berlin_area_mapping[area_lower]
    
    return data

def merge_preferences(existing: Dict, new: Dict) -> Dict:
    """合并偏好字典，智能处理不同类型字段"""
    if not existing:
        return new
    
    merged = existing.copy()
    
    for key, value in new.items():
        if value is not None and value != "":
            if key in ['amenities_keywords', 'location_keywords', 'experience_keywords']:
                # 🎯 关键词列表：合并去重
                existing_keywords = merged.get(key, [])
                new_keywords = value if isinstance(value, list) else [value]
                merged[key] = list(dict.fromkeys(existing_keywords + new_keywords))
            elif key == 'semantic_query':
                # 🎯 语义查询：保留最新的
                merged[key] = value
            else:
                # 🎯 其他字段：新值覆盖
                merged[key] = value
    
    return merged

def get_preference_completeness_score(preferences: Dict) -> float:
    """计算偏好完整度评分 (0-1)"""
    # 🎯 核心字段：基本推荐必需（权重60%）
    core_fields = ['room_type', 'price_max']  # 降低要求
    # 🎯 重要字段：提升推荐质量（权重30%）
    important_fields = ['neighbourhood_group', 'minimum_nights']
    # 🎯 增强字段：个性化推荐（权重10%）
    enhancement_fields = ['amenities_keywords', 'location_keywords', 'experience_keywords']
    
    # 计算各类别完成度
    core_count = 0
    for field in core_fields:
        if field == 'price_max':
            # 有price_min或price_max任一即可
            if preferences.get('price_min') or preferences.get('price_max'):
                core_count += 1
        else:
            if preferences.get(field) is not None:
                core_count += 1
    
    important_count = sum(1 for field in important_fields 
                         if preferences.get(field) is not None)
    
    enhancement_count = sum(1 for field in enhancement_fields 
                           if preferences.get(field) and len(preferences[field]) > 0)
    
    # 权重计算
    core_score = (core_count / len(core_fields)) * 0.6
    important_score = (important_count / len(important_fields)) * 0.3  
    enhancement_score = (enhancement_count / len(enhancement_fields)) * 0.1
    
    total_score = core_score + important_score + enhancement_score
    
    print(f"完整度评分 - 核心: {core_score:.2f}, 重要: {important_score:.2f}, 增强: {enhancement_score:.2f}, 总计: {total_score:.2f}")
    
    return min(total_score, 1.0)

def preferences_to_sql_conditions(preferences: Dict) -> Dict:
    """将偏好转换为SQL查询条件"""
    conditions = {
        "where_clauses": [],
        "params": {},
        "semantic_keywords": {
            "amenities": preferences.get("amenities_keywords", []),
            "location": preferences.get("location_keywords", []),
            "experience": preferences.get("experience_keywords", []),
            "query": preferences.get("semantic_query", "")
        }
    }
    
    # 🎯 直接字段映射
    direct_mappings = {
        "room_type": "room_type",
        "neighbourhood_group": "neighbourhood_group", 
        "neighbourhood": "neighbourhood"
    }
    
    for pref_key, db_field in direct_mappings.items():
        if preferences.get(pref_key):
            conditions["where_clauses"].append(f"{db_field} = %({pref_key})s")
            conditions["params"][pref_key] = preferences[pref_key]
    
    # 🎯 范围查询
    if preferences.get("price_min"):
        conditions["where_clauses"].append("price >= %(price_min)s")
        conditions["params"]["price_min"] = preferences["price_min"]
    
    if preferences.get("price_max"):
        conditions["where_clauses"].append("price <= %(price_max)s")
        conditions["params"]["price_max"] = preferences["price_max"]
        
    if preferences.get("minimum_nights"):
        conditions["where_clauses"].append("minimum_nights <= %(user_nights)s")
        conditions["params"]["user_nights"] = preferences["minimum_nights"]
    
    return conditions

# 🎯 测试函数
def test_preference_extraction():
    """测试偏好提取功能"""
    
    test_cases = [
        "i would like to go to berlin for a conference. About 3 days",
        "im going to live in Mitte of Berlin and want a private room!",
        "I need a place under 100 euros with good wifi",
        "How about the wifi signal there? I want some recommendations"
    ]
    
    existing_prefs = None
    for i, query in enumerate(test_cases):
        print(f"\n{'='*50}")
        print(f"Test Case {i+1}: {query}")
        print(f"{'='*50}")
        
        result = extract_preferences_with_llm(
            user_query=query,
            existing_preferences=existing_prefs
        )
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(f"✅ Extracted: {json.dumps(result, indent=2, ensure_ascii=False)}")
            completeness = get_preference_completeness_score(result)
            print(f"📊 Completeness Score: {completeness:.2f}")
            
            # 更新已有偏好以测试累积效果
            existing_prefs = merge_preferences(existing_prefs, result)
            print(f"🔄 Merged Preferences: {json.dumps(existing_prefs, indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    test_preference_extraction()