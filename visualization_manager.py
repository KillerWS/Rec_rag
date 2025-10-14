# visualization_manager.py
"""
可视化管理模块 - 统一管理可视化意图识别和数据生成
整合原有的 visualization_intent_recognizer.py 和新的 chart_data_generator.py
"""

from typing import Dict, List, Optional, Tuple
from llm_pipeline.visualization_intent_recognizer import VisualizationIntentRecognizer  # 🔑 使用你原有的模块
from chart_data_generator import ChartDataGenerator  # 🔑 使用新的数据生成模块

class VisualizationManager:
    """
    可视化管理器 - 统一协调意图识别和数据生成
    """
    
    def __init__(self):
        # 🔑 整合原有模块和新模块
        self.intent_recognizer = VisualizationIntentRecognizer()  # 你原有的意图识别
        self.chart_generator = ChartDataGenerator()              # 新的数据生成器
        
        # 🎯 定义关键词触发规则 - 补充LLM意图识别
        self.keyword_rules = {
            "price_keywords": {
                "keywords": ["价格", "price", "多少钱", "费用", "cost", "expensive", "cheap", "分布"],
                "suggested_charts": ["price_distribution"],
                "confidence": 0.6
            },
            "location_keywords": {
                "keywords": ["地区", "area", "neighbourhood", "location", "哪里", "where", "popular", "热门"],
                "suggested_charts": ["location_popularity"],
                "confidence": 0.6
            },
            "room_type_keywords": {
                "keywords": ["房型", "room type", "房间", "类型", "整套", "private", "shared"],
                "suggested_charts": ["room_type_comparison"],
                "confidence": 0.6
            },
            "comparison_keywords": {
                "keywords": ["对比", "比较", "compare", "difference", "哪个更好", "选择"],
                "suggested_charts": ["location_popularity", "room_type_comparison"],
                "confidence": 0.5
            },
            "analysis_keywords": {
                "keywords": ["分析", "analysis", "趋势", "trend", "统计", "数据", "distribution", "图表", "chart"],
                "suggested_charts": ["price_distribution", "location_popularity"],
                "confidence": 0.5
            }
        }
    
    def should_trigger_visualization(self, 
                                   user_message: str, 
                                   conversation_context: Dict,
                                   user_preferences: Dict) -> Tuple[bool, List[str], float]:
        """
        判断是否应该触发可视化建议
        
        Returns:
            (should_trigger: bool, suggested_charts: List[str], max_confidence: float)
        """
        try:
            print(f"🔍 分析可视化需求: {user_message[:50]}...")
            
            # 🎯 第一步：使用原有的LLM意图识别
            llm_intents = self.intent_recognizer.recognize_visualization_intent(
                user_message, conversation_context
            )
            
            # 🎯 第二步：关键词规则匹配（作为补充）
            keyword_suggestions = self._check_keyword_rules(user_message)
            
            # 🎯 第三步：综合决策
            final_decision = self._make_decision(llm_intents, keyword_suggestions, user_preferences)
            
            print(f"🎨 可视化分析结果:")
            print(f"   LLM意图: {len(llm_intents)} 个")
            print(f"   关键词匹配: {len(keyword_suggestions)} 个") 
            print(f"   最终决策: {final_decision}")
            
            return final_decision
            
        except Exception as e:
            print(f"❌ 可视化触发判断失败: {e}")
            return False, [], 0.0
    
    def generate_visualization_response(self, 
                                      suggested_charts: List[str],
                                      user_preferences: Dict,
                                      context: Dict = None) -> Dict:
        """
        生成包含可视化数据的响应
        """
        try:
            print(f"📊 开始生成 {len(suggested_charts)} 个图表...")
            
            visualization_data = {}
            chart_suggestions = []
            
            # 🎯 为每个建议的图表生成数据
            for chart_type in suggested_charts[:3]:  # 限制最多3个图表
                print(f"🎨 生成图表: {chart_type}")
                
                chart_data = self.chart_generator.generate_chart_data(
                    chart_type, 
                    user_preferences, 
                    context
                )
                
                if chart_data and chart_data.get("success", True):
                    visualization_data[chart_type] = chart_data
                    chart_suggestions.append({
                        "chart_type": chart_type,
                        "title": chart_data.get("chart_config", {}).get("title", chart_type),
                        "description": self._get_chart_description(chart_type, chart_data.get("metadata", {}))
                    })
                    print(f"✅ 图表 {chart_type} 生成成功")
                else:
                    print(f"⚠️ 图表 {chart_type} 生成失败")
            
            # 🎯 生成建议消息
            suggestion_message = self._generate_suggestion_message(list(visualization_data.keys()))
            
            result = {
                "has_visualizations": len(visualization_data) > 0,
                "visualization_data": visualization_data,
                "chart_suggestions": chart_suggestions,
                "suggested_message": suggestion_message,
                "chart_count": len(visualization_data)
            }
            
            print(f"📊 可视化响应生成完成: {len(visualization_data)} 个图表")
            return result
            
        except Exception as e:
            print(f"❌ 生成可视化响应失败: {e}")
            return {
                "has_visualizations": False,
                "error": str(e)
            }
    
    def _check_keyword_rules(self, user_message: str) -> List[str]:
        """基于关键词规则检查是否应该触发图表"""
        suggested_charts = []
        message_lower = user_message.lower()
        
        for rule_name, rule_config in self.keyword_rules.items():
            # 检查是否包含关键词
            if any(keyword.lower() in message_lower for keyword in rule_config["keywords"]):
                print(f"🔍 触发关键词规则: {rule_name}")
                suggested_charts.extend(rule_config["suggested_charts"])
        
        # 去重并保持顺序
        return list(dict.fromkeys(suggested_charts))
    
    def _make_decision(self, 
                      llm_intents: List[Dict], 
                      keyword_suggestions: List[str], 
                      user_preferences: Dict) -> Tuple[bool, List[str], float]:
        """综合LLM意图和关键词建议做出最终决策"""
        
        all_suggestions = []
        max_confidence = 0.0
        
        # 🎯 LLM意图中的高置信度建议
        for intent in llm_intents:
            confidence = intent.get("confidence", 0)
            if confidence > 0.4:  # 降低阈值，让更多意图通过
                all_suggestions.append(intent["intent"])
                max_confidence = max(max_confidence, confidence)
                print(f"   ✅ LLM意图: {intent['intent']} (置信度: {confidence:.2f})")
        
        # 🎯 关键词匹配的建议
        if keyword_suggestions:
            all_suggestions.extend(keyword_suggestions)
            max_confidence = max(max_confidence, 0.6)  # 关键词匹配给予中等置信度
            print(f"   ✅ 关键词建议: {keyword_suggestions}")
        
        # 🎯 基于用户偏好的兜底建议
        if not all_suggestions and user_preferences and any(user_preferences.values()):
            # 如果用户有偏好但没有触发其他规则，提供基础图表
            all_suggestions = ["price_distribution"]
            max_confidence = 0.3
            print(f"   ✅ 兜底建议: price_distribution")
        
        # 去重并保持顺序
        final_suggestions = list(dict.fromkeys(all_suggestions))
        
        # 🎯 决策逻辑
        should_trigger = len(final_suggestions) > 0 and (
            max_confidence > 0.3 or  # 有一定置信度
            len(keyword_suggestions) > 0  # 或者有关键词匹配
        )
        
        print(f"🎯 最终决策: 触发={should_trigger}, 图表={final_suggestions}, 置信度={max_confidence:.2f}")
        
        return should_trigger, final_suggestions[:3], max_confidence
    
    def _get_chart_description(self, chart_type: str, metadata: Dict) -> str:
        """获取图表描述"""
        descriptions = {
            "price_distribution": f"显示价格分布情况，帮助了解不同价格区间的房源数量",
            "location_popularity": f"展示各地区受欢迎程度，帮助选择合适的居住区域", 
            "room_type_comparison": f"对比不同房型分布，了解各类型房源的占比情况",
            "neighbourhood_comparison": f"具体社区对比分析，帮助选择最适合的社区",
            "reviews_analysis": "评论数据分析，了解房源受欢迎程度和质量",
            "price_trend": "价格趋势分析，帮助了解市场行情变化",
            "availability_analysis": "房源可用性分析，了解预订难易程度",
            "host_analysis": "房东分析，了解房东经营模式和服务质量"
        }
        
        base_desc = descriptions.get(chart_type, f"{chart_type} 数据分析")
        
        # 如果有元数据，添加具体数字
        if metadata.get("total_records"):
            base_desc += f"，基于 {metadata['total_records']} 条数据"
        
        return base_desc
    
    def _generate_suggestion_message(self, chart_types: List[str]) -> str:
        """生成建议消息"""
        if not chart_types:
            return ""
        
        chart_names = {
            "price_distribution": "价格分布图",
            "location_popularity": "地区受欢迎度图", 
            "room_type_comparison": "房型对比图",
            "neighbourhood_comparison": "社区对比图",
            "reviews_analysis": "评论分析图",
            "price_trend": "价格趋势图",
            "availability_analysis": "可用性分析图",
            "host_analysis": "房东分析图"
        }
        
        names = [chart_names.get(ct, ct) for ct in chart_types]
        
        if len(names) == 1:
            return f"📊 我可以为您展示{names[0]}，帮助您更好地了解相关信息。"
        elif len(names) == 2:
            return f"📊 我可以为您展示{names[0]}和{names[1]}，让您更全面地了解情况。"
        else:
            return f"📊 我可以为您展示{names[0]}、{names[1]}等{len(names)}个图表，帮您深入分析数据。"


# ===== 🔑 关键的集成函数 - 在 routes.py 中使用 =====

def integrate_visualization_to_existing_response(response: Dict, 
                                                visualization_manager: VisualizationManager,
                                                user_message: str,
                                                conversation_context: Dict,
                                                user_preferences: Dict) -> Dict:
    """
    将可视化功能集成到现有响应中
    这是在 routes.py 中调用的主要函数
    
    Args:
        response: 现有的响应字典
        visualization_manager: 可视化管理器实例
        user_message: 用户消息
        conversation_context: 对话上下文
        user_preferences: 用户偏好
        
    Returns:
        增强后的响应字典
    """
    try:
        print("🎨 开始集成可视化功能...")
        
        # 🎯 判断是否应该触发可视化
        should_trigger, suggested_charts, confidence = visualization_manager.should_trigger_visualization(
            user_message, conversation_context, user_preferences
        )
        
        if should_trigger and suggested_charts:
            print(f"🎨 触发可视化建议: {suggested_charts} (置信度: {confidence:.2f})")
            
            # 🎯 生成可视化数据
            viz_response = visualization_manager.generate_visualization_response(
                suggested_charts, user_preferences, conversation_context
            )
            
            # 🎯 增强原有响应
            if viz_response.get("has_visualizations"):
                response.update({
                    "visualizations": viz_response["visualization_data"],
                    "chart_suggestions": viz_response["chart_suggestions"], 
                    "visualization_message": viz_response["suggested_message"],
                    "show_visualization_prompt": True,
                    "visualization_confidence": confidence
                })
                
                print(f"✅ 已添加 {viz_response['chart_count']} 个图表建议到响应")
            else:
                print("⚠️ 可视化数据生成失败")
                response["show_visualization_prompt"] = False
        else:
            print("ℹ️ 未触发可视化建议")
            response["show_visualization_prompt"] = False
        
        return response
        
    except Exception as e:
        print(f"❌ 集成可视化功能失败: {e}")
        response["show_visualization_prompt"] = False
        response["visualization_error"] = str(e)
        return response


# ===== 🧪 测试函数 =====

def test_visualization_manager():
    """测试可视化管理器"""
    manager = VisualizationManager()
    
    # 测试场景
    test_cases = [
        {
            "name": "价格询问",
            "message": "我想了解不同价格区间的房源分布情况",
            "context": {"stage": "preference_collection"},
            "preferences": {"price_min": 50, "price_max": 200}
        },
        {
            "name": "地区对比",
            "message": "哪个地区最受欢迎？",
            "context": {"stage": "information_seeking"},
            "preferences": {"neighbourhood_group": "Mitte"}
        },
        {
            "name": "一般聊天",
            "message": "你好，我想了解柏林住宿",
            "context": {"stage": "greeting"},
            "preferences": {}
        }
    ]
    
    print("🧪 测试可视化管理器")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {test_case['name']}")
        print(f"消息: {test_case['message']}")
        
        should_trigger, suggested_charts, confidence = manager.should_trigger_visualization(
            test_case["message"],
            test_case["context"],
            test_case["preferences"]
        )
        
        print(f"结果: 触发={should_trigger}, 图表={suggested_charts}, 置信度={confidence:.2f}")


if __name__ == "__main__":
    print("🚀 可视化管理器模块加载完成")
    
    # 运行测试
    test_visualization_manager()