# visualization_enhancer.py
"""
可视化增强模块 - 支持预算高亮和个性化图表生成
"""

import pandas as pd
from typing import Dict, List, Any, Optional
from chart_data_generator import ChartDataGenerator

class VisualizationEnhancer:
    """
    可视化增强器 - 为图表添加预算高亮、文字说明等增强功能
    """
    
    def __init__(self):
        self.chart_generator = ChartDataGenerator()
        
        # 🎯 关键词到图表类型的映射
        self.keyword_chart_mapping = {
            "price": ["price_distribution", "price_trend"],
            "location": ["location_popularity", "neighbourhood_comparison"],
            "room type": ["room_type_comparison"],
            "review": ["review_analysis"],
            "availability": ["availability_analysis"],
            "host": ["host_analysis"],
            "distribution": ["price_distribution", "room_type_comparison"],
            "comparison": ["location_popularity", "room_type_comparison", "neighbourhood_comparison"],
            "trend": ["price_trend"],
            "analysis": ["review_analysis", "availability_analysis", "host_analysis"]
        }
    
    def enhance_visualization_with_charts(self, visualization_intents: List[Dict], user_preferences: Dict, context: Optional[Dict] = None) -> Dict:
        """
        增强可视化意图，生成实际的图表数据（支持预算高亮和上下文感知）
        
        Args:
            visualization_intents: 原有的可视化意图列表
            user_preferences: 用户偏好
            context: 上下文信息，包含当前追问维度、路由信息等
            
        Returns:
            增强后的可视化数据
        """
        try:
            print("🎨 Starting to enhance visualization data...")
            
            enhanced_visualizations = {}
            chart_suggestions = []
            
            # 🎯 提取用户预算信息
            user_budget = self._extract_user_budget(user_preferences)
            print(f"💰 User budget: {user_budget}")
            
            # 🎯 NEW: 检查上下文，确定是否需要上下文驱动的图表
            context_driven_charts = self._get_context_driven_charts(context, user_preferences)
            if context_driven_charts:
                print(f"🎯 Context-driven charts: {context_driven_charts}")
            
            # 🎯 基于意图生成实际图表数据
            for intent in visualization_intents:
                if intent.get('confidence', 0) > 0.4:  # 只处理高置信度的意图
                    chart_type = intent.get('intent')
                    if chart_type:
                        print(f"📊 Generating chart: {chart_type}")
                        
                        # 使用图表生成器创建数据
                        chart_data = self.chart_generator.generate_chart_data(
                            chart_type, 
                            user_preferences
                        )
                        
                        if chart_data and chart_data.get('success', True):
                            # 🎯 为图表添加预算高亮和文字说明
                            enhanced_chart_data = self._enhance_chart_with_budget_highlight(
                                chart_data, 
                                chart_type, 
                                user_budget, 
                                user_preferences
                            )
                            
                            enhanced_visualizations[chart_type] = enhanced_chart_data
                            
                            # 🎯 生成个性化的图表建议
                            suggestion = self._create_personalized_chart_suggestion(
                                chart_type, 
                                enhanced_chart_data, 
                                user_budget, 
                                intent
                            )
                            chart_suggestions.append(suggestion)
                            
                            print(f"✅ Chart {chart_type} generated successfully (with budget highlight)")
                        else:
                            print(f"⚠️ Chart {chart_type} generation failed")
            
            # 🎯 如果原有意图识别没有结果，基于关键词生成兜底图表
            if not enhanced_visualizations and user_preferences:
                print("🔍 No results from intent recognition, trying keyword matching...")
                
                # 🎯 优先使用上下文驱动的图表
                charts_to_try = context_driven_charts if context_driven_charts else self._get_fallback_charts_by_keywords(user_preferences)
                
                for chart_type in charts_to_try:
                    chart_data = self.chart_generator.generate_chart_data(chart_type, user_preferences)
                    if chart_data and chart_data.get('success', True):
                        # 同样添加预算高亮
                        enhanced_chart_data = self._enhance_chart_with_budget_highlight(
                            chart_data, 
                            chart_type, 
                            user_budget, 
                            user_preferences
                        )
                        
                        enhanced_visualizations[chart_type] = enhanced_chart_data
                        
                        # 🎯 根据是否为上下文驱动生成不同的描述
                        description = self._get_context_aware_description(chart_type, context) if context_driven_charts else f"Recommended {chart_type} analysis based on your preferences"
                        
                        suggestion = self._create_personalized_chart_suggestion(
                            chart_type, 
                            enhanced_chart_data, 
                            user_budget, 
                            {"description": description}
                        )
                        chart_suggestions.append(suggestion)
                        break  # 只生成一个兜底图表
            
            result = {
                "enhanced_visualizations": enhanced_visualizations,
                "chart_suggestions": chart_suggestions,
                "has_charts": len(enhanced_visualizations) > 0,
                "user_budget_info": user_budget  # 🎯 返回预算信息
            }
            
            print(f"🎨 Visualization enhancement completed: Generated {len(enhanced_visualizations)} charts")
            return result
            
        except Exception as e:
            print(f"❌ Visualization enhancement failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                "enhanced_visualizations": {},
                "chart_suggestions": [],
                "has_charts": False,
                "error": str(e)
            }
    
    def check_message_for_chart_keywords(self, user_message: str) -> List[str]:
        """
        检查用户消息中的图表关键词
        
        Args:
            user_message: 用户消息
            
        Returns:
            建议的图表类型列表
        """
        message_lower = user_message.lower()
        suggested_charts = []
        
        for keyword, chart_types in self.keyword_chart_mapping.items():
            if keyword in message_lower:
                suggested_charts.extend(chart_types)
        
        # 去重并返回
        return list(set(suggested_charts))
    
    def _get_context_driven_charts(self, context: Optional[Dict], user_preferences: Dict) -> List[str]:
        """🎯 根据上下文（如当前追问维度）生成相关图表"""
        if not context:
            return []
        
        context_charts = []
        
        # 🎯 从追问信息中获取目标维度
        followup_info = context.get('followup_info', {})
        if followup_info:
            followup_question = followup_info.get('followup_question', {})
            target_dimensions = followup_question.get('target_dimensions', [])
            
            print(f"🎯 Current follow-up target dimensions: {target_dimensions}")
            
            # 🎯 根据追问维度映射到相关图表
            dimension_chart_mapping = {
                "budget": ["price_distribution", "price_trend"],
                "location": ["location_popularity", "neighbourhood_comparison"], 
                "room_type": ["room_type_comparison"],
                "stay_duration": ["availability_analysis"],
                "popularity": ["review_analysis"],
                "amenities_focus": ["room_type_comparison"],  # 设施通常与房型相关
                "location_convenience": ["location_popularity", "neighbourhood_comparison"]
            }
            
            for dimension in target_dimensions:
                if dimension in dimension_chart_mapping:
                    context_charts.extend(dimension_chart_mapping[dimension])
                    print(f"🎯 Dimension '{dimension}' mapped to charts: {dimension_chart_mapping[dimension]}")
        
        # 🎯 从路由信息中获取上下文
        route_info = context.get('route_info', {})
        if route_info:
            missing_preferences = route_info.get('missing_preferences', [])
            
            # 🎯 根据缺失偏好类型推荐图表
            preference_chart_mapping = {
                "budget range": ["price_distribution"],
                "price": ["price_distribution"], 
                "preferred area": ["location_popularity"],
                "location": ["location_popularity"],
                "room type": ["room_type_comparison"],
                "accommodation type": ["room_type_comparison"]
            }
            
            for missing_pref in missing_preferences:
                for pref_key, charts in preference_chart_mapping.items():
                    if pref_key.lower() in missing_pref.lower():
                        context_charts.extend(charts)
                        print(f"🎯 Missing preference '{missing_pref}' mapped to charts: {charts}")
        
        # 🎯 去重并返回
        return list(set(context_charts))
    
    def _get_context_aware_description(self, chart_type: str, context: Optional[Dict]) -> str:
        """🎯 根据上下文生成图表描述"""
        if not context:
            return f"{chart_type} Analysis"
        
        followup_info = context.get('followup_info', {})
        if followup_info:
            target_dimensions = followup_info.get('followup_question', {}).get('target_dimensions', [])
            
            if "budget" in target_dimensions and chart_type == "price_distribution":
                return "Helps you understand the distribution of listings across different price ranges for setting an appropriate budget"
            elif "location" in target_dimensions and chart_type == "location_popularity":
                return "Shows the distribution of listings across different areas to help you choose an ideal accommodation area"
            elif "room_type" in target_dimensions and chart_type == "room_type_comparison":
                return "Compares different room types by price and quantity to help you choose the right accommodation type"
        
        return f"Recommended {chart_type} analysis based on current conversation"
    
    # ===== 私有方法 =====
    
    def _extract_user_budget(self, user_preferences: Dict) -> Dict:
        """提取用户预算信息"""
        budget_info = {
            "min_price": user_preferences.get('price_min'),
            "max_price": user_preferences.get('price_max'),
            "has_budget": False,
            "budget_range": None,
            "budget_description": "No budget set"
        }
        
        if budget_info["min_price"] is not None and budget_info["max_price"] is not None:
            budget_info["has_budget"] = True
            budget_info["budget_range"] = f"{budget_info['min_price']}-{budget_info['max_price']}€"
            budget_info["budget_description"] = f"Budget range: {budget_info['budget_range']}"
        elif budget_info["max_price"] is not None:
            budget_info["has_budget"] = True
            budget_info["budget_range"] = f"≤{budget_info['max_price']}€"
            budget_info["budget_description"] = f"Maximum budget: {budget_info['max_price']}€"
        elif budget_info["min_price"] is not None:
            budget_info["has_budget"] = True
            budget_info["budget_range"] = f"≥{budget_info['min_price']}€"
            budget_info["budget_description"] = f"Minimum budget: {budget_info['min_price']}€"
        
        return budget_info
    
    def _enhance_chart_with_budget_highlight(self, chart_data: Dict, chart_type: str, user_budget: Dict, user_preferences: Dict) -> Dict:
        """为图表添加预算高亮和文字说明"""
        enhanced_data = chart_data.copy()
        
        # 🎯 只对价格相关的图表进行预算高亮
        if chart_type == "price_distribution" and user_budget["has_budget"]:
            enhanced_data = self._enhance_price_distribution_highlight(enhanced_data, user_budget)
        
        elif chart_type == "location_popularity" and user_budget["has_budget"]:
            enhanced_data = self._enhance_location_popularity_with_budget(enhanced_data, user_budget)
        
        elif chart_type == "room_type_comparison" and user_budget["has_budget"]:
            enhanced_data = self._enhance_room_type_with_budget(enhanced_data, user_budget)
        
        # 🎯 为所有图表添加预算相关的文字说明
        enhanced_data["budget_context"] = self._generate_budget_context_text(
            chart_type, chart_data, user_budget, user_preferences
        )
        
        return enhanced_data
    
    def _enhance_price_distribution_highlight(self, chart_data: Dict, user_budget: Dict) -> Dict:
        """为价格分布图添加预算高亮"""
        enhanced_data = chart_data.copy()
        
        # 🎯 标记用户预算区间
        categories = enhanced_data["data"]["categories"]
        highlighted_indices = []
        
        for i, price_range in enumerate(categories):
            if self._is_price_range_in_budget(price_range, user_budget):
                highlighted_indices.append(i)
        
        # 🎯 修改ECharts配置以高亮预算区间
        echarts_option = enhanced_data["echarts_option"]
        
        # 为series数据添加高亮样式
        for i, data_point in enumerate(echarts_option["series"][0]["data"]):
            if i in highlighted_indices:
                data_point["itemStyle"] = {
                    "color": "#ff6b6b",  # 高亮色：红色
                    "borderColor": "#fff",
                    "borderWidth": 2,
                    "shadowBlur": 10,
                    "shadowColor": "rgba(255, 107, 107, 0.5)"
                }
                data_point["emphasis"] = {
                    "itemStyle": {
                        "color": "#ff5252"
                    }
                }
        
        # 🎯 添加预算区间标注
        echarts_option["graphic"] = [{
            "type": "text",
            "left": "10%",
            "top": "10%",
            "style": {
                "text": f"Your Budget: {user_budget['budget_range']}",
                "fontSize": 14,
                "fontWeight": "bold",
                "fill": "#ff6b6b"
            }
        }]
        
        # 🎯 更新tooltip以显示预算匹配信息
        echarts_option["tooltip"]["formatter"] = f"""
        function(params) {{
            var p = params[0];
            var budgetMatch = {highlighted_indices}.includes(p.dataIndex) ? ' ✓ Matches your budget' : '';
            return p.name + '<br/>' +
                   'Listings: ' + p.value + '<br/>' +
                   'Average price: €' + p.data.avgPrice + budgetMatch;
        }}
        """
        
        enhanced_data["echarts_option"] = echarts_option
        enhanced_data["highlighted_ranges"] = [categories[i] for i in highlighted_indices]
        
        return enhanced_data
    
    def _enhance_location_popularity_with_budget(self, chart_data: Dict, user_budget: Dict) -> Dict:
        """为地区受欢迎程度图添加预算相关信息"""
        enhanced_data = chart_data.copy()
        
        # 🎯 标记价格在预算范围内的地区
        avg_prices = enhanced_data["data"]["additional_metrics"]["avg_prices"]
        categories = enhanced_data["data"]["categories"]
        
        affordable_areas = []
        for i, avg_price in enumerate(avg_prices):
            if self._is_price_in_budget_range(avg_price, user_budget):
                affordable_areas.append(i)
        
        # 🎯 修改ECharts配置
        echarts_option = enhanced_data["echarts_option"]
        
        # 为符合预算的地区添加特殊样式
        series_data = echarts_option["series"][0]["data"]
        for i in range(len(series_data)):
            if i in affordable_areas:
                if isinstance(series_data[i], (int, float)):
                    series_data[i] = {
                        "value": series_data[i],
                        "itemStyle": {"color": "#52c41a"}  # 绿色表示符合预算
                    }
        
        enhanced_data["echarts_option"] = echarts_option
        enhanced_data["affordable_areas"] = [categories[i] for i in affordable_areas]
        
        return enhanced_data
    
    def _enhance_room_type_with_budget(self, chart_data: Dict, user_budget: Dict) -> Dict:
        """为房型对比图添加预算相关信息"""
        enhanced_data = chart_data.copy()
        
        # 🎯 标记价格符合预算的房型
        avg_prices = enhanced_data["data"]["additional_metrics"]["avg_prices"]
        categories = enhanced_data["data"]["categories"]
        
        affordable_types = []
        for i, avg_price in enumerate(avg_prices):
            if self._is_price_in_budget_range(avg_price, user_budget):
                affordable_types.append(i)
        
        # 🎯 修改饼图数据
        echarts_option = enhanced_data["echarts_option"]
        pie_data = echarts_option["series"][0]["data"]
        
        for i, data_point in enumerate(pie_data):
            if i in affordable_types:
                data_point["itemStyle"] = {
                    "borderColor": "#52c41a",
                    "borderWidth": 3
                }
                data_point["label"] = {
                    "color": "#52c41a",
                    "fontWeight": "bold"
                }
        
        enhanced_data["echarts_option"] = echarts_option
        enhanced_data["affordable_types"] = [categories[i] for i in affordable_types]
        
        return enhanced_data
    
    def _is_price_range_in_budget(self, price_range_str: str, user_budget: Dict) -> bool:
        """判断价格区间是否在用户预算范围内"""
        if not user_budget["has_budget"]:
            return False
        
        try:
            # 解析价格区间字符串 (例如: "51-100€")
            if "€+" in price_range_str:
                # 处理 "300€+" 这种情况
                min_price = int(price_range_str.replace("€+", ""))
                max_price = float('inf')
            elif "-" in price_range_str:
                # 处理 "51-100€" 这种情况
                price_parts = price_range_str.replace("€", "").split("-")
                min_price = int(price_parts[0])
                max_price = int(price_parts[1])
            else:
                return False
            
            # 检查是否与用户预算有重叠
            user_min = user_budget["min_price"] or 0
            user_max = user_budget["max_price"] or float('inf')
            
            return not (max_price < user_min or min_price > user_max)
        
        except (ValueError, IndexError):
            return False
    
    def _is_price_in_budget_range(self, price: float, user_budget: Dict) -> bool:
        """判断价格是否在用户预算范围内"""
        if not user_budget["has_budget"]:
            return True
        
        user_min = user_budget["min_price"] or 0
        user_max = user_budget["max_price"] or float('inf')
        
        return user_min <= price <= user_max
    
    def _generate_budget_context_text(self, chart_type: str, chart_data: Dict, user_budget: Dict, user_preferences: Dict) -> Dict:
        """生成预算相关的文字说明"""
        if not user_budget["has_budget"]:
            return {
                "title": "Data Overview",
                "description": "Analysis based on current filtering criteria",
                "budget_note": ""
            }
        
        budget_range = user_budget["budget_range"]
        
        if chart_type == "price_distribution":
            total_in_budget = sum(
                chart_data["data"]["values"][i] 
                for i, category in enumerate(chart_data["data"]["categories"])
                if self._is_price_range_in_budget(category, user_budget)
            )
            total_listings = chart_data["metadata"]["total_records"]
            percentage = (total_in_budget / total_listings * 100) if total_listings > 0 else 0
            
            return {
                "title": f"Your Budget Analysis ({budget_range})",
                "description": f"There are {total_in_budget} listings within your budget range, representing {percentage:.1f}% of the total",
                "budget_note": f"Price ranges highlighted in red match your budget"
            }
        
        elif chart_type == "location_popularity":
            avg_prices = chart_data["data"]["additional_metrics"]["avg_prices"]
            affordable_count = sum(
                1 for price in avg_prices 
                if self._is_price_in_budget_range(price, user_budget)
            )
            total_areas = len(avg_prices)
            
            return {
                "title": f"Location Budget Compatibility ({budget_range})",
                "description": f"{affordable_count}/{total_areas} areas have average prices within your budget",
                "budget_note": "Green bars represent areas with average prices within your budget"
            }
        
        elif chart_type == "room_type_comparison":
            avg_prices = chart_data["data"]["additional_metrics"]["avg_prices"]
            affordable_types = [
                chart_data["data"]["categories"][i]
                for i, price in enumerate(avg_prices)
                if self._is_price_in_budget_range(price, user_budget)
            ]
            
            return {
                "title": f"Room Type Budget Match ({budget_range})",
                "description": f"Recommended types: {', '.join(affordable_types) if affordable_types else 'No perfect matches'}",
                "budget_note": "Green borders indicate room types with average prices within your budget"
            }
        
        else:
            return {
                "title": f"Budget-Based Analysis ({budget_range})",
                "description": "Data filtered based on your budget preferences",
                "budget_note": ""
            }
    
    def _create_personalized_chart_suggestion(self, chart_type: str, enhanced_chart_data: Dict, user_budget: Dict, intent: Dict) -> Dict:
        """创建个性化的图表建议"""
        base_suggestion = {
            "chart_type": chart_type,
            "title": enhanced_chart_data.get('chart_config', {}).get('title', chart_type),
            "confidence": intent.get('confidence', 0.5)
        }
        
        # 🎯 根据预算情况生成个性化描述
        if user_budget["has_budget"]:
            budget_context = enhanced_chart_data.get("budget_context", {})
            base_suggestion["description"] = budget_context.get("description", intent.get('description', f'{chart_type} Analysis'))
            base_suggestion["budget_insight"] = budget_context.get("budget_note", "")
        else:
            base_suggestion["description"] = intent.get('description', f'{chart_type} Analysis')
            base_suggestion["budget_insight"] = ""
        
        return base_suggestion
    
    def _get_fallback_charts_by_keywords(self, user_preferences: Dict) -> List[str]:
        """基于用户偏好获取兜底图表"""
        fallback_charts = []
        
        # 如果设置了价格偏好，推荐价格分布图
        if user_preferences.get('price_min') or user_preferences.get('price_max'):
            fallback_charts.append("price_distribution")
        
        # 如果设置了地区偏好，推荐地区对比图
        if user_preferences.get('neighbourhood_group') or user_preferences.get('neighbourhood'):
            fallback_charts.append("location_popularity")
        
        # 如果设置了房型偏好，推荐房型对比图
        if user_preferences.get('room_type'):
            fallback_charts.append("room_type_comparison")
        
        # 默认推荐价格分布图
        if not fallback_charts:
            fallback_charts.append("price_distribution")
        
        return fallback_charts

# ===== 便捷函数 =====

def extract_visualization_filters(preferences: Dict) -> Dict:
    """从用户偏好中提取可视化过滤器"""
    filters = {}
    
    # 价格相关
    if preferences.get('price_min'):
        filters['price_min'] = preferences['price_min']
    if preferences.get('price_max'):
        filters['price_max'] = preferences['price_max']
    
    # 地理相关
    if preferences.get('neighbourhood_group'):
        filters['neighbourhood_group'] = preferences['neighbourhood_group']
    if preferences.get('neighbourhood'):
        filters['neighbourhood'] = preferences['neighbourhood']
    
    # 房型相关
    if preferences.get('room_type'):
        filters['room_type'] = preferences['room_type']
    
    # 其他筛选条件
    if preferences.get('minimum_nights'):
        filters['minimum_nights'] = preferences['minimum_nights']
    if preferences.get('min_reviews'):
        filters['min_reviews'] = preferences['min_reviews']
    
    return filters

# ===== 全局实例 =====
# 可以在routes.py中直接导入使用
visualization_enhancer = VisualizationEnhancer()

if __name__ == "__main__":
    print("🚀 Visualization Enhancement Module loaded")
    
    # 测试
    enhancer = VisualizationEnhancer()
    
    test_preferences = {
        "price_min": 80,
        "price_max": 150,
        "neighbourhood_group": "Mitte",
        "room_type": "Private room"
    }
    
    test_intents = [{
        "intent": "price_distribution",
        "confidence": 0.8,
        "description": "Price Distribution Analysis"
    }]
    
    print("🧪 Testing visualization enhancement...")
    result = enhancer.enhance_visualization_with_charts(test_intents, test_preferences)
    print(f"✅ Test result: Generated {len(result['enhanced_visualizations'])} charts")
    print(f"📊 Budget info: {result['user_budget_info']}")