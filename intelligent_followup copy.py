# 修正的 intelligent_followup.py

"""
修正版智能追问系统
解决LLM输出解析和质量验证问题
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
        self._call_count = 0  # 🎯 添加调用计数，调试重复调用
        
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
        
        # 🎯 添加调用计数调试
        self._call_count += 1
        print(f"🔍 追问分析第{self._call_count}次调用")
        
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
                    "dimension": dimension
                }
            else:
                if field.endswith("_keywords"):
                    has_value = len(preferences.get(field, [])) > 0
                else:
                    has_value = preferences.get(field) is not None
                
                dimension_status[dimension.name] = {
                    "has_value": has_value,
                    "dimension": dimension
                }
        
        total_dimensions = len(self.followup_dimensions)
        filled_dimensions = sum(1 for status in dimension_status.values() if status["has_value"])
        completeness_score = filled_dimensions / total_dimensions
        
        missing_dimensions = [
            name for name, status in dimension_status.items() 
            if not status["has_value"]
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
    
    def _determine_followup_priority(self, dimension_status: Dict, 
                                   preferences: Dict, conversation_history: List) -> List[FollowupDimension]:
        """确定追问优先级"""
        
        missing_dimensions = [
            status["dimension"] for status in dimension_status.values() 
            if not status["has_value"]
        ]
        
        if not missing_dimensions:
            return []
        
        def priority_score(dim: FollowupDimension) -> float:
            score = 0.0
            
            if dim.priority == Priority.HIGH:
                score += 3.0
            elif dim.priority == Priority.MEDIUM:
                score += 2.0
            else:
                score += 1.0
            
            if dim.name == "budget" and not (preferences.get("price_min") or preferences.get("price_max")):
                score += 2.0
            
            if dim.name == "location" and not (preferences.get("neighbourhood_group") or preferences.get("neighbourhood")):
                score += 1.5
            
            return score
        
        missing_dimensions.sort(key=priority_score, reverse=True)
        return missing_dimensions[:3]
    
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
        """生成智能追问问题"""
        
        strategy = analysis_result["followup_strategy"]
        priority_dimensions = analysis_result["next_followup_priority"]
        
        if not priority_dimensions:
            return {
                "question": "I think I have enough information. Ready to see some great recommendations?",
                "question_type": "recommendation_ready",
                "target_dimensions": [],
                "use_llm": False,
                "fallback_question": ""
            }
        
        target_dimensions = priority_dimensions[:2]
        
        # 🎯 尝试使用LLM生成自然追问
        llm_question = self._generate_llm_followup(
            target_dimensions, strategy, user_message, current_preferences
        )
        
        fallback_question = self._generate_template_followup(target_dimensions, strategy)
        
        final_question = llm_question if llm_question else fallback_question
        
        print(f"💬 生成追问: {final_question[:50]}... (方法: {'LLM' if llm_question else 'Template'})")
        
        return {
            "question": final_question,
            "question_type": strategy,
            "target_dimensions": [dim.name for dim in target_dimensions],
            "use_llm": llm_question is not None,
            "fallback_question": fallback_question
        }
    
    def _generate_llm_followup(self, target_dimensions: List[FollowupDimension], 
                              strategy: str, user_message: str, current_preferences: Dict) -> Optional[str]:
        """使用LLM生成自然追问 - 修正版"""
        
        llm = self.get_llm()
        if not llm:
            print("🚫 LLM不可用，使用模板回退")
            return None
        
        try:
            # 🎯 改进的LLM提示 - 要求只输出问题
            dimension_names = [dim.name for dim in target_dimensions]
            
            # 🎯 精简提示，明确要求格式
            prompt_template = """You are a helpful assistant asking follow-up questions about Berlin accommodation preferences.

USER MESSAGE: "{user_message}"
CURRENT PREFERENCES: {current_preferences}
ASK ABOUT: {target_dimensions}

RULES:
1. Generate ONE natural question only
2. Ask about the target dimensions
3. Be conversational and friendly
4. Connect to user's context when possible
5. Output ONLY the question, no explanations

Question:"""
            
            prompt = PromptTemplate(
                input_variables=["user_message", "current_preferences", "target_dimensions"],
                template=prompt_template
            )
            
            chain = LLMChain(llm=llm, prompt=prompt)
            
            response = chain.predict(
                user_message=user_message or "",
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
        """🎯 改进的问题提取和验证逻辑"""
        
        if not response:
            return None
        
        # 清理响应
        response = response.strip()
        
        # 🎯 尝试提取实际问题
        # 1. 寻找引号内的问题
        quote_patterns = [
            r'"([^"]*\?[^"]*)"',  # "问题?"
            r"'([^']*\?[^']*)'",  # '问题?'
        ]
        
        for pattern in quote_patterns:
            matches = re.findall(pattern, response)
            for match in matches:
                question = match.strip()
                if self._is_valid_question(question):
                    return question
        
        # 2. 寻找以大写字母开头、以问号结尾的句子
        sentence_pattern = r'[A-Z][^.!]*\?'
        sentences = re.findall(sentence_pattern, response)
        for sentence in sentences:
            question = sentence.strip()
            if self._is_valid_question(question):
                return question
        
        # 3. 如果整个响应看起来像一个问题
        if self._is_valid_question(response):
            return response
        
        # 4. 尝试提取最后一个问号前的内容
        if '?' in response:
            parts = response.split('?')
            for part in reversed(parts[:-1]):  # 倒序检查每个部分
                potential_question = part.strip() + '?'
                # 查找最近的句子开始
                sentences = re.split(r'[.!]\s*', potential_question)
                if sentences:
                    last_sentence = sentences[-1].strip()
                    if self._is_valid_question(last_sentence):
                        return last_sentence
        
        return None
    
    def _is_valid_question(self, text: str) -> bool:
        """🎯 改进的问题验证逻辑"""
        
        if not text or not text.strip():
            return False
        
        text = text.strip()
        
        # 基本格式检查
        if not text.endswith('?'):
            return False
        
        # 长度检查 - 放宽限制
        if len(text) < 10 or len(text) > 300:
            return False
        
        # 内容质量检查
        # 必须包含疑问词或常见问题开头
        question_indicators = [
            'what', 'which', 'where', 'when', 'how', 'do you', 'are you', 
            'would you', 'could you', 'is', 'any', 'what\'s', 'which'
        ]
        
        text_lower = text.lower()
        if not any(indicator in text_lower for indicator in question_indicators):
            return False
        
        # 排除明显的非问题内容
        invalid_indicators = [
            'here\'s', 'this question', 'the question', 'addresses', 'explanation'
        ]
        
        if any(invalid in text_lower for invalid in invalid_indicators):
            return False
        
        return True
    
    def _generate_template_followup(self, target_dimensions: List[FollowupDimension], 
                                  strategy: str) -> str:
        """生成模板化追问（备用）"""
        
        if not target_dimensions:
            return "Tell me more about what you're looking for!"
        
        first_dim = target_dimensions[0]
        
        # 根据维度类型选择模板
        if first_dim.name == "budget":
            return "What's your budget range per night? This will help me find the best options for you."
        elif first_dim.name == "location":
            return "Which area of Berlin would you prefer? Central, trendy, or quieter neighborhoods?"
        elif first_dim.name == "room_type":
            return "Would you like a private room or entire place?"
        elif first_dim.name == "popularity":
            return "Do you prefer popular, well-reviewed places or are you open to newer listings?"
        elif first_dim.name == "amenities_focus":
            return "Any specific amenities that are important to you, like WiFi or kitchen access?"
        else:
            return random.choice(first_dim.examples) if first_dim.examples else "Tell me more about your preferences!"

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
        'Here\'s a natural follow-up question:\n"So you\'re heading to Berlin for a conference - are you looking to stay in the city center?"',
        'What\'s your budget range per night?',
        'Which area of Berlin would you prefer? Central or quieter neighborhoods?',
        'Here is the question: "Do you prefer popular places?" This addresses the popularity dimension.',
        'Random text without question',
        'This is not a question.',
        '"Are you comfortable with shared spaces?"',
    ]
    
    manager = intelligent_followup
    
    for i, response in enumerate(test_responses, 1):
        print(f"\n测试 {i}: {response[:50]}...")
        question = manager._extract_and_validate_question(response)
        print(f"结果: {question if question else '❌ 提取失败'}")

if __name__ == "__main__":
    test_question_extraction()