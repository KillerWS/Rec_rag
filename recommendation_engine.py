"""
recommendation_engine.py
修正的推荐引擎模块 - 使用独立地理信息和可选地理筛选
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from db import execute_query
import json

# 🎯 导入独立的地理信息模块
from berlin_geography import berlin_geo, is_location_mentioned

class RecommendationEngine:
    """智能推荐引擎，结合结构化查询和可选地理筛选"""
    
    def __init__(self):
        self.geo_manager = berlin_geo
    
    def validate_preferences(self, preferences: Dict) -> Dict:
        """🎯 验证和修正偏好数据"""
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
        
        # 🎯 验证地区信息（使用独立地理模块）
        if validated_prefs.get('neighbourhood_group_cleansed'):
            all_groups = self.geo_manager.get_all_neighbourhood_groups()
            if validated_prefs['neighbourhood_group_cleansed'] not in all_groups:
                changes_made.append(f"未知大区: {validated_prefs['neighbourhood_group_cleansed']} -> None")
                validated_prefs['neighbourhood_group_cleansed'] = None
        
        if validated_prefs.get('neighbourhood_cleansed'):
            all_neighbourhoods = self.geo_manager.get_all_neighbourhoods()
            if validated_prefs['neighbourhood_cleansed'] not in all_neighbourhoods:
                changes_made.append(f"未知社区: {validated_prefs['neighbourhood_cleansed']} -> None")
                validated_prefs['neighbourhood_cleansed'] = None
        
        if changes_made:
            print("⚠️  数据修正:")
            for change in changes_made:
                print(f"  - {change}")
        
        return validated_prefs
    
    def should_apply_geo_filter(self, preferences: Dict, original_query: str = "") -> bool:
        """
        🎯 判断是否应该应用地理筛选
        
        Args:
            preferences: 用户偏好
            original_query: 用户原始查询
            
        Returns:
            True if should apply geo filter
        """
        # 🎯 策略1: 用户明确指定了地理信息
        has_geo_prefs = (preferences.get('neighbourhood_group_cleansed') or 
                        preferences.get('neighbourhood_cleansed'))
        
        # 🎯 策略2: 原始查询中提到了地理位置
        query_mentions_location = False
        if original_query:
            query_mentions_location = is_location_mentioned(original_query)
        
        should_apply = has_geo_prefs or query_mentions_location
        
        print(f"🗺️  地理筛选决策:")
        print(f"  - 有地理偏好: {has_geo_prefs}")
        print(f"  - 查询提及位置: {query_mentions_location}")
        print(f"  - 应用地理筛选: {should_apply}")
        
        return should_apply
    
    def generate_recommendations(self, preferences: Dict, limit: int = 10, 
                               original_query: str = "") -> List[Dict]:
        """
        根据用户偏好生成推荐
        
        Args:
            preferences: 用户偏好字典
            limit: 返回结果数量限制
            original_query: 用户原始查询（用于判断地理意图）
            
        Returns:
            推荐列表，包含匹配度评分
        """
        try:
            print(f"🎯 生成推荐，原始偏好: {preferences}")
            
            # 🎯 验证和修正偏好
            validated_prefs = self.validate_preferences(preferences)
            print(f"✅ 验证后偏好: {validated_prefs}")
            
            # 🎯 判断是否应用地理筛选
            apply_geo_filter = self.should_apply_geo_filter(validated_prefs, original_query)
            
            # 第一步：基于结构化字段进行SQL筛选
            base_results = self._get_base_recommendations(
                validated_prefs, 
                limit * 3, 
                apply_geo_filter=apply_geo_filter
            )
            
            if base_results.empty:
                print("❌ SQL查询无结果，尝试放宽条件...")
                # 🎯 放宽条件重试（移除地理筛选）
                relaxed_prefs = self._relax_preferences(validated_prefs)
                print(f"🔄 放宽后偏好: {relaxed_prefs}")
                base_results = self._get_base_recommendations(
                    relaxed_prefs, 
                    limit * 5, 
                    apply_geo_filter=False  # 放宽时不应用地理筛选
                )
                
                if base_results.empty:
                    print("❌ 放宽条件后仍无结果")
                    return []
            
            print(f"✅ SQL查询返回 {len(base_results)} 条结果")
            
            # 第二步：基于关键词进行语义匹配和评分
            scored_results = self._score_with_semantic_matching(base_results, validated_prefs)
            
            # 第三步：排序和返回顶部结果
            final_recommendations = self._rank_and_format_results(scored_results, validated_prefs, limit)
            
            return final_recommendations
            
        except Exception as e:
            print(f"❌ 推荐生成失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _relax_preferences(self, preferences: Dict) -> Dict:
        """放宽偏好条件"""
        relaxed = preferences.copy()
        
        # 移除可能过于严格的条件
        relaxed_items = []
        
        if relaxed.get('minimum_nights'):
            relaxed['minimum_nights'] = None
            relaxed_items.append("最小停留天数")
        
        if relaxed.get('price_min'):
            relaxed['price_min'] = None
            relaxed_items.append("价格下限")
        
        if relaxed.get('neighbourhood_group_cleansed'):
            relaxed['neighbourhood_group_cleansed'] = None
            relaxed_items.append("大区限制")
            
        if relaxed.get('neighbourhood_cleansed'):
            relaxed['neighbourhood_cleansed'] = None
            relaxed_items.append("社区限制")
        
        if relaxed_items:
            print(f"🔄 放宽条件: {', '.join(relaxed_items)}")
        
        return relaxed
    
    def _get_base_recommendations(self, preferences: Dict, limit: int, 
                                apply_geo_filter: bool = True) -> pd.DataFrame:
        """🎯 修正的SQL查询 - 可选地理筛选"""
        
        conditions = []
        params = []
        
        # === 价格筛选 ===
        if preferences.get('price_min') and preferences['price_min'] > 0:
            conditions.append("price >= %s")
            params.append(preferences['price_min'])
        if preferences.get('price_max') and preferences['price_max'] > 0:
            conditions.append("price <= %s")
            params.append(preferences['price_max'])
            
        # === 房间类型筛选 ===
        if preferences.get('room_type'):
            conditions.append("room_type = %s")
            params.append(preferences['room_type'])
            
        # === 🎯 可选的地理筛选 ===
        if apply_geo_filter:
            if preferences.get('neighbourhood_cleansed'):
                # 具体社区优先
                conditions.append("neighbourhood_cleansed = %s")
                params.append(preferences['neighbourhood_cleansed'])
                print(f"🗺️  应用社区筛选: {preferences['neighbourhood_cleansed']}")
            elif preferences.get('neighbourhood_group_cleansed'):
                # 大区筛选
                conditions.append("neighbourhood_group_cleansed = %s")
                params.append(preferences['neighbourhood_group_cleansed'])
                print(f"🗺️  应用大区筛选: {preferences['neighbourhood_group_cleansed']}")
        else:
            print("🗺️  跳过地理筛选，返回全柏林结果")
            
        # === 停留天数筛选 ===
        if preferences.get('minimum_nights') and preferences['minimum_nights'] > 0:
            conditions.append("minimum_nights <= %s")
            params.append(preferences['minimum_nights'])
            
        # === 热度筛选（可选）===
        if preferences.get('min_reviews') and preferences['min_reviews'] > 0:
            conditions.append("number_of_reviews >= %s")
            params.append(preferences['min_reviews'])
        
        #  id, name, host_id, host_name, neighbourhood_group_cleansed, neighbourhood_cleansed, 
        #     latitude, longitude, room_type, price, minimum_nights, 
        #     number_of_reviews, last_review, reviews_per_month, 
        #     calculated_host_listings_count, availability_365

        # 🎯 简化的SQL查询
        base_query = """
        SELECT *
        FROM listings 
        WHERE 1=1
        """
        
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
            
        # 🎯 简化的排序策略
        base_query += """
        ORDER BY 
            (COALESCE(number_of_reviews, 0) * 0.7 + 
             COALESCE(reviews_per_month, 0) * 10 * 0.3) DESC,
            price ASC
        LIMIT %s
        """
        params.append(limit)
        
        print(f"📝 SQL查询条件数: {len(conditions)}")
        print(f"📝 参数: {params}")
        
        # 🎯 安全的SQL拼接
        try:
            formatted_params = []
            for param in params:
                if isinstance(param, str):
                    escaped_param = param.replace("'", "''")
                    formatted_params.append(f"'{escaped_param}'")
                elif param is None:
                    formatted_params.append("NULL")
                else:
                    formatted_params.append(str(param))
            
            final_query = base_query
            for param in formatted_params:
                final_query = final_query.replace("%s", param, 1)
            
            print(f"📝 最终SQL: {final_query[:200]}...")
            
            result = execute_query(final_query)
            print(f"📊 查询结果: {type(result)}, 行数: {len(result)}")
            
            # 🎯 调试：显示地区分布
            if not result.empty and 'neighbourhood_group_cleansed' in result.columns:
                area_dist = result['neighbourhood_group_cleansed'].value_counts()
                print("📋 地区分布:")
                for area, count in area_dist.head(5).items():
                    print(f"  - {area}: {count} 个房源")
            
            return result
            
        except Exception as e:
            print(f"❌ SQL查询执行失败: {e}")
            return pd.DataFrame()
    
    def _score_with_semantic_matching(self, base_results: pd.DataFrame, preferences: Dict) -> pd.DataFrame:
        """语义匹配评分（简化版）"""
        
        if base_results.empty:
            return base_results
            
        base_results = base_results.copy()
        base_results['semantic_score'] = 0.0
        base_results['keyword_matches'] = ''
        
        # 提取关键词
        amenities_keywords = preferences.get('amenities_keywords', [])
        location_keywords = preferences.get('location_keywords', [])
        experience_keywords = preferences.get('experience_keywords', [])
        
        if not (amenities_keywords or location_keywords or experience_keywords):
            return base_results
        
        print(f"🔍 语义关键词匹配 - 设施: {amenities_keywords}, 位置: {location_keywords}, 体验: {experience_keywords}")
        
        # 简单关键词匹配
        for idx, row in base_results.iterrows():
            score = 0.0
            matches = []
            
            searchable_text = f"{row.get('name', '')} {row.get('neighbourhood_cleansed', '')}".lower()
            
            for keyword in amenities_keywords:
                if keyword.lower() in searchable_text:
                    score += 0.4
                    matches.append(f"amenity:{keyword}")
            
            for keyword in location_keywords:
                if keyword.lower() in searchable_text:
                    score += 0.3
                    matches.append(f"location:{keyword}")
                    
            for keyword in experience_keywords:
                if keyword.lower() in searchable_text:
                    score += 0.3
                    matches.append(f"experience:{keyword}")
            
            base_results.at[idx, 'semantic_score'] = score
            base_results.at[idx, 'keyword_matches'] = '; '.join(matches)
        
        return base_results
    
    def _rank_and_format_results(self, scored_results: pd.DataFrame, 
                                preferences: Dict, limit: int) -> List[Dict]:
        """排序结果并格式化输出"""
        
        if scored_results.empty:
            return []
        
        scored_results = scored_results.copy()
        
        # 简化的评分算法
        if len(scored_results) > 1:
            semantic_scores = scored_results['semantic_score']
            
            review_counts = scored_results['number_of_reviews'].fillna(0)
            if review_counts.max() > 0:
                review_scores = review_counts / review_counts.max()
            else:
                review_scores = pd.Series([0] * len(scored_results))
                
            prices = scored_results['price']
            # 将价格字符串转换为数值
            prices = prices.astype(float)

            # 检查价格范围
            if prices.max() > prices.min():
                # 然后再进行归一化计算
                price_scores = 1 - (prices - prices.min()) / (prices.max() - prices.min())
            else:
                # 所有价格相同时，分配中间得分
                price_scores = pd.Series([0.5] * len(scored_results))
            
            # 简化权重
            scored_results['final_score'] = (
                semantic_scores * 0.3 +     
                review_scores * 0.4 +       
                price_scores * 0.3          
            )
        else:
            scored_results['final_score'] = 1.0
        
        scored_results = scored_results.sort_values('final_score', ascending=False)
        
        # 格式化输出
        recommendations = []
        for idx, row in scored_results.head(limit).iterrows():
            rec = {
                'id': int(row['id']),
                'name': str(row['name']),
                'host_id': int(row['host_id']) if pd.notna(row['host_id']) else None,
                'host_name': str(row['host_name']) if pd.notna(row['host_name']) else '',
                'neighbourhood_group_cleansed': str(row['neighbourhood_group_cleansed']) if pd.notna(row['neighbourhood_group_cleansed']) else '',
                'neighbourhood_cleansed': str(row['neighbourhood_cleansed']) if pd.notna(row['neighbourhood_cleansed']) else '',
                'room_type': str(row['room_type']),
                'price': float(row['price']),
                'minimum_nights': int(row['minimum_nights']),
                'number_of_reviews': int(row['number_of_reviews']) if pd.notna(row['number_of_reviews']) else 0,
                'reviews_per_month': float(row['reviews_per_month']) if pd.notna(row['reviews_per_month']) else 0.0,
                'availability_365': int(row['availability_365']) if pd.notna(row['availability_365']) else 0,
                'latitude': float(row['latitude']) if pd.notna(row['latitude']) else 0.0,
                'longitude': float(row['longitude']) if pd.notna(row['longitude']) else 0.0,
                
                # 推荐系统字段
                'final_score': float(row['final_score']),
                'semantic_score': float(row['semantic_score']),
                'keyword_matches': str(row['keyword_matches']),
                'match_reason': self._generate_match_reason(row, preferences)
            }
            recommendations.append(rec)
            
        return recommendations
    
    def _generate_match_reason(self, row: pd.Series, preferences: Dict) -> str:
        """生成匹配原因说明"""
        reasons = []
        
        if preferences.get('price_max'):
            reasons.append(f"Under €{preferences['price_max']}")
        
        if row.get('neighbourhood_cleansed'):
            reasons.append(f"In {row['neighbourhood_cleansed']}")
        elif row.get('neighbourhood_group_cleansed'):
            reasons.append(f"In {row['neighbourhood_group_cleansed']}")
            
        if row.get('room_type'):
            reasons.append(f"{row['room_type']}")
            
        if row.get('number_of_reviews', 0) > 10:
            reasons.append(f"{int(row['number_of_reviews'])} reviews")
            
        return "; ".join(reasons) if reasons else "Basic match"

    def enhance_with_semantic_analysis(self, recommendations, semantic_dimensions, user_query=""):
        """
        使用语义分析增强推荐结果，特别处理User Care等特殊维度
        
        Args:
            recommendations: 初步推荐列表
            semantic_dimensions: 语义维度字典 (如 {'user care': '✨ premium service expected'})
            user_query: 用户原始查询，用于上下文
        
        Returns:
            增强后的推荐列表
        """
        if not semantic_dimensions or not recommendations:
            return recommendations
            
        print(f"🔍 开始语义分析推荐增强，语义维度: {semantic_dimensions}")
        
        # 深拷贝，避免修改原始推荐
        import copy
        enhanced_recommendations = copy.deepcopy(recommendations)
        
        # 处理"User Care"维度
        user_care = semantic_dimensions.get('user care', '')
        if user_care:
            print(f"🌟 处理User Care语义维度: '{user_care}'")
            self._enhance_with_user_care(enhanced_recommendations, user_care)
        
        # 可以添加其他语义维度处理...
        
        return enhanced_recommendations
    
    def _enhance_with_user_care(self, recommendations, user_care_value):
        """
        基于User Care维度增强推荐
        
        Args:
            recommendations: 推荐列表
            user_care_value: User Care值 (例如 "✨ premium service expected")
        """
        # 提取关键词和意图
        keywords = self._extract_user_care_keywords(user_care_value)
        
        print(f"🔑 从User Care中提取的关键词: {keywords}")
        
        # 为每个推荐项添加语义匹配数据（暂不修改得分）
        for rec in recommendations:
            rec["semantic_match"] = {
                "user_care": {
                    "original_value": user_care_value,
                    "extracted_keywords": keywords,
                    "match_level": "not_analyzed"  # 初始值
                }
            }
            
            # 这里可以添加基于关键词的简单匹配逻辑
            # 示例：简单关键词匹配
            if "name" in rec:
                name_lower = rec["name"].lower()
                matched_keywords = [k for k in keywords if k in name_lower]
                if matched_keywords:
                    rec["semantic_match"]["user_care"]["matched_keywords"] = matched_keywords
                    rec["semantic_match"]["user_care"]["match_level"] = "basic_match"
    
    def _extract_user_care_keywords(self, user_care_value):
        """从User Care值中提取关键词"""
        # 移除特殊字符
        clean_value = user_care_value.replace("✨", "").strip()
        
        # 预定义关键词映射
        keyword_mapping = {
            "premium": ["premium", "luxury", "high-end", "quality", "exclusive"],
            "service": ["service", "hospitality", "attention", "staff", "host"],
            "expected": ["expected", "required", "needed", "anticipated"]
        }
        
        # 提取词素
        words = clean_value.lower().split()
        
        # 扩展关键词
        extended_keywords = []
        for word in words:
            extended_keywords.append(word)
            # 添加映射的同义词
            for key, synonyms in keyword_mapping.items():
                if word == key:
                    extended_keywords.extend(synonyms)
        
        return list(set(extended_keywords))  # 去重

def generate_recommendations_from_preferences(preferences: Dict, limit: int = 10,
                                             original_query: str = "") -> List[Dict]:
    """
    主要推荐生成函数，供外部调用
    
    Args:
        preferences: 用户偏好字典
        limit: 返回结果数量
        original_query: 用户原始查询（用于地理意图判断）
        
    Returns:
        推荐列表
    """
    engine = RecommendationEngine()
    return engine.generate_recommendations(preferences, limit, original_query)

# 🧪 单元测试函数
def test_recommendation_engine():
    """测试推荐引擎"""
    print("=" * 60)
    print("🧪 推荐引擎单元测试 - 可选地理筛选版")
    print("=" * 60)
    
    # 🎯 测试用例1：无地理信息（应该不应用地理筛选）
    test_preferences_1 = {
        'room_type': 'Private room',
        'price_max': 100,
        'amenities_keywords': [],
        'location_keywords': [],
        'experience_keywords': []
    }
    
    print("\n📋 测试用例1 - 无地理信息:")
    print(f"偏好: {test_preferences_1}")
    recommendations_1 = generate_recommendations_from_preferences(
        test_preferences_1, limit=5, original_query="I need a private room under 100 euros"
    )
    print(f"结果: {len(recommendations_1)} 个推荐")
    for i, rec in enumerate(recommendations_1[:3]):
        print(f"  {i+1}. {rec['name']} - €{rec['price']} - {rec['neighbourhood_group_cleansed']}")
    
    # 🎯 测试用例2：明确地理信息（应该应用地理筛选）
    test_preferences_2 = {
        'room_type': 'Private room',
        'price_max': 150,
        'neighbourhood_group_cleansed': 'Mitte',
        'amenities_keywords': [],
        'location_keywords': [],
        'experience_keywords': []
    }
    
    print("\n📋 测试用例2 - 明确地理信息:")
    print(f"偏好: {test_preferences_2}")
    recommendations_2 = generate_recommendations_from_preferences(
        test_preferences_2, limit=5, original_query="I want a private room in Mitte"
    )
    print(f"结果: {len(recommendations_2)} 个推荐")
    for i, rec in enumerate(recommendations_2[:3]):
        print(f"  {i+1}. {rec['name']} - €{rec['price']} - {rec['neighbourhood_group_cleansed']}")
    
    # 🎯 测试用例3：异常数据修正
    test_preferences_3 = {
        'room_type': 'Private room',
        'price_min': -7,  # 异常价格
        'price_max': 13,  # 异常价格
        'neighbourhood_group_cleansed': 'Unknown Area',  # 未知地区
        'minimum_nights': 3,
        'amenities_keywords': [],
        'location_keywords': [],
        'experience_keywords': []
    }
    
    print("\n📋 测试用例3 - 异常数据修正:")
    print(f"偏好: {test_preferences_3}")
    recommendations_3 = generate_recommendations_from_preferences(
        test_preferences_3, limit=5, original_query="show me all listings"
    )
    print(f"结果: {len(recommendations_3)} 个推荐")
    for i, rec in enumerate(recommendations_3[:3]):
        print(f"  {i+1}. {rec['name']} - €{rec['price']} - {rec['neighbourhood_group_cleansed']}")

if __name__ == "__main__":
    test_recommendation_engine()

def recommend_listings(sql_query, user_preference, used_preferences=[], top_k=10):
    """
    兼容旧API的推荐函数 - 将旧接口适配到新的推荐引擎
    
    Args:
        sql_query: SQL查询字符串
        user_preference: 用户偏好字典
        used_preferences: 已使用的偏好列表
        top_k: 返回结果数量
    
    Returns:
        推荐列表
    """
    print("🔄 使用新推荐引擎处理旧接口请求")
    
    try:
        # 过滤不支持的维度，避免处理错误
        supported_dimensions = ["price", "price_min", "price_max", "room_type", "location", 
                               "neighbourhood_cleansed", "neighbourhood_group_cleansed", "minimum_nights", "min_reviews"]
        filtered_preference = {}
        semantic_dimensions = {}
        
        # 分离常规维度和语义维度
        for key, value in user_preference.items():
            key_lower = key.lower()
            if key_lower in supported_dimensions:
                filtered_preference[key_lower] = value
            else:
                # 将不支持的维度视为语义维度
                semantic_dimensions[key_lower] = value
                print(f"⚠️ 检测到语义维度: {key}='{value}' (将用于语义推荐但不计入常规评分)")
        
        # 1. 执行SQL查询获取初始结果集
        from db import execute_query
        base_results = execute_query(sql_query)
        
        if base_results.empty:
            print("❌ SQL查询无结果")
            return []
        
        # 2. 创建推荐引擎实例
        engine = RecommendationEngine()
        
        # 3. 使用语义匹配和评分
        scored_results = engine._score_with_semantic_matching(base_results, filtered_preference)
        
        # 4. 排序并格式化
        final_results = engine._rank_and_format_results(scored_results, filtered_preference, top_k)
        
        # 5. 确保结果包含 recommendation_score 字段
        for item in final_results:
            if "final_score" in item and "recommendation_score" not in item:
                item["recommendation_score"] = item["final_score"]
        
        # 6. 如果有语义维度，标记需要进一步语义分析
        if semantic_dimensions:
            for item in final_results:
                item["needs_semantic_analysis"] = True
                item["semantic_dimensions"] = semantic_dimensions
        
        return final_results
        
    except Exception as e:
        print(f"❌ 推荐生成失败: {e}")
        import traceback
        traceback.print_exc()
        return []

def calculate_recommendation_score(listing, preferences, df, used_preferences=[]):
    """
    计算推荐分数
    
    Args:
        listing: 单个房源数据
        preferences: 用户偏好
        df: 包含所有候选房源的DataFrame
        used_preferences: 已使用的偏好维度
        
    Returns:
        float: 推荐分数
    """
    score = 0.0
    
    # 价格匹配分数
    if "price" in listing:
        price = listing["price"]
        # 根据价格与预算的匹配度计算分数
        price_score = 1.0
        if preferences.get("price_min") and preferences.get("price_max"):
            if price >= preferences["price_min"] and price <= preferences["price_max"]:
                price_score = 1.0
            else:
                price_score = 0.5
        score += price_score * 2.0  # 价格权重高
    
    # 评分和评论数量分数
    if "review_scores_rating" in listing and listing["review_scores_rating"] > 0:
        score += (listing["review_scores_rating"] / 100.0) * 1.5
    
    if "number_of_reviews" in listing and df["number_of_reviews"].max() > 0:
        score += (listing["number_of_reviews"] / df["number_of_reviews"].max()) * 1.0
    
    if "reviews_per_month" in listing and df["reviews_per_month"].max() > 0:
        score += (listing["reviews_per_month"] / df["reviews_per_month"].max()) * 0.5
    
    return score

def recommend_listings_with_semantic(sql_query, user_preference, used_preferences=[], top_k=5, user_query=""):
    """
    增强版推荐函数，包含语义分析
    
    Args:
        sql_query: SQL查询字符串
        user_preference: 用户偏好字典
        used_preferences: 已使用的偏好列表
        top_k: 返回结果数量
        user_query: 用户原始查询
    
    Returns:
        包含语义增强的推荐列表
    """
    # 分离标准维度和语义维度
    supported_dimensions = ["price", "price_min", "price_max", "room_type", "location", 
                          "neighbourhood_cleansed", "neighbourhood_group_cleansed", "minimum_nights", "min_reviews"]
    standard_preference = {}
    semantic_dimensions = {}
    
    for key, value in user_preference.items():
        key_lower = key.lower()
        if key_lower in supported_dimensions:
            standard_preference[key_lower] = value
        else:
            semantic_dimensions[key_lower] = value
    
    # 1. 获取基础推荐结果
    base_recommendations = recommend_listings(sql_query, standard_preference, used_preferences, top_k)
    
    # 2. 如果有语义维度，进行语义增强
    if semantic_dimensions:
        engine = RecommendationEngine()
        enhanced_recommendations = engine.enhance_with_semantic_analysis(
            base_recommendations, 
            semantic_dimensions,
            user_query
        )
        return enhanced_recommendations
    else:
        return base_recommendations

# 未来：集成RAG检索结果
def enhance_with_rag_results(recommendations, semantic_dimensions, rag_results=[]):
    """
    使用RAG检索结果增强推荐
    
    Args:
        recommendations: 初步推荐列表
        semantic_dimensions: 语义维度字典
        rag_results: RAG检索结果
    
    Returns:
        增强后的推荐列表
    """
    if not rag_results or not recommendations:
        return recommendations
    
    print(f"📚 使用{len(rag_results)}条RAG结果增强推荐")
    
    # 深拷贝，避免修改原始推荐
    import copy
    enhanced_recommendations = copy.deepcopy(recommendations)
    
    # TODO: 实现以下RAG增强逻辑：
    # 1. 从RAG结果中提取与语义维度相关的关键信息
    # 2. 将这些信息与推荐项匹配
    # 3. 为匹配的推荐项添加额外的语义分数和解释
    
    return enhanced_recommendations