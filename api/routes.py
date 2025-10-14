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
from chart_generators.comments_wordcloud import generate as wc_generate
from scripetdAPI.reviews_overview_service import compute_reviews_overview, compute_reviews_sentiment, compute_reviews_top_phrases

import json
import uuid
import re
import math
import time
import os

# 🆕 analytics helpers
from db import db
from analysis_log.analytics_logger import log_session_metrics
from analysis_log.likert_logger import log_likert_feedback

# 🆕 预计算：词云全量生成接口依赖
try:
    from chart_generators.precompute.wordcloud_precompute import list_areas as wc_list_areas, precompute_for_area as wc_precompute_for_area
    _wc_precompute_available = True
except Exception as _e:
    print(f"⚠️ 词云预计算模块不可用: {_e}")
    _wc_precompute_available = False


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

# 脚本模式的 接口
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

            # 🆕 Ensure description present
            try:
                ids_for_desc = [int(item.get("id")) for item in (recommended or []) if item.get("id")]
                if ids_for_desc:
                    id_list = ",".join(str(i) for i in sorted(set(ids_for_desc)))
                    df_desc = execute_query(f"SELECT id, description FROM listings WHERE id IN ({id_list})")
                    if df_desc is not None and not df_desc.empty:
                        desc_map = {int(row['id']): (row['description'] or '') for _, row in df_desc.iterrows()}
                        for item in recommended:
                            iid = int(item.get("id") or 0)
                            if not iid:
                                continue
                            desc = desc_map.get(iid, "")
                            if desc is not None:
                                item["description"] = str(desc)
            except Exception:
                pass

            # 🆕 Ensure table fields present (review_scores_value, accommodates, bathrooms, bathrooms_text, bedrooms, beds, amenities)
            try:
                ids_for_fields = [int(item.get("id")) for item in (recommended or []) if item.get("id")]
                if ids_for_fields:
                    id_list2 = ",".join(str(i) for i in sorted(set(ids_for_fields)))
                    df_extra = execute_query(
                        f"SELECT id, review_scores_value, accommodates, bathrooms, bathrooms_text, bedrooms, beds, amenities FROM listings WHERE id IN ({id_list2})"
                    )
                    if df_extra is not None and not df_extra.empty:
                        extra_map = {
                            int(r['id']): {
                                'review_scores_value': r.get('review_scores_value'),
                                'accommodates': r.get('accommodates'),
                                'bathrooms': r.get('bathrooms'),
                                'bathrooms_text': r.get('bathrooms_text'),
                                'bedrooms': r.get('bedrooms'),
                                'beds': r.get('beds'),
                                'amenities': r.get('amenities'),
                            }
                            for _, r in df_extra.iterrows()
                        }
                        for item in recommended:
                            iid = int(item.get('id') or 0)
                            if not iid:
                                continue
                            extra = extra_map.get(iid) or {}
                            for k, v in extra.items():
                                if k not in item or item.get(k) is None:
                                    # amenities 原样透传（若引擎已生成数组则不覆盖）
                                    if k == 'amenities' and isinstance(item.get('amenities'), list):
                                        continue
                                    item[k] = v
            except Exception:
                pass

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

        # 🆕 Ensure description present
        try:
            ids_for_desc = [int(item.get("id")) for item in (recommended or []) if item.get("id")]
            if ids_for_desc:
                id_list = ",".join(str(i) for i in sorted(set(ids_for_desc)))
                df_desc = execute_query(f"SELECT id, description FROM listings WHERE id IN ({id_list})")
                if df_desc is not None and not df_desc.empty:
                    desc_map = {int(row['id']): (row['description'] or '') for _, row in df_desc.iterrows()}
                    for item in recommended:
                        iid = int(item.get("id") or 0)
                        if not iid:
                            continue
                        desc = desc_map.get(iid, "")
                        if desc is not None:
                            item["description"] = str(desc)
        except Exception:
            pass

        # 🆕 Ensure table fields present (review_scores_value, accommodates, bathrooms, bathrooms_text, bedrooms, beds, amenities)
        try:
            ids_for_fields = [int(item.get("id")) for item in (recommended or []) if item.get("id")]
            if ids_for_fields:
                id_list2 = ",".join(str(i) for i in sorted(set(ids_for_fields)))
                df_extra = execute_query(
                    f"SELECT id, review_scores_value, accommodates, bathrooms, bathrooms_text, bedrooms, beds, amenities FROM listings WHERE id IN ({id_list2})"
                )
                if df_extra is not None and not df_extra.empty:
                    extra_map = {
                        int(r['id']): {
                            'review_scores_value': r.get('review_scores_value'),
                            'accommodates': r.get('accommodates'),
                            'bathrooms': r.get('bathrooms'),
                            'bathrooms_text': r.get('bathrooms_text'),
                            'bedrooms': r.get('bedrooms'),
                            'beds': r.get('beds'),
                            'amenities': r.get('amenities'),
                        }
                        for _, r in df_extra.iterrows()
                    }
                    for item in recommended:
                        iid = int(item.get('id') or 0)
                        if not iid:
                            continue
                        extra = extra_map.get(iid) or {}
                        for k, v in extra.items():
                            if k not in item or item.get(k) is None:
                                if k == 'amenities' and isinstance(item.get('amenities'), list):
                                    continue
                                item[k] = v
        except Exception:
            pass

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

        # ✅ 预算上下限自动纠正（倒挂预算修正 + 非负约束）
        def _normalize_budget_in_preferences(prefs: dict) -> dict:
            try:
                pmin = prefs.get('price_min')
                pmax = prefs.get('price_max')
                # 仅在两者同时存在且为数字时处理
                if isinstance(pmin, (int, float)) and isinstance(pmax, (int, float)):
                    # 非负约束
                    if pmin is not None and pmin < 0:
                        pmin = 0
                    if pmax is not None and pmax < 0:
                        pmax = 0
                    # 倒挂修正：若最小值大于最大值，则交换
                    if pmin is not None and pmax is not None and pmin > pmax:
                        print(f"⚠️ 检测到倒挂预算，将交换区间: min={pmin}, max={pmax}")
                        pmin, pmax = pmax, pmin
                    prefs['price_min'] = pmin
                    prefs['price_max'] = pmax
                else:
                    # 单边或非数字时，仅做非负约束
                    if isinstance(prefs.get('price_min'), (int, float)) and prefs['price_min'] is not None and prefs['price_min'] < 0:
                        prefs['price_min'] = 0
                    if isinstance(prefs.get('price_max'), (int, float)) and prefs['price_max'] is not None and prefs['price_max'] < 0:
                        prefs['price_max'] = 0
            except Exception as _e:
                pass
            return prefs

        conv_state.preferences = _normalize_budget_in_preferences(conv_state.preferences)

        
        # 🎯 第二步：智能路由判断（保持原有逻辑）
        routing_result = route_conversation(user_message, history, conv_state)
        print(f"路由决策: {routing_result}")

        # ✅ 可选增强：在第二阶段且显式请求图表时，避免被 preference_prompt 抢走
        try:
            msg_lower = (user_message or "").lower()
            explicit_keywords = smart_viz_manager.show_viz_scenarios["explicit_request"]["keywords"]
            stage_val = getattr(conv_state.stage, 'value', str(conv_state.stage)).lower()
            if stage_val == "exploration" and any(k in msg_lower for k in explicit_keywords):
                # 显式要图已在探索阶段，允许可视化流优先
                routing_result["route"] = routing_result.get("route") or "conversational"
                print("✅ 显式图表请求在探索阶段，允许可视化流程优先")
        except Exception as _e:
            pass

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

        # ✅ 第二阶段开始后，重置并裁剪历史：总长度（user+system）<=10
        try:
            stage_val_for_trim = getattr(conv_state.stage, 'value', str(conv_state.stage)).lower()
            if stage_val_for_trim in ["exploration", "recommendation_shown", "refinement"]:
                trimmed = []
                # 将最新一轮作为起点，然后向前取最多9条
                recent_history = list(history)[-9:] if isinstance(history, list) else []
                # 仅保留必要字段，避免噪声
                for h in recent_history:
                    if isinstance(h, dict):
                        trimmed.append({k: h.get(k) for k in ("type", "data") if k in h})
                # 写回会话状态（用于后续模型上下文）
                conv_state.conversation_history = trimmed
                print(f"🧹 第二阶段启用：已裁剪历史到 {len(trimmed)} 条")
        except Exception as _e:
            pass
        
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
                "intent": "reviews_analysis",  # 明确指定意图为 reviews_analysis
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
                
            # 对话式回应：如果关键维度未齐全，则走追问并返回结构化元数据；否则进入自由对话
            essential = conv_state.has_essential_preferences()
            if not essential["is_complete"]:
                from rag_module.follow_up.preference_follow_up import generate_single_followup as new_generate_single_followup
                followup_question = new_generate_single_followup(conv_state, user_message)
                response_text = followup_question.get("question", "Tell me more about your preferences!")
                
                result = {
                    "answer": response_text,
                    "source_documents": [],
                    "route_info": {
                        "route_type": "conversational",
                        "intent": routing_result["intent"],
                        "stage": conv_state.stage.value,
                        "missing_preferences": conv_state.get_missing_critical_preferences()
                    },
                    "message_type": "intelligent_followup",
                    "decision_card": {
                        "should_update": True,
                        "preferences": conv_state.preferences.copy(),
                        "completeness_score": conv_state.get_completeness_score(),
                        "preference_count": conv_state.get_preference_count(),
                        "missing_critical": conv_state.get_missing_critical_preferences(),
                        "stage": conv_state.stage.value
                    },
                    "followup_info": {
                        "ready_for_recommendation": followup_question.get("ready_for_recommendation", False),
                        "followup_question": followup_question,
                        "completeness_score": conv_state.get_completeness_score(),
                        "strategy": "targeted_followup",
                        "target_dimensions": [followup_question.get("target_dimension")] if followup_question.get("target_dimension") else []
                    }
                }
            else:
                # 关键维度齐全：自由对话简短回应
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
        # 阶段号标注：Phase 1 = preference_collection, Phase 2 = exploration/recommendation_shown/refinement
        print("🎨 开始智能可视化处理检查 (Phase tagging enabled)...")

        # 🎯 检查偏好完整度和必要偏好，生成总结
        essential_prefs = conv_state.has_essential_preferences()

        # 如果必要偏好都已填写：生成总结，并强制切换到 EXPLORATION（若仍在 preference_collection）
        if essential_prefs["is_complete"]:
            # 生成/刷新偏好总结（幂等）
            preference_summary = generate_preference_summary(conv_state.preferences)
            result["preference_summary"] = preference_summary
            result["essential_preferences_complete"] = True

            # 强制切换阶段（移除一次性开关的限制）
            if getattr(conv_state.stage, 'value', str(conv_state.stage)) == "preference_collection":
                result["stage_transition"] = {
                    "from": "preference_collection",
                    "to": "exploration",
                    "message": "Essential preferences collected. Moving to exploration phase."
                }
                conv_state.stage = ChatStage.EXPLORATION
                print("🎯 阶段转换：从偏好收集进入到探索阶段")
        else:
            # 如果必要偏好不完整，添加缺失信息
            if not essential_prefs["is_complete"] and not result.get("answer"):
                missing_dims = essential_prefs["missing"]
                missing_text = ", ".join(missing_dims)
                print(f"🎯 缺少必要偏好: {missing_text}")
                result["missing_preferences"] = missing_dims
                result["essential_preferences_complete"] = False

        # 只在非偏好收集阶段生成可视化内容（第二阶段）
        viz_result = {"show_visualization": False, "reason": "preference_collection_stage"}
        print(f"🎨 当前阶段: {conv_state.stage} (Phase={'2' if getattr(conv_state.stage,'value',str(conv_state.stage)).lower() in ['exploration','recommendation_shown','refinement'] else '1'})")
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

    # 日志：变更前快照
    try:
        prev_prefs = dict(conv_state.preferences)
        prev_stage = getattr(conv_state.stage, "value", str(conv_state.stage))
    except Exception:
        prev_prefs = {}
        prev_stage = "unknown"
    print(f"📝 [user_selection] before session={session_id} level={level} name={name}")
    print(f"   prefs(before)={prev_prefs}")
    print(f"   stage(before)={prev_stage}")

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

    # 日志：变更后快照 + 差异
    try:
        next_prefs = dict(conv_state.preferences)
        next_stage = getattr(conv_state.stage, "value", str(conv_state.stage))
    except Exception:
        next_prefs = {}
        next_stage = "unknown"

    # 计算变更差异
    changed_keys = []
    for k in set(list(prev_prefs.keys()) + list(next_prefs.keys())):
        if prev_prefs.get(k) != next_prefs.get(k):
            changed_keys.append(k)
    print(f"   changed_keys={changed_keys}")
    for k in changed_keys:
        print(f"   {k}: {prev_prefs.get(k)} -> {next_prefs.get(k)}")
    if prev_stage != next_stage:
        print(f"   stage: {prev_stage} -> {next_stage}")

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
        
        # 偏好完整：生成总结并强制切换到 EXPLORATION（若仍在 preference_collection）
        if essential_prefs["is_complete"]:
            preference_summary = generate_preference_summary(conv_state.preferences)
            result["preference_summary"] = preference_summary
            result["essential_preferences_complete"] = True
            if getattr(conv_state.stage, 'value', str(conv_state.stage)) == "preference_collection":
                result["stage_transition"] = {
                    "from": "preference_collection",
                    "to": "exploration",
                    "message": "Essential preferences collected. Moving to exploration phase."
                }
                conv_state.stage = ChatStage.EXPLORATION
                print("🎯 阶段转换：从偏好收集进入到探索阶段")
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
    返回评论关键词词频列表（legacy，仍保留以兼容旧前端）。
    建议使用 /comments/wordcloud_v2。
    """
    try:
        level = request.args.get('level')
        name  = request.args.get('name')
        # 假设已经有 reviews_keywords(word, count, level, name) 视图
        safe = name.replace("'", "''") if name else ''
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

@api.route('/comments/wordcloud_v2', methods=['GET'])
def comments_wordcloud_v2():
    """
    新版词云接口：读取预计算 JSON 缓存，支持地区切换。
    Query params:
      - level: 'district' | 'neighbourhood'
      - name:  district or neighbourhood name
      - top_n (optional): 10-100
      - metric (optional): 'frequency' | 'tfidf' | 'pmi'
      - debug (optional): 1|true 开启调试信息
    返回：默认直接返回数组；debug=1 时返回对象，包含 data 和调试信息。
    """
    try:
        level_in = request.args.get('level', type=str) or 'district'
        name     = request.args.get('name', type=str)
        top_n    = request.args.get('top_n', type=int)
        metric   = request.args.get('metric', type=str)
        debug    = request.args.get('debug', default='0', type=str)
        debug_flag = str(debug).lower() in ('1', 'true', 'yes', 'y', 'on')

        # 默认名称：若未提供 name，根据层级给出可用的默认
        if not name:
            if level_in == 'neighbourhood':
                name = 'Alexanderplatz'
            else:
                name = 'Mitte'

        # 前端用 'district'；后端内部用 'neighbourhood_group'
        level = 'neighbourhood_group' if level_in == 'district' else 'neighbourhood'

        prefs = {
            "level": level,
            "name": name,
        }
        if top_n is not None:
            prefs["top_n"] = max(1, min(300, int(top_n)))
        if metric:
            # 映射：frequency -> freq
            m = metric.lower()
            if m == 'frequency':
                prefs["measure"] = 'freq'
            elif m in ('tfidf', 'pmi'):
                prefs["measure"] = m

        result = wc_generate(prefs)
        if not result.get('success'):
            # 直接透传错误，便于定位 cache miss
            resp = {"success": False, **result}
            if debug_flag:
                resp["debug"] = {
                    "params": {"level": level_in, "name": name, "top_n": top_n, "metric": metric},
                    "resolved_prefs": prefs
                }
            return jsonify(resp), 404

        # 统一返回数组结构
        data = result.get('data', {})
        entries = data.get('entries_mixed') or data.get('entries')
        payload = []
        if entries:
            for e in entries:
                item = {
                    "text": e.get('canonical') or e.get('keyword') or e.get('text') or '',
                }
                # 可选指标
                if e.get('freq') is not None:
                    try:
                        item['freq'] = int(e.get('freq'))
                    except Exception:
                        pass
                if e.get('tfidf') is not None:
                    try:
                        item['tfidf'] = float(e.get('tfidf'))
                    except Exception:
                        pass
                if e.get('pmi') is not None:
                    try:
                        item['pmi'] = float(e.get('pmi'))
                    except Exception:
                        pass
                if e.get('sentiment'):
                    item['sentiment'] = e.get('sentiment')
                if e.get('examples'):
                    item['examples'] = e.get('examples')
                payload.append(item)
        else:
            # 兜底：words + counts
            words = data.get('words') or []
            counts = data.get('counts') or []
            for i, w in enumerate(words):
                item = {"text": w}
                if i < len(counts):
                    try:
                        item['freq'] = int(counts[i])
                    except Exception:
                        pass
                payload.append(item)

        if debug_flag:
            return jsonify({
                "success": True,
                "count": len(payload),
                "data": payload,
                "meta": {
                    "level": level_in,
                    "name": name,
                    "top_n": top_n,
                    "metric": metric
                },
                "resolved_prefs": prefs,
                "wc_metadata": result.get('metadata')
            })

        return jsonify(payload)
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


@api.route("/metrics/commit", methods=["POST"])
def commit_metrics():
    """
    前端一次性上报会话统计，后端合并为一条 interaction_events 写库：
    - event_type 固定为 'core_event_summary'
    - 各计数保存在 context_json.metrics 中，位置交互保存在 context_json.location_interaction 中
    """
    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON payload"}), 400

    ok, result = log_session_metrics(payload)
    if not ok:
        return jsonify({"ok": False, "error": result}), 400

    return jsonify({"ok": True, **result}), 200


@api.route("/metrics/likert", methods=["POST"])
def commit_likert():
    """
    接收 5-Likert 问卷提交，写入 interaction_events：
    - event_type = 'likert_feedback'
    - answers 存入 context_json.likert.answers
    - summary(avg,count) 存入 context_json.likert.summary
    - 若表存在 likert_avg_score/likert_answer_count 列则同步写入
    """
    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON payload"}), 400

    ok, result = log_likert_feedback(payload)
    if not ok:
        return jsonify({"ok": False, "error": result}), 400

    return jsonify({"ok": True, **result}), 200


@api.route("/rag_chat_scripted", methods=["POST"])
def rag_chat_scripted():
    """
    脚本化（scripted）RAG问答接口：
    - 始终走全量全局检索（global FAISS），不依赖会话状态
    - 支持历史记录（与现有 rag_chat 相同的 history 结构）
    - 尽量复用现有 RAG 实现
    
    Request JSON:
    {
        "message": str,            # 必填
        "history": List[{'type': 'user'|'system', 'data': str}]  # 可选
    }
    """
    try:
        data = request.json or {}
        user_message = (data.get("message") or "").strip()
        raw_history = data.get("history", [])
        # 规范化前端传入的历史格式，兼容 {type,data} / {sender,text} / {role,content} / str
        history = []
        try:
            iterable = raw_history if isinstance(raw_history, list) else []
            for msg in iterable:
                if isinstance(msg, dict):
                    if "type" in msg and "data" in msg:
                        history.append({"type": msg.get("type"), "data": msg.get("data", "")})
                    elif "sender" in msg and "text" in msg:
                        role = str(msg.get("sender", "")).lower()
                        mapped_type = "user" if role in ("user", "human") else "system"
                        history.append({"type": mapped_type, "data": msg.get("text", "")})
                    elif "role" in msg and "content" in msg:
                        role = str(msg.get("role", "")).lower()
                        mapped_type = "user" if role in ("user", "human") else "system"
                        history.append({"type": mapped_type, "data": msg.get("content", "")})
                elif isinstance(msg, str):
                    history.append({"type": "user", "data": msg})
        except Exception:
            history = []

        if not user_message:
            return jsonify({"error": "缺少 message 参数"}), 400

        # 预热全局向量库（lru_cache 确保只加载一次）
        get_global_vectordb()

        # 始终启用全局检索；不传入偏好
        result = rag_chat_with_memory_focused(
            user_message,
            history,
            pref={},
            global_search=True
        )

        # 结果兜底字段
        if "source_documents" not in result:
            result["source_documents"] = []

        # 如果answer为空，做轻量兜底：基于检索到的文档元数据汇总区域评分
        answer_text = (result.get("answer") or "").strip()
        if not answer_text and result.get("source_documents"):
            try:
                area_stats = {}
                for doc in result["source_documents"]:
                    detail = doc.get("item_detail") or {}
                    # 优先使用大区名，否则用小区
                    area = detail.get("neighbourhood_group_cleansed") or detail.get("neighbourhood_cleansed")
                    if not area:
                        continue
                    rating_raw = detail.get("review_scores_rating")
                    try:
                        rating_val = float(rating_raw) if rating_raw is not None and rating_raw != "" else None
                    except Exception:
                        rating_val = None
                    if area not in area_stats:
                        area_stats[area] = {"sum": 0.0, "cnt": 0}
                    if rating_val is not None and rating_val > 0:
                        area_stats[area]["sum"] += rating_val
                        area_stats[area]["cnt"] += 1
                # 计算平均并排序
                ranked = []
                for area, s in area_stats.items():
                    if s["cnt"] > 0:
                        avg = s["sum"] / s["cnt"]
                        ranked.append((area, avg, s["cnt"]))
                ranked.sort(key=lambda x: (x[1], x[2]), reverse=True)
                if ranked:
                    top = ranked[:3]
                    parts = [f"{name} ({avg:.2f})" for name, avg, _ in top]
                    synthesized = "Top areas by guest ratings: " + ", ".join(parts) + "."
                    result["answer"] = synthesized
                    result.setdefault("fallback_info", {})
                    result["fallback_info"].update({
                        "strategy": "area_rating_aggregation",
                        "top_areas": [{"name": n, "avg_rating": round(a, 2), "sample": c} for n, a, c in top]
                    })
            except Exception as _:
                # 静默兜底；保持空字符串
                pass

        # 附加路由信息（用于前端区分模式）
        result.setdefault("route_info", {})
        result["route_info"].update({
            "route_type": "rag_scripted_global",
            "retrieval_triggered": True
        })
        result["is_scripted_mode"] = True

        return jsonify(result)
    except Exception as e:
        import traceback
        print(f"❌ scripted RAG 接口失败: {e}\n{traceback.format_exc()}")
        return jsonify({
            "error": "scripted rag_chat failed",
            "message": str(e)
        }), 500

@api.route('/test/chart-option', methods=['POST'])
def get_test_chart_option():
    """
    返回单个图表的 ECharts option（用于前端主页测试按钮）
    Body(JSON):
      - type: 图表类型（默认 price_distribution）
      - preferences/filters: 偏好/过滤参数对象（可选）
      - 也支持将常用参数直接放在顶层（price_min, price_max 等）
    """
    payload = request.get_json(silent=True) or {}
    chart_type = payload.get('type', 'price_distribution')
    # 轻量别名修正（防止前端拼写截断）
    alias = {
        'price_coverage_delt': 'price_coverage_delta',
    }
    chart_type = alias.get(chart_type, chart_type)

    # 合并 preferences、filters 与顶层常见字段
    prefs_from_body = payload.get('preferences') or payload.get('filters') or {}
    merged_prefs = dict(prefs_from_body)
    for key in [
        'price_min', 'price_max', 'neighbourhood', 'neighbourhood_group', 'room_type', 'area',
        'base_budget', 'new_budget', 'step', 'min_reviews', 'availability_min'
    ]:
        if payload.get(key) is not None and key not in merged_prefs:
            merged_prefs[key] = payload.get(key)

    # 清理空值
    user_prefs = {k: v for k, v in merged_prefs.items() if v is not None}

    # 针对 price_coverage_delta 做参数桥接：用 price_min/price_max 映射 base/new
    if chart_type == 'price_coverage_delta':
        if 'base_budget' not in user_prefs and user_prefs.get('price_min') is not None:
            try:
                user_prefs['base_budget'] = int(user_prefs.get('price_min'))
            except Exception:
                pass
        if 'new_budget' not in user_prefs and user_prefs.get('price_max') is not None:
            try:
                user_prefs['new_budget'] = int(user_prefs.get('price_max'))
            except Exception:
                pass
        # 默认步长
        if 'step' not in user_prefs:
            user_prefs['step'] = 5
        # 参数校验（生成器会再次校验，这里提前报错更直观）
        if user_prefs.get('base_budget') is None or user_prefs.get('new_budget') is None:
            return jsonify({
                'error': 'price_coverage_delta requires base_budget/new_budget (or price_min/price_max)'
            }), 400

    result = chart_generator.generate_chart_data(chart_type, user_prefs)
    if not result.get('success', False):
        return jsonify({"error": result.get('error', 'Chart generation failed')}), 400

    option = _build_echarts_option_from_result(chart_type, result)
    response_payload = {
        "chart_type": chart_type,
        "echarts_option": option
    }
    # 透传 value_quality_quadrant 的趋势线统计
    if chart_type == 'value_quality_quadrant':
        try:
            trend_obj = ((result or {}).get('data') or {}).get('trend')
            if trend_obj is not None:
                response_payload['trend'] = trend_obj
        except Exception:
            pass
    # 透传 price_coverage_delta 额外字段（预算与英文摘要等）
    if chart_type == 'price_coverage_delta':
        # 选择性附加，避免污染其他类型
        for k in [
            'request_budgets',
            'narrative',
            'narrative_en',
            'delta_summary',
            'inputs',
            'coverage_curve',
            'top_gain_areas',
            'delta_bar',
        ]:
            if result.get(k) is not None:
                response_payload[k] = result.get(k)
    return jsonify(response_payload)


def _build_echarts_option_from_result(chart_type: str, result: dict) -> dict:
    """将 generate_chart_data 返回结果转换为 ECharts option。
    若结果已包含 echarts_option 则直接返回；否则根据数据结构构建一个最小可用的 option。
    """
    option = result.get('echarts_option')
    if option:
        return option

    data = (result or {}).get('data') or {}
    categories = data.get('categories') or []
    values = data.get('values') or []

    # 针对没有内置 option 的两类做兜底：
    if chart_type == 'comments_wordcloud':
        # 将 {words, counts} 转换为 ECharts wordCloud 数据结构
        words = data.get('words') or []
        counts = data.get('counts') or []
        wc_data = [{"name": w, "value": int(counts[i]) if i < len(counts) else 1} for i, w in enumerate(words)]
        return {
            "title": {"text": "Review Keywords Wordcloud", "left": "center"},
            # 注意：前端需要引入 echarts-wordcloud 插件
            "series": [{
                "type": "wordCloud",
                "gridSize": 8,
                "sizeRange": [12, 48],
                "rotationRange": [-90, 90],
                "shape": "circle",
                "textStyle": {"color": "#5470c6"},
                "emphasis": {"textStyle": {"shadowBlur": 10, "shadowColor": "#333"}},
                "data": wc_data
            }]
        }

    # 通用兜底：如果有 categories/values，则给个柱状图
    if categories and values:
        return {
            "title": {"text": result.get('chart_config', {}).get('title', 'Chart'), "left": "center"},
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": categories},
            "yAxis": {"type": "value"},
            "series": [{"type": "bar", "data": values}]
        }

    # 最终兜底：返回原始数据，交给前端处理
    return {"raw": result}

@api.route('/precompute/wordcloud', methods=['GET'])
def precompute_wordcloud_all():
    """
    触发全量预计算（最终产物）：按 level 列出所有区域并生成混合 n-gram 的词云缓存 JSON。
    - 最终文件命名：
      · level=neighbourhood_group: chart_generators/precompute/cache/wordcloud/neighbourhood_group/{Group}.json
      · level=neighbourhood:       chart_generators/precompute/cache/wordcloud/neighbourhood/{Group}/{Neighbourhood}.json
    - 固定生成 TopK=300，ngram=混合（1/2/3 全部），无需传递 ngram/top_k 参数

    GET /precompute/wordcloud?level=neighbourhood_group|neighbourhood
    默认 level=neighbourhood_group
    返回生成结果摘要，服务端控制台输出进度日志。
    """
    if not _wc_precompute_available:
        return jsonify({"success": False, "error": "precompute module not available"}), 500
    try:
        level = request.args.get('level', default='neighbourhood_group', type=str)
        if level not in ("neighbourhood", "neighbourhood_group"):
            return jsonify({"success": False, "error": "Invalid level", "message": "level must be 'neighbourhood' or 'neighbourhood_group'"}), 400

        FIXED_TOP_K = 300

        # helper imports
        from chart_generators.precompute.wordcloud_precompute import precompute_mixed_for_area as _wc_precompute_mixed
        from chart_generators.precompute.wordcloud_precompute import list_groups as _wc_list_groups
        from chart_generators.precompute.wordcloud_precompute import list_neighbourhoods_in_group as _wc_list_neigh_in_group
        from chart_generators.precompute.wordcloud_precompute import list_areas as _wc_list_areas

        saved: List[dict] = []
        failed: List[dict] = []

        t0 = time.time()

        if level == 'neighbourhood_group':
            groups = _wc_list_groups()
            total = len(groups)
            _wc_progress_update(status="running", level=level, total=total, processed=0, current_index=0, current_area=None, started_at=t0, elapsed_sec=0.0, eta_sec=None, last_saved_path=None, error=None)
            print(f"🟢 [precompute] Start: level=neighbourhood_group, mode=mixed, top_k={FIXED_TOP_K}, total_groups={total}", flush=True)
            for idx, group in enumerate(groups, start=1):
                _wc_progress_update(current_index=idx, current_area=group, processed=idx-1, elapsed_sec=(time.time()-t0))
                try:
                    print(f"➡️  [{idx}/{total}] Generating group: {group} ...", flush=True)
                    t_area = time.time()
                    path = _wc_precompute_mixed('neighbourhood_group', group, top_k_store=FIXED_TOP_K)
                    dt = time.time() - t_area
                    print(f"✅  [{idx}/{total}] Saved: {path} ({dt:.2f}s)", flush=True)
                    saved.append({"area": group, "path": path, "elapsed_sec": round(dt, 2)})
                    _wc_progress_update(processed=idx, last_saved_path=path, elapsed_sec=(time.time()-t0))
                    avg = (time.time()-t0) / idx
                    _wc_progress_update(eta_sec=round(avg * (total - idx), 2))
                except Exception as e:
                    print(f"❌  [{idx}/{total}] Failed group: {group} -> {e}", flush=True)
                    failed.append({"area": group, "error": str(e)})
                    _wc_progress_update(processed=idx, error=str(e))
        else:
            # neighbourhood: iterate by group, and within each group iterate neighbourhoods; write under group folder
            groups = _wc_list_groups()
            # compute total as sum of neighbourhoods for progress
            all_neighs = []
            for g in groups:
                try:
                    neighs = _wc_list_neigh_in_group(g)
                except Exception:
                    neighs = []
                all_neighs.append((g, neighs))
            total = sum(len(neighs) for _, neighs in all_neighs)
            _wc_progress_update(status="running", level=level, total=total, processed=0, current_index=0, current_area=None, started_at=t0, elapsed_sec=0.0, eta_sec=None, last_saved_path=None, error=None)
            print(f"🟢 [precompute] Start: level=neighbourhood (nested by group), mode=mixed, top_k={FIXED_TOP_K}, total_neighs={total}, groups={len(groups)}", flush=True)
            idx = 0
            for g, neighs in all_neighs:
                print(f"— Group: {g} (neighs={len(neighs)})", flush=True)
                for n in neighs:
                    idx += 1
                    label = f"{g}/{n}"
                    _wc_progress_update(current_index=idx, current_area=label, processed=idx-1, elapsed_sec=(time.time()-t0))
                    try:
                        print(f"➡️  [{idx}/{total}] Generating: {label} ...", flush=True)
                        t_area = time.time()
                        path = _wc_precompute_mixed('neighbourhood', n, top_k_store=FIXED_TOP_K, parent_group=g)
                        dt = time.time() - t_area
                        print(f"✅  [{idx}/{total}] Saved: {path} ({dt:.2f}s)", flush=True)
                        saved.append({"group": g, "neighbourhood": n, "path": path, "elapsed_sec": round(dt, 2)})
                        _wc_progress_update(processed=idx, last_saved_path=path, elapsed_sec=(time.time()-t0))
                        avg = (time.time()-t0) / idx
                        _wc_progress_update(eta_sec=round(avg * (total - idx), 2))
                    except Exception as e:
                        print(f"❌  [{idx}/{total}] Failed: {label} -> {e}", flush=True)
                        failed.append({"group": g, "neighbourhood": n, "error": str(e)})
                        _wc_progress_update(processed=idx, error=str(e))

        _wc_progress_update(status="done", elapsed_sec=(time.time()-t0), current_area=None)
        summary = {
            "success": True,
            "level": level,
            "mode": "mixed",
            "top_k": FIXED_TOP_K,
            "total": _wc_progress.get("total", 0),
            "saved_count": len(saved),
            "failed_count": len(failed),
            "saved": saved[:20],
            "failed": failed[:20]
        }
        print(f"🏁 [precompute] Done. saved={len(saved)}, failed={len(failed)}, elapsed={time.time()-t0:.2f}s", flush=True)
        return jsonify(summary)
    except Exception as e:
        import traceback
        _wc_progress_update(status="error", error=str(e))
        print(f"❌ [precompute] Exception: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


@api.route('/precompute/wordcloud/progress', methods=['GET'])
def precompute_wordcloud_progress():
    """
    查询词云预计算进度（内存状态 + 可选写入到 cache/progress.json）。
    返回 status/level/total/processed/current_index/current_area/elapsed_sec/eta_sec/last_saved_path。
    """
    try:
        payload = dict(_wc_progress)
        # 友好显示时间
        for k in ("started_at", "updated_at"):
            if payload.get(k):
                payload[k] = payload[k]
        return jsonify({"success": True, **payload})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# 🆕 词云预计算进度状态（简单内存状态 + 可选写文件）
_wc_progress = {
    "status": "idle",            # idle|running|done|error
    "level": None,
    "total": 0,
    "processed": 0,
    "current_index": 0,
    "current_area": None,
    "started_at": None,
    "updated_at": None,
    "elapsed_sec": 0.0,
    "eta_sec": None,
    "last_saved_path": None,
    "error": None
}


def _wc_progress_update(**kwargs):
    now = time.time()
    _wc_progress.update(kwargs)
    _wc_progress["updated_at"] = now
    # 可选：将进度写入缓存目录，方便外部查看（忽略异常）
    try:
        from chart_generators.precompute.wordcloud_precompute import CACHE_ROOT as _WC_CACHE_ROOT  # type: ignore
        os.makedirs(_WC_CACHE_ROOT, exist_ok=True)
        with open(os.path.join(_WC_CACHE_ROOT, "progress.json"), "w", encoding="utf-8") as _f:
            json.dump(_wc_progress, _f, ensure_ascii=False)
    except Exception:
        pass

# 预算区域的接口
@api.route('/areas/by_budget', methods=['GET'])
def areas_by_budget():
    """
    根据预算区间筛选地区：优先返回均价在 [price_min, price_max] 内的区域；
    若没有命中，则返回均价高于 price_max 的区域（按均价升序）。

    Query params:
      - level: 'district' | 'neighbourhood'（默认 district）
      - price_min: float（必填）
      - price_max: float（必填）
      - parent_district: 当 level=neighbourhood 时可选，用于限定父区
      - room_type: 可选
      - min_reviews: 可选
    返回：{"areas": [...], "meta": {level, price_min, price_max, matched: 'within'|'above'}}
    """
    try:
        from scripetdAPI.budget_area_service import find_areas_by_budget

        level = request.args.get('level', default='district', type=str)
        price_min = request.args.get('price_min', type=float)
        price_max = request.args.get('price_max', type=float)
        parent_district = request.args.get('parent_district', type=str)
        room_type = request.args.get('room_type', type=str)
        min_reviews = request.args.get('min_reviews', type=int)

        if price_min is None or price_max is None:
            return jsonify({
                "success": False,
                "error": "Missing required parameters",
                "message": "price_min and price_max are required"
            }), 400

        # 规范化：确保 min <= max
        try:
            lo = float(price_min)
            hi = float(price_max)
            if lo > hi:
                lo, hi = hi, lo
            price_min, price_max = lo, hi
        except Exception:
            return jsonify({
                "success": False,
                "error": "Invalid budget",
                "message": "price_min/price_max must be numbers"
            }), 400

        result = find_areas_by_budget(
            level=level,
            price_min=price_min,
            price_max=price_max,
            parent_district=parent_district,
            room_type=room_type,
            min_reviews=min_reviews,
        )

        within = result.get('within') or []
        above = result.get('above') or []
        matched_set = 'within' if within else 'above'
        selected = within if within else above

        # 仅输出需要的字段
        def pick(item):
            return {
                'name': item.get('name'),
                'listing_count': item.get('listing_count'),
                'avg_price': item.get('avg_price'),
                'median_price': item.get('median_price'),
                'p25_price': item.get('p25_price'),
                'p75_price': item.get('p75_price'),
                # 距离或超额仅在对应集合补充（可选）
                **({'distance_to_center': item.get('distance_to_center')} if matched_set == 'within' else {}),
                **({'delta_above': item.get('delta_above')} if matched_set == 'above' else {}),
            }

        areas = [pick(x) for x in selected]

        return jsonify({
            'areas': areas,
            'meta': {
                'level': level,
                'price_min': price_min,
                'price_max': price_max,
                'matched': matched_set,
                'count': len(areas)
            }
        })
    except Exception as e:
        import traceback
        print(f"❌ /areas/by_budget failed: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": str(e)
        }), 500

@api.route('/recent_demand_30d', methods=['GET'])
def recent_demand_30d():
    """
    近30天需求强度分析：按行政区(district)或街区(neighbourhood)聚合。

    Query params:
      - level: 'district' | 'neighbourhood'（默认 'district'）
      - name:  当 level='neighbourhood' 时，指定父区名；level='district' 时可为具体大区或省略/ALL

    指标定义（基于严格清洗后的 l30d）:
      - l30d = GREATEST(0, COALESCE(CAST(number_of_reviews_l30d AS SIGNED), 0))
      - active_share = count(l30d>0)/count(*)
      - median_l30d_active = P50(l30d | l30d>0)
      - l30d_per_100 = sum(l30d) * 100.0 / count(*)

    返回：
      {
        success, level, parent,
        items: [{ name, listing_count, active_share, median_l30d_active, l30d_per_100, label }],
        computed_at
      }
    """
    try:
        level = request.args.get('level', default='district', type=str)
        name = request.args.get('name', type=str)

        if level not in ('district', 'neighbourhood'):
            return jsonify({
                "success": False,
                "error": "Invalid level",
                "message": "level must be 'district' or 'neighbourhood'"
            }), 400

        # 组装 WHERE 子句（保证分组字段有效）
        where_conditions = []
        if level == 'district':
            group_field = 'neighbourhood_group_cleansed'
            where_conditions.append(f"{group_field} IS NOT NULL")
            where_conditions.append(f"{group_field} != ''")
            if name and name.strip() and name.strip().upper() != 'ALL':
                safe_name = name.strip().replace("'", "''")
                where_conditions.append(f"{group_field} = '{safe_name}'")
        else:
            group_field = 'neighbourhood_cleansed'
            # 父区限定
            parent = (name or '').strip()
            if not parent:
                return jsonify({
                    "success": False,
                    "error": "Missing parameter",
                    "message": "name (parent district) is required when level is 'neighbourhood'"
                }), 400
            safe_parent = parent.replace("'", "''")
            where_conditions.append("neighbourhood_group_cleansed IS NOT NULL")
            where_conditions.append("neighbourhood_group_cleansed != ''")
            where_conditions.append(f"neighbourhood_group_cleansed = '{safe_parent}'")
            where_conditions.append(f"{group_field} IS NOT NULL")
            where_conditions.append(f"{group_field} != ''")

        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        # 仅取必要字段，l30d 在 SQL 中严格清洗
        sql = f"""
        SELECT
            {group_field} AS area_name,
            GREATEST(0, COALESCE(CAST(number_of_reviews_l30d AS SIGNED), 0)) AS l30d
        FROM listings
        WHERE {where_clause}
        """
        df = execute_query(sql)

        # 结果为空
        if df is None or getattr(df, 'empty', False):
            return jsonify({
                "success": True,
                "level": level,
                "parent": name if level == 'neighbourhood' else (name if name else None),
                "items": [],
                "computed_at": datetime.utcnow().isoformat() + 'Z'
            })

        # 保障列类型
        try:
            df['l30d'] = df['l30d'].fillna(0).astype(float)
            df['area_name'] = df['area_name'].astype(str)
        except Exception:
            pass

        items = []
        for area_name, g in df.groupby('area_name'):
            listing_count = int(len(g))
            if listing_count == 0:
                continue
            sum_l30d = float(g['l30d'].sum())
            active_count = int((g['l30d'] > 0).sum())
            active_share = (active_count / listing_count) if listing_count > 0 else 0.0
            # 中位数（仅在活跃样本上）
            pos = g.loc[g['l30d'] > 0, 'l30d']
            if pos.empty:
                median_active = 0.0
            else:
                median_active = float(pos.median())
            l30d_per_100 = (sum_l30d * 100.0 / listing_count) if listing_count > 0 else 0.0

            # 强弱标签
            if active_share < 0.20:
                label = 'Low'
            elif active_share <= 0.50:
                label = 'Medium'
            else:
                label = 'High'

            items.append({
                "name": area_name,
                "listing_count": listing_count,
                "active_share": round(active_share, 4),
                "median_l30d_active": int(round(median_active)) if median_active == median_active else 0,
                "l30d_per_100": round(l30d_per_100, 2),
                "label": label
            })

        # 默认按密度排序，其次按 active_share
        items.sort(key=lambda x: (x['l30d_per_100'], x['active_share']), reverse=True)

        return jsonify({
            "success": True,
            "level": level,
            "parent": name if level == 'neighbourhood' else (name if name else None),
            "items": items,
            "computed_at": datetime.utcnow().isoformat() + 'Z'
        })
    except Exception as e:
        import traceback
        print(f"❌ /recent_demand_30d 失败: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": str(e)
        }), 500

# scripted 模式下评论概览
@api.route('/reviews/overview', methods=['GET'])
def reviews_overview():
    """
    Reviews overview: sentiment distribution and top phrases within current scope.
    Query params:
      - area: neighbourhood_group name or ALL/empty for citywide
      - bmin: budget min (optional)
      - bmax: budget max (optional)
      - top_n: phrases count (default 5)
      - min_count: min frequency for phrases (default 20)
      - recent_months: optional integer (e.g., 12) to restrict by recent reviews (if review date available)
      - session_id: optional, to match user preferences to phrases
    """
    try:
        area = request.args.get('area', type=str)
        budget_min = request.args.get('bmin', type=float)
        budget_max = request.args.get('bmax', type=float)
        top_n = request.args.get('top_n', default=5, type=int)
        min_count = request.args.get('min_count', default=20, type=int)
        recent_months = request.args.get('recent_months', type=int)
        session_id = request.args.get('session_id', type=str)

        result = compute_reviews_overview(
            area=area,
            budget_min=budget_min,
            budget_max=budget_max,
            top_n=top_n,
            min_count=min_count,
            recent_months=recent_months,
        )

        # Optional: derive matched preferences from session preferences
        matched = []
        if session_id:
            try:
                conv_state = get_conversation_state(session_id)
                pref_tokens = set()
                for key in ('amenities_keywords', 'experience_keywords', 'location_keywords'):
                    vals = conv_state.preferences.get(key)
                    if isinstance(vals, list):
                        pref_tokens.update(str(x).lower() for x in vals if x)
                    elif isinstance(vals, str) and vals.strip():
                        pref_tokens.add(vals.strip().lower())
                care = conv_state.preferences.get('care_about')
                if isinstance(care, list):
                    pref_tokens.update(str(x).lower() for x in care if x)
                elif isinstance(care, str) and care.strip():
                    pref_tokens.add(care.strip().lower())

                phrases = [p.get('text', '').lower() for p in result.get('top_phrases', [])]
                for token in pref_tokens:
                    if any(token in ph for ph in phrases):
                        matched.append(token)
            except Exception:
                matched = []
        if matched:
            result['matched_preferences'] = sorted(list(set(matched)))

        return jsonify(result)
    except Exception as e:
        import traceback
        print(f"❌ /reviews/overview failed: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": str(e)
        }), 500

@api.route('/reviews/sentiment', methods=['GET'])
def reviews_sentiment():
    """
    Return sentiment distribution only.
    Query params: area, bmin, bmax, recent_months
    """
    try:
        area = request.args.get('area', type=str)
        bmin = request.args.get('bmin', type=float)
        bmax = request.args.get('bmax', type=float)
        recent_months = request.args.get('recent_months', type=int)
        result = compute_reviews_sentiment(area=area, budget_min=bmin, budget_max=bmax, recent_months=recent_months)
        return jsonify(result)
    except Exception as e:
        import traceback
        print(f"❌ /reviews/sentiment failed: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": "Internal server error", "message": str(e)}), 500


@api.route('/reviews/top_keywords', methods=['GET'])
def reviews_top_keywords():
    """
    Return top opinion phrases (LLM-based, English) only.
    Query params: area, bmin, bmax, top_n, recent_months, sample_size, sample_strategy, session_id(optional for preference matches)
    """
    try:
        area = request.args.get('area', type=str)
        bmin = request.args.get('bmin', type=float)
        bmax = request.args.get('bmax', type=float)
        top_n = request.args.get('top_n', default=5, type=int)
        recent_months = request.args.get('recent_months', type=int)
        session_id = request.args.get('session_id', type=str)
        # 默认 50 条（需求）
        sample_size = request.args.get('sample_size', default=50, type=int)
        sample_strategy = request.args.get('sample_strategy', default='recent', type=str)
        
        # 🔧 修复：如果没有传递area参数，尝试从session中获取用户选择的区域
        if area is None and session_id:
            try:
                from conversation_state import get_conversation_state
                conv_state = get_conversation_state(session_id)
                area = conv_state.preferences.get('neighbourhood_group')
                print(f"🔧 [reviews/top_keywords] area参数为空，从session中获取: area={area}")
            except Exception as e:
                print(f"⚠️ [reviews/top_keywords] 从session获取area失败: {e}")
        
        # 添加调试日志
        print(f"🔍 [reviews/top_keywords] 调用参数: area={area}, bmin={bmin}, bmax={bmax}, session_id={session_id}")

        result = compute_reviews_top_phrases(
            area=area,
            budget_min=bmin,
            budget_max=bmax,
            top_n=top_n,
            recent_months=recent_months,
            sample_size=sample_size,
            sample_strategy=sample_strategy,
        )

        # Optional: match preferences
        matched = []
        if session_id:
            try:
                conv_state = get_conversation_state(session_id)
                pref_tokens = set()
                for key in ('amenities_keywords', 'experience_keywords', 'location_keywords'):
                    vals = conv_state.preferences.get(key)
                    if isinstance(vals, list):
                        pref_tokens.update(str(x).lower() for x in vals if x)
                    elif isinstance(vals, str) and vals.strip():
                        pref_tokens.add(vals.strip().lower())
                care = conv_state.preferences.get('care_about')
                if isinstance(care, list):
                    pref_tokens.update(str(x).lower() for x in care if x)
                elif isinstance(care, str) and care.strip():
                    pref_tokens.add(care.strip().lower())

                phrases = [p.get('text', '').lower() for p in result.get('top_phrases', [])]
                for token in pref_tokens:
                    if any(token in ph for ph in phrases):
                        matched.append(token)
            except Exception:
                matched = []
        if matched:
            result['matched_preferences'] = sorted(list(set(matched)))

        return jsonify(result)
    except Exception as e:
        import traceback
        print(f"❌ /reviews/top_keywords failed: {e}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": "Internal server error", "message": str(e)}), 500