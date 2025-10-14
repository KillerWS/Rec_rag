# 🎯 Added: Smart Visualization Manager
from chat_router import ChatStage


class SmartVisualizationManager:
    """
    Smart Visualization Manager - Intelligently decides visualization display based on conversation context
    """
    
    def __init__(self):
        from visualization_enhancer import visualization_enhancer
        self.viz_enhancer = visualization_enhancer
        
        # 🎯 Define when to show visualizations
        self.show_viz_scenarios = {
            "explicit_request": {
                "keywords": ["图表", "分布", "对比", "分析", "chart", "distribution", "comparison"],
                "priority": "high",
                "description": "User explicitly requests visualization"
            },
            "dimension_mention": {
                "keywords": ["价格", "地区", "房型", "location", "price", "room type", "area"],
                "priority": "medium", 
                "description": "User mentions specific dimensions"
            },
            "information_seeking": {
                "stages": ["information_seeking", "recommendation_ready"],
                "priority": "low",
                "description": "User is in information seeking stage"
            }
        }
        
        # 🎯 Define when not to show visualizations
        self.skip_viz_scenarios = [
            "greeting",  # Greeting stage
            "basic_preference_collection",  # Basic preference collection
            "conversational_only",  # Conversational only
            "recommendation_confirmation"  # Recommendation confirmation
        ]
    
    # Helper: stage getters to be robust to Enum/str
    def _get_stage_value(self, conv_state) -> str:
        return getattr(conv_state.stage, "value", str(conv_state.stage)).lower()

    def _is_exploration(self, conv_state) -> bool:
        # Treat recommendation_shown/refinement as phase-2 (exploration family)
        return self._get_stage_value(conv_state) in (
            "exploration", "exploration_phase", "explore",
            "recommendation_shown", "refinement"
        )

    # Use explicit rules to determine when to show visualizations
    def should_show_visualization(self, user_message: str, conv_state, routing_result: dict) -> dict:
        """
        Stage-aware 可视化总开关：
        - 第一阶段（preference_collection）不出图
        - 第二阶段（exploration）允许“显式请求优先”
        """
        route_type = (routing_result or {}).get("route", "") or ""
        intent = (routing_result or {}).get("intent", "") or ""
        message_lower = (user_message or "").lower()

        # === [A] 第一阶段直接禁用可视化 ===
        if not self._is_exploration(conv_state):
            return {
                "should_show": False,
                "reason": "preference_collection_stage",
                "priority": "none",
                "suggested_charts": []
            }

        # === [B] 显式请求优先（覆盖一切 skip 规则） ===
        explicit_keywords = self.show_viz_scenarios["explicit_request"]["keywords"]
        if any(k in message_lower for k in explicit_keywords):
            charts = self._get_charts_for_explicit_request(user_message, conv_state.preferences)
            return {
                "should_show": True,
                "reason": "explicit_request",
                "priority": "high",
                "suggested_charts": charts[:2]
            }

        # === [C] 非显式请求再考虑是否跳过 ===
        if self._should_skip_visualization(route_type, intent, conv_state):
            return {
                "should_show": False,
                "reason": "skip_scenario",
                "priority": "none",
                "suggested_charts": []
            }

        # === [D] 保留原有自动分析逻辑 ===
        viz_decision = self._analyze_visualization_need(user_message, conv_state, routing_result)
        return viz_decision
    
    def _should_skip_visualization(self, route_type: str, intent: str, conv_state) -> bool:
        """Determine whether to skip visualization"""
        
        # 强制输出调试信息
        if hasattr(conv_state, 'stage'):
            print(f"📊 DEBUG: 当前对话阶段为: {conv_state.stage}, 值: {conv_state.stage.value}")
        
        # 检查是否为RAG模式
        is_rag_mode = route_type == "rag_retrieval"
        
        # 明确检查是否为第二阶段（探索家族）
        is_exploration = False
        try:
            is_exploration = self._is_exploration(conv_state)
        except Exception:
            is_exploration = (hasattr(conv_state, 'stage') and getattr(conv_state.stage, 'value', str(conv_state.stage)).lower() == "exploration")
        
        # 允许EXPLORATION阶段显示可视化
        if is_exploration:
            print("📊 处于探索阶段，允许展示可视化")
            return False
        
        # 偏好收集阶段只有RAG模式才显示可视化
        if hasattr(conv_state, 'stage') and conv_state.stage.value == "preference_collection":
            if is_rag_mode:
                print("📊 检测到RAG检索模式，允许在偏好收集阶段展示可视化")
                return False
            else:
                print("🚫 处于偏好收集阶段（非RAG模式），跳过可视化")
                return True
        
        # 🚫 Skip scenario 1: Greetings and basic conversations
        if route_type == "direct_response" and intent in ["greeting", "general_question"]:
            return True
        
        # 🚫 Skip scenario 2: Follow-up questions when preference completeness is too low
        if route_type == "preference_prompt" and conv_state.get_completeness_score() < 0.3:
            return True
        
        # 🚫 Skip scenario 3: Pure conversation scenarios without dimension keywords
        if route_type == "conversational":
            return True
        
        # 🚫 Skip scenario 4: Recommendation confirmation stage
        if route_type == "recommendation_request":
            return True
        
        return False
    
    # 在这个函数中分析可视化意图： 显示哪个图?
    def _analyze_visualization_need(self, user_message: str, conv_state, routing_result: dict) -> dict:
        """
        分析可视化需求 - 使用LLM替换基于规则的判断
        该方法将原来的关键词匹配规则替换为LLM驱动的意图识别
        """
        print(f"🎨 _analyze_visualization_need called")
        # 构建上下文信息
        context = {
            'preferences': conv_state.preferences,
            'conversation_stage': conv_state.stage.value,
            'route_info': routing_result
        }
        
        # 调用LLM可视化意图识别器
        from llm_pipeline.llm_visualization_intent import llm_viz_recognizer
        viz_decision = llm_viz_recognizer.recognize_visualization_intent(user_message, context)
        print(f"🎨 viz_decision: {viz_decision}")
        # 返回结果，确保兼容原有的字段格式
        return {
            "should_show": viz_decision["should_show"],
            "reason": viz_decision["reason"],
            "priority": viz_decision["priority"],
            "suggested_charts": viz_decision["suggested_charts"]
        }
    
    def _has_dimension_keywords(self, message_lower: str) -> bool:
        """Check if message contains dimension keywords"""
        dimension_keywords = ["price", "cost", "budget", "expensive", "cheap", "area", "location", "neighborhood", "room", "type"]
        return any(keyword in message_lower for keyword in dimension_keywords)
    
    def _get_charts_for_explicit_request(self, user_message: str, preferences: dict) -> list:
        """Generate chart suggestions for explicit requests"""
        message_lower = user_message.lower()
        charts = []
        
        if any(word in message_lower for word in ["price", "cost", "budget"]):
            charts.append("price_distribution")
        if any(word in message_lower for word in ["location", "area", "popular"]):
            charts.append("location_popularity")
        if any(word in message_lower for word in ["room", "type", "accommodation"]):
            charts.append("room_type_comparison")
        
        # If no specific indication, recommend based on preferences
        if not charts:
            charts = self._get_charts_for_context(preferences)
        
        return charts
    
    def _get_charts_for_dimensions(self, message_lower: str, preferences: dict) -> list:
        """Generate charts based on mentioned dimensions"""
        charts = []
        
        if any(word in message_lower for word in ["price", "cost", "budget", "expensive", "cheap"]):
            charts.append("price_distribution")
        
        if any(word in message_lower for word in ["area", "location", "neighborhood", "where"]):
            charts.append("location_popularity")
        
        if any(word in message_lower for word in ["room", "type", "accommodation"]):
            charts.append("room_type_comparison")
        
        return charts
    
    def _get_charts_for_context(self, preferences: dict) -> list:
        """Recommend charts based on user preference context"""
        charts = []
        
        # If price preference is set, recommend price distribution
        if preferences.get('price_min') or preferences.get('price_max'):
            charts.append("price_distribution")
        
        # If location preference is set, recommend location comparison
        if preferences.get('neighbourhood_group') or preferences.get('neighbourhood'):
            charts.append("location_popularity")
        
        # If room type preference is set, recommend room type comparison
        if preferences.get('room_type'):
            charts.append("room_type_comparison")
        
        # Default to price distribution
        if not charts:
            charts.append("price_distribution")
        
        return charts
    
    def _get_charts_for_rag_context(self, user_message: str, preferences: dict) -> list:
        """Recommend charts for post-RAG retrieval scenario"""
        # After RAG retrieval, provide relevant data analysis charts
        charts = ["price_distribution"]
        
        # If location preference exists, add location analysis
        if preferences.get('neighbourhood_group'):
            charts.append("location_popularity")
        
        return charts
    
    def generate_contextual_visualization(self, user_message: str, conv_state, routing_result: dict) -> dict:
        """Generate context-related visualization data"""
        
        # 🎯 Step 1: Determine whether to display
        viz_decision = self.should_show_visualization(user_message, conv_state, routing_result)
        
        if not viz_decision["should_show"]:
            return {"show_visualization": False, "reason": viz_decision["reason"]}
        
        # 🎯 Step 2: Generate specific chart data
        chart_types = viz_decision["suggested_charts"]
        # 多样化（简版）：若只有1个候选，补1个互补图
        if len(chart_types) == 1:
            primary = chart_types[0]
            complement_map = {
                'price_distribution': ['location_popularity', 'room_type_comparison'],
                'location_popularity': ['price_distribution', 'room_type_comparison'],
                'room_type_comparison': ['price_distribution', 'location_popularity'],
                'neighbourhood_comparison': ['price_distribution', 'location_popularity'],
                'availability_analysis': ['price_distribution', 'neighbourhood_comparison'],
                'distance_price_tradeoff': ['price_distribution', 'location_popularity'],
                'reviews_analysis': ['location_popularity', 'price_distribution']
            }
            for cand in complement_map.get(primary, []):
                if cand not in chart_types:
                    chart_types.append(cand)
                    break
        chart_types = chart_types[:2]
        if not chart_types:
            return {"show_visualization": False, "reason": "no_suitable_charts"}
        
        # 🎯 Step 3: Use existing enhancer to generate charts
        visualization_intents = [
            {
                "intent": chart_type,
                "confidence": 0.8,
                "description": f"{chart_type} analysis based on {viz_decision['reason']}"
            }
            for chart_type in chart_types
        ]
        
        # 🎯 Build context information
        context = {
            "route_info": routing_result,
            "user_message": user_message,
            "conversation_stage": conv_state.stage.value,
            "viz_decision": viz_decision
        }
        
        # 🎯 Use existing enhancer
        enhanced_viz = self.viz_enhancer.enhance_visualization_with_charts(
            visualization_intents,
            conv_state.preferences,
            context=context
        )
        
        if enhanced_viz["has_charts"]:
            return {
                "show_visualization": True,
                "visualizations": enhanced_viz["enhanced_visualizations"],
                "chart_suggestions": enhanced_viz["chart_suggestions"],
                "visualization_message": self._generate_contextual_message(viz_decision),
                "user_budget_info": enhanced_viz.get("user_budget_info", {}),
                "reason": viz_decision["reason"],
                "priority": viz_decision["priority"]
            }
        else:
            return {"show_visualization": False, "reason": "chart_generation_failed"}
    
    #   生成可视化的文本说明:
    def _generate_contextual_message(self, viz_decision: dict) -> str:
        """Generate context-related prompt message"""
        reason = viz_decision["reason"]
        chart_count = len(viz_decision["suggested_charts"])
        
        messages = {
            "explicit_request": f"📊 Based on your request, here are {chart_count} relevant charts:",
            "dimension_mention": f"📊 Based on what you mentioned, I've prepared {chart_count} relevant analysis charts:",
            "context_appropriate": f"📊 Based on your preferences, I've prepared {chart_count} data analysis charts:",
            "post_rag_analysis": f"📊 Based on the search results, here are {chart_count} relevant data analyses:",
        }
        
        return messages.get(reason, f"📊 Showing you {chart_count} relevant charts:")
