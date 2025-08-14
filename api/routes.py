# routes.py - 优化后的智能可视化集成版本

from typing import List
from llm_pipeline.conversational_chat import con_chat_with_memory
from db import execute_query
from flask import Blueprint, request, jsonify
from map_info.map_markers_service import MapMarkersService
from preference_route_handler import generate_recommendation_intro, process_preference_update, process_recommendation_request
from smartVisualizationManager import SmartVisualizationManager
from sql_generator import generate_sql_query, generate_sql_query_from_selectedDimensions
from recommendation_engine import recommend_listings, recommend_listings_with_semantic
from charts import generate_chart_data
from sqlalchemy.exc import SQLAlchemyError
from rag_module.rag_chat import get_global_vectordb, parse_history, rag_chat_with_memory_focused, rag_prepare
from aggregation import room_type_distribution_by_price_bins, overall_aggregation, neighbourhood_aggregation
from rag_module.reviews_analysis import get_review_wordcloud_data
from llm_pipeline.reviews_summary import get_review_insights
from llm_pipeline.agent_approach.analyze_user_intent import analyze_user_intent
from llm_pipeline.agent_approach.preference_store import PreferenceStore
from visualization_manager import VisualizationManager, integrate_visualization_to_existing_response
from chart_data_generator import ChartDataGenerator

import json
import uuid
import re
import math

api = Blueprint('api', __name__)

# 管局状态管理
pref_store = PreferenceStore()

# 初始化图表数据生成器
chart_generator = ChartDataGenerator()

def generate_preference_summary(preferences):
    """
    生成用户偏好的自然语言总结
    
    Args:
        preferences: 用户偏好字典
        
    Returns:
        str: 自然语言总结
    """
    summary_parts = []
    
    # 价格偏好
    price_min = preferences.get('price_min')
    price_max = preferences.get('price_max')
    if price_min and price_max:
        summary_parts.append(f"budget between €{price_min} and €{price_max} per night")
    elif price_max:
        summary_parts.append(f"budget up to €{price_max} per night")
    elif price_min:
        summary_parts.append(f"budget from €{price_min} per night")
    
    # 位置偏好
    neighbourhood = preferences.get('neighbourhood')
    neighbourhood_group = preferences.get('neighbourhood_group')
    if neighbourhood:
        summary_parts.append(f"in {neighbourhood}")
    elif neighbourhood_group:
        summary_parts.append(f"in {neighbourhood_group} district")
    
    # 房型偏好
    room_type = preferences.get('room_type')
    if room_type:
        summary_parts.append(f"{room_type.lower()}")
    
    # 停留时长
    minimum_nights = preferences.get('minimum_nights')
    if minimum_nights:
        summary_parts.append(f"for at least {minimum_nights} night{'s' if minimum_nights > 1 else ''}")
    
    # 评论数量要求
    min_reviews = preferences.get('min_reviews')
    if min_reviews:
        summary_parts.append(f"with at least {min_reviews} review{'s' if min_reviews > 1 else ''}")
    
    # 可用性要求
    availability_min = preferences.get('availability_min')
    if availability_min:
        summary_parts.append(f"with {availability_min}+ days availability")
    
    # 评论频率
    reviews_per_month_min = preferences.get('reviews_per_month_min')
    if reviews_per_month_min:
        summary_parts.append(f"with {reviews_per_month_min}+ reviews per month")
    
    # 关键词偏好
    amenities_keywords = preferences.get('amenities_keywords', [])
    if amenities_keywords:
        summary_parts.append(f"with amenities like {', '.join(amenities_keywords[:3])}")
    
    location_keywords = preferences.get('location_keywords', [])
    if location_keywords:
        summary_parts.append(f"near {', '.join(location_keywords[:3])}")
    
    experience_keywords = preferences.get('experience_keywords', [])
    if experience_keywords:
        summary_parts.append(f"for {', '.join(experience_keywords[:3])} experience")
    
    # 组合总结
    if summary_parts:
        # 使用适当的连接词
        if len(summary_parts) == 1:
            summary = f"You're looking for accommodation {summary_parts[0]}."
        elif len(summary_parts) == 2:
            summary = f"You're looking for accommodation {summary_parts[0]} and {summary_parts[1]}."
        else:
            # 对于3个或更多部分，使用逗号和and连接
            last_part = summary_parts[-1]
            other_parts = summary_parts[:-1]
            summary = f"You're looking for accommodation {', '.join(other_parts)}, and {last_part}."
    else:
        summary = "You're looking for accommodation in Berlin."
    
    return summary

# 🎯 初始化智能可视化管理器
smart_viz_manager = SmartVisualizationManager()

# �� 原有的API接口保持不变
@api.route('/chart-data', methods=['GET'])
def get_chart_data():
    print("get_chart_data")
    """获取不同维度的 ECharts 需要的数据"""
    chart_type = request.args.get('type', 'price_distribution')  
    min_price = request.args.get('min_price', default=0, type=int)
    max_price = request.args.get('max_price', default=9999, type=int)
    neighbourhood = request.args.get('neighbourhood', default=None, type=str)
    # 新增 
    ng_group     = request.args.get('neighbourhood_group', default=None, type=str)
    budget_min = request.args.get('min_price', default=None, type=int)
    budget_max = request.args.get('min_price', default=None, type=int)

    # ⚙️ 用我们新写的 ChartDataGenerator
    user_prefs = {
        "price_min": min_price,
        "price_max": max_price,
        "neighbourhood": neighbourhood,
        "neighbourhood_group": ng_group,
        # … 如果还需要 room_type、min_reviews 等，可以再接 request.args
    }

    data = chart_generator.generate_chart_data(chart_type, user_prefs)

    if not data.get("success", False):
        return jsonify({"error": data.get("error", "Chart generation failed")}), 400

    return jsonify(data)

@api.route("/price-overview", methods=["GET"])
def get_price_overview():
    """综合接口：返回 summary, pieChart, barChart 三块数据"""
    try:
        budget_min = request.args.get("budget_min", type=int)
        budget_max = request.args.get("budget_max", type=int)
        print("-------------")
        print(budget_min, budget_max)
        # 获取汇总信息
        summary = overall_aggregation()

        # 获取饼图数据（价格区间分布）
        pie_chart = generate_chart_data(
            chart_type="price_pie",
            budget_min=budget_min,
            budget_max=budget_max
        )

        # 获取柱状图数据（价格分布+高亮）
        bar_chart = generate_chart_data(
            chart_type="price_histogram",
            budget_min=budget_min,
            budget_max=budget_max
        )

        # 组装总返回结构
        result = {
            "summary": summary,
            "pieChart": pie_chart,
            "barChart": bar_chart
        }

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 🔹 原有的其他API接口保持不变
@api.route('/health', methods=['GET'])
def health_check():
    """健康检查，确保数据库可用"""
    try:
        execute_query("SELECT 1")
        return jsonify({"status": "OK", "message": "Server & Database are running fine"}), 200
    except SQLAlchemyError as e:
        return jsonify({"status": "ERROR", "message": f"Database connection failed: {str(e)}"}), 500

@api.route('/recommendations', methods=['POST'])
def fetch_recommendations():
    print("📩 /recommendations called")
    try:
        res = request.json
        if not res:
            res = {}
        data = res.get('data', {})
        session_id = data.get('session_id', 'default')
        preferences_from_frontend = data.get('selectedDimensions', [])
        top_k = data.get('top_k', 10)
        user_query = data.get('user_query', "")  # Optional: User's original query

        # 🎯 获取会话状态
        conv_state = get_conversation_state(session_id)
        
        if not preferences_from_frontend:
            print("📎 No preferences available, generating fallback recommendations")
            fallback_query = "SELECT * FROM listings ORDER BY number_of_reviews DESC LIMIT {}".format(top_k * 5)
            fallback_preferences = {}

            recommended = recommend_listings(
                fallback_query,
                fallback_preferences,
                used_preferences=[],   # Initially no dimensions
                top_k=top_k
            )

            return jsonify({
                "sql_query": fallback_query,
                "recommendations": recommended,
                "message": "Showing popular listings. Add preferences for personalized recommendations.",
                "session_id": session_id
            })

        # 使用修改后的函数生成SQL查询和提取偏好
        result = generate_sql_query_from_selectedDimensions(preferences_from_frontend)
        sql_query = result["sql_query"]
        extracted_preferences = result["extracted_preferences"]
        
        # 直接更新会话状态中的偏好，只更新有值的项
        for key, value in extracted_preferences.items():
            if value is not None:  # 只更新有值的偏好
                conv_state.preferences[key] = value
                print(f"📊 更新偏好: {key} = {value}")
        
        # 使用提取的偏好
        used_preferences = list(extracted_preferences.keys())
        print("✅ 使用的偏好维度:", used_preferences)
        
        # 使用增强的推荐函数
        recommended = recommend_listings_with_semantic(
            sql_query,
            extracted_preferences,
            used_preferences=used_preferences,
            top_k=top_k,
            user_query=user_query
        )

        response = {
            "sql_query": sql_query,
            "recommendations": recommended,
            "has_semantic_analysis": any("semantic_match" in item for item in recommended),
            "updated_preferences": extracted_preferences,
            "session_id": session_id
        }
        
        if not recommended:
            response["message"] = "No recommendations match your selected dimensions. Please adjust your preferences and try again."

        return jsonify(response)
    except Exception as e:
        import traceback
        print(f"❌ Recommendation generation failed: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": f"Recommendation failed: {str(e)}"}), 500

@api.route('/fetch_overall_aggregation', methods=['GET'])
def fetch_overall_aggregation():
    try:
        result = overall_aggregation()
        return jsonify({"status": "success", "data": result}), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to fetch overall aggregation: {str(e)}"
        }), 500

@api.route("/fetch_neighbourhood_aggregation", methods=["GET"])
def fetch_neighbourhood_aggregation():
    print("fetch_neighbourhood_aggregation called")
    
    budget_min = request.args.get("budget_min", type=int)
    budget_max = request.args.get("budget_max", type=int)
    try:
        result = neighbourhood_aggregation(budget_min, budget_max)
        return jsonify({"status": "success", "data": result}), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to fetch overall aggregation: {str(e)}"
        }), 500   

@api.route("/room_type_price_distribution", methods=["GET"])
def room_type_price_distribution():
    print("fetch_room_type_aggregation called")
    try:
        min_price = int(request.args.get("min_price", 0))
        max_price = int(request.args.get("max_price", 9999))
        print(min_price, max_price)
        data = room_type_distribution_by_price_bins(min_price, max_price)
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@api.route("/fetch_review_wordcloud", methods=["GET"])
def fetch_review_wordcloud():
    """获取评论关键词词云数据"""
    try:
        wordcloud_data = get_review_wordcloud_data(top_n=50)
        return jsonify({"status": "success", "data": wordcloud_data}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to fetch review wordcloud: {str(e)}"}), 500

@api.route("/fetch_review_insights", methods=["GET"])
def fetch_review_insights():
    """获取评论总结观点数据"""
    try:
        import time
        t0 = time.time()
        print("[routes.fetch_review_insights] called")
        # 参数控制示例（允许通过查询参数覆盖）
        sample_size = request.args.get('sample_size', default=15, type=int)
        batch_size = request.args.get('batch_size', default=15, type=int)
        top_n = request.args.get('top_n', default=20, type=int)
        min_length = request.args.get('min_length', default=30, type=int)
        print(f"[routes.fetch_review_insights] invoking get_review_insights with sample_size={sample_size}, batch_size={batch_size}, top_n={top_n}, min_length={min_length} ...")
        insights = get_review_insights(
            sample_size=sample_size,
            batch_size=batch_size,
            top_n=top_n,
            min_length=min_length
        )
        elapsed = time.time() - t0
        print(f"[routes.fetch_review_insights] get_review_insights returned in {elapsed:.3f}s, items={len(insights) if isinstance(insights, list) else 'N/A'}")
        return jsonify({"status": "success", "data": insights, "elapsed": elapsed}), 200
    except Exception as e:
        import traceback
        print(f"❌ [routes.fetch_review_insights] failed: {e}\n{traceback.format_exc()}")
        return jsonify({"status": "error", "message": f"Failed to fetch review insights: {str(e)}"}), 500

@api.route("/prepare_rag_context", methods=["POST"])
def prepare_rag_context():
    """
    1. 首次调用时，显式触发 get_global_vectordb()，把 55 万条评论的
       FAISS 索引加载进内存（lru_cache 保证只运行一次）
    2. 然后继续执行原来的 rag_prepare()，返回 index_id
    """
    print("prepare_rag_context called")

    try:
        # --------------- ① 预热全局向量库 -----------------
        # 如果已经加载过，这里几乎是 O(1)；否则会打印
        # ⚡ Loading global FAISS index ...
        get_global_vectordb()

        # --------------- ② 你的原始逻辑 --------------------
        req = request.json or {}
        selected_dimensions = req.get("selectedDimensions", [])

        # ✨ 如果 rag_prepare 需要用到 selected_dimensions，就传进去；
        #    否则可以不带参数，保持你原先的实现
        #index_id = rag_prepare(selected_dimensions)
        index_id = str(uuid.uuid4())
        return jsonify({"index_id": index_id})

    except Exception as e:
        import traceback, logging
        logging.exception("Error preparing RAG context")
        return jsonify({"error": str(e)}), 500

    except Exception as e:
        print(f"❌ Error preparing RAG context: {e}")
        return jsonify({"error": str(e)}), 500

# 在routes.py顶部添加导入
from chat_router import route_conversation, ConversationState, ChatStage, get_conversation_state
from intent.parser import parse_intent

from llm_pipeline.visualization_intent_recognizer import VisualizationIntentRecognizer

# 🎯 全局初始化可视化识别器
viz_recognizer = VisualizationIntentRecognizer()

def handle_recommendation_request(user_message: str, history: List, conv_state: ConversationState) -> dict:
    """处理推荐请求 - 第一步：确认"""
    
    # 🎯 直接访问现有的preferences属性
    current_preferences = conv_state.preferences
    
    # 🎯 使用现有的方法计算完整度
    completeness_score = conv_state.get_completeness_score()
    
    # 🎯 生成偏好摘要 - 让用户看到当前设置了什么
    pref_summary = []
    if current_preferences.get('price_max'):
        pref_summary.append(f"Budget: €{current_preferences['price_max']} per night")
    if current_preferences.get('price_min') and current_preferences.get('price_max'):
        pref_summary[-1] = f"Budget: €{current_preferences['price_min']}-{current_preferences['price_max']} per night"
    elif current_preferences.get('price_min'):
        pref_summary.append(f"Budget: From €{current_preferences['price_min']} per night")
        
    if current_preferences.get('neighbourhood_group'):
        pref_summary.append(f"Location: {current_preferences['neighbourhood_group']}")
    if current_preferences.get('room_type'):
        pref_summary.append(f"Room type: {current_preferences['room_type']}")
    if current_preferences.get('minimum_nights'):
        pref_summary.append(f"Stay duration: {current_preferences['minimum_nights']} nights")
    
    # 🎯 根据偏好数量生成不同的确认消息
    if len(pref_summary) >= 3:
        message = "Perfect! I have your key preferences:\n" + "\n".join([f"• {item}" for item in pref_summary]) + "\n\nReady to see personalized recommendations?"
    elif len(pref_summary) >= 1:
        message = "I have some preferences:\n" + "\n".join([f"• {item}" for item in pref_summary]) + "\n\nI can show recommendations now, or we can add more details first. What would you prefer?"
    else:
        message = "I can show you some popular Berlin recommendations, or we can gather your preferences first for better personalization. What would you prefer?"
    
    return {
        "response": message,
        "show_confirmation": True,  # 🎯 关键字段：告诉前端显示确认按钮
        "confirmation_type": "recommendation",
        "preferences_summary": pref_summary,
        "completeness_score": completeness_score
    }

def extract_visualization_filters(preferences: dict) -> dict:
    """从用户偏好中提取可视化过滤器"""
    filters = {}
    
    # 价格相关
    if preferences.get('price_min') is not None:
        filters['price_min'] = preferences['price_min']
    if preferences.get('price_max') is not None:
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
    if preferences.get('minimum_nights') is not None:
        filters['minimum_nights'] = preferences['minimum_nights']
    if preferences.get('min_reviews') is not None:
        filters['min_reviews'] = preferences['min_reviews']
    if preferences.get('reviews_per_month_min') is not None:
        filters['reviews_per_month_min'] = preferences['reviews_per_month_min']
    if preferences.get('availability_min') is not None:
        filters['availability_min'] = preferences['availability_min']
    
    # 关键词
    if preferences.get('amenities_keywords'):
        filters['amenities_keywords'] = preferences['amenities_keywords']
    if preferences.get('location_keywords'):
        filters['location_keywords'] = preferences['location_keywords']
    if preferences.get('experience_keywords'):
        filters['experience_keywords'] = preferences['experience_keywords']
    
    return filters

def handle_conversational_chat(message: str, history: List, conv_state: ConversationState) -> str:
    """处理一般性对话，不触发RAG"""
    
    # 简单的规则回复，或者调用轻量LLM
    msg_lower = message.lower()
    
    if "conference" in msg_lower or "business" in msg_lower:
        return "Perfect for a business trip! Berlin has great accommodations near conference venues. What's your budget and preferred area?"
    
    elif "visit" in msg_lower or "trip" in msg_lower:
        return "Exciting! Berlin is amazing to explore. I can help you find the perfect place to stay. What's your budget?"
    
    elif any(word in msg_lower for word in ["help", "find", "need", "looking"]):
        return "I'm here to help you find great Berlin accommodations! What's your budget and which area interests you?"
    
    else:
        return "I'd be happy to help you find accommodation in Berlin! Tell me about your budget and preferred area."

    

# 🎯 核心 rag_chat 接口
@api.route("/rag_chat", methods=["POST"])
def rag_chat():
    """🎯 优化后的RAG对话接口：智能路由 + 上下文感知可视化"""
    print("rag_chat called")
    
    try:
        data = request.json
        user_message = data.get("message", "")
        history = data.get("history", [])
        session_id = data.get("session_id") or str(uuid.uuid4())
        rec_confirm = data.get("rec_confirm", False)
        force_rag = data.get("force_rag", False)
        regenerate = data.get("regenerate", False)
        sub_mode = data.get("sub_mode", "default")
        global_search = data.get("global_search", False)

        print(f"收到消息: {user_message}")
        print(f"会话历史: {len(history)} 条")

        if not user_message:
            return jsonify({"error": "缺少 message 参数"}), 400
    
        # 🎯 第一步：获取对话状态
        conv_state = get_conversation_state(session_id)
        print(f"当前对话阶段: {conv_state.stage}")
        print(f"当前偏好完整度: {conv_state.get_completeness_score():.2f}")
        print(f"当前偏好: {conv_state.preferences}")

        
        # 🎯 第二步：智能路由判断（保持原有逻辑）
        routing_result = route_conversation(user_message, history, conv_state)
        print(f"路由决策: {routing_result}")

        # 🎯 处理强制RAG的场景
        if force_rag:
            print("🚀 检测到force_rag=True")
            routing_result = route_conversation(user_message, history, conv_state)
            allowed_routes = ["preference_update", "conversational", "rag_retrieval"]

            if routing_result["route"] not in allowed_routes:
                return jsonify({
                    "answer": "Knowledge base search is not suitable for this type of query. Try asking about specific accommodations, amenities, or experiences.",
                    "source_documents": [],
                    "route_info": {
                        "route_type": "force_rag_rejected",
                        "original_route": routing_result["route"],
                        "message": "Query type not suitable for knowledge base search"
                    }
                })
            
            print(f"✅ 允许强制RAG，原路由: {routing_result['route']}")
            routing_result["route"] = "rag_retrieval"

        # 🎯 第三步：更新对话状态
        conv_state.update_stage(routing_result["new_stage"])
        
        # 🎯 第四步：根据路由结果执行不同逻辑（保持原有功能）
        result = None
        
        if sub_mode == "review_qa":
            print("执行RAG检索流程")
            
            # 🎯 使用当前用户的偏好作为检索约束
            retrieval_prefs = conv_state.preferences.copy()
            
            # 如果没有偏好，使用默认值
            if not any(retrieval_prefs.values()):
                retrieval_prefs = {
                    "neighbourhood_group": None,
                    "neighbourhood": None,
                    "price_min": 50,
                    "price_max": 150,
                    "room_type": "Private room", 
                    "min_reviews": 1
                }

            # 运行原有的RAG逻辑
            result = rag_chat_with_memory_focused(user_message, history, retrieval_prefs, global_search=global_search)
            
            # 确保source_documents被保留
            if "source_documents" not in result:
                print("⚠️ RAG结果中缺少source_documents，添加空列表")
                result["source_documents"] = []
            
            # 添加调试日志
            print(f"RAG检索结果包含 {len(result.get('source_documents', []))} 个文档")
            
            # 添加路由信息
            result["route_info"] = {
                "route_type": "rag_retrieval",
                "intent": "review_analysis",  # 明确指定意图为review_analysis
                "stage": conv_state.stage.value,
                # "stage": ChatStage.EXPLORATION,
                "retrieval_triggered": True,
                "preferences_used": retrieval_prefs
            }
            conv_state.update_stage(ChatStage.EXPLORATION)

            # 强制设置当前请求为RAG模式，不应被视为偏好收集阶段
            # 这样做不会改变conversation_state的stage，只影响当前请求的处理
            result["is_rag_mode"] = True

        elif routing_result["route"] == "preference_update":
            print("routes: preference_update 状态 触发")
            
            dimension_type = data.get("dimension_type")
            structured_data = {}

            if dimension_type == "budget":
                budget_data = data.get("budget_data", {})
                structured_data["price_min"] = budget_data.get("min")
                structured_data["price_max"] = budget_data.get("max")

            elif dimension_type == "room_type":
                structured_data["room_type"] = data.get("room_type_data")

            # 🎯 使用新的偏好处理系统，传递LLM使用标志
            # use_llm = routing_result.get("use_llm_extraction", False)
            use_llm = True
            result = process_preference_update(user_message, history, conv_state, use_llm, structured_data=structured_data)

        elif rec_confirm == True:
            preferences = data.get("preferences", [])
            # 🎯 第二步：用户确认后执行推荐
            sql_query = generate_sql_query_from_selectedDimensions(preferences)
            pref_dict = {item["key"].lower(): item["value"] for item in preferences}

            # ✅ 动态传递已有的 used_preferences
            used_preferences = [item["key"].lower() for item in preferences]
            print("✅ Used preferences:", used_preferences)
            recommended = recommend_listings(
                sql_query,
                pref_dict,
                used_preferences=used_preferences,
                top_k=8
            ) 
            # result = process_recommendation_request(user_message, history, conv_state)

            response = generate_recommendation_intro(recommended, pref_dict)
            
            print(response)

            return jsonify({
                "sql_query": sql_query,
                "recommendations": recommended,
                "answer": response
            })

        elif routing_result["route"] == "preference_prompt":
            from intelligent_followup import analyze_followup_needs, generate_smart_followup
            
            # 使用智能追问系统
            followup_analysis = analyze_followup_needs(conv_state.preferences, conv_state.conversation_history)
            followup_question = generate_smart_followup(followup_analysis, user_message, conv_state.preferences)
            
            response = followup_question.get("question", 
                f"I'd love to show you recommendations! To find the perfect match, could you tell me your {' and '.join(conv_state.get_missing_critical_preferences())}?")
            
            result = {
                "answer": response,
                "source_documents": [],
                "route_info": {
                    "route_type": "preference_prompt",
                    "intent": routing_result["intent"],
                    "stage": conv_state.stage.value,
                    "missing_preferences": conv_state.get_missing_critical_preferences()
                },
                "message_type": "intelligent_followup",
                
                # 🎯 决策卡片信息
                "decision_card": {
                    "should_update": True,
                    "preferences": conv_state.preferences.copy(),
                    "completeness_score": conv_state.get_completeness_score(),
                    "preference_count": conv_state.get_preference_count(),
                    "missing_critical": conv_state.get_missing_critical_preferences(),
                    "stage": conv_state.stage.value
                },
                
                # 🎯 追问信息
                "followup_info": {
                    "ready_for_recommendation": False,
                    "followup_question": followup_question,
                    "completeness_score": followup_analysis["completeness_score"],
                    "strategy": followup_analysis["followup_strategy"]
                }
            }
        
        elif routing_result["route"] == "conversational":
            from llm_pipeline.should_fallback_to_rag import should_fallback_to_rag  # 加入头部
            # if sub_mode == "default" and should_fallback_to_rag(user_message):
            #     return jsonify({
            #         "answer": "It looks like you're asking something that relies on guest reviews. I can answer this in review search mode.",
            #         "message_type": "suggest_review_mode",
            #         "suggest_rag_mode": True,
            #         "recommendation_ready": conv_state.is_ready_for_recommendations(),
            #         "route_info": {
            #             "route_type": "conversational_review_redirect_suggestion",
            #             "reason": "RAG intent detected in default mode"
            #         },
            #         "guidance": {
            #             "primary_message": "Would you like me to search through guest reviews to answer this question?",
            #             "action_required": "Switch to review search mode",
            #             "preferences_collected": conv_state.get_preference_count(),
            #             "completeness_score": conv_state.get_completeness_score()
            #         }
            #     })
                
            # 对话式回应：简单的LLM生成，不检索文档
            # response = handle_conversational_chat(user_message, history, conv_state)
            response = con_chat_with_memory(user_message, history, {"session_id": session_id})
            
            result = {
                "answer": response,
                "source_documents": [],
                "route_info": {
                    "route_type": "conversational",
                    "intent": routing_result["intent"],
                    "stage": conv_state.stage.value
                }
            }
        
        else:
            # 兜底处理
            result = {
                "answer": "I'm here to help with Berlin accommodations. What would you like to know?",
                "source_documents": [],
                "route_info": {"route_type": "fallback"}
            }
        
        # 🎯 第五步：智能可视化处理（核心改进）
        print("🎨 开始智能可视化处理检查...")

        # 🎯 检查偏好完整度和必要偏好，生成总结
        essential_prefs = conv_state.has_essential_preferences()

        # 如果必要偏好都已填写，则生成总结
        if essential_prefs["is_complete"] and not getattr(conv_state, 'summary_generated', False):
            print(f"🎯 必要偏好已全部收集，生成偏好总结")
            preference_summary = generate_preference_summary(conv_state.preferences)
            result["preference_summary"] = preference_summary
            result["essential_preferences_complete"] = True
            result["stage_transition"] = {
                "from": "preference_collection",
                "to": "exploration",
                "message": "Essential preferences collected. Moving to exploration phase."
            }
            # 标记已生成总结，避免重复生成
            setattr(conv_state, 'summary_generated', True)
            # 更新阶段状态
            if conv_state.stage.value == "preference_collection":
                conv_state.stage = ChatStage.EXPLORATION
                print("🎯 阶段转换：从偏好收集进入到探索阶段")
        elif essential_prefs["is_complete"] and getattr(conv_state, 'summary_generated', False):
            print("🎯 必要偏好已全部收集，总结已生成")
            result["essential_preferences_complete"] = True
        else:
            # 如果必要偏好不完整，添加缺失信息
            if not essential_prefs["is_complete"] and not result.get("answer"):
                missing_dims = essential_prefs["missing"]
                missing_text = ", ".join(missing_dims)
                print(f"🎯 缺少必要偏好: {missing_text}")
                result["missing_preferences"] = missing_dims
                result["essential_preferences_complete"] = False

        # 只在非偏好收集阶段生成可视化内容
        viz_result = {"show_visualization": False, "reason": "preference_collection_stage"}
        print(f"🎨 当前阶段: {conv_state.stage}")
        print(f"🎨 当前阶段: {conv_state.stage.value}")
        if essential_prefs["is_complete"]:
            print("🎨 非偏好收集阶段，开始生成可视化内容...")
            # 🎯 使用新的智能可视化管理器
            viz_result = smart_viz_manager.generate_contextual_visualization(
                user_message, conv_state, routing_result
            )
            print(f"🎨 可视化决策: {viz_result.get('show_visualization', False)}")
            print(f"🎨 决策原因: {viz_result.get('reason', 'unknown')}")
        else:
            print("🎨 偏好收集阶段，跳过可视化生成")

        # 🎯 将可视化信息添加到结果中
        if viz_result["show_visualization"]:
            # 新的可视化字段
            result["visualizations"] = viz_result["visualizations"]
            result["chart_suggestions"] = viz_result["chart_suggestions"]
            result["show_visualization_prompt"] = True
            result["visualization_message"] = viz_result["visualization_message"]
            result["user_budget_info"] = viz_result.get("user_budget_info", {})
            
            # 兼容原有字段
            result["show_visualization_suggestions"] = True
            result["visualization_filters"] = extract_visualization_filters(conv_state.preferences)
            
            print(f"✅ 已添加可视化信息: {len(viz_result['visualizations'])} 个图表")
        else:
            result["show_visualization_prompt"] = False
            result["show_visualization_suggestions"] = False
            print(f"ℹ️ 未添加可视化: {viz_result.get('reason', 'unknown')}")

        # 🎯 第六步：保存对话轮次（保持原有逻辑）
        if not regenerate:
            conv_state.add_conversation_turn(user_message, result.get("answer", ""))
        else:
            print("🔄 重新生成模式：不更新对话轮次")

        # 🎯 第七步：添加调试信息（可选）
        if data.get("debug", False):
            result["debug_info"] = {
                "session_id": session_id,
                "conversation_stage": conv_state.stage.value,
                "preferences": conv_state.preferences,
                "completeness_score": conv_state.get_completeness_score(),
                "preference_count": conv_state.get_preference_count(),
                "conversation_turns": len(conv_state.conversation_history),
                "visualization_decision": viz_result.get("reason", "not_analyzed")
            }
        
        # 始终回传 session_id，便于前端持久化
        result["session_id"] = session_id
        return jsonify(result)
        
    except Exception as e:
        print(f"路由处理出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"dialog processed failed: {str(e)}"}), 500

# 🎯 保留原有的其他接口
@api.route("/intent-analysis", methods=["POST"])
def analyze_intent_api():
    print("analyze_intent_api called")
    data       = request.json or {}
    user_input = data.get("message", "")
    history    = data.get("history", [])

    # 1️⃣ 先判 intent（不用 LLM 也能返回）
    intent_res = parse_intent(user_input, history)
    print("parse_intent--")
    print(intent_res)
    
    return jsonify(intent_res)

import traceback
from datetime import datetime

# 初始化识别器（可以放在文件顶部）
try:
    viz_recognizer = VisualizationIntentRecognizer()
    print("✅ 可视化识别器初始化成功")
except Exception as e:
    print(f"❌ 可视化识别器初始化失败: {e}")
    viz_recognizer = None


@api.route('/heatmap/districts', methods=['GET'])
def get_heatmap_districts():
    """
    🗺️ 获取柏林区域的房源统计数据，支持两级查询
    
    功能说明：
    - 不传district_name：返回12个大行政区域(neighbourhood_group)统计
    - 传入district_name：返回该大区域下所有小社区(neighbourhood)统计
    
    Query Parameters:
    - district_name: 大区域名称（如"Mitte"，"Friedrichshain-Kreuzberg"等）
    - price_min: 最低价格筛选
    - price_max: 最高价格筛选  
    - room_type: 房间类型筛选
    - min_reviews: 最少评论数筛选
    """
    try:
        # 🔍 获取筛选参数
        district_name = request.args.get('district_name', type=str)  # 🆕 新增区域名称参数
        price_min = request.args.get('price_min', type=int)
        price_max = request.args.get('price_max', type=int)
        room_type = request.args.get('room_type', type=str)
        min_reviews = request.args.get('min_reviews', default=0, type=int)
        
        # 🎯 确定查询层级
        if district_name and district_name.strip():
            query_level = "neighbourhood_cleansed"  # 查询小社区
            group_by_field = "neighbourhood_cleansed"
            level_description = f"neighbourhoods in {district_name}"
        else:
            query_level = "neighbourhood_group_cleansed"  # 查询大行政区域
            group_by_field = "neighbourhood_group_cleansed"
            level_description = "administrative districts"
        
        print(f"🗺️ 获取区域统计数据 - 查询层级: {query_level}, 目标区域: {district_name or 'ALL'}")
        print(f"📊 筛选条件: price_min={price_min}, price_max={price_max}, room_type={room_type}, min_reviews={min_reviews}")
        
        # 🔧 构建动态查询条件
        where_conditions = [
            f"{group_by_field} IS NOT NULL",
            f"{group_by_field} != ''"
        ]
        
        # 🎯 如果指定了大区域，添加区域筛选条件
        if district_name and district_name.strip():
            safe_district_name = district_name.strip().replace("'", "''")
            where_conditions.append(f"neighbourhood_group_cleansed = '{safe_district_name}'")
        
        # 🛡️ 安全地添加其他筛选条件
        if price_min is not None:
            where_conditions.append(f"(price IS NOT NULL AND price >= {int(price_min)})")
        
        if price_max is not None:
            where_conditions.append(f"(price IS NOT NULL AND price <= {int(price_max)})")
        else:
            where_conditions.append("(price IS NULL OR price >= 0)")
        
        if room_type and room_type.strip():
            safe_room_type = room_type.strip().replace("'", "''")
            where_conditions.append(f"room_type = '{safe_room_type}'")
        
        if min_reviews > 0:
            where_conditions.append(f"(number_of_reviews IS NOT NULL AND number_of_reviews >= {int(min_reviews)})")
        
        where_clause = " AND ".join(where_conditions)
        
        # 📊 构建查询语句
        if query_level == "neighbourhood":
            # 🏘️ 查询小社区统计
            districts_query = f"""
            SELECT 
                neighbourhood_cleansed as area_name,
                neighbourhood_group_cleansed as parent_district,
                COUNT(*) as listing_count,
                -- 价格统计
                ROUND(AVG(CASE WHEN price IS NOT NULL AND price > 0 THEN CAST(price AS DECIMAL) END), 2) as avg_price,
                MIN(CASE WHEN price IS NOT NULL AND price > 0 THEN price END) as min_price,
                MAX(CASE WHEN price IS NOT NULL AND price > 0 THEN price END) as max_price,
                -- 评论统计
                SUM(CASE WHEN number_of_reviews IS NOT NULL THEN number_of_reviews ELSE 0 END) as total_reviews,
                ROUND(AVG(CASE WHEN number_of_reviews IS NOT NULL THEN CAST(number_of_reviews AS DECIMAL) END), 1) as avg_reviews,
                -- 位置信息（用于地图标记）
                ROUND(AVG(CASE WHEN latitude IS NOT NULL THEN CAST(latitude AS DECIMAL) END), 6) as center_lat,
                ROUND(AVG(CASE WHEN longitude IS NOT NULL THEN CAST(longitude AS DECIMAL) END), 6) as center_lng,
                -- 其他统计
                ROUND(AVG(CASE WHEN availability_365 IS NOT NULL THEN CAST(availability_365 AS DECIMAL) END), 1) as avg_availability,
                COUNT(CASE WHEN number_of_reviews > 0 THEN 1 END) as listings_with_reviews,
                COUNT(CASE WHEN price IS NOT NULL AND price > 0 THEN 1 END) as listings_with_valid_price
            FROM listings 
            WHERE {where_clause}
            GROUP BY neighbourhood_cleansed, neighbourhood_group_cleansed
            HAVING COUNT(*) > 0
            ORDER BY listing_count DESC
            """
        else:
            # 🏛️ 查询大行政区域统计
            districts_query = f"""
            SELECT 
                neighbourhood_group_cleansed as area_name,
                NULL as parent_district,
                COUNT(*) as listing_count,
                -- 价格统计
                ROUND(AVG(CASE WHEN price IS NOT NULL AND price > 0 THEN CAST(price AS DECIMAL) END), 2) as avg_price,
                MIN(CASE WHEN price IS NOT NULL AND price > 0 THEN price END) as min_price,
                MAX(CASE WHEN price IS NOT NULL AND price > 0 THEN price END) as max_price,
                -- 评论统计
                SUM(CASE WHEN number_of_reviews IS NOT NULL THEN number_of_reviews ELSE 0 END) as total_reviews,
                ROUND(AVG(CASE WHEN number_of_reviews IS NOT NULL THEN CAST(number_of_reviews AS DECIMAL) END), 1) as avg_reviews,
                -- 区域中心坐标（所有房源的平均位置）
                ROUND(AVG(CASE WHEN latitude IS NOT NULL THEN CAST(latitude AS DECIMAL) END), 6) as center_lat,
                ROUND(AVG(CASE WHEN longitude IS NOT NULL THEN CAST(longitude AS DECIMAL) END), 6) as center_lng,
                -- 其他统计
                COUNT(DISTINCT neighbourhood_cleansed) as neighbourhood_count,
                ROUND(AVG(CASE WHEN availability_365 IS NOT NULL THEN CAST(availability_365 AS DECIMAL) END), 1) as avg_availability,
                COUNT(CASE WHEN number_of_reviews > 0 THEN 1 END) as listings_with_reviews,
                COUNT(CASE WHEN price IS NOT NULL AND price > 0 THEN 1 END) as listings_with_valid_price
            FROM listings 
            WHERE {where_clause}
            GROUP BY neighbourhood_group_cleansed
            HAVING COUNT(*) > 0
            ORDER BY listing_count DESC
            """
        
        print(f"🔍 执行查询: {districts_query}")
        
        # 🗃️ 执行查询
        df_results = execute_query(districts_query)
        
        if df_results.empty:
            print(f"⚠️ 没有查询到{level_description}数据")
            return jsonify({
                "success": True,
                "data": {
                    "areas": [],
                    "query_level": query_level,
                    "parent_district": district_name,
                    "summary": {
                        "total_areas": 0,
                        "total_listings": 0,
                        "avg_price_overall": 0,
                        "price_range": {"min": 0, "max": 0}
                    }
                },
                "timestamp": "2025-01-01T00:00:00Z"
            })
        
        # 📋 处理查询结果
        results = df_results.to_dict('records')
        total_listings = sum(row['listing_count'] for row in results)
        max_listings = max(row['listing_count'] for row in results)
        
        # 计算价格和评论的最大值
        valid_prices = [float(row['avg_price']) for row in results if row['avg_price'] is not None and row['avg_price'] > 0]
        max_price = max(valid_prices) if valid_prices else 1
        max_total_reviews = max(row['total_reviews'] for row in results) if max(row['total_reviews'] for row in results) > 0 else 1
        
        print(f"📊 查询结果: {len(results)} 个{level_description}, 总房源: {total_listings}")
        
        # 🎨 处理每个区域的数据
        areas_data = []
        
        for row in results:
            # 📈 基础数据
            listing_count = int(row['listing_count'])
            avg_price = float(row['avg_price']) if row['avg_price'] is not None else 0
            min_price = int(row['min_price']) if row['min_price'] is not None else 0
            max_price_area = int(row['max_price']) if row['max_price'] is not None else 0
            total_reviews = int(row['total_reviews'])
            center_lat = float(row['center_lat']) if row['center_lat'] is not None else 52.5200
            center_lng = float(row['center_lng']) if row['center_lng'] is not None else 13.4050
            
            # 🔥 计算热力图强度
            count_intensity = listing_count / max_listings if max_listings > 0 else 0
            price_intensity = avg_price / max_price if max_price > 0 and avg_price > 0 else 0
            popularity_intensity = total_reviews / max_total_reviews if max_total_reviews > 0 else 0
            
            # 📊 计算受欢迎程度分数
            listing_percentage = (listing_count / total_listings) * 100 if total_listings > 0 else 0
            listings_with_reviews = int(row['listings_with_reviews']) if row['listings_with_reviews'] is not None else 0
            review_activity = (listings_with_reviews / listing_count) * 100 if listing_count > 0 else 0
            
            # 价格吸引力
            if avg_price > 0:
                optimal_price = 90
                price_attraction = max(0, 100 - abs(avg_price - optimal_price) / optimal_price * 100)
            else:
                price_attraction = 0
            
            popularity_score = round(
                listing_percentage * 0.40 +
                (review_activity / 100 * 35) +
                (price_attraction / 100 * 25),
                1
            )
            
            # 🏠 构建区域信息
            area_info = {
                "name": row['area_name'],
                "parent_district": row['parent_district'],  # 🆕 上级区域信息
                "listing_count": listing_count,
                "avg_price": avg_price,
                "min_price": min_price,
                "max_price": max_price_area,
                "total_reviews": total_reviews,
                "popularity_score": popularity_score,
                "center_position": {  # 🆕 用于地图标记的中心坐标
                    "lat": center_lat,
                    "lng": center_lng
                },
                "heat_intensity": {
                    "count": round(count_intensity, 3),
                    "price": round(price_intensity, 3),
                    "popularity": round(popularity_intensity, 3)
                }
            }
            
            # 🏛️ 大区域特有信息
            if query_level == "neighbourhood_group":
                area_info["neighbourhood_count"] = int(row['neighbourhood_count']) if row['neighbourhood_count'] is not None else 0
            
            areas_data.append(area_info)
        
        # 📈 统计摘要
        summary = {
            "total_areas": len(areas_data),
            "total_listings": total_listings,
            "avg_price_overall": round(sum(d['avg_price'] * d['listing_count'] for d in areas_data) / total_listings, 2) if total_listings > 0 else 0,
            "price_range": {
                "min": min(d['min_price'] for d in areas_data if d['min_price'] > 0) if any(d['min_price'] > 0 for d in areas_data) else 0,
                "max": max(d['max_price'] for d in areas_data) if areas_data else 0
            },
            "filters_applied": {
                "district_name": district_name,  # 🆕 当前查询的区域
                "price_min": price_min,
                "price_max": price_max,
                "room_type": room_type,
                "min_reviews": min_reviews
            }
        }
        
        print(f"✅ {level_description}数据处理完成: {len(areas_data)} 个区域")
        
        return jsonify({
            "success": True,
            "data": {
                "areas": areas_data,  # 🔄 改名为areas，支持两种层级
                "districts": areas_data,  # 🔄 保持向后兼容
                "query_level": query_level,  # 🆕 当前查询层级
                "parent_district": district_name,  # 🆕 上级区域（如果有）
                "summary": summary
            },
            "timestamp": "2025-01-01T00:00:00Z"
        })
        
    except Exception as e:
        print(f"❌ 获取区域统计数据失败: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to fetch district statistics data"
        }), 500
    

@api.route('/map-markers', methods=['GET'])
def get_map_markers():
    """
    获取地图标记数据接口
    
    Query Parameters:
        - level (required): neighbourhood_group | neighbourhood
        - district_name (optional): 大区域名称（获取小区域时必需）
        - price_min (optional): 最低价格筛选
        - price_max (optional): 最高价格筛选
        - room_type (optional): 房间类型筛选
        - min_reviews (optional): 最少评论数筛选
    
    Returns:
        JSON: 标记数据响应
    """
    
    try:
        # 🔍 获取请求参数
        level = request.args.get('level')
        district_name = request.args.get('district_name')
        
        # 价格筛选参数
        price_min = request.args.get('price_min')
        price_max = request.args.get('price_max')
        room_type = request.args.get('room_type')
        min_reviews = request.args.get('min_reviews')
        
        # 🔧 参数类型转换
        try:
            price_min = float(price_min) if price_min else None
            price_max = float(price_max) if price_max else None
            min_reviews = int(min_reviews) if min_reviews else None
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "error": "Invalid parameter types",
                "message": "price_min, price_max must be numbers, min_reviews must be integer"
            }), 400
        
        # ✅ 验证必需参数
        if not level:
            return jsonify({
                "success": False,
                "error": "Missing required parameter",
                "message": "level parameter is required"
            }), 400
        
        if not MapMarkersService.validate_level(level):
            return jsonify({
                "success": False,
                "error": "Invalid level parameter",
                "message": "level must be 'neighbourhood_group' or 'neighbourhood'"
            }), 400
        
        # ✅ 验证筛选参数
        validation_errors = MapMarkersService.validate_filters(
            price_min, price_max, room_type, min_reviews
        )
        
        if validation_errors:
            return jsonify({
                "success": False,
                "error": "Parameter validation failed",
                "message": "Invalid filter parameters",
                "details": validation_errors
            }), 400
        
        # 🏛️ 处理大区域请求
        if level == 'neighbourhood_group':
            print(f"🏛️ 请求大区域标记数据 - 筛选条件: price({price_min}-{price_max}), room_type({room_type}), min_reviews({min_reviews})")
            
            markers = MapMarkersService.get_large_district_markers(
                price_min=price_min,
                price_max=price_max,
                room_type=room_type,
                min_reviews=min_reviews
            )
            
            return jsonify({
                "success": True,
                "level": level,
                "parent_district": None,
                "markers": markers,
                "total_count": len(markers),
                "message": f"Successfully retrieved {len(markers)} district markers",
                "filters_applied": {
                    "price_min": price_min,
                    "price_max": price_max,
                    "room_type": room_type,
                    "min_reviews": min_reviews
                }
            })
        
        # 🏘️ 处理小区域请求
        elif level == 'neighbourhood':
            if not district_name:
                return jsonify({
                    "success": False,
                    "error": "Missing required parameter",
                    "message": "district_name is required when level is 'neighbourhood'"
                }), 400
            
            print(f"🏘️ 请求小区域标记数据 - 大区域: {district_name}, 筛选条件: price({price_min}-{price_max}), room_type({room_type}), min_reviews({min_reviews})")
            
            markers = MapMarkersService.get_small_district_markers(
                district_name=district_name,
                price_min=price_min,
                price_max=price_max,
                room_type=room_type,
                min_reviews=min_reviews
            )
            
            return jsonify({
                "success": True,
                "level": level,
                "parent_district": district_name,
                "markers": markers,
                "total_count": len(markers),
                "message": f"Successfully retrieved {len(markers)} neighbourhood markers in {district_name}",
                "filters_applied": {
                    "district_name": district_name,
                    "price_min": price_min,
                    "price_max": price_max,
                    "room_type": room_type,
                    "min_reviews": min_reviews
                }
            })
            
    except Exception as e:
        print(f"❌ 获取地图标记数据失败: {str(e)}")
        print(f"📋 错误详情: {traceback.format_exc()}")
        
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": f"Failed to fetch map markers: {str(e)}",
            "level": level,
            "parent_district": district_name
        }), 500

@api.route('/district-center/<district_name>', methods=['GET'])
def get_district_center(district_name: str):
    """
    获取区域中心坐标接口
    
    Path Parameters:
        - district_name: 区域名称
    
    Returns:
        JSON: 包含中心坐标的响应
    """
    
    try:
        print(f"📍 请求区域中心坐标: {district_name}")
        
        # ✅ 验证参数
        if not district_name or district_name.strip() == '':
            return jsonify({
                "success": False,
                "error": "Invalid parameter",
                "message": "district_name cannot be empty"
            }), 400
        
        # 🗺️ 获取区域中心坐标
        result = MapMarkersService.get_district_center(district_name)
        
        print(f"✅ 成功获取 {district_name} 中心坐标: ({result['center']['lat']}, {result['center']['lng']})")
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ 获取区域中心坐标失败: {str(e)}")
        print(f"📋 错误详情: {traceback.format_exc()}")
        
        # 🔍 根据错误类型返回不同的状态码
        if "not found" in str(e).lower():
            return jsonify({
                "success": False,
                "error": "District not found",
                "message": f"District '{district_name}' not found in database",
                "district_name": district_name
            }), 404
        elif "no listings" in str(e).lower():
            return jsonify({
                "success": False,
                "error": "No data available",
                "message": f"District '{district_name}' has no listing data",
                "district_name": district_name
            }), 404
        else:
            return jsonify({
                "success": False,
                "error": "Internal server error",
                "message": f"Failed to get district center: {str(e)}",
                "district_name": district_name
            }), 500


@api.route('/map-markers/districts', methods=['GET'])
def get_available_districts():
    """
    获取可用区域列表接口
    
    Returns:
        JSON: 可用区域列表
    """
    
    try:
        print("📋 请求可用区域列表")
        
        # 🗄️ 查询所有可用的大区域和小区域
        sql = """
        SELECT 
            neighbourhood_group_cleansed AS neighbourhood_group,
            neighbourhood_cleansed AS neighbourhood,
            COUNT(*) as listing_count
        FROM listings 
        WHERE neighbourhood_group_cleansed IS NOT NULL
          AND neighbourhood_cleansed IS NOT NULL
          AND neighbourhood_group_cleansed != ''
          AND neighbourhood_cleansed != ''
        GROUP BY neighbourhood_group_cleansed, neighbourhood_cleansed
        HAVING listing_count > 0
        ORDER BY neighbourhood_group_cleansed, neighbourhood_cleansed
        """
        
        from db import execute_query
        results = execute_query(sql)
        
        # 📊 组织数据结构
        districts = {}
        for row in results:
            district_group = row['neighbourhood_group']
            neighbourhood = row['neighbourhood']
            listing_count = row['listing_count']
            
            if district_group not in districts:
                districts[district_group] = {
                    "name": district_group,
                    "total_listings": 0,
                    "neighbourhoods": []
                }
            
            districts[district_group]["total_listings"] += listing_count
            districts[district_group]["neighbourhoods"].append({
                "name": neighbourhood,
                "listing_count": listing_count
            })
        
        # 📋 转换为列表格式
        district_list = list(districts.values())
        
        # 📊 计算统计信息
        total_districts = len(district_list)
        total_neighbourhoods = sum(len(d["neighbourhoods"]) for d in district_list)
        total_listings = sum(d["total_listings"] for d in district_list)
        
        print(f"✅ 返回 {total_districts} 个大区域, {total_neighbourhoods} 个小区域, 共 {total_listings} 个房源")
        
        return jsonify({
            "success": True,
            "districts": district_list,
            "statistics": {
                "total_districts": total_districts,
                "total_neighbourhoods": total_neighbourhoods,
                "total_listings": total_listings
            },
            "message": f"Successfully retrieved {total_districts} districts with {total_neighbourhoods} neighbourhoods"
        })
        
    except Exception as e:
        print(f"❌ 获取可用区域列表失败: {str(e)}")
        print(f"📋 错误详情: {traceback.format_exc()}")
        
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": f"Failed to fetch available districts: {str(e)}"
        }), 500

# Map Heatmap 分布
@api.route('/stats/map_distribution', methods=['GET'])
def map_distribution():
    """
    为前端 ECharts heatmap 提供每个行政区（或小区）的中心点和强度。
    Query Params:
      - level: 'district' or 'neighbourhood'
      - name: groupName（大区名称或小区名称）
    """
    level       = request.args.get('level')
    district    = request.args.get('name')
    price_min   = request.args.get('price_min', type=float)
    price_max   = request.args.get('price_max', type=float)
    room_type   = request.args.get('room_type', type=str)
    min_reviews = request.args.get('min_reviews', type=int)

    # 1) 构建 WHERE 子句
    where = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
    if level == 'neighbourhood' and district:
        safe = district.replace("'", "''")
        where.append(f"neighbourhood_group_cleansed = '{safe}'")
    if price_min is not None:
        where.append(f"price >= {price_min}")
    if price_max is not None:
        where.append(f"price <= {price_max}")
    if room_type:
        safe = room_type.replace("'", "''")
        where.append(f"room_type = '{safe}'")
    if min_reviews is not None:
        where.append(f"number_of_reviews >= {min_reviews}")
    where_clause = " AND ".join(where)

    # 2) 设置分组字段
    group_field = "neighbourhood_cleansed" if level == 'neighbourhood' else "neighbourhood_group_cleansed"

    # 3) 编写 MySQL 兼容 SQL
    sql = f"""
    SELECT 
        {group_field} AS area_name,
        ROUND(AVG(longitude), 6) AS center_lng,
        ROUND(AVG(latitude), 6)  AS center_lat,
        COUNT(*) AS listing_count
    FROM listings
    WHERE {where_clause}
    GROUP BY {group_field}
    ORDER BY listing_count DESC;
    """

    df = execute_query(sql)
    records = df.to_dict('records')

    if not records:
        return jsonify({"coords": [], "values": []})

    max_count = max(r['listing_count'] for r in records if r['listing_count'] is not None)

    coords = []
    values = []
    for r in records:
        coords.append([r['center_lng'], r['center_lat']])
        values.append(round(r['listing_count'] / max_count, 4) if max_count else 0)

    return jsonify({
        "coords": coords,
        "values": values
    })

# 方形（栅格）分布
@api.route('/stats/square_distribution', methods=['GET'])
def square_distribution():
    """
    返回指定层级和区域下的栅格统计：
    将经纬度按小数点后两位截断，分箱计数，前端可以用 heatmap 或 custom 绘制方格图。
    Query Params 同上。
    """
    level      = request.args.get('level')
    name       = request.args.get('name')
    price_min  = request.args.get('price_min', type=float)
    price_max  = request.args.get('price_max', type=float)
    room_type  = request.args.get('room_type', type=str)
    min_reviews= request.args.get('min_reviews', type=int)

    where = ["latitude IS NOT NULL", "longitude IS NOT NULL"]
    if level == 'neighbourhood' and name:
        safe = name.replace("'", "''")
        where.append(f"neighbourhood_group_cleansed = '{safe}'")
    if price_min is not None:
        where.append(f"price >= {price_min}")
    if price_max is not None:
        where.append(f"price <= {price_max}")
    if room_type:
        safe = room_type.replace("'", "''")
        where.append(f"room_type = '{safe}'")
    if min_reviews is not None:
        where.append(f"number_of_reviews >= {min_reviews}")
    where_clause = " AND ".join(where)

    # 分箱：将经纬度截断到小数点后两位
    sql = f"""
      SELECT
        CAST(longitude AS DECIMAL(10,2)) AS lng_bin,
        CAST(latitude  AS DECIMAL(10,2)) AS lat_bin,
        COUNT(*) AS cnt
      FROM listings
      WHERE {where_clause}
      GROUP BY lng_bin, lat_bin
    """
    df = execute_query(sql)
    records = df.to_dict('records')

    bins = [
      {"x": r['lng_bin'], "y": r['lat_bin'], "value": r['cnt']}
      for r in records
    ]
    return jsonify({"bins": bins})


@api.route('/user/selection', methods=["GET"])
def user_selection():
    """
    接收前端区域/维度选择：
      GET /user/selection?level=neighbourhood_group|neighbourhood|room_type&name=…
    把选中的 neighbourhood_group/neighbourhood/room_type 写入 ConversationState.preferences，
    并根据完整度切换阶段，最终返回新的偏好和完整度给前端（仅同步状态，不做额外数据返回）。
    """
    # 1) 读取参数
    level = request.args.get("level")         # 'neighbourhood_group' | 'neighbourhood' | 'room_type'
    name  = request.args.get("name")          # 选中的名称
    session_id = request.args.get("session_id") or str(uuid.uuid4())

    if level not in ("neighbourhood_group", "neighbourhood", "room_type") or not name:
        return jsonify({"error": "参数 level/name 缺失或不合法"}), 400

    # 2) 获取当前会话状态
    conv_state = get_conversation_state(session_id)

    # 3) 根据层级写入偏好
    if level == "neighbourhood_group":
        conv_state.preferences["neighbourhood_group"] = name
    elif level == "neighbourhood":
        conv_state.preferences["neighbourhood"] = name
    elif level == "room_type":
        conv_state.preferences["room_type"] = name

    # 4) 更新阶段：如果已经齐了足够偏好就进入推荐就绪
    if conv_state.is_ready_for_recommendations():
        conv_state.update_stage(ChatStage.RECOMMENDATION_READY)
    else:
        conv_state.update_stage(ChatStage.PREFERENCE_COLLECTION)


    # 5) 返回给前端
    return jsonify({
        "message":       f"{level} 已设为 {name}",
        "preferences":   conv_state.preferences,
        "stage":         conv_state.stage.value,
        "completeness":  conv_state.get_completeness_score(),

    })


@api.route('/test/visualization', methods=['POST'])
def test_visualization():
    """
    测试可视化功能的独立接口，提取自rag_chat函数的可视化部分
    
    请求参数:
    - user_message: 用户消息
    - session_id: 会话ID
    - force_stage: 可选，强制设置会话阶段（用于测试）
    - force_preferences: 可选，强制设置偏好（用于测试）
    
    返回:
    与rag_chat接口相同格式的可视化相关响应
    """
    try:
        data = request.json
        user_message = data.get("message", "")
        session_id = data.get("session_id") or str(uuid.uuid4())
        force_stage = data.get("force_stage")
        force_preferences = data.get("force_preferences")
        
        print(f"🧪 测试可视化功能: '{user_message}'")
        
        # 获取会话状态
        conv_state = get_conversation_state(session_id)
        
        # 如果提供了强制阶段，则设置
        if force_stage:
            try:
                conv_state.stage = ChatStage[force_stage]
                print(f"🔄 强制设置会话阶段为: {force_stage}")
            except KeyError:
                print(f"⚠️ 无效的会话阶段: {force_stage}")
                
        # 如果提供了强制偏好，则设置
        if force_preferences:
            for key, value in force_preferences.items():
                conv_state.preferences[key] = value
            print(f"🔄 强制设置偏好: {force_preferences}")
            
        # 创建基本路由结果对象（简化版）
        routing_result = {
            "route": "conversational",
            "intent": "general",
            "new_stage": conv_state.stage,
            "confidence": 0.9
        }
            
        # 初始化结果对象
        result = {
            "answer": "这是一个可视化测试响应",
            "source_documents": [],
            "route_info": {
                "route_type": "test_visualization",
                "intent": routing_result["intent"],
                "stage": conv_state.stage.value
            }
        }
        
        # 🎯 检查偏好完整度和必要偏好
        print("🎨 开始智能可视化处理检查...")
        essential_prefs = conv_state.has_essential_preferences()
        
        # 如果必要偏好都已填写，则生成总结
        if essential_prefs["is_complete"] and not getattr(conv_state, 'summary_generated', False):
            print(f"🎯 必要偏好已全部收集，生成偏好总结")
            preference_summary = generate_preference_summary(conv_state.preferences)
            result["preference_summary"] = preference_summary
            result["essential_preferences_complete"] = True
            result["stage_transition"] = {
                "from": "preference_collection",
                "to": "exploration",
                "message": "Essential preferences collected. Moving to exploration phase."
            }
            # 标记已生成总结，避免重复生成
            setattr(conv_state, 'summary_generated', True)
            # 更新阶段状态
            if conv_state.stage.value == "preference_collection":
                conv_state.stage = ChatStage.EXPLORATION
                print("🎯 阶段转换：从偏好收集进入到探索阶段")
        elif essential_prefs["is_complete"] and getattr(conv_state, 'summary_generated', False):
            print("🎯 必要偏好已全部收集，总结已生成")
            result["essential_preferences_complete"] = True
        else:
            # 如果必要偏好不完整，添加缺失信息
            if not essential_prefs["is_complete"] and not result.get("answer"):
                missing_dims = essential_prefs["missing"]
                missing_text = ", ".join(missing_dims)
                print(f"🎯 缺少必要偏好: {missing_text}")
                result["missing_preferences"] = missing_dims
                result["essential_preferences_complete"] = False

        # 只在非偏好收集阶段生成可视化内容
        viz_result = {"show_visualization": False, "reason": "preference_collection_stage"}
        print(f"🎨 当前阶段: {conv_state.stage}")
        print(f"🎨 当前阶段: {conv_state.stage.value}")
        if essential_prefs["is_complete"]:
            print("🎨 非偏好收集阶段，开始生成可视化内容...")
            # 🎯 使用智能可视化管理器
            viz_result = smart_viz_manager.generate_contextual_visualization(
                user_message, conv_state, routing_result
            )
            print(f"🎨 可视化决策: {viz_result.get('show_visualization', False)}")
            print(f"🎨 决策原因: {viz_result.get('reason', 'unknown')}")
        else:
            print("🎨 偏好收集阶段，跳过可视化生成")

        # 🎯 将可视化信息添加到结果中
        if viz_result["show_visualization"]:
            # 新的可视化字段
            result["visualizations"] = viz_result["visualizations"]
            result["chart_suggestions"] = viz_result["chart_suggestions"]
            result["show_visualization_prompt"] = True
            result["visualization_message"] = viz_result["visualization_message"]
            result["user_budget_info"] = viz_result.get("user_budget_info", {})
            
            # 兼容原有字段
            result["show_visualization_suggestions"] = True
            result["visualization_filters"] = extract_visualization_filters(conv_state.preferences)
            
            print(f"✅ 已添加可视化信息: {len(viz_result['visualizations'])} 个图表")
        else:
            result["show_visualization_prompt"] = False
            result["show_visualization_suggestions"] = False
            print(f"ℹ️ 未添加可视化: {viz_result.get('reason', 'unknown')}")
        
        # 添加调试信息
        result["debug_info"] = {
            "session_id": session_id,
            "conversation_stage": conv_state.stage.value,
            "preferences": conv_state.preferences,
            "completeness_score": conv_state.get_completeness_score(),
            "preference_count": conv_state.get_preference_count(),
            "conversation_turns": len(conv_state.conversation_history),
            "visualization_decision": viz_result.get("reason", "not_analyzed"),
            "is_test_endpoint": True
        }
        
        return jsonify(result)
    
    except Exception as e:
        print(f"❌ 可视化测试接口处理出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": f"Visualization test failed: {str(e)}",
            "traceback": traceback.format_exc()
        }), 500

# 评论洞察模块

# -------------------------------------------------------------------
# 1) 评论汇总接口（用 listings.number_of_reviews 代替"总评论数"）
#    - totalComments         = SUM(number_of_reviews)
#    - avgCommentsPerListing = AVG(number_of_reviews)
#    - uniqueHosts           = COUNT(DISTINCT host_id)
# -------------------------------------------------------------------
@api.route('/api/comments/summary', methods=['GET'])
def comments_summary():
    level = request.args.get('level', 'district')
    name  = request.args.get('name', '')  # groupName

    where = ["number_of_reviews IS NOT NULL"]
    if level == 'neighbourhood' and name:
        safe = name.replace("'", "''")
        where.append(f"neighbourhood_group_cleansed = '{safe}'")
    where_clause = " AND ".join(where)

    sql = f"""
      SELECT
        SUM(number_of_reviews)                   AS total_comments,
        ROUND(AVG(number_of_reviews),2)          AS avg_comments_per_listing,
        COUNT(DISTINCT host_id)                  AS unique_hosts
      FROM listings
      WHERE {where_clause}
    """
    df = execute_query(sql)
    # 如果没有数据，填 0
    if df.empty:
        result = {
            "totalComments": 0,
            "avgCommentsPerListing": 0.0,
            "uniqueHosts": 0
        }
    else:
        row = df.iloc[0]
        result = {
            "totalComments":        int(row["total_comments"] or 0),
            "avgCommentsPerListing":float(row["avg_comments_per_listing"] or 0.0),
            "uniqueHosts":          int(row["unique_hosts"] or 0)
        }

    return jsonify(result), 200

@api.route('/comments/wordcloud', methods=['GET'])
def comments_wordcloud():
    """
    返回评论关键词词频列表
    Query params: level, name
    """
    try:
        level = request.args.get('level')
        name  = request.args.get('name')
        # 假设已经有 reviews_keywords(word, count, level, name) 视图
        safe = name.replace("'", "''")
        sql = f"""
          SELECT word, count
          FROM reviews_keywords
          WHERE level = '{level}' AND name = '{safe}'
          ORDER BY count DESC
          LIMIT 100
        """
        df = execute_query(sql)
        return jsonify(df.to_dict('records'))
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------------
# 3) 评论情感比例 —— 因为没有 sentiment_score 字段，这里用 reviews_per_month
#    做一个「评论频率分布」示例：低(<1/mo)、中(1-5)、高(>5)
# -------------------------------------------------------------------
@api.route('/api/comments/sentiment', methods=['GET'])
def comments_sentiment():
    level = request.args.get('level', 'district')
    name  = request.args.get('name', '')

    where = ["reviews_per_month IS NOT NULL"]
    if level == 'neighbourhood' and name:
        safe = name.replace("'", "''")
        where.append(f"neighbourhood_group_cleansed = '{safe}'")
    where_clause = " AND ".join(where)

    sql = f"""
      SELECT reviews_per_month
      FROM listings
      WHERE {where_clause}
    """
    df = execute_query(sql)

    # 分段计数
    low  = int((df['reviews_per_month'] < 1).sum())
    mid  = int(((df['reviews_per_month'] >= 1) & (df['reviews_per_month'] <= 5)).sum())
    high = int((df['reviews_per_month'] > 5).sum())
    total = low + mid + high or 1

    return jsonify({
        "positive": round(high/total,2),
        "neutral":  round(mid/total,2),
        "negative": round(low/total,2)
    }), 200

# -------------------------------------------------------------------
# 4) 用户聚类 —— 因为没有聚类结果表，这里把每个 listing 的 (price, number_of_reviews) 当作"特征"
#    前端可以当成示例散点图来展示
# -------------------------------------------------------------------
@api.route('/comments/user_clusters', methods=['GET'])
def comments_user_clusters():
    level = request.args.get('level', 'district')
    name  = request.args.get('name', '')

    where = ["price IS NOT NULL", "number_of_reviews IS NOT NULL"]
    if level == 'neighbourhood' and name:
        safe = name.replace("'", "''")
        where.append(f"neighbourhood_group_cleansed = '{safe}'")
    where_clause = " AND ".join(where)

    sql = f"""
      SELECT price, number_of_reviews
      FROM listings
      WHERE {where_clause}
      LIMIT 500
    """
    df = execute_query(sql)

    # 前端期望 {x, y, clusterId} 数组，这里 clusterId 都写成 "0"
    clusters = [
      {"x": float(row["price"]), "y": float(row["number_of_reviews"]), "clusterId": "0"}
      for _, row in df.iterrows()
    ]

    return jsonify(clusters), 200

@api.route('/heat-points', methods=['GET'])
def get_heat_points():
    """
    返回热力图所需的大量点：
      GET /heat-points?district_name=...&price_min=...&price_max=...&room_type=...&min_reviews=...&
                   bbox=minLng,minLat,maxLng,maxLat&weight_by=uniform|reviews|price&
                   max_points=20000&format=json|geojson
    """
    try:
        # 1) 取参数
        district_name = request.args.get('district_name')
        price_min = request.args.get('price_min', type=float)
        price_max = request.args.get('price_max', type=float)
        room_type = request.args.get('room_type')
        min_reviews = request.args.get('min_reviews', type=int)
        weight_by = request.args.get('weight_by', default='uniform')
        max_points = request.args.get('max_points', default=20000, type=int)
        fmt = request.args.get('format', default='json')

        # bbox: minLng,minLat,maxLng,maxLat
        bbox_arg = request.args.get('bbox')
        bbox = None
        if bbox_arg:
            try:
                parts = [float(x) for x in bbox_arg.split(',')]
                if len(parts) == 4:
                    bbox = (parts[0], parts[1], parts[2], parts[3])
            except ValueError:
                return jsonify({
                    "success": False,
                    "message": "Invalid bbox. Expected 'minLng,minLat,maxLng,maxLat'."
                }), 400

        # 2) 轻量校验（沿用你已有的校验逻辑）
        errors = MapMarkersService.validate_filters(price_min, price_max, room_type, min_reviews)
        if errors:
            return jsonify({
                "success": False,
                "error": "Parameter validation failed",
                "details": errors
            }), 400

        if weight_by not in ('uniform', 'reviews', 'price'):
            return jsonify({
                "success": False,
                "error": "Invalid weight_by",
                "message": "weight_by must be one of 'uniform','reviews','price'"
            }), 400

        if max_points <= 0 or max_points > 200000:
            return jsonify({
                "success": False,
                "error": "Invalid max_points",
                "message": "max_points must be 1~200000"
            }), 400

        # 3) 取数
        as_geojson = (fmt == 'geojson')
        result = MapMarkersService.get_heat_points(
            price_min=price_min,
            price_max=price_max,
            room_type=room_type,
            min_reviews=min_reviews,
            district_name=district_name,
            bbox=bbox,
            weight_by=weight_by,
            max_points=max_points,
            as_geojson=as_geojson
        )

        # 4) 包装返回
        payload = {
            "success": True,
            "filters_applied": {
                "district_name": district_name,
                "price_min": price_min,
                "price_max": price_max,
                "room_type": room_type,
                "min_reviews": min_reviews,
                "bbox": bbox,
                "weight_by": weight_by,
                "max_points": max_points,
                "format": fmt
            },
            "count": result.get("count", 0)
        }
        if as_geojson:
            payload["geojson"] = result.get("geojson", {"type":"FeatureCollection","features":[]})
        else:
            payload["points"] = result.get("points", [])

        return jsonify(payload)

    except Exception as e:
        print(f"❌ /heat-points 接口失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": f"Failed to fetch heat points: {str(e)}"
        }), 500

@api.route('/api/value-for-money', methods=['GET'])
def value_for_money():
    """
    计算并返回"性价比（Value-for-money）"数据。

    Query params:
      - level: 'district' | 'neighbourhood'
      - name: 当 level='neighbourhood' 时为父区名；level='district' 时可为 'ALL' 或具体大区
      - price_min, price_max, room_type, min_reviews
      - top_n: 默认 12（district），30（neighbourhood）
    """
    try:
        level = request.args.get('level', default='district', type=str)
        name = request.args.get('name', default='ALL', type=str)
        price_min = request.args.get('price_min', type=float)
        price_max = request.args.get('price_max', type=float)
        room_type = request.args.get('room_type', type=str)
        min_reviews = request.args.get('min_reviews', default=0, type=int)
        top_n = request.args.get('top_n', type=int)

        if level not in ('district', 'neighbourhood'):
            return jsonify({
                "success": False,
                "error": "Invalid level",
                "message": "level must be 'district' or 'neighbourhood'"
            }), 400

        # 默认 top_n
        if top_n is None:
            top_n = 12 if level == 'district' else 30

        # 校验筛选参数（沿用已有校验逻辑）
        validation_errors = MapMarkersService.validate_filters(price_min, price_max, room_type, min_reviews)
        if validation_errors:
            return jsonify({
                "success": False,
                "error": "Parameter validation failed",
                "details": validation_errors
            }), 400

        # 组装 WHERE 子句
        where_conditions = [
            "price IS NOT NULL",
            "price > 0"
        ]

        if level == 'neighbourhood':
            if not name or not name.strip():
                return jsonify({
                    "success": False,
                    "error": "Missing parameter",
                    "message": "name (parent district) is required when level is 'neighbourhood'"
                }), 400
            safe_name = name.strip().replace("'", "''")
            where_conditions.append(f"neighbourhood_group_cleansed = '{safe_name}'")
        else:
            # level == 'district'
            if name and name.strip() and name.strip().upper() != 'ALL':
                safe_name = name.strip().replace("'", "''")
                where_conditions.append(f"neighbourhood_group_cleansed = '{safe_name}'")

        if price_min is not None:
            where_conditions.append(f"price >= {float(price_min)}")
        if price_max is not None:
            where_conditions.append(f"price <= {float(price_max)}")
        if room_type and room_type.strip():
            safe_room_type = room_type.strip().replace("'", "''")
            where_conditions.append(f"room_type = '{safe_room_type}'")
        if min_reviews is not None and min_reviews > 0:
            where_conditions.append(f"number_of_reviews >= {int(min_reviews)}")

        where_clause = " AND ".join(where_conditions)

        # 设定分组字段
        group_field = 'neighbourhood_group_cleansed' if level == 'district' else 'neighbourhood_cleansed'

        # 取所需字段（逐条 listing，用 pandas 聚合计算分位数等）
        sql = f"""
        SELECT
            {group_field} AS area_name,
            price,
            number_of_reviews,
            reviews_per_month
        FROM listings
        WHERE {where_clause}
        """
        df = execute_query(sql)

        # 空结果处理
        if df is None or df.empty:
            return jsonify({
                "success": True,
                "city_baseline": {
                    "city_median_price": 0,
                    "city_popularity_avg": 0
                },
                "items": [],
                "meta": {
                    "level": level,
                    "name": name,
                    "filters_applied": {
                        "price_min": price_min,
                        "price_max": price_max,
                        "room_type": room_type,
                        "min_reviews": min_reviews
                    },
                    "computed_at": datetime.utcnow().isoformat() + 'Z'
                }
            }), 200

        # 计算城市基线
        df_prices = df['price'].astype(float)
        city_median_price = float(df_prices.median()) if not df_prices.empty else 0.0
        city_popularity_avg = float(df['reviews_per_month'].fillna(0).astype(float).mean())
        p90_reviews = float(df['number_of_reviews'].fillna(0).astype(float).quantile(0.90))
        if p90_reviews <= 0:
            p90_reviews = 1.0

        # 分组计算
        grouped = df.copy()
        grouped['price'] = grouped['price'].astype(float)
        grouped['number_of_reviews'] = grouped['number_of_reviews'].fillna(0).astype(float)
        grouped['reviews_per_month'] = grouped['reviews_per_month'].fillna(0).astype(float)

        items = []
        for area_name, g in grouped.groupby('area_name'):
            listing_count = int(len(g))
            if listing_count == 0:
                continue

            median_price = float(g['price'].median())
            p25_price = float(g['price'].quantile(0.25))
            p75_price = float(g['price'].quantile(0.75))

            # 人气：用 reviews_per_month 的均值
            popularity_score = float(g['reviews_per_month'].mean())

            # 评论总数
            review_count = int(g['number_of_reviews'].sum())

            # 指标归一化
            norm_popularity = (popularity_score / city_popularity_avg) if city_popularity_avg > 0 else 0.0
            # 控制极端值：简单裁剪到 [0, 3]
            norm_popularity = max(0.0, min(norm_popularity, 3.0))

            norm_log_reviews = 0.0
            if p90_reviews > 0:
                norm_log_reviews = math.log(1.0 + max(0, review_count)) / math.log(1.0 + p90_reviews)
            norm_log_reviews = max(0.0, min(norm_log_reviews, 3.0))

            # 质量指数（无评分场景）
            if city_popularity_avg > 0:
                quality_index = 0.7 * norm_popularity + 0.3 * norm_log_reviews
            else:
                # 兜底：只用评论量强度
                quality_index = norm_log_reviews

            # 价格指数
            price_index = (median_price / city_median_price) if city_median_price > 0 else 0.0
            price_index = max(price_index, 1e-6)

            # 性价比分数（越大越划算）
            value_score = quality_index / price_index

            # 置信度
            confidence = 'High' if listing_count >= 300 else ('Medium' if listing_count >= 100 else 'Low')

            items.append({
                "name": area_name,
                "listing_count": listing_count,
                "median_price": int(round(median_price)) if median_price == median_price else 0,
                "p25_price": int(round(p25_price)) if p25_price == p25_price else 0,
                "p75_price": int(round(p75_price)) if p75_price == p75_price else 0,
                "popularity_score": round(popularity_score, 2),
                "review_count": review_count,
                "price_index": round(price_index, 3),
                "quality_index": round(quality_index, 3),
                "value_score": round(value_score, 3),
                "confidence": confidence
            })

        # 排序并裁剪
        items.sort(key=lambda x: x['value_score'], reverse=True)
        if top_n and top_n > 0:
            items = items[:top_n]

        payload = {
            "success": True,
            "city_baseline": {
                "city_median_price": int(round(city_median_price)) if city_median_price == city_median_price else 0,
                "city_popularity_avg": round(city_popularity_avg, 2)
            },
            "items": items,
            "meta": {
                "level": level,
                "name": name,
                "filters_applied": {
                    "price_min": price_min,
                    "price_max": price_max,
                    "room_type": room_type,
                    "min_reviews": min_reviews
                },
                "computed_at": datetime.utcnow().isoformat() + 'Z'
            }
        }
        return jsonify(payload)

    except Exception as e:
        import traceback
        print(f"❌ /api/value-for-money 失败: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": f"Failed to compute value-for-money: {str(e)}"
        }), 500