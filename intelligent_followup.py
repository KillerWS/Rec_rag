"""
修复版智能追问系统
解决重复调用、问题验证过严和意图识别问题
"""

import json
import re
import random
from typing import Dict, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass
from load_llm import get_llm
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

class DimensionType(Enum):
    EXPLICIT = "explicit"
    IMPLICIT = "implicit"

class Priority(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class FollowupDimension:
    """追问维度定义"""
    name: str
    dimension_type: DimensionType
    priority: Priority
    field_mapping: str
    description: str
    examples: List[str]
    
class IntelligentFollowupManager:
    """智能追问管理器 - 修正版"""
    
    def __init__(self):
        self.llm_model = None
        self.followup_dimensions = self._define_followup_dimensions()
        self._call_count = 0
        self._last_question_target = None  # 🎯 防止重复问同一维度
        self._conversation_memory = []     # 🎯 记录已问过的维度
        
    def get_llm(self):
        """获取LLM实例"""
        if self.llm_model is None:
            try:
                self.llm_model = get_llm()
            except Exception as e:
                print(f"LLM加载失败: {e}")
                self.llm_model = None
        return self.llm_model
    
    def _define_followup_dimensions(self) -> List[FollowupDimension]:
        """定义所有可追问的维度"""
        return [
            FollowupDimension(
                name="budget",
                dimension_type=DimensionType.EXPLICIT,
                priority=Priority.HIGH,
                field_mapping="price_max",
                description="用户预算范围",
                examples=["What's your budget per night?", "How much are you planning to spend daily?"]
            ),
            FollowupDimension(
                name="location",
                dimension_type=DimensionType.EXPLICIT,
                priority=Priority.HIGH,
                field_mapping="neighbourhood_group",
                description="位置偏好",
                examples=["Which area of Berlin interests you?", "Do you prefer central or quieter neighborhoods?"]
            ),
            FollowupDimension(
                name="room_type",
                dimension_type=DimensionType.EXPLICIT,
                priority=Priority.HIGH,
                field_mapping="room_type",
                description="房间类型",
                examples=["Would you like a private room or entire place?", "Are you comfortable sharing space with others?"]
            ),
            FollowupDimension(
                name="stay_duration",
                dimension_type=DimensionType.EXPLICIT,
                priority=Priority.MEDIUM,
                field_mapping="minimum_nights",
                description="停留时长",
                examples=["How long are you planning to stay?", "Is this for a short trip or longer stay?"]
            ),
            FollowupDimension(
                name="popularity",
                dimension_type=DimensionType.IMPLICIT,
                priority=Priority.MEDIUM,
                field_mapping="min_reviews",
                description="热门程度偏好",
                examples=["Do you prefer popular, well-reviewed places?", "Are you comfortable with newer listings?"]
            ),
            FollowupDimension(
                name="amenities_focus",
                dimension_type=DimensionType.IMPLICIT,
                priority=Priority.MEDIUM,
                field_mapping="amenities_keywords",
                description="设施重点关注",
                examples=["What amenities are important to you?", "Any must-have facilities like wifi or kitchen?"]
            ),
            FollowupDimension(
                name="location_convenience",
                dimension_type=DimensionType.IMPLICIT,
                priority=Priority.MEDIUM,
                field_mapping="location_keywords",
                description="位置便利性",
                examples=["Do you need to be close to public transport?", "Is walking distance to city center important?"]
            )
        ]
    
    def analyze_current_state(self, preferences: Dict, conversation_history: List) -> Dict:
        """分析当前对话状态，决定追问策略"""
        
        # 🎯 防止重复调用 - 添加调用检查
        self._call_count += 1
        if self._call_count % 10 == 0:  # 每10次调用警告一次
            print(f"⚠️  追问分析被调用了{self._call_count}次，可能存在重复调用问题")
        
        # 🎯 更新对话记忆
        self._update_conversation_memory(conversation_history)
        
        dimension_status = {}
        
        for dimension in self.followup_dimensions:
            field = dimension.field_mapping
            
            if dimension.dimension_type == DimensionType.EXPLICIT:
                has_value = preferences.get(field) is not None
                if field in ["price_min", "price_max"]:
                    has_value = (preferences.get("price_min") is not None or 
                               preferences.get("price_max") is not None)
                elif field in ["neighbourhood_group", "neighbourhood"]:
                    has_value = (preferences.get("neighbourhood_group") is not None or 
                               preferences.get("neighbourhood") is not None)
                
                dimension_status[dimension.name] = {
                    "has_value": has_value,
                    "dimension": dimension,
                    "recently_asked": self._was_recently_asked(dimension.name)  # 🎯 新增
                }
            else:
                if field.endswith("_keywords"):
                    has_value = len(preferences.get(field, [])) > 0
                else:
                    has_value = preferences.get(field) is not None
                
                dimension_status[dimension.name] = {
                    "has_value": has_value,
                    "dimension": dimension,
                    "recently_asked": self._was_recently_asked(dimension.name)  # 🎯 新增
                }
        
        total_dimensions = len(self.followup_dimensions)
        filled_dimensions = sum(1 for status in dimension_status.values() if status["has_value"])
        completeness_score = filled_dimensions / total_dimensions
        
        missing_dimensions = [
            name for name, status in dimension_status.items() 
            if not status["has_value"] and not status["recently_asked"]  # 🎯 排除最近问过的
        ]
        
        next_followup_priority = self._determine_followup_priority(
            dimension_status, preferences, conversation_history
        )
        
        followup_strategy = self._determine_followup_strategy(
            completeness_score, missing_dimensions, conversation_history
        )
        
        print(f"📊 分析结果: 完整度={completeness_score:.2f}, 策略={followup_strategy}, 优先维度={[d.name for d in next_followup_priority[:2]]}")
        
        return {
            "completeness_score": completeness_score,
            "missing_dimensions": missing_dimensions,
            "next_followup_priority": next_followup_priority,
            "followup_strategy": followup_strategy,
            "dimension_status": dimension_status
        }
    
    def _update_conversation_memory(self, conversation_history: List):
        """🎯 更新对话记忆，避免重复问题"""
        self._conversation_memory = conversation_history[-10:]  # 只保留最近10条
    
    def _was_recently_asked(self, dimension_name: str) -> bool:
        """🎯 检查是否最近问过某个维度"""
        if not self._conversation_memory:
            return False
        
        # 检查最近3条系统消息
        recent_system_messages = [
            msg.get('text', '') for msg in self._conversation_memory[-6:]
            if msg.get('sender') == 'system'
        ][-3:]
        
        # 根据维度名称检查关键词
        dimension_keywords = {
            "budget": ["budget", "price", "cost", "spend", "euro", "€"],
            "location": ["area", "location", "neighborhood", "central", "centre", "where"],
            "room_type": ["room", "apartment", "entire", "private", "shared", "hotel"],
            "stay_duration": ["long", "stay", "night", "duration", "days"],
            "popularity": ["popular", "review", "rating", "well-reviewed"],
            "amenities_focus": ["amenities", "facilities", "wifi", "kitchen"],
            "location_convenience": ["transport", "metro", "subway", "walking distance"]
        }
        
        keywords = dimension_keywords.get(dimension_name, [])
        
        for message in recent_system_messages:
            message_lower = message.lower()
            if any(keyword in message_lower for keyword in keywords):
                print(f"🔍 检测到维度 '{dimension_name}' 最近被问过: {message[:50]}...")
                return True
        
        return False
    
    def _determine_followup_priority(self, dimension_status: Dict, 
                                   preferences: Dict, conversation_history: List) -> List[FollowupDimension]:
        """确定追问优先级 - 修正版"""
        
        missing_dimensions = [
            status["dimension"] for status in dimension_status.values() 
            if not status["has_value"] and not status["recently_asked"]  # 🎯 排除最近问过的
        ]
        
        if not missing_dimensions:
            print("✅ 所有维度都已填充或最近问过，准备推荐")
            return []
        
        def priority_score(dim: FollowupDimension) -> float:
            score = 0.0
            
            if dim.priority == Priority.HIGH:
                score += 3.0
            elif dim.priority == Priority.MEDIUM:
                score += 2.0
            else:
                score += 1.0
            
            # 🎯 预算优先级最高（如果没有设置）
            if dim.name == "budget" and not (preferences.get("price_min") or preferences.get("price_max")):
                score += 2.0
            
            # 🎯 位置其次重要
            if dim.name == "location" and not (preferences.get("neighbourhood_group") or preferences.get("neighbourhood")):
                score += 1.5
            
            # 🎯 房间类型也很重要
            if dim.name == "room_type" and not preferences.get("room_type"):
                score += 1.3
            
            return score
        
        missing_dimensions.sort(key=priority_score, reverse=True)
        return missing_dimensions[:2]  # 🎯 减少到最多2个维度
    
    def _determine_followup_strategy(self, completeness_score: float, 
                                   missing_dimensions: List, conversation_history: List) -> str:
        """确定追问策略"""
        
        if completeness_score >= 0.8:
            return "ready_for_recommendation"
        elif completeness_score >= 0.6:
            return "final_confirmation"
        elif completeness_score >= 0.4:
            return "targeted_followup"
        else:
            return "basic_collection"
    
    def generate_followup_question(self, analysis_result: Dict, 
                                 user_message: str = "", 
                                 current_preferences: Dict = None) -> Dict:
        """生成智能追问问题 - 修正版"""
        
        strategy = analysis_result["followup_strategy"]
        priority_dimensions = analysis_result["next_followup_priority"]
        
        # 🎯 如果没有需要追问的维度，准备推荐
        if not priority_dimensions:
            return {
                "question": "I think I have enough information. Ready to see some great recommendations?",
                "question_type": "recommendation_ready",
                "target_dimensions": [],
                "use_llm": False,
                "fallback_question": ""
            }
        
        target_dimensions = priority_dimensions[:1]  # 🎯 一次只问一个维度
        
        # 🎯 检测用户意图冲突并优先处理
        conflict_question = self._detect_preference_conflicts(user_message, current_preferences)
        if conflict_question:
            print(f"🔍 检测到偏好冲突，生成澄清问题")
            return {
                "question": conflict_question,
                "question_type": "conflict_resolution",
                "target_dimensions": [dim.name for dim in target_dimensions],
                "use_llm": False,
                "fallback_question": conflict_question
            }
        
        # 🎯 尝试使用LLM生成自然追问
        llm_question = self._generate_llm_followup(
            target_dimensions, strategy, user_message, current_preferences
        )
        
        fallback_question = self._generate_template_followup(target_dimensions, strategy)
        
        final_question = llm_question if llm_question else fallback_question
        
        # 🎯 记录本次追问的目标维度
        self._last_question_target = target_dimensions[0].name if target_dimensions else None
        
        print(f"💬 生成追问: {final_question[:50]}... (方法: {'LLM' if llm_question else 'Template'})")
        
        return {
            "question": final_question,
            "question_type": strategy,
            "target_dimensions": [dim.name for dim in target_dimensions],
            "use_llm": llm_question is not None,
            "fallback_question": fallback_question
        }
    
    def _detect_preference_conflicts(self, user_message: str, current_preferences: Dict) -> Optional[str]:
        """🎯 检测用户偏好冲突"""
        if not user_message:
            return None
        
        user_lower = user_message.lower()
        
        # 检测位置偏好冲突
        central_keywords = ['central', 'centre', 'center', 'city center', 'downtown']
        quiet_keywords = ['quiet', 'quieter', 'peaceful', 'calm', 'residential']
        
        wants_central = any(keyword in user_lower for keyword in central_keywords)
        wants_quiet = any(keyword in user_lower for keyword in quiet_keywords)
        
        # 🎯 修复：如果用户在同一条消息中既要中心又要安静，需要澄清
        if wants_central and wants_quiet:
            return "I understand you want both central location and quiet environment. Would you prefer a quieter area within the city center, or are you open to slightly outside central but very peaceful neighborhoods like Prenzlauer Berg?"
        
        # 检测已有location_keywords是否与新需求冲突（仅当有现有偏好时）
        if current_preferences:
            existing_location_keywords = current_preferences.get('location_keywords', [])
            if existing_location_keywords:
                has_central_existing = any(keyword in ' '.join(existing_location_keywords).lower() 
                                         for keyword in central_keywords)
                if has_central_existing and wants_quiet:
                    return "I noticed you mentioned both central location and quieter neighborhoods. Would you like me to focus on quiet areas within central Berlin, or would you prefer truly peaceful areas even if they're a bit further from the very center?"
        
        return None
    
    def _generate_llm_followup(self, target_dimensions: List[FollowupDimension], 
                              strategy: str, user_message: str, current_preferences: Dict) -> Optional[str]:
        """使用LLM生成自然追问 - 修正版"""
        
        llm = self.get_llm()
        if not llm:
            print("🚫 LLM不可用，使用模板回退")
            return None
        
        try:
            # 🎯 改进的LLM提示 - 更简洁明确
            dimension_names = [dim.name for dim in target_dimensions]
            
            prompt_template = """You are a helpful assistant asking follow-up questions about Berlin accommodation.

USER: "{user_message}"
CURRENT PREFERENCES: {current_preferences}
ASK ABOUT: {target_dimensions}

Generate ONE short, natural question (max 15 words). Be friendly and conversational.
Only output the question, nothing else.

Question:"""
            
            prompt = PromptTemplate(
                input_variables=["user_message", "current_preferences", "target_dimensions"],
                template=prompt_template
            )
            
            chain = LLMChain(llm=llm, prompt=prompt)
            
            response = chain.predict(
                user_message=user_message or "looking for accommodation",
                current_preferences=json.dumps(current_preferences or {}, ensure_ascii=False),
                target_dimensions=", ".join(dimension_names)
            )
            
            # 🎯 改进的问题提取和验证
            question = self._extract_and_validate_question(response)
            
            if question:
                print(f"✅ LLM生成成功: {question}")
                return question
            else:
                print(f"❌ LLM生成的问题质量不佳: {response[:100]}...")
                return None
                
        except Exception as e:
            print(f"❌ LLM追问生成失败: {e}")
            return None
    
    def _extract_and_validate_question(self, response: str) -> Optional[str]:
        """🎯 更宽松的问题提取和验证逻辑"""
        
        if not response:
            return None
        
        # 清理响应
        response = response.strip()
        
        # 🎯 首先尝试最简单的方法 - 如果整个响应看起来像问题
        if self._is_valid_question_relaxed(response):
            return response
        
        # 🎯 提取引号内的问题
        quote_patterns = [
            r'"([^"]*\?[^"]*)"',
            r"'([^']*\?[^']*)'",
        ]
        
        for pattern in quote_patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                question = match.strip()
                if self._is_valid_question_relaxed(question):
                    return question
        
        # 🎯 寻找以大写字母开头、以问号结尾的句子
        sentence_pattern = r'[A-Z][^.!]*\?'
        sentences = re.findall(sentence_pattern, response)
        for sentence in sentences:
            question = sentence.strip()
            if self._is_valid_question_relaxed(question):
                return question
        
        # 🎯 最后尝试提取包含问号的内容
        if '?' in response:
            parts = response.split('?')
            for i, part in enumerate(parts[:-1]):
                potential_question = part.strip() + '?'
                if self._is_valid_question_relaxed(potential_question):
                    return potential_question
        
        return None
    
    def _is_valid_question_relaxed(self, text: str) -> bool:
        """🎯 更宽松的问题验证逻辑"""
        
        if not text or not text.strip():
            return False
        
        text = text.strip()
        
        # 基本格式检查
        if not text.endswith('?'):
            return False
        
        # 🎯 更宽松的长度检查
        if len(text) < 5 or len(text) > 200:
            return False
        
        # 🎯 简化的内容质量检查
        # 必须包含一些基本的问题特征
        text_lower = text.lower()
        
        # 检查是否包含疑问词或问题结构
        has_question_word = any(word in text_lower for word in [
            'what', 'which', 'where', 'when', 'how', 'do you', 'are you', 
            'would you', 'could you', 'is', 'any', 'what\'s', 'how about',
            'interested', 'prefer', 'looking', 'need', 'want'
        ])
        
        # 🎯 放宽验证 - 如果有问号且有基本问题结构就接受
        if has_question_word:
            # 排除明显的非问题
            invalid_phrases = ['here is', 'this is', 'explanation', 'note that']
            if not any(phrase in text_lower for phrase in invalid_phrases):
                return True
        
        return False
    
    def _generate_template_followup(self, target_dimensions: List[FollowupDimension], 
                                  strategy: str) -> str:
        """生成模板化追问（备用）"""
        
        if not target_dimensions:
            return "Tell me more about what you're looking for!"
        
        first_dim = target_dimensions[0]
        
        # 🎯 简化模板，避免过长问题
        if first_dim.name == "budget":
            return "What's your budget range per night?"
        elif first_dim.name == "location":
            return "Which area of Berlin would you prefer?"
        elif first_dim.name == "room_type":
            return "Would you like a private room or entire place?"
        elif first_dim.name == "stay_duration":
            return "How long are you planning to stay?"
        elif first_dim.name == "popularity":
            return "Do you prefer popular, well-reviewed places?"
        elif first_dim.name == "amenities_focus":
            return "Any specific amenities that are important to you?"
        elif first_dim.name == "location_convenience":
            return "Do you need to be close to public transport?"
        else:
            return "Tell me more about your preferences!"

# 🎯 全局实例
intelligent_followup = IntelligentFollowupManager()

def analyze_followup_needs(preferences: Dict, conversation_history: List) -> Dict:
    """分析追问需求的便捷函数"""
    return intelligent_followup.analyze_current_state(preferences, conversation_history)

def generate_smart_followup(analysis_result: Dict, user_message: str = "", 
                          current_preferences: Dict = None) -> Dict:
    """生成智能追问的便捷函数"""
    return intelligent_followup.generate_followup_question(
        analysis_result, user_message, current_preferences
    )

# 🧪 测试函数
def test_question_extraction():
    """测试问题提取功能"""
    print("=" * 60)
    print("🧪 测试问题提取功能")
    print("=" * 60)
    
    test_responses = [
        'What\'s your budget range per night?',
        'Which area of Berlin would you prefer?',
        'Are you looking to be close to any specific landmarks?',
        'Do you prefer popular places?',
        'Here is a question: "What about central areas?" This is good.',
        'Random text without question',
        'This is not a question.',
        '"Are you comfortable with shared spaces?"',
        'How about Kreuzberg or Mitte?',
        'What amenities are important to you?'
    ]
    
    manager = intelligent_followup
    
    for i, response in enumerate(test_responses, 1):
        print(f"\n测试 {i}: {response}")
        question = manager._extract_and_validate_question(response)
        print(f"结果: {question if question else '❌ 提取失败'}")

def test_conflict_detection():
    """测试冲突检测功能"""
    print("\n" + "=" * 60)
    print("🧪 测试冲突检测功能")
    print("=" * 60)
    
    test_cases = [
        {
            "user_message": "I want central location but also quieter neighborhoods",
            "preferences": {},
            "expected": "should detect conflict"
        },
        {
            "user_message": "quieter neighborhoods is better for me",
            "preferences": {"location_keywords": ["central", "city center"]},
            "expected": "should detect conflict with existing central preference"
        },
        {
            "user_message": "I need wifi",
            "preferences": {},
            "expected": "no conflict"
        }
    ]
    
    manager = intelligent_followup
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {case['user_message']}")
        print(f"现有偏好: {case['preferences']}")
        conflict = manager._detect_preference_conflicts(case['user_message'], case['preferences'])
        print(f"冲突检测: {conflict if conflict else '无冲突'}")
        print(f"期望: {case['expected']}")

if __name__ == "__main__":
    test_question_extraction()
    test_conflict_detection()