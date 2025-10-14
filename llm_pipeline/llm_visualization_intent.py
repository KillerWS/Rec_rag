# llm_visualization_intent.py
"""
LLM驱动的可视化意图识别模块 - 替换基于规则的可视化意图判断
该模块可以识别所有10种图表类型，而不仅限于基于规则方法的3种
"""

import json
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from load_llm import get_client_llm

# 定义可视化意图的响应模型（英文配置）
class VisualizationIntent(BaseModel):
    intent: str = Field(description="Visualization type name")
    confidence: float = Field(description="Confidence score between 0-1", ge=0, le=1) 
    reasoning: Optional[str] = Field(description="Reason for recommending this visualization type")

class VisualizationResponse(BaseModel):
    visualizations: List[VisualizationIntent] = Field(description="List of identified visualization intents")
    should_show_visualization: bool = Field(description="Whether to display visualization")
    priority: str = Field(description="Priority level: high/medium/low/none")
    reason: Optional[str] = Field(description="Reason for recommending charts")
    best_chart_types: Optional[List[str]] = Field(description="List of best chart types")

class LLMVisualizationIntentRecognizer:
    """
    使用LLM识别用户查询中的可视化意图，支持全部10种图表类型
    """
    
    def __init__(self):
        self.client = get_client_llm()
        
        # 定义支持的所有10种图表类型
        self.visualization_types = {
            "price_distribution": {
                "description": "Price distribution analysis – shows how listings are distributed across price ranges, useful for checking budget feasibility.",
                "chart_type": "histogram",
                "dimensions": ["price_min", "price_max", "neighbourhood_group", "room_type"],
                "keywords": ["price distribution", "price range", "price analysis", "price histogram", "budget feasibility"]
            },
            "location_popularity": {
                "description": "Location popularity analysis – compares which districts or areas are most popular based on listing counts or reviews.",
                "chart_type": "bar",
                "dimensions": ["neighbourhood_group", "neighbourhood", "min_reviews"],
                "keywords": [
                    "popular area", "most popular", "top districts", "popular districts",
                    "which districts", "which areas", "popular neighbourhoods", "location popularity", "area comparison",
                    "地区受欢迎", "热门地区", "热门区域", "最受欢迎", "受欢迎 程度", "人气"
                ]
            },
            "room_type_comparison": {
                "description": "Room type comparison – compares proportions of room types (entire home, private room, shared room, hotel) within a region or budget range.",
                "chart_type": "pie",
                "dimensions": ["neighbourhood_group", "price_min", "price_max"],
                "keywords": [
                    "room type", "accommodation type", "room type comparison", "type distribution", "listing type",
                    "distribution of room types", "types in berlin", "房型 分布", "按 房型"
                ]
            },
            "neighbourhood_comparison": {
                "description": "Neighbourhood comparison – detailed comparison across neighbourhoods, such as average price, review scores, or listing volume.",
                "chart_type": "bar",
                "dimensions": ["neighbourhood_group", "room_type"],
                "keywords": ["neighbourhood comparison", "community analysis", "area details", "neighbourhood statistics", "district comparison"]
            },
            "reviews_analysis": {
                "description": "Reviews analysis – analyzes reviews, ratings, or review counts by area or listing type to identify popular or highly rated listings.",
                "chart_type": "bar",
                "dimensions": ["neighbourhood_group", "neighbourhood", "min_reviews"],
                "keywords": [
                    "reviews", "review analysis", "review scores", "analyze review scores",
                    "by neighbourhood", "by district", "ratings by area", "评分 分析", "按 区 评分",
                    "评论分析", "评论 分析", "评分 按 区"
                ]
            },
            "price_trend": {
                "description": "Price trend analysis – shows how prices change over time or across locations, useful for observing seasonal or spatial trends.",
                "chart_type": "line",
                "dimensions": ["neighbourhood_group"],
                "keywords": ["price trend", "price over time", "price changes", "temporal trend", "price evolution"]
            },
            "availability_analysis": {
                "description": "Availability analysis – visualizes the proportion of available or booked listings within certain areas or time frames.",
                "chart_type": "pie",
                "dimensions": ["neighbourhood_group"],
                "keywords": ["availability", "booking availability", "vacancy status", "occupancy rate", "listing availability"]
            },
            "host_analysis": {
                "description": "Host analysis – examines host-level information such as number of listings, response rate, and superhost status.",
                "chart_type": "scatter",
                "dimensions": [],
                "keywords": ["host analysis", "host statistics", "superhost", "host behavior", "host activity"]
            },
            "comments_wordcloud": {
                "description": "Comments word cloud – displays frequent keywords or topics extracted from guest reviews, highlighting common themes or sentiments.",
                "chart_type": "wordcloud",
                "dimensions": ["neighbourhood_group"],
                "keywords": [
                    "wordcloud", "review keywords", "review topics", "text analysis", "feedback summary",
                    "word cloud of frequent review keywords", "评论 词云", "高频 关键词"
                ]
            },
            "distance_price_tradeoff": {
                "description": "Distance–price trade-off analysis – explores how listing prices vary with distance from the city center, allowing alpha-weighted balance between proximity and price.",
                "chart_type": "bar",
                "dimensions": ["granularity", "alpha", "center", "min_listings", "room_type", "minimum_nights", "min_reviews", "price_min", "price_max", "top_k"],
                "keywords": [
                    "distance", "near", "close to", "travel time", "proximity",
                    "price vs distance", "tradeoff", "alpha", "balanced", "distance-price relationship"
                ]
            },
            "value_quality_quadrant": {
                "description": "Value–quality quadrant – visualizes the relationship between value for money and quality index, showing which areas or listings offer the best balance between price and rating.",
                "chart_type": "scatter",
                "dimensions": ["area", "neighbourhood_group", "neighbourhood", "room_type", "min_reviews"],
                "keywords": [
                    "value vs quality", "value-quality quadrant", "bang for buck", "cost–quality tradeoff", "value index", "quality score"
                ]
            },
            "price_coverage_delta": {
                "description": "Budget coverage delta analysis – compares how many listings are covered when budget limits increase or decrease, showing marginal coverage gain per budget step.",
                "chart_type": "line",
                "dimensions": ["base_budget", "new_budget", "step", "neighbourhood_group", "room_type", "min_reviews", "availability_min"],
                "keywords": [
                    "budget coverage", "coverage curve", "budget increase", "budget change", "budget comparison",
                    "what if budget", "increase budget", "decrease budget", "budget impact", "coverage analysis",
                    "budget range", "price coverage", "availability by budget", "budget vs coverage"
                ]
            },
        }


        # self.visualization_types = {
        #     "price_distribution": {
        #         "description": "价格分布分析",
        #         "chart_type": "histogram",
        #         "dimensions": ["price_min", "price_max", "neighbourhood_group", "room_type"],
        #         "keywords": ["price distribution", "price range", "price analysis", "价格分布", "价格区间", "价格分析"]
        #     },
        #     "location_popularity": {
        #         "description": "地区受欢迎程度分析", 
        #         "chart_type": "bar",
        #         "dimensions": ["price_min", "price_max", "neighbourhood_group", "room_type"],
        #         "keywords": ["popular area", "location popularity", "area comparison", "地区受欢迎", "热门地区"]
        #     },
        #     "room_type_comparison": {
        #         "description": "房型分布对比",
        #         "chart_type": "pie", 
        #         "dimensions": ["neighbourhood_group", "price_min", "price_max"],
        #         "keywords": ["room type", "accommodation type", "房型对比", "房间类型"]
        #     },
        #     "neighbourhood_comparison": {
        #         "description": "社区详细对比",
        #         "chart_type": "bar",
        #         "dimensions": ["neighbourhood_group", "room_type"],
        #         "keywords": ["neighbourhood comparison", "community analysis", "detailed areas", "社区对比", "社区分析", "详细地区"]
        #     },
        #     "reviews_analysis": {
        #         "description": "评论数据分析",
        #         "chart_type": "bar",
        #         "dimensions": ["neighbourhood_group", "min_reviews"],
        #         "keywords": ["reviews", "review analysis", "popular listings", "high ratings", "评论分析", "高评分"]
        #     },
        #     "price_trend": {
        #         "description": "价格趋势分析",
        #         "chart_type": "line",
        #         "dimensions": ["neighbourhood_group"],
        #         "keywords": ["price trend", "price over time", "price changes", "价格趋势", "价格变化"]
        #     },
        #     "availability_analysis": {
        #         "description": "可用性分析",
        #         "chart_type": "pie",
        #         "dimensions": ["neighbourhood_group"],
        #         "keywords": ["availability", "booking availability", "vacancy status", "可用性", "空房情况"]
        #     },
        #     "host_analysis": {
        #         "description": "房东分析",
        #         "chart_type": "scatter",
        #         "dimensions": [],
        #         "keywords": ["host analysis", "host statistics", "房东分析", "房东情况"]
        #     },
            
        #     "comments_wordcloud": {
        #         "description": "评论关键词词云",
        #         "chart_type": "wordcloud",
        #         "dimensions": ["neighbourhood_group"],
        #         "keywords": ["wordcloud", "review keywords", "词云", "评论关键词"]
        #     },
        #     "distance_price_tradeoff": {
        #         "description": "价格-距离权衡分析（可调权重α）",
        #         "chart_type": "bar",
        #         "dimensions": ["granularity", "alpha", "center", "min_listings", "room_type", "minimum_nights", "min_reviews", "price_min", "price_max", "top_k"],
        #         "keywords": [
        #             "distance", "near", "close to", "travel time", "proximity",
        #             "price vs distance", "tradeoff", "α", "alpha", "balanced",
        #             "距离", "离得近", "离中心", "就近", "权衡", "均衡", "价格 距离"
        #         ]
        #     },
        #     "value_quality_quadrant": {
        #         "description": "价值-质量象限（性价比 vs 质量指数）",
        #         "chart_type": "scatter",
        #         "dimensions": ["area", "neighbourhood_group", "neighbourhood", "room_type", "min_reviews"],
        #         "keywords": [
        #             "value vs quality", "value-quality quadrant", "bang for buck", "性价比", "质量指数", "价值 质量 象限", "划算"
        #         ]
        #     },
        #     "price_coverage_delta": {
        #         "description": "预算覆盖率增量分析 - 比较不同预算下的房源覆盖情况",
        #         "chart_type": "line",
        #         "dimensions": ["base_budget", "new_budget", "step", "neighbourhood_group", "room_type", "min_reviews", "availability_min"],
        #         "keywords": [
        #             "budget coverage", "coverage curve", "budget increase", "budget change", "budget comparison",
        #             "what if budget", "increase budget", "decrease budget", "budget impact", "coverage analysis",
        #             "budget range", "price coverage", "availability by budget", "budget vs coverage",
        #             "预算覆盖率", "预算增量", "预算变化", "预算对比", "预算影响", "覆盖率分析", "预算范围"
        #         ]
        #     },
        # }
    
    # 在smartVisualizationManager.py中调用 的函数!!!
    def recognize_visualization_intent(self, user_message: str, conversation_context: Dict = None) -> Dict:
        """
        使用LLM识别用户查询中的可视化意图
        
        Args:
            user_message: 用户消息
            conversation_context: 会话上下文，包含当前偏好、路由信息等
            
        Returns:
            Dict: 包含是否显示图表、原因、优先级和建议图表列表的字典
        """
        try:
            print(f"🔍 LLM开始识别可视化意图: {user_message[:50]}...")
            
            # 构造简化的提示词 - 不再指定JSON格式
            prompt_content = self._build_recognition_prompt(user_message, conversation_context)
            
            # 使用新的client API调用模型，并指定响应格式为JSON
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt_content,
                config={
                    "response_mime_type": "application/json",
                    "response_schema": VisualizationResponse,
                    "temperature": 0.2,
                }
            )
            
            # print(f"🔍 LLM响应状态: {response}")
            
            # 使用Pydantic解析响应
            try:
                result: VisualizationResponse = response.parsed
                print(f"✅ 成功解析JSON，找到 {len(result.visualizations)} 个可视化意图")

                # 如果LLM明确表示不需要展示可视化，则直接返回不展示
                if hasattr(result, 'should_show_visualization') and result.should_show_visualization is False:
                    print("ℹ️ LLM建议不展示可视化，直接返回不显示")
                    return {
                        "should_show": False,
                        "reason": (result.reason if getattr(result, 'reason', None) else "llm_decision_no_visualization"),
                        "priority": "none",
                        "suggested_charts": []
                    }
                
                # 验证和过滤结果
                validated_intents = self._validate_intents(result.visualizations, user_message)
                
                # 制定决策
                decision = self._make_visualization_decision(validated_intents, conversation_context)
                
                print(f"🎨 LLM可视化意图识别结果: {len(validated_intents)} 个意图")
                for intent in validated_intents:
                    print(f"  - {intent['intent']}: {intent['confidence']:.2f}")
                # 中文分数排行打印（高→低）
                try:
                    ranking = ", ".join([f"{i+1}. {vi['intent']}={vi['confidence']:.2f}" for i, vi in enumerate(validated_intents)])
                    print(f"📈 可视化图表的分数排行（高→低）: {ranking}")
                except Exception:
                    pass
                print(f"📊 最终决策: 显示={decision['should_show']}, 图表={decision['suggested_charts']}")
                
                return decision
                
            except Exception as e:
                print(f"❌ 响应解析失败: {str(e)}")
                print(f"原始响应: {response.text[:200]}...")
                return {
                    "should_show": False,
                    "reason": "parse_error",
                    "priority": "none",
                    "suggested_charts": []
                }
                
        except Exception as e:
            print(f"❌ LLM可视化意图识别失败: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                "should_show": False,
                "reason": "llm_error",
                "priority": "none",
                "suggested_charts": []
            }
    
    def _build_recognition_prompt(self, user_message: str, context: Dict = None) -> str:
        """构造简化的识别提示 - 不再指定JSON格式"""
        
        # 获取当前用户偏好信息
        current_preferences = ""
        if context and context.get('preferences'):
            prefs = context['preferences']
            pref_list = []
            for key, value in prefs.items():
                if value is not None and value != []:
                    pref_list.append(f"{key}: {value}")
            current_preferences = f"用户当前偏好: {', '.join(pref_list)}" if pref_list else "用户偏好: 未设置"
        
        # 获取对话上下文信息
        conversation_info = ""
        if context:
            stage = context.get('conversation_stage', '')
            if stage:
                conversation_info = f"当前对话阶段: {stage}\n"
            
            if context.get('route_info'):
                route_type = context.get('route_info').get('route', '')
                conversation_info += f"当前路由类型: {route_type}\n"
        
        # 构造可视化类型说明
        viz_types_desc = []
        for viz_type, config in self.visualization_types.items():
            viz_types_desc.append(f"- {viz_type}: {config['description']} (Chart type: {config['chart_type']})")
        
        viz_types_text = "\n".join(viz_types_desc)
        
        # 加强版提示词：明确禁止不必要可视化、给出判定标准与输出要求
#         prompt_old = f"""You are an intelligent visualization intent recognizer. Analyze the user's query and determine if data visualization charts are needed and which types should be recommended.

# User query: "{user_message}"
# {current_preferences}
# {conversation_info}

# Available visualization types:
# {viz_types_text}

# Decision rules (be conservative, avoid over-suggesting):
# - Only set should_show_visualization = true if at least one of the following is met:
#   1) The user explicitly asks to see a chart/visualization/plot/graph
#   2) The task clearly benefits from numeric aggregation/comparison or distribution analysis
#   3) The query references dimensions such as price, area, room type, reviews that are better answered visually
#   4) **SPECIAL CASE**: Budget change queries (e.g., "what if I increase budget to 900", "show me budget coverage curve") should suggest "price_coverage_delta"
# - Otherwise, set should_show_visualization = false and return an empty visualizations list

# When NOT to suggest visualization (set should_show_visualization = false):
# - General knowledge or travel advice (e.g., best time to visit, tips, general descriptions)
# - Purely qualitative questions without numeric aspects
# - The query lacks clear dimensions for comparison or distribution
# - The conversation stage does not suggest exploration via charts

# Special budget change detection:
# - Look for phrases like "what if", "increase budget", "decrease budget", "budget to", "coverage curve"
# - These should trigger "price_coverage_delta" with high confidence (0.8+)
# - Budget comparison queries are perfect candidates for coverage analysis

# Confidence calibration:
# - confidence should reflect the strength of evidence from the query and context
# - Use lower confidence when signals are weak or ambiguous; do NOT force a chart type
# - Budget change queries should have high confidence (0.8+) for price_coverage_delta

# Output requirements (must comply with the provided response schema):
# - Populate "visualizations" with 0–3 items from the available types only
# - If no visualization is appropriate, set should_show_visualization = false, visualizations = []
# - Provide brief reasoning in English

# IMPORTANT: Please provide your response in English only.
# """
        
#         return prompt_old
        prompt = f"""You are a strict visualization intent classifier. Decide whether to show 0–2 charts and which types from the catalog. Be conservative and avoid over-suggesting.

USER QUERY:
"{user_message}"

CURRENT PREFERENCES (may be partial):
{current_preferences}

CONVERSATION CONTEXT:
{conversation_info}

CATALOG (each item has: name, chart_type, when_to_use, requires_any, nice_to_have, hard_triggers, anti_signals, examples):
{viz_types_text}

Decision rubric (apply exactly, step-by-step in your reasoning, but only return JSON as specified by the response schema):
1) First, check SPECIAL BUDGET CHANGE. If the query mentions phrases like
   "what if", "increase budget", "decrease budget", "budget to", "coverage curve",
   then the best chart is "price_coverage_delta".
   - If required parameters for "price_coverage_delta" are missing (e.g., base_budget/new_budget), set should_show_visualization = false and reason = "missing_params".
   - Otherwise, return only "price_coverage_delta" with high priority.
2) If not a budget change request, evaluate each catalog item:
   - Strong signals:
     • hard_triggers present in the user query → strong match
     • when_to_use semantically fits the user query → strong match
   - Context fit:
     • requires_any are available in CURRENT PREFERENCES → good match
     • nice_to_have present → slight boost
   - Anti-signals:
     • If any anti_signals appear in the user query → do not select
3) Select at most 2 chart types with the strongest evidence. If evidence is weak or ambiguous, do NOT suggest any chart.
4) Confidence calibration:
   - High confidence when hard_triggers or explicit chart wording appears, or when when_to_use is a perfect semantic fit and requires_any are satisfied.
   - Medium confidence when only partial signals are present.
   - Low confidence items should be excluded entirely.

Output requirements (VERY IMPORTANT):
- Return JSON complying with the provided response schema (VisualizationResponse).
- Set should_show_visualization = true only if at least one chart type has strong evidence.
- "visualizations" list: include up to 2 items, each with intent (chart name), confidence (0–1), and a brief English reasoning.
- If no chart is appropriate, set should_show_visualization = false and visualizations = [].
- Keep reasoning concise and in English only.

IMPORTANT: Please provide your response in English only.
"""
        
        return prompt

    def _validate_intents(self, intents: List[Dict], user_message: str) -> List[Dict]:
        """验证和过滤识别出的意图"""
        validated = []
        
        for intent in intents:
            intent_obj = intent
            if hasattr(intent, 'dict'):
                # 如果是Pydantic模型，转换为字典
                intent_obj = intent.dict()
            
            intent_name = intent_obj.get('intent')
            confidence = intent_obj.get('confidence', 0.0)
            
            # 检查意图是否在支持列表中
            if intent_name not in self.visualization_types:
                print(f"⚠️ 跳过未知意图: {intent_name}")
                continue
            
            # 提高置信度阈值，避免弱匹配导致的过度可视化
            if confidence < 0.5:
                print(f"⚠️ 跳过低置信度意图: {intent_name} ({confidence:.2f})")
                continue
            
            # 添加图表配置信息
            viz_config = self.visualization_types[intent_name]
            validated_intent = {
                **intent_obj,
                'chart_type': viz_config['chart_type'],
                'dimensions': viz_config['dimensions'],
                'description': viz_config['description']
            }
            
            validated.append(validated_intent)
        
        # 按置信度排序
        validated.sort(key=lambda x: x['confidence'], reverse=True)
        
        # 最少返回2个（尽量补齐相近/互补类型）；最多返回3个
        top = validated[:3]
        if len(top) == 1:
            # 尝试补充一个互补图表
            primary = top[0]['intent']
            complement_map = {
                'price_distribution': ['location_popularity', 'room_type_comparison'],
                'location_popularity': ['price_distribution', 'room_type_comparison'],
                'room_type_comparison': ['price_distribution', 'location_popularity'],
                'price_trend': ['price_distribution', 'location_popularity'],
                'reviews_analysis': ['location_popularity', 'price_distribution'],
                'availability_analysis': ['price_distribution', 'location_popularity'],
                'host_analysis': ['price_distribution', 'reviews_analysis'],
                'neighbourhood_comparison': ['location_popularity', 'price_distribution'],
                'comments_wordcloud': ['reviews_analysis', 'location_popularity'],
                'distance_price_tradeoff': ['price_distribution', 'location_popularity'],
                'value_quality_quadrant': ['price_distribution', 'reviews_analysis'],
                'price_coverage_delta': ['price_distribution']
            }
            for cand in complement_map.get(primary, []):
                if all(i['intent'] != cand for i in top):
                    # 构造一个低置信度但可展示的补充意图（不低于0.6便于进入中优先级）
                    top.append({
                        'intent': cand,
                        'confidence': 0.65,
                        'chart_type': self.visualization_types[cand]['chart_type'],
                        'dimensions': self.visualization_types[cand]['dimensions'],
                        'description': self.visualization_types[cand]['description']
                    })
                    break
        return top[:3]
    
    def _make_visualization_decision(self, validated_intents: List[Dict], context: Dict = None) -> Dict:
        """基于识别的意图制定可视化决策"""
        if not validated_intents:
            return {
                "should_show": False,
                "reason": "no_intent_detected",
                "priority": "none",
                "suggested_charts": []
            }
        
        # 获取最高置信度的意图
        top_intent = validated_intents[0]
        confidence = top_intent['confidence']
        
        # 决定优先级
        priority = "none"
        if confidence > 0.8:
            priority = "high"
        elif confidence > 0.5:
            priority = "medium"
        elif confidence > 0.3:
            priority = "low"
        
        # 制定原因
        if priority == "high":
            reason = "explicit_request"
        elif priority == "medium":
            reason = "dimension_mention"
        elif priority == "low":
            reason = "context_appropriate"
        else:
            reason = "no_match"
        
        # 获取建议的图表类型列表
        suggested_charts = [intent['intent'] for intent in validated_intents]

        # 🎯 预算变动场景增强：确保 price_distribution 也一并建议
        # 只要包含 price_coverage_delta，就追加 price_distribution（避免重复）
        if any(i == "price_coverage_delta" for i in suggested_charts):
            if "price_distribution" not in suggested_charts:
                suggested_charts.append("price_distribution")
        
        return {
            "should_show": priority != "none",
            "reason": reason,
            "priority": priority,
            "suggested_charts": suggested_charts[:2]  # 最多2个图表
        }

# 创建全局实例供其他模块使用
llm_viz_recognizer = LLMVisualizationIntentRecognizer()


def test_visualization_intent_recognition():
    """测试可视化意图识别功能 - 使用英文输入"""
    import json
    import time
    import sys
    import os
    from langchain_core.messages import HumanMessage, SystemMessage
    
    print("🧪 开始测试可视化意图识别器...")
    
    try:
        # 更彻底的导入路径修复
        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)
        project_root = os.path.dirname(current_dir)
        
        print(f"当前文件路径: {current_file}")
        print(f"当前目录: {current_dir}")
        print(f"项目根目录: {project_root}")
        
        # 确保项目根目录在sys.path中
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            print(f"已添加项目根目录到sys.path: {project_root}")
        
        # 尝试直接导入
        try:
            import load_llm
            print("✅ 成功导入load_llm")
        except ImportError as e:
            print(f"❌ 导入load_llm失败: {e}")
        
        # 使用全局实例
        recognizer = llm_viz_recognizer
        
        # 英文测试用例 - 更丰富的场景
        test_queries = [
            # 明确的可视化请求
            "I want to see the price distribution in different Berlin districts",
            "Can you show me a comparison of different room types?",
            "Show me a chart of review analysis for top neighborhoods",
            "I'd like to see trends in prices over time in Berlin",
            
            # 隐含的可视化需求
            "Which districts have the most affordable apartments?",
            "What's the distribution of entire homes vs private rooms?",
            "How do reviews vary across different areas?",
            
            # 模糊或边缘情况
            "Tell me about popular areas in Berlin",
            "What should I know about accommodation in Mitte?",
            
            # 完全非可视化的请求
            "What's the best time to visit Berlin?"
        ]
        
        # 模拟对话上下文
        mock_context = {
            "preferences": {
                "price_min": 50,
                "price_max": 150,
                "neighbourhood_group": "Mitte"
            },
            "conversation_stage": "exploration",
            "route_info": {"route": "conversational"}
        }
        
        # 测试意图识别
        print("\n🔍 测试意图识别流程...")
        
        results = []
        for i, query in enumerate(test_queries):
            print(f"\n测试查询 {i+1}: '{query}'")
            
            start_time = time.time()
            
            try:
                decision = recognizer.recognize_visualization_intent(query, mock_context)
                end_time = time.time()
                
                print(f"⏱️ 处理时间: {end_time - start_time:.2f}秒")
                print(f"📊 识别结果:")
                print(f"  显示图表: {decision['should_show']}")
                print(f"  优先级: {decision['priority']}")
                print(f"  原因: {decision['reason']}")
                print(f"  建议图表: {decision['suggested_charts']}")
                
                # 检查是否有特定类型的图表建议
                if decision['should_show']:
                    chart_types = []
                    for chart in decision['suggested_charts']:
                        if chart in recognizer.visualization_types:
                            chart_info = recognizer.visualization_types[chart]
                            chart_types.append(f"{chart} ({chart_info['chart_type']})")
                    
                    if chart_types:
                        print(f"  🎨 具体图表类型: {', '.join(chart_types)}")
                
                results.append({
                    "query": query,
                    "decision": decision,
                    "success": True
                })
                
            except Exception as e:
                print(f"❌ 识别失败: {str(e)}")
                import traceback
                traceback.print_exc()
                
                results.append({
                    "query": query,
                    "error": str(e),
                    "success": False
                })
        
        # 结果统计分析
        successful = len([r for r in results if r["success"]])
        positive_viz = len([r for r in results if r["success"] and r["decision"]["should_show"]])
        negative_viz = len([r for r in results if r["success"] and not r["decision"]["should_show"]])
        
        print(f"\n🏁 测试完成统计:")
        print(f"  总测试用例: {len(test_queries)}")
        print(f"  成功处理: {successful}")
        print(f"  识别为需要可视化: {positive_viz}")
        print(f"  识别为不需要可视化: {negative_viz}")
        print(f"  处理失败: {len(test_queries) - successful}")
        
        # 分析各类图表的推荐频率
        if positive_viz > 0:
            chart_counts = {}
            for r in results:
                if r["success"] and r["decision"]["should_show"]:
                    for chart in r["decision"]["suggested_charts"]:
                        chart_counts[chart] = chart_counts.get(chart, 0) + 1
            
            print("\n📈 图表推荐统计:")
            for chart, count in sorted(chart_counts.items(), key=lambda x: x[1], reverse=True):
                if chart in recognizer.visualization_types:
                    chart_info = recognizer.visualization_types[chart]
                    print(f"  {chart} ({chart_info['chart_type']}): {count}次")
                else:
                    print(f"  {chart}: {count}次")
        
        return results
        
    except Exception as e:
        print(f"❌ 测试过程中出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# 如果直接运行
if __name__ == "__main__":
    test_visualization_intent_recognition()