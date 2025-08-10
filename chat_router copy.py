# 修正的 chat_router.py - 集成LLM偏好抽取

import re
import json
import time
from typing import Dict, List, Optional
from enum import Enum

class ChatStage(Enum):
    GREETING = "greeting"
    PREFERENCE_COLLECTION = "preference_collection"
    RECOMMENDATION_READY = "recommendation_ready"
    RECOMMENDATION_SHOWN = "recommendation_shown"
    REFINEMENT = "refinement"
    BOOKING_INQUIRY = "booking_inquiry"

class ConversationState:
    def __init__(self):
        self.stage = ChatStage.GREETING
        # 🎯 基于实际数据库字段重新设计偏好结构
        self.preferences = {
            # === 直接映射到数据库字段 ===
            "room_type": None,              # 'Entire home/apt', 'Private room', 'Shared room', 'Hotel room'
            "price_min": None,              # 最低价格
            "price_max": None,              # 最高价格
            "neighbourhood_group": None,    # 大区域（12个）
            "neighbourhood": None,          # 具体社区（138个）
            "minimum_nights": None,         # 最少停留天数（用户计划天数）
            "maximum_nights": None,         # 最多停留天数（用于灵活性）
            
            # === 筛选条件字段 ===
            "min_reviews": None,            # 最少评论数（热度门槛）
            "reviews_per_month_min": None,  # 最少月评论数（活跃度）
            "availability_min": None,       # 最少可预订天数
            
            # === 语义搜索字段（无法直接映射的偏好）===
            "amenities_keywords": [],       # 设施需求：["wifi", "kitchen", "air conditioning", "parking"]
            "location_keywords": [],        # 位置需求：["near metro", "close to supermarket", "central", "quiet area"]
            "experience_keywords": [],      # 体验需求：["clean", "spacious", "cozy", "modern", "friendly host"]
            "semantic_query": ""            # 完整的语义查询："I want wifi better hotel"
        }
        self.has_shown_listings = False
        self.current_listings = []
        self.conversation_history = []
        self.last_recommendation_time = None
    
    def update_preferences_from_message(self, user_message: str, use_llm: bool = False) -> Dict:
        """
        从用户消息更新偏好
        
        Args:
            user_message: 用户消息
            use_llm: 是否使用LLM进行深度抽取
            
        Returns:
            提取结果字典
        """
        if use_llm:
            # 🎯 使用LLM管道进行深度抽取
            try:
                from preference_manager import extract_preferences_with_llm, merge_preferences
                
                # 准备对话上下文
                context = [{"sender": "user" if i % 2 == 0 else "ai", "text": msg.get("user", "")} 
                          for i, msg in enumerate(self.conversation_history[-6:])]
                
                extraction_result = extract_preferences_with_llm(
                    user_query=user_message,
                    conversation_context=context,
                    existing_preferences=self.preferences
                )
                
                if "error" not in extraction_result:
                    # 合并新抽取的偏好
                    self.preferences = merge_preferences(self.preferences, extraction_result)
                    extraction_result["method"] = "llm_extraction"
                else:
                    print(f"LLM抽取失败，使用简单规则: {extraction_result['error']}")
                    # 回退到简单规则
                    extraction_result = self.simple_preference_update(user_message)
                    extraction_result["method"] = "simple_rules_fallback"
                    
                return extraction_result
                
            except ImportError:
                print("preference_manager模块未找到，使用简单规则抽取")
                result = self.simple_preference_update(user_message)
                result["method"] = "simple_rules_only"
                return result
        else:
            # 🎯 使用简单规则快速更新（实时决策卡片）
            result = self.simple_preference_update(user_message)
            result["method"] = "simple_rules"
            return result

    def simple_preference_update(self, user_message: str) -> Dict:
        """
        🎯 简化版偏好更新 - 专注于可靠提取
        """
        msg_lower = user_message.lower()
        updated_fields = []
        
        # === 价格识别 ===
        price_patterns = [
            (r'(\d+)\s*[-–到至]\s*(\d+)', 'range'),  # 100-150
            (r'under\s+(\d+)|below\s+(\d+)|less\s+than\s+(\d+)', 'max'),  # under 100
            (r'above\s+(\d+)|over\s+(\d+)|more\s+than\s+(\d+)', 'min'),   # above 100
            (r'around\s+(\d+)|about\s+(\d+)', 'around'),     # around 100
            (r'€(\d+)|(\d+)\s*euro', 'single')  # €100, 100 euro
        ]
        
        for pattern, price_type in price_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                groups = [g for g in match.groups() if g]
                if price_type == 'range' and len(groups) >= 2:
                    self.preferences['price_min'] = int(groups[0])
                    self.preferences['price_max'] = int(groups[1])
                    updated_fields.extend(['price_min', 'price_max'])
                elif price_type == 'max' and groups:
                    self.preferences['price_max'] = int(groups[0])
                    updated_fields.append('price_max')
                elif price_type == 'min' and groups:
                    self.preferences['price_min'] = int(groups[0])
                    updated_fields.append('price_min')
                elif price_type == 'around' and groups:
                    price = int(groups[0])
                    self.preferences['price_min'] = price - 10
                    self.preferences['price_max'] = price + 10
                    updated_fields.extend(['price_min', 'price_max'])
                elif price_type == 'single' and groups:
                    # 如果没有明确方向，设为最大值
                    self.preferences['price_max'] = int(groups[0])
                    updated_fields.append('price_max')
                break
        
        # === 停留天数识别 ===
        days_patterns = [
            r'(\d+)\s*days?',
            r'for\s+(\d+)\s*days?',
            r'about\s+(\d+)\s*days?'
        ]
        
        for pattern in days_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                days = int(match.group(1))
                self.preferences['minimum_nights'] = days
                updated_fields.append('minimum_nights')
                break
        
        # === 房间类型识别 ===
        room_type_mapping = {
            'private room': 'Private room',
            'entire place': 'Entire home/apt',
            'entire apartment': 'Entire home/apt',
            'entire home': 'Entire home/apt',
            'whole place': 'Entire home/apt',
            'shared room': 'Shared room',
            'hotel room': 'Hotel room'
        }
        
        for key, value in room_type_mapping.items():
            if key in msg_lower:
                self.preferences['room_type'] = value
                updated_fields.append('room_type')
                break
        
        # === 区域识别 - 需要查询实际数据库获取 ===
        # 🎯 这里需要动态获取，暂时用常见的
        berlin_areas = {
            # 常见大区映射
            'mitte': 'Mitte',
            'kreuzberg': 'Friedrichshain-Kreuzberg', 
            'friedrichshain': 'Friedrichshain-Kreuzberg',
            'prenzlauer berg': 'Pankow',
            'charlottenburg': 'Charlottenburg-Wilm.',
            'neukölln': 'Neukölln',
            'tempelhof': 'Tempelhof - Schöneberg',
        }
        
        for area_key, area_value in berlin_areas.items():
            if area_key in msg_lower:
                self.preferences['neighbourhood_group'] = area_value
                updated_fields.append('neighbourhood_group')
                break
        
        # === 关键词识别 ===
        # 设施关键词
        amenity_keywords = ['wifi', 'kitchen', 'balcony', 'parking', 'gym', 'pool', 
                           'laundry', 'air conditioning', 'heating', 'elevator']
        # 位置关键词
        location_keywords = ['central', 'quiet', 'metro', 'station', 'supermarket', 
                           'city center', 'near', 'close']
        # 体验关键词
        experience_keywords = ['clean', 'cozy', 'modern', 'spacious', 'bright', 
                             'comfortable', 'friendly']
        
        for keyword in amenity_keywords:
            if keyword in msg_lower and keyword not in self.preferences['amenities_keywords']:
                self.preferences['amenities_keywords'].append(keyword)
                updated_fields.append('amenities_keywords')
        
        for keyword in location_keywords:
            if keyword in msg_lower and keyword not in self.preferences['location_keywords']:
                self.preferences['location_keywords'].append(keyword)
                updated_fields.append('location_keywords')
                
        for keyword in experience_keywords:
            if keyword in msg_lower and keyword not in self.preferences['experience_keywords']:
                self.preferences['experience_keywords'].append(keyword)
                updated_fields.append('experience_keywords')
        
        # 🎯 保存完整的语义查询用于后续RAG检索
        if any(updated_fields):
            self.preferences['semantic_query'] = user_message
        
        return {
            "updated_fields": updated_fields,
            "extraction_method": "simple_rules",
            "confidence": "medium" if updated_fields else "low"
        }
    
    # ... 其他方法保持不变
    def update_stage(self, new_stage: ChatStage):
        self.stage = new_stage
        
    def get_preference_count(self) -> int:
        important_fields = ['room_type', 'price_min', 'price_max', 'neighbourhood_group', 'neighbourhood']
        return sum(1 for field in important_fields 
                  if self.preferences.get(field) is not None)
    
    def get_completeness_score(self) -> float:
        try:
            from preference_manager import get_preference_completeness_score
            return get_preference_completeness_score(self.preferences)
        except ImportError:
            total_fields = 5
            filled_fields = self.get_preference_count()
            return filled_fields / total_fields
    
    def add_conversation_turn(self, user_message: str, ai_response: str):
        self.conversation_history.append({
            "user": user_message,
            "ai": ai_response,
            "timestamp": time.time()
        })
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
    
    def should_show_recommendation_prompt(self) -> bool:
        completeness = self.get_completeness_score()
        preference_count = self.get_preference_count()
        return completeness >= 0.4 or preference_count >= 2  # 降低门槛
    
    def is_ready_for_recommendations(self) -> bool:
        # 🎯 降低推荐门槛：有预算或位置信息即可
        has_budget = (self.preferences.get('price_min') is not None or 
                     self.preferences.get('price_max') is not None)
        has_location = (self.preferences.get('neighbourhood') is not None or 
                       self.preferences.get('neighbourhood_group') is not None)
        has_room_type = self.preferences.get('room_type') is not None
        
        return has_budget or has_location or has_room_type
    
    def get_missing_critical_preferences(self) -> List[str]:
        missing = []
        
        if not (self.preferences.get('price_min') or self.preferences.get('price_max')):
            missing.append("budget range")
            
        if not (self.preferences.get('neighbourhood') or self.preferences.get('neighbourhood_group')):
            missing.append("preferred area")
            
        return missing  # 移除房间类型要求，让用户更容易开始
    
    def set_recommendations(self, recommendations: List[Dict]):
        self.current_listings = recommendations
        self.has_shown_listings = True
        self.last_recommendation_time = time.time()
        self.update_stage(ChatStage.RECOMMENDATION_SHOWN)
    
    def clear_recommendations(self):
        self.current_listings = []
        self.has_shown_listings = False
        self.last_recommendation_time = None

# ChatRouter 类保持不变...
class ChatRouter:
    def __init__(self):
        self.greeting_patterns = [
            r'^(hi|hello|hey|hiya|good\s+(morning|afternoon|evening))\s*[!.]*$',
            r'^(glad\s+to\s+see\s+you)\s*[!.]*$',
        ]
        
        self.thanks_patterns = [
            r'^(thanks?|thank\s+you|thx|appreciated?)\s*[!.]*$'
        ]
        
        self.berlin_qa_patterns = [
            r'landlord.*respon[ds]|respond.*landlord',
            r'how\s+long.*reply|reply.*how\s+long',
            r'wifi|internet|amenities',
            r'transport|metro|u-bahn|s-bahn',
        ]
        
        self.accommodation_keywords = [
            'accommodation', 'hotel', 'airbnb', 'room', 'apartment', 'stay', 'place',
            'listing', 'rent', 'book', 'sleep', 'night', 'berlin', 'area', 'neighborhood',
            'price', 'budget', 'euro', '€', 'private', 'shared', 'entire', 'conference', 'days'
        ]

    def classify_message(self, message: str, history: List, conv_state: ConversationState) -> Dict:
        """智能路由：决定是否需要RAG检索"""
        msg_lower = message.lower().strip()
        
        # 🎯 检查推荐请求
        show_patterns = [
            r'show\s+me', r'recommend', r'suggest', r'find\s+me', 
            r'any\s+options', r'what.*available', r'listings', r'all\s+listings'
        ]
        
        if any(re.search(pattern, msg_lower, re.I) for pattern in show_patterns):
            if conv_state.is_ready_for_recommendations():
                return {
                    "route": "recommendation_request",
                    "intent": "show_recommendations",
                    "new_stage": ChatStage.RECOMMENDATION_SHOWN,
                    "use_llm_extraction": True  # 🎯 推荐时深度抽取
                }
            else:
                return {
                    "route": "preference_prompt",
                    "intent": "need_more_preferences",
                    "new_stage": ChatStage.PREFERENCE_COLLECTION
                }
        
        # 🎯 包含住宿关键词 -> 更新偏好
        if self._contains_accommodation_keywords(msg_lower):
            # 先快速更新偏好
            conv_state.simple_preference_update(message)
            
            return {
                "route": "preference_update",
                "intent": "preference_update", 
                "new_stage": ChatStage.PREFERENCE_COLLECTION,
                "use_llm_extraction": False  # 平时不用LLM
            }
        
        # 其他路由逻辑...
        return {
            "route": "conversational",
            "intent": "general_inquiry",
            "new_stage": conv_state.stage
        }
    
    def _contains_accommodation_keywords(self, msg: str) -> bool:
        return any(keyword in msg for keyword in self.accommodation_keywords)

# 全局状态管理
conversation_states = {}

def get_conversation_state(session_id: str) -> ConversationState:
    if session_id not in conversation_states:
        conversation_states[session_id] = ConversationState()
    return conversation_states[session_id]

def route_conversation(message: str, history: List, conv_state: ConversationState) -> Dict:
    router = ChatRouter()
    return router.classify_message(message, history, conv_state)