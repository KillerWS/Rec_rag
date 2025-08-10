"""
preference_route_handler.py
修正的偏好路由处理器 - 解决重复调用问题
"""

import json
from typing import Dict, List
from chat_router import ConversationState, ChatStage
from recommendation_engine import generate_recommendations_from_preferences, calculate_recommendation_score
from rag_module.follow_up.preference_follow_up import generate_single_followup as new_generate_single_followup

def handle_preference_update_route(user_message: str, history: List, 
                                   conv_state: ConversationState, use_llm: bool = False, 
                                   structured_data=None) -> Dict:
    """
    处理偏好更新路由 - 修正版，避免结构化数据被覆盖
    """
    print(f"🎯 偏好更新处理 - use_llm: {use_llm}")
    
    updated_fields = []

    # 优先处理结构化数据（如果存在）
    if structured_data:
        for key, value in structured_data.items():
            if value is not None:
                conv_state.preferences[key] = value
                updated_fields.append(key)

    # 如果存在结构化数据，则跳过这些字段的后续解析
    extraction_result = {"updated_fields": [], "extraction_method": "none"}
    if structured_data:
        print(f"🎯 已处理结构化数据: {structured_data}")
        extraction_result["updated_fields"] = updated_fields
    else:
        # 🎯 没有结构化数据时，使用现有逻辑解析
        extraction_result = conv_state.update_preferences_from_message(user_message, use_llm=use_llm)
        updated_fields.extend(extraction_result.get("updated_fields", []))

        if "error" in extraction_result:
            print(f"偏好提取错误: {extraction_result['error']}")
            response = "I understand you're sharing your preferences. Could you tell me more about your budget and preferred area in Berlin?"
            show_recommendation = False
            followup_info = None
        else:
            completeness = conv_state.get_completeness_score()
            preference_count = conv_state.get_preference_count()
            
            print(f"📊 当前状态: 完整度={completeness:.2f}, 偏好数量={preference_count}")
            
            if completeness >= 0.8:
                # 信息充足，准备推荐
                response = generate_confirmation_response(user_message, extraction_result, conv_state)
                show_recommendation = True
                followup_info = {
                    "ready_for_recommendation": True,
                    "completeness_score": completeness,
                    "strategy": "ready_for_recommendation"
                }
            else:
                try:
                    # 使用新的追问生成函数
                    followup_question = new_generate_single_followup(conv_state, user_message)
                    
                    response = generate_preference_response_with_followup(
                        user_message, extraction_result, conv_state, followup_question
                    )
                    show_recommendation = False
                    followup_info = {
                        "ready_for_recommendation": followup_question.get("ready_for_recommendation", False),
                        "followup_question": followup_question,
                        "completeness_score": completeness,
                        "strategy": "targeted_followup"
                    }
                except Exception as e:
                    print(f"❌ 追问生成失败: {e}")
                    response = generate_simple_confirmation(user_message, extraction_result, conv_state)
                    show_recommendation = False
                    followup_info = None
    # 如果使用结构化数据，则单独决定回应内容
    if structured_data:
        completeness = conv_state.get_completeness_score()
        missing_prefs = conv_state.get_missing_critical_preferences()

        if missing_prefs:
            response = f"Got it! I've updated your {', '.join(updated_fields)}. Could you also specify your {', '.join(missing_prefs)} in berlin ?"
            show_recommendation = False
            followup_info = {
                "ready_for_recommendation": False,
                "missing_preferences": missing_prefs,
                "completeness_score": completeness,
                "strategy": "structured_data_followup"
            }
        else:
            response = f"Great! Your {', '.join(updated_fields)} are updated and complete. Ready to recommend!"
            show_recommendation = True
            followup_info = {
                "ready_for_recommendation": True,
                "completeness_score": completeness,
                "strategy": "structured_data_ready"
            }

    # 🎯 确定消息类型
    if show_recommendation:
        message_type = "recommendation_prompt"
    elif followup_info and followup_info.get("followup_question"):
        message_type = "intelligent_followup"
    else:
        message_type = "text"
    
    # 🎯 动态生成推荐（每次偏好更新后都更新推荐）
    recommendations = []
    # 默认设置has_recommendations为False
    has_recommendations = False
    
    # 修改逻辑：当有structured_data时，总是尝试生成推荐
    if structured_data or conv_state.get_preference_count() > 0:
        try:
            print(f"🔄 基于更新后的偏好生成推荐: {conv_state.preferences}")
            recommendations = generate_recommendations_from_preferences(
                conv_state.preferences,
                limit=8,
                original_query=user_message
            )
            has_recommendations = len(recommendations) > 0
            print(f"✅ 生成了 {len(recommendations)} 条推荐")

            # 添加推荐分数
            if recommendations:
                try:
                    # 从推荐引擎导入评分函数
                    from recommendation_engine import calculate_recommendation_score
                    import pandas as pd
                    
                    # 创建DataFrame
                    df_result = pd.DataFrame(recommendations)
                    
                    # 定义已使用的偏好维度
                    used_preferences = []
                    for key, value in conv_state.preferences.items():
                        if value is not None and value != [] and value != "":
                            used_preferences.append(key)
                            
                    # 确保所有必要字段存在，使用默认值填充缺失字段
                    required_fields = ['number_of_reviews', 'reviews_per_month', 'review_scores_rating']
                    for field in required_fields:
                        if field not in df_result.columns:
                            df_result[field] = 0
                    
                    # 为每个推荐项添加分数
                    for listing in recommendations:
                        # 尝试使用可用字段计算分数
                        score = calculate_recommendation_score(
                            listing,
                            conv_state.preferences,
                            df_result,
                            used_preferences
                        )
                        listing["recommendation_score"] = round(score, 2)
                    
                    print(recommendations[:2])
                    print(f"✅ 已为推荐结果添加评分")
                
                except Exception as e:
                    print(f"❌ 添加推荐分数失败: {e}")
                    import traceback
                    traceback.print_exc()

        except Exception as e:
            print(f"❌ 推荐生成失败: {e}")
            import traceback
            traceback.print_exc()
    
    # 当有structured_data时，即使没有生成推荐，也强制设置has_recommendations为True
    if structured_data:
        has_recommendations = True
        print("✅ 结构化数据更新，强制设置has_recommendations=True以触发前端卡片更新")
    
    # 🎯 构建返回结果
    result = {
        "answer": response,
        "source_documents": [],
        "route_info": {
            "route_type": "preference_update",
            "intent": "structured_data_update" if structured_data else "preference_update",
            "stage": conv_state.stage.value,
            "preference_count": conv_state.get_preference_count(),
            "completeness_score": conv_state.get_completeness_score(),
            "show_recommendation_prompt": show_recommendation,
            "missing_preferences": conv_state.get_missing_critical_preferences(),
            "extraction_method": extraction_result.get("extraction_method", "structured_data" if structured_data else "unknown"),
            "llm_used": use_llm,
            "has_recommendations": has_recommendations
        },
        "message_type": message_type,
        "preferences": conv_state.preferences.copy(),
        "extraction_result": extraction_result,
        
        # 🎯 决策卡片相关信息
        "decision_card": {
            "should_update": True,
            "preferences": conv_state.preferences.copy(),
            "completeness_score": conv_state.get_completeness_score(),
            "preference_count": conv_state.get_preference_count(),
            "missing_critical": conv_state.get_missing_critical_preferences(),
            "stage": conv_state.stage.value
        },
        
        # 🎯 智能追问信息
        "followup_info": followup_info
    }
    
    # 添加推荐到返回结果
    if has_recommendations:
        # 如果是结构化数据但没有成功生成推荐，确保至少返回一个空的recommendations列表
        if structured_data and len(recommendations) == 0:
            result["recommendations"] = []
        else:
            result["recommendations"] = recommendations
        
        # 如果有足够的偏好并生成了推荐，保存到会话状态
        if conv_state.get_completeness_score() >= 0.5 and len(recommendations) > 0:
            conv_state.set_recommendations(recommendations)
    
    return result

def handle_recommendation_request_route(user_message: str, history: List,
                                      conv_state: ConversationState, use_semantic_search: bool = False) -> Dict:
    """
    处理推荐请求路由 - 修正版
    """
    print(f"🎯 推荐请求处理 - use_semantic_search: {use_semantic_search}")
    
    # 🎯 在推荐时使用LLM进行深度偏好抽取
    extraction_result = conv_state.update_preferences_from_message(user_message, use_llm=True)
    print(f"深度偏好抽取结果: {extraction_result}")
    
    # 检查是否有足够的偏好信息
    if not conv_state.is_ready_for_recommendations():
        missing_prefs = conv_state.get_missing_critical_preferences()
        
        # 🎯 使用简化的追问生成
        followup_question = generate_single_followup(
            conv_state.preferences, user_message, conv_state.get_completeness_score()
        )
        
        response = followup_question.get("question", 
            f"I'd love to show you recommendations! To find the perfect match, I need to know your {' and '.join(missing_prefs)}.")
        
        return {
            "answer": response,
            "source_documents": [],
            "route_info": {
                "route_type": "recommendation_request",
                "intent": "show_recommendations", 
                "stage": conv_state.stage.value,
                "ready_for_recommendations": False,
                "missing_preferences": missing_prefs
            },
            "message_type": "intelligent_followup",
            
            "decision_card": {
                "should_update": True,
                "preferences": conv_state.preferences.copy(),
                "completeness_score": conv_state.get_completeness_score(),
                "preference_count": conv_state.get_preference_count(),
                "missing_critical": missing_prefs,
                "stage": conv_state.stage.value
            },
            
            "followup_info": {
                "ready_for_recommendation": False,
                "followup_question": followup_question,
                "completeness_score": conv_state.get_completeness_score(),
                "strategy": "basic_collection"
            }
        }
    
    # 🎯 生成推荐
    try:
        print(f"当前偏好状态: {conv_state.preferences}")
        
        if use_semantic_search:
            recommendations = generate_semantic_recommendations(conv_state.preferences, user_message, limit=8)
        else:
            recommendations = generate_recommendations_from_preferences(
                conv_state.preferences, 
                limit=8,
                original_query=user_message
            )
        
        print(f"生成推荐数量: {len(recommendations)}")
        
        if not recommendations:
            response = "I couldn't find any listings matching your preferences. Would you like to adjust your criteria?"
            conv_state.update_stage(ChatStage.REFINEMENT)
            
            return {
                "answer": response,
                "source_documents": [],
                "recommendations": [],
                "route_info": {
                    "route_type": "recommendation_request",
                    "intent": "show_recommendations",
                    "stage": conv_state.stage.value,
                    "recommendations_found": False,
                    "semantic_search_used": use_semantic_search
                },
                "message_type": "refinement_prompt",
                
                "decision_card": {
                    "should_update": True,
                    "preferences": conv_state.preferences.copy(),
                    "completeness_score": conv_state.get_completeness_score(),
                    "preference_count": conv_state.get_preference_count(),
                    "missing_critical": [],
                    "stage": conv_state.stage.value
                }
            }
        
        conv_state.set_recommendations(recommendations)
        response = generate_recommendation_intro(recommendations, conv_state.preferences)
        
        return {
            "answer": response,
            "source_documents": [],
            "recommendations": recommendations,
            "route_info": {
                "route_type": "recommendation_request",
                "intent": "show_recommendations",
                "stage": conv_state.stage.value,
                "recommendations_found": True,
                "recommendation_count": len(recommendations),
                "semantic_search_used": use_semantic_search
            },
            "message_type": "recommendations",
            "preferences_used": conv_state.preferences.copy(),
            
            "decision_card": {
                "should_update": True,
                "preferences": conv_state.preferences.copy(),
                "completeness_score": conv_state.get_completeness_score(),
                "preference_count": conv_state.get_preference_count(),
                "missing_critical": [],
                "stage": conv_state.stage.value,
                "recommendations_shown": True,
                "recommendation_count": len(recommendations)
            }
        }
        
    except Exception as e:
        print(f"推荐生成失败: {e}")
        import traceback
        traceback.print_exc()
        response = "Sorry, I encountered an issue generating recommendations. Please try again."
        
        return {
            "answer": response,
            "source_documents": [],
            "route_info": {
                "route_type": "recommendation_request",
                "intent": "show_recommendations",
                "error": str(e)
            },
            "message_type": "error"
        }

def generate_preference_response_with_followup(user_message: str, extracted_prefs: Dict, 
                                             conv_state: ConversationState, 
                                             followup_question: Dict) -> str:
    """生成包含智能追问的偏好回应 - 修正版：先验证偏好再生成回复"""
    
    # 🎯 关键修正：先验证和修正偏好，再生成回复文本
    validated_prefs = validate_preferences_before_response(conv_state.preferences)
    conv_state.preferences = validated_prefs  # 更新状态中的偏好
    
    # 生成确认信息
    confirmations = []
    updated_fields = extracted_prefs.get('updated_fields', [])
    
    # 🎯 现在使用已验证的偏好生成回复
    if 'price_min' in updated_fields or 'price_max' in updated_fields:
        price_min = validated_prefs.get('price_min')  # 使用验证后的数据
        price_max = validated_prefs.get('price_max')  # 使用验证后的数据
        
        if price_min and price_max and price_min > 0 and price_max > 0:
            budget_text = f"€{price_min}-{price_max}"
        elif price_max and price_max > 0:
            budget_text = f"under €{price_max}"
        elif price_min and price_min > 0:
            budget_text = f"from €{price_min}"
        else:
            budget_text = "budget preferences"  # 更安全的默认值
        confirmations.append(f"budget {budget_text}")
    
    if 'minimum_nights' in updated_fields:
        nights = validated_prefs.get('minimum_nights')
        if nights and nights > 0:
            confirmations.append(f"{nights}-day stay")
    
    if 'neighbourhood' in updated_fields:
        neighbourhood = validated_prefs.get('neighbourhood')
        if neighbourhood:
            confirmations.append(f"{neighbourhood} area")
    elif 'neighbourhood_group' in updated_fields:
        neighbourhood_group = validated_prefs.get('neighbourhood_group') 
        if neighbourhood_group:
            confirmations.append(f"{neighbourhood_group} district")
    
    if 'room_type' in updated_fields:
        room_type = validated_prefs.get('room_type')
        if room_type:
            confirmations.append(f"{room_type.lower()}")
    
    if 'amenities_keywords' in updated_fields:
        keywords = validated_prefs.get('amenities_keywords', [])
        if keywords:
            confirmations.append(f"with {', '.join(keywords[-3:])}")
    
    # 构建回应
    if confirmations:
        confirmation_text = f"Perfect! I've noted: {', '.join(confirmations)}. "
    else:
        confirmation_text = "Got it! "
    
    # 添加智能追问
    followup_text = followup_question.get("question", "Tell me more about your preferences!")
    
    return confirmation_text + followup_text

def generate_simple_confirmation(user_message: str, extracted_prefs: Dict,
                               conv_state: ConversationState) -> str:
    """生成简单确认回应"""
    
    updated_fields = extracted_prefs.get('updated_fields', [])
    
    if updated_fields:
        return "Perfect! I've noted your preferences. Tell me more about what you're looking for!"
    else:
        return "I understand you're sharing your preferences. Could you tell me more about your budget and preferred area?"

def validate_preferences_before_response(preferences: Dict) -> Dict:
    """🎯 在生成回复前验证和修正偏好数据"""
    validated_prefs = preferences.copy()
    changes_made = []
    
    # 修正价格异常
    if validated_prefs.get('price_min') is not None:
        if validated_prefs['price_min'] < 0:
            changes_made.append(f"修正异常价格下限: {validated_prefs['price_min']} -> None")
            validated_prefs['price_min'] = None
        elif validated_prefs['price_min'] < 10:
            changes_made.append(f"修正过低价格下限: {validated_prefs['price_min']} -> 15")
            validated_prefs['price_min'] = 15
    
    if validated_prefs.get('price_max') is not None:
        if validated_prefs['price_max'] < 15:
            changes_made.append(f"修正异常价格上限: {validated_prefs['price_max']} -> None")
            validated_prefs['price_max'] = None
        elif validated_prefs['price_max'] > 1000:
            changes_made.append(f"修正过高价格上限: {validated_prefs['price_max']} -> 500")
            validated_prefs['price_max'] = 500
    
    # 修正停留天数
    if validated_prefs.get('minimum_nights') is not None:
        if validated_prefs['minimum_nights'] < 1:
            validated_prefs['minimum_nights'] = 1
            changes_made.append("修正停留天数下限: < 1 -> 1")
        elif validated_prefs['minimum_nights'] > 365:
            validated_prefs['minimum_nights'] = 30
            changes_made.append("修正停留天数上限: > 365 -> 30")
    
    if changes_made:
        print("⚠️  偏好数据修正（回复生成前）:")
        for change in changes_made:
            print(f"  - {change}")
    
    return validated_prefs

def generate_confirmation_response(user_message: str, extracted_prefs: Dict,
                                 conv_state: ConversationState) -> str:
    """生成确认推荐的回应 - 修正版"""
    
    # 🎯 同样在这里也先验证偏好
    validated_prefs = validate_preferences_before_response(conv_state.preferences)
    conv_state.preferences = validated_prefs
    
    confirmations = []
    updated_fields = extracted_prefs.get('updated_fields', [])
    
    if updated_fields:
        confirmations.append("preferences updated")
    
    confirmation_text = "Excellent! " if confirmations else "Great! "
    
    return confirmation_text + "I have all the details I need. Ready to see some perfect recommendations for your Berlin stay?"

# def generate_confirmation_response(user_message: str, extracted_prefs: Dict,
#                                  conv_state: ConversationState) -> str:
#     """生成确认推荐的回应"""
    
#     confirmations = []
#     updated_fields = extracted_prefs.get('updated_fields', [])
    
#     if updated_fields:
#         confirmations.append("preferences updated")
    
#     confirmation_text = "Excellent! " if confirmations else "Great! "
    
#     return confirmation_text + "I have all the details I need. Ready to see some perfect recommendations for your Berlin stay?"

def generate_recommendation_intro(recommendations: List[Dict], preferences: Dict) -> str:
    """生成推荐介绍文本"""
    
    count = len(recommendations)
    
    pref_parts = []
    if preferences.get('price_min') and preferences.get('price_max'):
        pref_parts.append(f"€{preferences['price_min']}-{preferences['price_max']} budget")
    elif preferences.get('price_max'):
        pref_parts.append(f"under €{preferences['price_max']} budget")
    
    if preferences.get('minimum_nights'):
        pref_parts.append(f"{preferences['minimum_nights']}-day stay")
    
    if preferences.get('room_type'):
        pref_parts.append(preferences['room_type'].lower())
    
    if preferences.get('neighbourhood'):
        pref_parts.append(f"in {preferences['neighbourhood']}")
    elif preferences.get('neighbourhood_group'):
        pref_parts.append(f"in {preferences['neighbourhood_group']}")
    
    pref_text = " ".join(pref_parts) if pref_parts else "your preferences"
    
    intro = f"Fantastic! I found {count} excellent options that match {pref_text}. "
    
    if recommendations:
        price_range = [r['price'] for r in recommendations]
        min_price, max_price = min(price_range), max(price_range)
        if min_price != max_price:
            intro += f"Prices range from €{min_price} to €{max_price} per night. "
    
    intro += "Here are my top recommendations:"
    
    return intro

def generate_semantic_recommendations(preferences: Dict, user_query: str, limit: int = 10) -> List[Dict]:
    """基于语义搜索的推荐生成（待实现）"""
    print(f"语义搜索推荐暂未实现，回退到结构化推荐。用户查询: {user_query}")
    return generate_recommendations_from_preferences(preferences, limit, user_query)

# 🎯 主要的集成函数，用于在routes.py中调用
def process_preference_update(user_message: str, history: List, 
                            conv_state: ConversationState, use_llm: bool = False, structured_data=None) -> Dict:
    """
    处理偏好更新的主要函数 
    """
    return handle_preference_update_route(user_message, history, conv_state, use_llm, structured_data=structured_data)

def process_recommendation_request(user_message: str, history: List,
                                 conv_state: ConversationState) -> Dict:
    """
    处理推荐请求的主要函数
    """
    semantic_keywords = ['wifi', 'clean', 'quiet', 'cozy', 'modern', 'spacious', 'bright']
    use_semantic = any(keyword in user_message.lower() for keyword in semantic_keywords)
    
    return handle_recommendation_request_route(user_message, history, conv_state, use_semantic)