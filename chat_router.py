# chat_router.py

import re
import json
import time
from typing import Dict, List, Optional
from enum import Enum

class ChatStage(Enum):
    GREETING = "greeting"
    PREFERENCE_COLLECTION = "preference_collection"
    EXPLORATION = "exploration"  # 新增状态
    RECOMMENDATION_READY = "recommendation_ready"
    RECOMMENDATION_SHOWN = "recommendation_shown"
    REFINEMENT = "refinement"
    BOOKING_INQUIRY = "booking_inquiry"

class ConversationState:
    def __init__(self):
        self.stage = ChatStage.GREETING
        self.preferences = {
            "room_type": None,
            "price_min": None,
            "price_max": None,
            "neighbourhood_group": None,
            "neighbourhood": None,
            "minimum_nights": None,
            "maximum_nights": None,
            "min_reviews": None,
            "reviews_per_month_min": None,
            "availability_min": None,
            "amenities_keywords": [],
            "location_keywords": [],
            "experience_keywords": [],
            "semantic_query": ""
        }
        self.has_shown_listings = False
        self.current_listings = []
        self.conversation_history = []
        self.last_recommendation_time = None
        
    def update_stage(self, new_stage: ChatStage):
        self.stage = new_stage
        
    def update_preferences_from_message(self, user_message: str, use_llm: bool = False) -> Dict:
        """从用户消息更新偏好"""
        if use_llm:
            print("use_llm为true, 使用llm抽取")
            try:
                from preference_manager import extract_preferences_with_llm, merge_preferences
                
                
                context = [{"sender": "user" if i % 2 == 0 else "ai", "text": msg.get("user", "")} 
                          for i, msg in enumerate(self.conversation_history[-6:])]
                
                extraction_result = extract_preferences_with_llm(
                    user_query=user_message,
                    conversation_context=context,
                    existing_preferences=self.preferences
                )
                
                if "error" not in extraction_result:
                    self.preferences = merge_preferences(self.preferences, extraction_result)
                    extraction_result["method"] = "llm_extraction"
                else:
                    print(f"LLM抽取失败，使用简单规则: {extraction_result['error']}")
                    extraction_result = self.simple_preference_update(user_message)
                    extraction_result["method"] = "simple_rules_fallback"
                    
                return extraction_result
                
            except ImportError:
                print("preference_manager模块未找到，使用简单规则抽取")
                result = self.simple_preference_update(user_message)
                result["method"] = "simple_rules_only"
                return result
        else:
            print("use_llm为false, 不使用llm抽取")
            result = self.simple_preference_update(user_message)
            result["method"] = "simple_rules"
            return result

    def simple_preference_update(self, user_message: str) -> Dict:
        """🎯 改进的简单偏好更新"""
        msg_lower = user_message.lower()
        updated_fields = []
        
        # === 价格识别 ===
        price_patterns = [
            (r'(\d+)\s*[-–到至]\s*(\d+)', 'range'),
            (r'under\s+(\d+)|below\s+(\d+)|less\s+than\s+(\d+)', 'max'),
            (r'above\s+(\d+)|over\s+(\d+)|more\s+than\s+(\d+)', 'min'),
            (r'around\s+(\d+)|about\s+(\d+)', 'around'),
            (r'€(\d+)|(\d+)\s*euro', 'single')
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
        
        # === 🎯 改进的地区识别 ===
        # 导入地理信息模块
        try:
            from berlin_geography import find_berlin_area
            
            # 使用智能地理匹配
            field_type, field_value, confidence, reason = find_berlin_area(user_message)
            
            if confidence >= 0.5:  # 置信度阈值
                if field_type == "neighbourhood_group":
                    self.preferences['neighbourhood_group'] = field_value
                    updated_fields.append('neighbourhood_group')
                    print(f"🗺️ 地区识别成功: {user_message} -> {field_value} (置信度: {confidence:.2f})")
                elif field_type == "neighbourhood":
                    self.preferences['neighbourhood'] = field_value
                    updated_fields.append('neighbourhood')
                    print(f"🗺️ 社区识别成功: {user_message} -> {field_value} (置信度: {confidence:.2f})")
        except ImportError:
            print("⚠️ berlin_geography模块未找到，使用简单地区匹配")
            # 回退到简单匹配
            berlin_areas = {
                'mitte': 'Mitte',
                'central': 'Mitte',
                'center': 'Mitte',
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
                    print(f"🗺️ 简单地区匹配: {area_key} -> {area_value}")
                    break
        
        # === 关键词识别 ===
        amenity_keywords = ['wifi', 'kitchen', 'balcony', 'parking', 'gym', 'pool', 
                           'laundry', 'air conditioning', 'heating', 'elevator']
        location_keywords = ['central', 'quiet', 'metro', 'station', 'supermarket', 
                           'city center', 'near', 'close']
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
        
        # 🎯 保存完整的语义查询
        if any(updated_fields):
            self.preferences['semantic_query'] = user_message
        
        print(f"🔍 简单偏好更新: 输入='{user_message}', 更新字段={updated_fields}")
        
        return {
            "updated_fields": updated_fields,
            "extraction_method": "simple_rules",
            "confidence": "medium" if updated_fields else "low"
        }
    
    # 其他方法保持不变...
    def get_preference_count(self) -> int:
        important_fields = ['room_type', 'price_min', 'price_max', 'neighbourhood_group', 'neighbourhood', 'minimum_nights']
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
        return completeness >= 0.4 or preference_count >= 2
    
    def is_ready_for_recommendations(self) -> bool:
        has_budget = (self.preferences.get('price_min') is not None or 
                     self.preferences.get('price_max') is not None)
        has_location = (self.preferences.get('neighbourhood') is not None or 
                       self.preferences.get('neighbourhood_group') is not None)
        has_room_type = self.preferences.get('room_type') is not None
        
        return has_budget or has_location or has_room_type

    def is_ready_for_recommendations_strict(self) -> bool:
        """
        严格就绪：房型 + 预算(任一) + 位置(任一) 三大关键维度同时具备
        """
        has_budget = (self.preferences.get('price_min') is not None or 
                     self.preferences.get('price_max') is not None)
        has_location = (self.preferences.get('neighbourhood') is not None or 
                       self.preferences.get('neighbourhood_group') is not None)
        has_room_type = self.preferences.get('room_type') is not None
        return has_budget and has_location and has_room_type
    
    def has_essential_preferences(self) -> dict:
        """
        Check if all essential preference dimensions are filled.
        Returns a dictionary with the check result and missing dimensions.
        """
        has_room_type = self.preferences.get('room_type') is not None
        has_price = (self.preferences.get('price_min') is not None or 
                    self.preferences.get('price_max') is not None)
        has_location = (self.preferences.get('neighbourhood') is not None or 
                       self.preferences.get('neighbourhood_group') is not None)
        
        all_essential_filled = has_room_type and has_price and has_location
        
        missing = []
        if not has_room_type:
            missing.append("room type")
        if not has_price:
            missing.append("price range")
        if not has_location:
            missing.append("location")
            
        return {
            "is_complete": all_essential_filled,
            "missing": missing
        }
    
    def get_missing_critical_preferences(self) -> List[str]:
        missing = []
        
        if not (self.preferences.get('price_min') or self.preferences.get('price_max')):
            missing.append("budget range")
            
        if not (self.preferences.get('neighbourhood') or self.preferences.get('neighbourhood_group')):
            missing.append("preferred area")
            
        return missing
    
    def set_recommendations(self, recommendations: List[Dict]):
        self.current_listings = recommendations
        self.has_shown_listings = True
        self.last_recommendation_time = time.time()
        # self.update_stage(ChatStage.RECOMMENDATION_SHOWN)
    
    def clear_recommendations(self):
        self.current_listings = []
        self.has_shown_listings = False
        self.last_recommendation_time = None

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
            r'wifi|internet|amenities',
            r'transport|metro|u-bahn|s-bahn',
        ]
        
        # 🎯 扩展住宿关键词，包含地理位置词汇
        self.accommodation_keywords = [
            'accommodation', 'hotel', 'airbnb', 'room', 'apartment', 'stay', 'place',
            'listing', 'rent', 'book', 'sleep', 'night', 'berlin', 'area', 'neighborhood',
            'price', 'budget', 'euro', '€', 'private', 'shared', 'entire', 'conference', 'days',
            # 🎯 地理位置关键词
            'central', 'center', 'mitte', 'kreuzberg', 'friedrichshain', 'prenzlauer',
            'charlottenburg', 'neukölln', 'tempelhof', 'district', 'location', 'where'
        ]

    def classify_message(self, message: str, history: List, conv_state: ConversationState) -> Dict:
        """🎯 改进的智能路由判断 - 仅保留三种路由类型"""
        msg_lower = message.lower().strip()
        

        print(f"🎯 路由分析: '{message}'")
        
        print(f"🎯 对话历史记录: '{history}'")

        # 1. 明确的问候或感谢 -> 转为对话式处理
        if self._is_greeting(msg_lower) or self._is_thanks(msg_lower):
            return {
                "route": "conversational",
                "intent": "greeting" if self._is_greeting(msg_lower) else "thanks",
                "new_stage": ChatStage.PREFERENCE_COLLECTION if self._is_greeting(msg_lower) else conv_state.stage
            }
        
        # 2. 检查推荐请求 -> 转为偏好提示
        show_patterns = [
            r'show\s+me', r'recommend', r'suggest', r'find\s+me', 
            r'any\s+options', r'what.*available', r'listings', r'all\s+listings',
            r'options', r'places', r'see.*recommendation',
            # 接受/确认类
            r'^yes\s+please$', r'^give\s+it\s+to\s+me$', r'^go\s+ahead$', r"^let'?s\s+see$", r'^sounds\s+good$', r'^ok(ay)?$'
        ]
        
        if any(re.search(pattern, msg_lower, re.I) for pattern in show_patterns):
            if conv_state.is_ready_for_recommendations_strict():
                print("✅ 路由到偏好提示 - 信息充足，准备推荐")
                return {
                    "route": "preference_prompt",
                    "intent": "show_recommendations",
                    "new_stage": ChatStage.RECOMMENDATION_SHOWN
                }
            else:
                print("⚠️ 路由到偏好提示 - 信息不足")
                return {
                    "route": "preference_prompt",
                    "intent": "need_more_preferences",
                    "new_stage": ChatStage.PREFERENCE_COLLECTION
                }
        
        # 3. 包含住宿关键词 -> 偏好更新（包含地理位置）
        if self._contains_accommodation_keywords(msg_lower):
            print("✅ 路由到偏好更新 - 检测到住宿关键词")
            return {
                "route": "preference_update",
                "intent": "preference_update", 
                "new_stage": ChatStage.PREFERENCE_COLLECTION,
                "use_llm_extraction": True
            }
        
        # 4. 地理位置提及检测 -> 偏好更新
        if self._mentions_location(msg_lower):
            print("✅ 路由到偏好更新 - 检测到地理位置")
            return {
                "route": "preference_update",
                "intent": "preference_update", 
                "new_stage": ChatStage.PREFERENCE_COLLECTION,
                "use_llm_extraction": True
            }
        
        # 5. 其他情况：对话式处理
        print("🤖 路由到对话式处理")
        return {
            "route": "conversational",
            "intent": "general_inquiry",
            "new_stage": conv_state.stage
        }
    
    def _mentions_location(self, msg: str) -> bool:
        """🎯 检测是否提及地理位置"""
        location_indicators = [
            # 直接地名
            'mitte', 'central', 'center', 'kreuzberg', 'friedrichshain', 
            'prenzlauer', 'charlottenburg', 'neukölln', 'tempelhof',
            # 位置描述词
            'area', 'district', 'neighborhood', 'location', 'where',
            'near', 'close to', 'around', 'in the'
        ]
        
        return any(indicator in msg for indicator in location_indicators)
    
    def _is_greeting(self, msg: str) -> bool:
        return any(re.match(pattern, msg, re.I) for pattern in self.greeting_patterns)
    
    def _is_thanks(self, msg: str) -> bool:
        return any(re.match(pattern, msg, re.I) for pattern in self.thanks_patterns)
    
    def _contains_accommodation_keywords(self, msg: str) -> bool:
        return any(keyword in msg for keyword in self.accommodation_keywords)

# 🎯 处理一般对话的处理函数
def handle_conversational_chat(message: str, history: List, conv_state: ConversationState) -> str:
    """🎯 使用小模型处理一般性对话"""
    
    msg_lower = message.lower()
    
    # 🎯 上下文感知的回复
    if "conference" in msg_lower or "business" in msg_lower:
        return "Perfect for a business trip! Berlin has great accommodations near conference venues. What's your budget and preferred area?"
    
    elif "visit" in msg_lower or "trip" in msg_lower or "vacation" in msg_lower:
        return "Exciting! Berlin is amazing to explore. I can help you find the perfect place to stay. What's your budget?"
    
    elif any(word in msg_lower for word in ["help", "find", "need", "looking"]):
        return "I'm here to help you find great Berlin accommodations! What's your budget and which area interests you?"
    
    elif any(word in msg_lower for word in ["thanks", "thank", "good", "great"]):
        return "You're welcome! Is there anything specific about Berlin accommodations I can help you with?"
    
    else:
        # 🎯 TODO: 这里可以集成1B小模型
        # 现在使用通用回复
        return "I'd be happy to help you find accommodation in Berlin! Tell me about your budget and preferred area."

# 全局状态管理
conversation_states = {}

def get_conversation_state(session_id: str) -> ConversationState:
    if session_id not in conversation_states:
        conversation_states[session_id] = ConversationState()
    return conversation_states[session_id]

def route_conversation(message: str, history: List, conv_state: ConversationState) -> Dict:
    router = ChatRouter()
    return router.classify_message(message, history, conv_state)