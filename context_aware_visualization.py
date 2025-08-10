# context_aware_visualization.py
"""
基于追问上下文的智能可视化系统
根据当前追问的维度智能显示相关图表
"""

from typing import Dict, List, Optional
from visualization_enhancer import VisualizationEnhancer

class ContextAwareVisualizationManager:
    """
    上下文感知的可视化管理器
    根据追问上下文智能选择合适的图表类型
    """
    
    def __init__(self):
        self.viz_enhancer = VisualizationEnhancer()
        
        # 🎯 追问维度到图表类型的精确映射
        self.followup_dimension_chart_mapping = {
            "budget": ["price_distribution"],           # 询问预算 → 价格分布图
            "price_range": ["price_distribution"],      # 询问价格范围 → 价格分布图
            "location": ["location_popularity"],        # 询问地区 → 地区受欢迎程度图
            "area": ["location_popularity"],            # 询问区域 → 地区受欢迎程度图
            "neighbourhood": ["neighbourhood_comparison"], # 询问社区 → 社区对比图
            "room_type": ["room_type_comparison"],      # 询问房型 → 房型对比图
            "stay_duration": ["availability_analysis"], # 询问住宿时长 → 可用性分析
            "popularity": ["review_analysis"],          # 询问受欢迎程度 → 评论分析
            "amenities": ["location_popularity"],       # 询问设施 → 地区对比（看哪些地区设施好）
            "transport": ["location_popularity"]        # 询问交通 → 地区对比（看交通便利性）
        }
        
        # 🎯 追问阶段到图表类型的映射
        self.stage_chart_mapping = {
            "preference_collection": {
                "default": ["price_distribution"],      # 收集偏好阶段默认显示价格分布
                "after_budget": ["location_popularity"], # 设置预算后显示地区对比
                "after_location": ["room_type_comparison"] # 设置地区后显示房型对比
            },
            "information_seeking": {
                "default": ["price_distribution", "location_popularity"]
            },
            "recommendation_ready": {
                "default": ["price_trend", "room_type_comparison"]
            }
        }
    
    def get_contextual_visualizations(self, 
                                    followup_info: Dict, 
                                    user_preferences: Dict,
                                    user_message: str = "",
                                    conversation_stage: str = "preference_collection") -> Dict:
        """
        根据追问上下文获取相关的可视化
        
        Args:
            followup_info: 追问信息，包含target_dimensions等
            user_preferences: 用户偏好
            user_message: 用户消息
            conversation_stage: 对话阶段
            
        Returns:
            可视化数据字典
        """
        try:
            print(f"🎯 开始上下文感知可视化分析...")
            print(f"   追问信息: {followup_info}")
            print(f"   对话阶段: {conversation_stage}")
            print(f"   用户消息: {user_message[:50]}...")
            
            # 🎯 第一步：从追问信息中提取目标维度
            target_dimensions = followup_info.get("target_dimensions", [])
            followup_strategy = followup_info.get("strategy", "basic_collection")
            
            print(f"   目标维度: {target_dimensions}")
            print(f"   追问策略: {followup_strategy}")
            
            # 🎯 第二步：根据目标维度选择图表类型
            suggested_charts = self._get_charts_for_dimensions(target_dimensions)
            
            # 🎯 第三步：如果没有明确的维度，根据对话阶段和已有偏好推荐
            if not suggested_charts:
                suggested_charts = self._get_charts_for_stage(conversation_stage, user_preferences)
            
            # 🎯 第四步：根据用户消息进行补充调整
            message_charts = self._get_charts_from_message(user_message)
            if message_charts:
                # 优先使用消息中的意图，但与维度相关的图表优先级更高
                suggested_charts = list(set(suggested_charts + message_charts))
            
            print(f"   建议图表: {suggested_charts}")
            
            # 🎯 第五步：生成实际的图表数据
            if suggested_charts:
                return self._generate_contextual_charts(
                    suggested_charts[:2],  # 最多2个图表
                    user_preferences,
                    target_dimensions,
                    followup_info
                )
            else:
                return {"has_charts": False, "reason": "no_suitable_charts"}
                
        except Exception as e:
            print(f"❌ 上下文感知可视化分析失败: {e}")
            import traceback
            traceback.print_exc()
            return {"has_charts": False, "error": str(e)}
    
    def _get_charts_for_dimensions(self, target_dimensions: List[str]) -> List[str]:
        """根据目标维度获取相关图表"""
        charts = []
        
        for dimension in target_dimensions:
            dimension_lower = dimension.lower()
            
            # 🎯 精确匹配维度到图表的映射
            for key, chart_types in self.followup_dimension_chart_mapping.items():
                if key in dimension_lower or dimension_lower in key:
                    charts.extend(chart_types)
                    print(f"   ✅ 维度 '{dimension}' 匹配到图表: {chart_types}")
        
        return list(set(charts))  # 去重
    
    def _get_charts_for_stage(self, stage: str, preferences: Dict) -> List[str]:
        """根据对话阶段获取相关图表"""
        stage_mapping = self.stage_chart_mapping.get(stage, {})
        
        # 🎯 根据已有偏好判断用户处于哪个子阶段
        if stage == "preference_collection":
            if preferences.get("price_min") or preferences.get("price_max"):
                # 已设置预算，推荐地区图表
                return stage_mapping.get("after_budget", stage_mapping.get("default", []))
            elif preferences.get("neighbourhood_group") or preferences.get("neighbourhood"):
                # 已设置地区，推荐房型图表
                return stage_mapping.get("after_location", stage_mapping.get("default", []))
            else:
                # 默认推荐价格图表
                return stage_mapping.get("default", [])
        
        return stage_mapping.get("default", [])
    
    def _get_charts_from_message(self, user_message: str) -> List[str]:
        """从用户消息中提取图表需求"""
        if not user_message:
            return []
        
        message_lower = user_message.lower()
        suggested_charts = []
        
        # 🎯 关键词到图表的映射
        keyword_mappings = {
            "price": ["price_distribution"],
            "budget": ["price_distribution"],
            "cost": ["price_distribution"],
            "area": ["location_popularity"],
            "location": ["location_popularity"],
            "neighborhood": ["location_popularity"],
            "room": ["room_type_comparison"],
            "apartment": ["room_type_comparison"],
            "type": ["room_type_comparison"],
            "popular": ["review_analysis"],
            "review": ["review_analysis"],
            "trend": ["price_trend"]
        }
        
        for keyword, charts in keyword_mappings.items():
            if keyword in message_lower:
                suggested_charts.extend(charts)
        
        return list(set(suggested_charts))
    
    def _generate_contextual_charts(self, 
                                  chart_types: List[str], 
                                  user_preferences: Dict,
                                  target_dimensions: List[str],
                                  followup_info: Dict) -> Dict:
        """生成上下文相关的图表数据"""
        enhanced_visualizations = {}
        chart_suggestions = []
        
        for chart_type in chart_types:
            print(f"📊 生成上下文图表: {chart_type}")
            
            # 使用可视化增强器生成图表数据
            chart_data = self.viz_enhancer.chart_generator.generate_chart_data(
                chart_type, 
                user_preferences
            )
            
            if chart_data and chart_data.get('success', True):
                # 添加预算高亮
                user_budget = self.viz_enhancer._extract_user_budget(user_preferences)
                enhanced_chart = self.viz_enhancer._enhance_chart_with_budget_highlight(
                    chart_data, 
                    chart_type, 
                    user_budget, 
                    user_preferences
                )
                
                # 🎯 添加上下文相关的描述
                contextual_description = self._generate_contextual_description(
                    chart_type, target_dimensions, followup_info
                )
                enhanced_chart["contextual_info"] = contextual_description
                
                enhanced_visualizations[chart_type] = enhanced_chart
                
                # 生成建议
                suggestion = {
                    "chart_type": chart_type,
                    "title": enhanced_chart.get('chart_config', {}).get('title', chart_type),
                    "description": contextual_description["title"],
                    "context_relevance": contextual_description["relevance_score"],
                    "confidence": 0.8  # 上下文匹配的置信度较高
                }
                chart_suggestions.append(suggestion)
                
                print(f"✅ 上下文图表 {chart_type} 生成成功")
            else:
                print(f"⚠️ 上下文图表 {chart_type} 生成失败")
        
        return {
            "enhanced_visualizations": enhanced_visualizations,
            "chart_suggestions": chart_suggestions,
            "has_charts": len(enhanced_visualizations) > 0,
            "context_type": "followup_dimension_based"
        }
    
    def _generate_contextual_description(self, 
                                       chart_type: str, 
                                       target_dimensions: List[str], 
                                       followup_info: Dict) -> Dict:
        """生成上下文相关的图表描述"""
        
        # 🎯 根据图表类型和目标维度生成描述
        descriptions = {
            "price_distribution": {
                "budget": {
                    "title": "价格分布分析 - 帮助您了解预算选择",
                    "description": "这个图表显示了不同价格区间的房源分布，帮助您选择合适的预算范围",
                    "relevance_score": 0.9
                },
                "default": {
                    "title": "价格分布概览",
                    "description": "查看不同价格区间的房源分布情况",
                    "relevance_score": 0.7
                }
            },
            "location_popularity": {
                "location": {
                    "title": "地区受欢迎程度对比 - 帮助您选择理想区域",
                    "description": "这个图表显示了各地区的房源数量和受欢迎程度，帮助您做出位置选择",
                    "relevance_score": 0.9
                },
                "area": {
                    "title": "各区域对比分析",
                    "description": "比较不同区域的房源情况和特点",
                    "relevance_score": 0.9
                },
                "default": {
                    "title": "地区热门度分析",
                    "description": "查看各地区的房源分布和受欢迎程度",
                    "relevance_score": 0.7
                }
            },
            "room_type_comparison": {
                "room_type": {
                    "title": "房型对比分析 - 帮助您选择合适的住宿类型",
                    "description": "这个图表显示了不同房型的占比和价格对比，帮助您选择适合的房间类型",
                    "relevance_score": 0.9
                },
                "default": {
                    "title": "房型分布对比",
                    "description": "查看不同房型的分布情况和价格对比",
                    "relevance_score": 0.7
                }
            }
        }
        
        chart_desc = descriptions.get(chart_type, {})
        
        # 🎯 根据目标维度选择最相关的描述
        for dimension in target_dimensions:
            dimension_lower = dimension.lower()
            for key in chart_desc.keys():
                if key in dimension_lower or dimension_lower in key:
                    return chart_desc[key]
        
        # 返回默认描述
        return chart_desc.get("default", {
            "title": f"{chart_type} 分析",
            "description": f"查看 {chart_type} 相关数据",
            "relevance_score": 0.5
        })

# ===== 全局实例 =====
context_aware_viz_manager = ContextAwareVisualizationManager()

# ===== 集成到路由的便捷函数 =====

def get_followup_contextual_visualizations(followup_info: Dict, 
                                         user_preferences: Dict,
                                         user_message: str = "",
                                         conversation_stage: str = "preference_collection") -> Dict:
    """
    便捷函数：获取基于追问上下文的可视化
    
    Args:
        followup_info: 追问信息
        user_preferences: 用户偏好  
        user_message: 用户消息
        conversation_stage: 对话阶段
        
    Returns:
        可视化数据字典
    """
    return context_aware_viz_manager.get_contextual_visualizations(
        followup_info, user_preferences, user_message, conversation_stage
    )

def should_show_contextual_visualization(followup_info: Dict, user_preferences: Dict) -> bool:
    """
    判断是否应该显示上下文相关的可视化
    
    Args:
        followup_info: 追问信息
        user_preferences: 用户偏好
        
    Returns:
        是否应该显示可视化
    """
    # 🎯 如果有明确的追问目标维度，应该显示相关可视化
    target_dimensions = followup_info.get("target_dimensions", [])
    if target_dimensions:
        return True
    
    # 🎯 如果用户已经有一些偏好，可以显示相关可视化
    if user_preferences and any(user_preferences.values()):
        return True
    
    return False

# ===== 测试函数 =====

def test_contextual_visualization():
    """测试上下文感知可视化功能"""
    print("🧪 测试上下文感知可视化功能")
    print("=" * 60)
    
    test_cases = [
        {
            "name": "询问预算时的可视化",
            "followup_info": {
                "target_dimensions": ["budget"],
                "strategy": "targeted_followup",
                "question": "What's your budget range per night?"
            },
            "user_preferences": {"minimum_nights": 3},
            "user_message": "I will go to Berlin for a conference, about 3 days",
            "expected_charts": ["price_distribution"]
        },
        {
            "name": "询问地区时的可视化", 
            "followup_info": {
                "target_dimensions": ["location"],
                "strategy": "targeted_followup",
                "question": "Which area of Berlin would you prefer?"
            },
            "user_preferences": {"price_min": 80, "price_max": 150},
            "user_message": "I prefer somewhere central",
            "expected_charts": ["location_popularity"]
        },
        {
            "name": "询问房型时的可视化",
            "followup_info": {
                "target_dimensions": ["room_type"],
                "strategy": "targeted_followup", 
                "question": "Would you like a private room or entire place?"
            },
            "user_preferences": {"price_max": 200, "neighbourhood_group": "Mitte"},
            "user_message": "I need a private space",
            "expected_charts": ["room_type_comparison"]
        }
    ]
    
    manager = context_aware_viz_manager
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {case['name']}")
        print(f"追问维度: {case['followup_info']['target_dimensions']}")
        
        result = manager.get_contextual_visualizations(
            case["followup_info"],
            case["user_preferences"], 
            case["user_message"]
        )
        
        print(f"生成图表: {list(result.get('enhanced_visualizations', {}).keys())}")
        print(f"期望图表: {case['expected_charts']}")
        print(f"是否成功: {result.get('has_charts', False)}")
        
        if result.get("has_charts"):
            for chart_type, chart_data in result["enhanced_visualizations"].items():
                contextual_info = chart_data.get("contextual_info", {})
                print(f"  - {chart_type}: {contextual_info.get('title', 'N/A')}")

if __name__ == "__main__":
    test_contextual_visualization()