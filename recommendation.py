import re
import pandas as pd
from db import execute_query
from datetime import datetime

def parse_budget(budget_str):
    """解析预算字符串"""
    match = re.search(r'(\d+)', budget_str)
    return float(match.group(1)) if match else None
def parse_budget_range(budget_str):
    """解析价格范围字符串，例如 '100-200'"""
    try:
        parts = budget_str.split("-")
        if len(parts) == 2:
            return int(parts[0]), int(parts[1])
    except:
        return None, None
    return None, None

def convert_selected_dimensions(dimensions: list) -> dict:
    """将前端传来的数组格式转换为 dict"""
    result = {}
    for item in dimensions:
        key = item['key'].strip().lower().replace(" ", "_")  # e.g. 'Property Type' -> 'property_type'
        result[key] = item['value'].strip()
    return result

# def calculate_recommendation_score(listing, pref, df, used_preferences):
#     scores, weights = [], []

#     # ✅ 修复预算匹配逻辑（从 'budget' 改为 'price'）
#     if 'price' not in used_preferences and 'price' in pref and pref['price']:
#         low, high = parse_budget_range(pref['price'])  # 你之前定义好的解析函数
#         if low is not None and high is not None:
#             closeness = 1 - abs(listing['price'] - high) / max(high, 1)
#             scores.append(closeness)
#             weights.append(0.4)

#     # ✅ 房型匹配
#     if 'room_type' in pref:
#         user_type = pref['room_type'].strip().lower()
#         if user_type != "both":
#             listing_type = listing['room_type'].strip().lower()
#             room_type_score = 1 if user_type == listing_type else 0
#             scores.append(room_type_score)
#             weights.append(0.2)
    
#     # location 匹配 打分
#     if 'location' in pref:
#         # 假设 pref["location"] = 'true'
#         location_score = 1 if listing['neighbourhood'] else 0
#         scores.append(location_score)
#         weights.append(0.2)

#     # ✅ 热度匹配
#     popularity_score = (
#         (listing['number_of_reviews_ltm'] / df['number_of_reviews_ltm'].max()) * 0.5 +
#         (listing['reviews_per_month'] / df['reviews_per_month'].max()) * 0.6
#     )
#     scores.append(popularity_score)
#     weights.append(0.25)

#     # ✅ 入住灵活性
#     stay_flexibility_score = listing['availability_365'] / 365
#     scores.append(stay_flexibility_score)
#     weights.append(0.15)

#     total_score = sum([s * w for s, w in zip(scores, weights)]) / sum(weights)
#     return total_score

def calculate_recommendation_score(listing, pref, df, used_preferences):
    scores, weights = [], []

    # ✅ 预算 closeness — 只有用户没有明确价格偏好才打分
    if 'price' not in used_preferences and 'price' in pref:
        low, high = parse_budget_range(pref['price'])
        if low is not None and high is not None:
            closeness = 1 - abs(listing['price'] - high) / max(high, 1)
            scores.append(closeness)
            weights.append(0.4)

    # ✅ 房型匹配 — 始终打分，不能因为选择了就跳过
    if 'room type' in pref:
        user_type = pref['room type'].strip().lower()
        if user_type != "both":
            listing_type = listing['room_type'].strip().lower()
            room_type_score = 1 if user_type == listing_type else 0
            scores.append(room_type_score)
            weights.append(0.2)

    # ✅ 地点匹配（简单版） — 只要房源有位置就给分
    if 'location' in pref and pref['location'] and 'neighbourhood' in listing:
        target_area = pref['location'].lower()
        current_area = (listing['neighbourhood_group'] or '').lower()

        if target_area in current_area:
            location_score = 1.0
        else:
            location_score = 0.5  # 或 0

        scores.append(location_score)
        weights.append(0.2)  # 适当权重

    # ✅ 热度打分 — 正常使用
    popularity_score = (
        (listing['number_of_reviews_ltm'] / df['number_of_reviews_ltm'].max()) * 0.5 +
        (listing['reviews_per_month'] / df['reviews_per_month'].max()) * 0.6
    )
    scores.append(popularity_score)
    weights.append(0.2)

    # ✅ 活跃度打分
    stay_flexibility_score = listing['availability_365'] / 365
    scores.append(stay_flexibility_score)
    weights.append(0.1)

    # ✅ 🌟 社交维度打分（Social Engagement Score）
    if 'social dimension' in pref:
        # -- 评论活跃度
        reviews_monthly_score = listing['reviews_per_month'] / df['reviews_per_month'].max()

        # -- 近12个月评论
        reviews_recent_score = listing['number_of_reviews_ltm'] / df['number_of_reviews_ltm'].max()

        # -- 总评论量
        total_reviews_score = listing['number_of_reviews'] / df['number_of_reviews'].max()

        # -- 最近评论新鲜度
        if listing.get('last_review'):
            try:
                last_review_date = datetime.strptime(listing['last_review'], "%Y-%m-%d").date()
                days_since_last_review = (datetime.now().date() - last_review_date).days
                freshness_score = 1 - min(days_since_last_review / 180, 1)  # 半年内为高分
            except Exception as e:
                print(f"⚠️ last_review parse error: {e}")
                freshness_score = 0
        else:
            freshness_score = 0

        # -- 综合社交分
        social_engagement_score = (
            reviews_monthly_score * 0.3 +
            reviews_recent_score * 0.3 +
            total_reviews_score * 0.2 +
            freshness_score * 0.2
        )

        scores.append(social_engagement_score)
        weights.append(0.2)  # 社交维度适中权重
    
    # ✅ 综合得分（归一化）`
    total_score = sum([s * w for s, w in zip(scores, weights)]) / sum(weights)
    return total_score


# def recommend_listings(sql_query, user_preference, used_preferences=[], top_k=5):
#     print("recommend_listings called")
#     df_result = execute_query(sql_query)
#     # print("df_result:", df_result)

#     df_result['recommendation_score'] = df_result.apply(
#         lambda row: calculate_recommendation_score(row, user_preference, df_result, used_preferences), axis=1
#     )

#     # ✅ 只取前 top_k 个
#     recommended_listings = df_result.sort_values(
#         by='recommendation_score', ascending=False
#     ).head(top_k)
#     # print("recommended_listings--------------------")
#     # print(recommended_listings)
#     return recommended_listings.to_dict(orient='records')
def recommend_listings(sql_query, user_preference, used_preferences=[], top_k=5):
    print("recommend_listings called")
    print("Used Preferences:", used_preferences)  # 打印已完成的维度
    df_result = execute_query(sql_query)

    df_result['recommendation_score'] = df_result.apply(
        lambda row: calculate_recommendation_score(row, user_preference, df_result, used_preferences),
        axis=1
    )
    
    recommended_listings = df_result.sort_values(
        by='recommendation_score', ascending=False
    ).head(top_k)

    return recommended_listings.to_dict(orient='records')