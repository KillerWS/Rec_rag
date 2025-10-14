# visualization_intent_recognizer.py
"""
LLM驱动的可视化意图识别系统
"""

import json
from typing import Dict, List, Optional
from load_llm import get_llm

class VisualizationIntentRecognizer:
    """
    使用LLM识别用户查询中的可视化意图
    """
    
    def __init__(self):
        self.llm = get_llm()
        
        # 🎯 定义支持的可视化维度和图表类型
        self.visualization_types = {
            "price_distribution": {
                "description": "价格分布分析",
                "chart_type": "histogram",
                "dimensions": ["price_min", "price_max"],
                "keywords": ["价格分布", "price distribution", "价格区间", "price range", "价格分析"]
            },
            "location_popularity": {
                "description": "地区受欢迎程度分析", 
                "chart_type": "bar",
                "dimensions": ["neighbourhood_group", "neighbourhood"],
                "keywords": ["地区受欢迎", "popular area", "热门地区", "location popularity", "area comparison"]
            },
            "room_type_comparison": {
                "description": "房型分布对比",
                "chart_type": "pie", 
                "dimensions": ["room_type"],
                "keywords": ["房型对比", "room type", "房间类型", "accommodation type"]
            },
            "price_trend": {
                "description": "价格趋势分析",
                "chart_type": "line",
                "dimensions": ["price_min", "price_max", "neighbourhood_group"],
                "keywords": ["价格趋势", "price trend", "价格变化", "price over time"]
            },
            "reviews_analysis": {
            "description": "评论数据分析",
            "chart_type": "scatter",
            "dimensions": ["min_reviews", "reviews_per_month_min"],
            "keywords": ["评论分析", "review analysis", "popular listings", "高评分"]
            },
            "availability_analysis": {
                "description": "可用性分析",
                "chart_type": "bar",
                "dimensions": ["availability_min", "neighbourhood_group"],
                "keywords": ["可用性", "availability", "空房情况", "booking availability"]
            },
            "distance_price_tradeoff": {
                "description": "价格-距离权衡分析（可调权重α）",
                "chart_type": "bar",
                "dimensions": ["granularity", "alpha", "center", "min_listings", "room_type", "minimum_nights", "min_reviews", "price_min", "price_max", "top_k"],
                "keywords": ["distance", "near", "proximity", "tradeoff", "alpha", "价格", "距离", "权衡"]
            },
            "price_coverage_delta": {
                "description": "预算覆盖率增量分析 - 比较不同预算下的房源覆盖情况",
                "chart_type": "line",
                "dimensions": ["base_budget", "new_budget", "step", "neighbourhood_group", "room_type", "min_reviews", "availability_min"],
                "keywords": [
                    "budget coverage", "coverage curve", "budget increase", "budget change", "budget comparison",
                    "what if budget", "increase budget", "decrease budget", "budget impact", "coverage analysis",
                    "budget range", "price coverage", "availability by budget", "budget vs coverage",
                    "预算覆盖率", "预算增量", "预算变化", "预算对比", "预算影响", "覆盖率分析", "预算范围"
                ]
            },
        }
    
    def recognize_visualization_intent(self, user_message: str, conversation_context: Dict = None) -> List[Dict]:
        """
        使用LLM识别用户查询中的可视化意图
        
        Args:
            user_message: 用户消息
            conversation_context: 会话上下文，包含当前偏好等
            
        Returns:
            List of visualization intents with confidence scores
        """
        try:
            print(f"🔍 开始识别可视化意图: {user_message[:50]}...")
            
            # 🎯 构造LLM Prompt
            prompt = self._build_recognition_prompt(user_message, conversation_context)
            print(f"📝 Prompt长度: {len(prompt)} 字符")
            
            # 🎯 调用LLM
            print("🤖 调用LLM...")
            llm_response = self.llm.invoke(prompt)
            print(f"🤖 LLM响应类型: {type(llm_response)}")
            print(f"🤖 LLM响应前100字符: {str(llm_response)[:100]}...")
            
            # 🎯 解析LLM响应 - 直接传入原始响应对象
            intents = self._parse_llm_response(llm_response)
            
            # 🎯 验证和过滤结果
            validated_intents = self._validate_intents(intents, user_message)
            
            print(f"🔍 可视化意图识别结果: {len(validated_intents)} 个意图")
            for intent in validated_intents:
                print(f"  - {intent['intent']}: {intent['confidence']:.2f}")
            
            return validated_intents
            
        except Exception as e:
            print(f"❌ 可视化意图识别失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _build_recognition_prompt(self, user_message: str, context: Dict = None) -> str:
        """构造LLM识别提示"""
        
        # 获取当前用户偏好信息
        current_preferences = ""
        if context and context.get('preferences'):
            prefs = context['preferences']
            pref_list = []
            for key, value in prefs.items():
                if value is not None and value != []:
                    pref_list.append(f"{key}: {value}")
            current_preferences = f"用户当前偏好: {', '.join(pref_list)}" if pref_list else "用户偏好: 未设置"
        
        # 构造可视化类型说明
        viz_types_desc = []
        for viz_type, config in self.visualization_types.items():
            viz_types_desc.append(f"- {viz_type}: {config['description']} (图表类型: {config['chart_type']})")
        
        viz_types_text = "\n".join(viz_types_desc)
        
        prompt = f"""你是一个智能可视化意图识别助手。请分析用户的查询，判断是否需要提供数据可视化图表。

用户查询: "{user_message}"
{current_preferences}

支持的可视化类型:
{viz_types_text}

请分析用户查询，判断是否暗示需要以下任何类型的可视化:

分析规则:
1. 如果用户明确提到"图表"、"分布"、"对比"、"分析"等词汇，优先识别
2. 如果用户询问关于价格、地区、房型等维度的信息，考虑相应的可视化
3. 如果用户想了解"哪个更好"、"如何选择"等，可能需要对比图表
4. **特殊规则**: 预算变更查询（如"如果预算增加到900"、"显示预算覆盖率曲线"）应该建议"price_coverage_delta"
5. 如果用户只是简单聊天或询问具体信息，不需要可视化

预算变更检测:
- 寻找"如果"、"增加预算"、"减少预算"、"预算到"、"覆盖率曲线"等短语
- 这些应该触发"price_coverage_delta"，置信度0.8+
- 预算比较查询是覆盖率分析的完美候选

请以JSON格式返回结果，示例格式:
{{
    "visualizations": [
        {{
            "intent": "visualization_type_name",
            "confidence": 0.8,
            "reasoning": "为什么识别为这个意图的原因",
            "trigger_keywords": ["触发的关键词列表"]
        }}
    ],
    "overall_visualization_need": true,
    "summary": "简要分析用户是否需要可视化以及原因"
}}

只返回JSON，不要其他文字。"""
        
        return prompt
    
    def _parse_llm_response(self, llm_response) -> List[Dict]:
        """解析LLM响应"""
        try:
            # 🎯 处理不同类型的LLM响应
            if hasattr(llm_response, 'content'):
                response_text = llm_response.content
                print(f"🔍 使用 llm_response.content")
            elif hasattr(llm_response, 'text'):
                response_text = llm_response.text
                print(f"🔍 使用 llm_response.text")
            elif isinstance(llm_response, str):
                response_text = llm_response
                print(f"🔍 使用字符串响应")
            else:
                response_text = str(llm_response)
                print(f"🔍 强制转换为字符串")
            
            print(f"🔍 解析LLM响应，响应类型: {type(llm_response)}")
            print(f"🔍 提取的文本前200字符: {response_text[:200]}...")
            
            # 清理响应文本
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]
                print("🔧 移除 ```json 前缀")
            if response_text.startswith('```'):
                response_text = response_text[3:]
                print("🔧 移除 ``` 前缀")
            if response_text.endswith('```'):
                response_text = response_text[:-3]
                print("🔧 移除 ``` 后缀")
            
            print(f"🔍 清理后的JSON文本前200字符: {response_text[:200]}...")
            
            # 解析JSON
            parsed = json.loads(response_text)
            print(f"✅ JSON解析成功，键: {list(parsed.keys())}")
            
            # 提取可视化意图
            visualizations = parsed.get('visualizations', [])
            print(f"✅ 提取到 {len(visualizations)} 个原始意图")
            
            # 验证必要字段
            valid_intents = []
            for i, viz in enumerate(visualizations):
                print(f"🔍 检查意图 {i}: {viz}")
                if all(key in viz for key in ['intent', 'confidence']):
                    # 确保置信度在合理范围内
                    confidence = max(0.0, min(1.0, float(viz['confidence'])))
                    viz['confidence'] = confidence
                    valid_intents.append(viz)
                    print(f"✅ 意图 {i} 有效")
                else:
                    print(f"❌ 意图 {i} 缺少必要字段")
            
            print(f"✅ 最终有效意图数量: {len(valid_intents)}")
            return valid_intents
            
        except json.JSONDecodeError as e:
            print(f"❌ LLM响应JSON解析失败: {e}")
            print(f"错误位置: 第{getattr(e, 'lineno', '?')}行, 第{getattr(e, 'colno', '?')}列")
            print(f"原始响应类型: {type(llm_response)}")
            print(f"原始响应: {str(llm_response)[:500]}...")
            
            # 🎯 尝试提取JSON部分
            response_str = str(llm_response)
            try:
                # 查找JSON开始和结束
                start_idx = response_str.find('{')
                end_idx = response_str.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_part = response_str[start_idx:end_idx]
                    print(f"🔄 尝试解析提取的JSON: {json_part[:200]}...")
                    parsed = json.loads(json_part)
                    return parsed.get('visualizations', [])
            except Exception as extract_error:
                print(f"❌ JSON提取也失败: {extract_error}")
            
            return []
        except Exception as e:
            print(f"❌ LLM响应处理失败: {e}")
            print(f"响应类型: {type(llm_response)}")
            import traceback
            traceback.print_exc()
            return []
    
    def _validate_intents(self, intents: List[Dict], user_message: str) -> List[Dict]:
        """验证和过滤识别出的意图"""
        validated = []
        
        for intent in intents:
            intent_name = intent.get('intent')
            confidence = intent.get('confidence', 0.0)
            
            # 检查意图是否在支持列表中
            if intent_name not in self.visualization_types:
                print(f"⚠️  跳过未知意图: {intent_name}")
                continue
            
            # 检查置信度阈值
            if confidence < 0.3:
                print(f"⚠️  跳过低置信度意图: {intent_name} ({confidence:.2f})")
                continue
            
            # 添加图表配置信息
            viz_config = self.visualization_types[intent_name]
            validated_intent = {
                **intent,
                'chart_type': viz_config['chart_type'],
                'dimensions': viz_config['dimensions'],
                'description': viz_config['description']
            }
            
            validated.append(validated_intent)
        
        # 按置信度排序
        validated.sort(key=lambda x: x['confidence'], reverse=True)
        
        # 最多返回3个意图
        return validated[:3]
    
    def should_show_visualization_suggestions(self, intents: List[Dict]) -> bool:
        """判断是否应该向用户显示可视化建议"""
        if not intents:
            return False
        
        # 如果有高置信度的意图，显示建议
        high_confidence_intents = [i for i in intents if i['confidence'] > 0.6]
        return len(high_confidence_intents) > 0

# ===== 集成到rag_chat的代码 =====

def integrate_visualization_to_rag_chat():
    """
    集成可视化识别到rag_chat接口的代码示例
    """
    code_snippet = '''
# 在rag_chat接口中添加的代码

from visualization_intent_recognizer import VisualizationIntentRecognizer

# 初始化可视化识别器（可以作为全局变量）
viz_recognizer = VisualizationIntentRecognizer()

@api.route("/rag_chat", methods=["POST"])
def rag_chat():
    """改进的RAG对话接口：智能路由 + 可视化意图识别"""
    print("rag_chat called")
    
    try:
        data = request.json
        user_message = data.get("message", "")
        history = data.get("history", [])
        session_id = data.get("session_id", "default")
        rec_confirm = data.get("rec_confirm", False)

        print(f"收到消息: {user_message}")
        
        if not user_message:
            return jsonify({"error": "缺少 message 参数"}), 400
    
        # 🎯 第一步：获取对话状态
        conv_state = get_conversation_state(session_id)
        print(f"当前对话阶段: {conv_state.stage}")
        
        # 🎯 第二步：可视化意图识别
        viz_context = {
            'preferences': conv_state.preferences,
            'stage': conv_state.stage.value,
            'conversation_turns': len(conv_state.conversation_history)
        }
        
        visualization_intents = viz_recognizer.recognize_visualization_intent(
            user_message, 
            viz_context
        )
        
        print(f"🎨 识别到 {len(visualization_intents)} 个可视化意图")
        
        # 🎯 第三步：智能路由判断
        routing_result = route_conversation(user_message, history, conv_state)
        print(f"路由决策: {routing_result}")

        # 🎯 第四步：根据路由结果执行不同逻辑
        # ... 原有的路由逻辑 ...
        
        # 🎯 第五步：在结果中添加可视化信息
        if routing_result["route"] == "rag_retrieval":
            # 原有的RAG检索逻辑
            result = rag_chat_with_memory_focused(user_message, history, retrieval_prefs)
            
            # 🎯 新增：添加可视化建议
            if visualization_intents:
                result["visualizations"] = visualization_intents
                result["show_visualization_suggestions"] = viz_recognizer.should_show_visualization_suggestions(visualization_intents)
                
                # 生成可视化相关的过滤器
                result["visualization_filters"] = extract_visualization_filters(conv_state.preferences)
        
        elif routing_result["route"] == "preference_update":
            # 原有的偏好更新逻辑
            result = process_preference_update(user_message, history, conv_state, use_llm)
            
            # 🎯 新增：如果更新了与可视化相关的偏好，添加可视化建议
            if visualization_intents:
                result["visualizations"] = visualization_intents
                result["show_visualization_suggestions"] = True
                result["visualization_filters"] = extract_visualization_filters(conv_state.preferences)
        
        # ... 其他路由逻辑保持不变 ...
        
        return jsonify(result)
        
    except Exception as e:
        print(f"路由处理出错: {str(e)}")
        return jsonify({"error": f"dialog processed failed: {str(e)}"}), 500

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
'''
    
    return code_snippet

# ===== 测试接口 =====

from flask import Flask, request, jsonify

def create_visualization_test_api(app):
    """创建可视化意图识别测试接口"""
    
    # 初始化识别器
    viz_recognizer = VisualizationIntentRecognizer()
    
    @app.route("/test/visualization_intent", methods=["POST"])
    def test_visualization_intent():
        """
        测试可视化意图识别接口
        
        POST /test/visualization_intent
        {
            "message": "用户查询消息",
            "context": {
                "preferences": {...},
                "stage": "preference_collection",
                "conversation_turns": 5
            }
        }
        """
        try:
            data = request.json
            user_message = data.get("message", "")
            context = data.get("context", {})
            
            if not user_message:
                return jsonify({"error": "缺少 message 参数"}), 400
            
            print(f"🧪 测试可视化意图识别:")
            print(f"   用户消息: {user_message}")
            print(f"   上下文: {context}")
            
            # 识别可视化意图
            intents = viz_recognizer.recognize_visualization_intent(user_message, context)
            
            # 判断是否显示建议
            should_show = viz_recognizer.should_show_visualization_suggestions(intents)
            
            # 生成测试用的过滤器
            test_filters = {
                'price_min': context.get('preferences', {}).get('price_min', 50),
                'price_max': context.get('preferences', {}).get('price_max', 200),
                'neighbourhood_group': context.get('preferences', {}).get('neighbourhood_group'),
                'room_type': context.get('preferences', {}).get('room_type')
            }
            
            result = {
                "success": True,
                "user_message": user_message,
                "visualization_intents": intents,
                "should_show_suggestions": should_show,
                "total_intents": len(intents),
                "high_confidence_intents": len([i for i in intents if i['confidence'] > 0.6]),
                "visualization_filters": test_filters,
                "test_timestamp": str(pd.Timestamp.now())
            }
            
            print(f"✅ 识别结果: {len(intents)} 个意图, 应显示建议: {should_show}")
            
            return jsonify(result)
            
        except Exception as e:
            print(f"❌ 测试接口错误: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    @app.route("/test/visualization_examples", methods=["GET"])
    def get_visualization_examples():
        """获取测试用例示例"""
        examples = [
            {
                "name": "价格分布查询",
                "message": "我想看看不同价格区间的房源分布情况",
                "context": {
                    "preferences": {
                        "price_min": 50,
                        "price_max": 150,
                        "room_type": "Private room"
                    },
                    "stage": "preference_collection"
                },
                "expected_intent": "price_distribution"
            },
            {
                "name": "地区受欢迎程度", 
                "message": "哪个地区最受欢迎？能给我看个对比图吗？",
                "context": {
                    "preferences": {
                        "neighbourhood_group": "Mitte"
                    },
                    "stage": "information_seeking"
                },
                "expected_intent": "location_popularity"
            },
            {
                "name": "房型对比",
                "message": "不同房间类型的价格和数量对比",
                "context": {
                    "preferences": {
                        "price_max": 200
                    },
                    "stage": "preference_collection"
                },
                "expected_intent": "room_type_comparison"
            },
            {
                "name": "无可视化需求",
                "message": "你好，我想了解一下柏林的住宿情况",
                "context": {
                    "preferences": {},
                    "stage": "greeting"
                },
                "expected_intent": None
            },
            {
                "name": "多维度分析",
                "message": "帮我分析一下不同地区的价格分布和房型对比",
                "context": {
                    "preferences": {
                        "price_min": 80,
                        "price_max": 300
                    },
                    "stage": "information_seeking"
                },
                "expected_intent": ["price_distribution", "location_popularity", "room_type_comparison"]
            }
        ]
        
        return jsonify({
            "examples": examples,
            "usage": "POST /test/visualization_intent",
            "supported_intents": list(viz_recognizer.visualization_types.keys())
        })

if __name__ == "__main__":
    # 测试运行
    recognizer = VisualizationIntentRecognizer()
    
    test_cases = [
        "我想看看不同价格区间的房源分布",
        "哪个地区最受欢迎？",
        "能给我展示一下房型对比图吗？",
        "价格趋势如何？",
        "你好，我需要住宿",
        "帮我分析一下Mitte地区的价格和房型分布"
    ]
    
    print("🧪 测试可视化意图识别:")
    print("=" * 50)
    
    for i, test_msg in enumerate(test_cases, 1):
        print(f"\n测试 {i}: {test_msg}")
        intents = recognizer.recognize_visualization_intent(test_msg)
        print(f"结果: {len(intents)} 个意图")
        for intent in intents:
            print(f"  - {intent['intent']}: {intent['confidence']:.2f}")