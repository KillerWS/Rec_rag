"""
更新的对话状态管理模块
集成新的偏好管理系统
"""

import time
from typing import Dict, List, Optional
from enum import Enum
from preference_manager import (
    extract_preferences_with_llm, 
    merge_preferences, 
    get_preference_completeness_score
)

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
        # 🎯 使用新的偏好schema
        self.preferences = {
            # 直接映射到数据库字段
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
            
            # 语义搜索字段
            "amenities_keywords": [],
            "location_keywords": [],
            "comfort_keywords": [],
            "missing_dimension": []
        }
        self.has_shown_listings = False
        self.current_listings = []
        self.conversation_history = []
        self.last_recommendation_time = None
        
    def update_stage(self, new_stage: ChatStage):
        """更新对话阶段"""
        self.stage = new_stage
        
    def update_preferences_from_message(self, user_message: str) -> Dict:
        """
        从用户消息更新偏好
        
        Args:
            user_message: 用户消息
            
        Returns:
            提取结果字典
        """
        # 准备对话上下文
        context = [{"sender": "user" if i % 2 == 0 else "ai", "text": msg.get("message", "")} 
                  for i, msg in enumerate(self.conversation_history[-6:])]
        
        # 使用LLM提取偏好
        extraction_result = extract_preferences_with_llm(
            user_query=user_message,
            conversation_context=context,
            existing_preferences=self.preferences
        )
        
        if "error" not in extraction_result:
            # 合并新偏好到现有偏好
            self.preferences = merge_preferences(self.preferences, extraction_result)
            
        return extraction_result
    
    def get_preference_count(self) -> int:
        """获取已设置的重要偏好数量"""
        important_fields = ['room_type', 'price_min', 'price_max', 'neighbourhood_group', 'neighbourhood']
        return sum(1 for field in important_fields 
                  if self.preferences.get(field) is not None)
    
    def get_completeness_score(self) -> float:
        """获取偏好完整度评分"""
        return get_preference_completeness_score(self.preferences)
    
    def add_conversation_turn(self, user_message: str, ai_response: str):
        """添加对话轮次"""
        self.conversation_history.append({
            "user": user_message,
            "ai": ai_response,
            "timestamp": time.time()
        })
        # 只保留最近10轮对话
        if len(self.conversation_history) > 10:
            self.conversation_history = self.conversation_history[-10:]
    
    def should_show_recommendation_prompt(self) -> bool:
        """判断是否应该显示推荐提示"""
        completeness = self.get_completeness_score()
        preference_count = self.get_preference_count()
        
        # 满足以下条件之一就显示推荐提示：
        # 1. 完整度达到60%
        # 2. 已有2个或以上重要偏好
        # 3. 用户明确表达想看推荐的意图
        return completeness >= 0.6 or preference_count >= 2
    
    def is_ready_for_recommendations(self) -> bool:
        """判断是否准备好进行推荐"""
        # 至少需要预算范围
        has_budget = (self.preferences.get('price_min') is not None or 
                     self.preferences.get('price_max') is not None)
        
        # 最好有位置信息，但不是必须的
        has_location = (self.preferences.get('neighbourhood') is not None or 
                       self.preferences.get('neighbourhood_group') is not None)
        
        # 如果有预算就可以推荐，位置信息可以后续refinement
        return has_budget
    
    def get_missing_critical_preferences(self) -> List[str]:
        """获取缺失的关键偏好信息"""
        missing = []
        
        if not (self.preferences.get('price_min') or self.preferences.get('price_max')):
            missing.append("budget range")
            
        if not (self.preferences.get('neighbourhood') or self.preferences.get('neighbourhood_group')):
            missing.append("preferred area")
            
        if not self.preferences.get('room_type'):
            missing.append("room type")
            
        return missing
    
    def set_recommendations(self, recommendations: List[Dict]):
        """设置当前推荐结果"""
        self.current_listings = recommendations
        self.has_shown_listings = True
        self.last_recommendation_time = time.time()
        self.update_stage(ChatStage.RECOMMENDATION_SHOWN)
    
    def clear_recommendations(self):
        """清除推荐结果"""
        self.current_listings = []
        self.has_shown_listings = False
        self.last_recommendation_time = None

# 全局对话状态存储
conversation_states = {}

def get_conversation_state(session_id: str) -> ConversationState:
    """获取或创建对话状态"""
    if session_id not in conversation_states:
        conversation_states[session_id] = ConversationState()
    return conversation_states[session_id]

def clear_conversation_state(session_id: str):
    """清除对话状态"""
    if session_id in conversation_states:
        del conversation_states[session_id]