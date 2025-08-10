from db import execute_query

def register_aggregation_functions():
    """注册全局聚合查询（价格分布、区域分布）"""
    print("✅ 聚合函数已注册")



# overall_aggregation: price
# 可视化建议：

# 卡片式/数值概览：无需复杂图表；展示“房源总数、均价、最低价、最高价”等一目了然。
# 如果想对比多个城市，可用柱状图对比“城市 vs. 均价/房源数”。

import pandas as pd
from db import execute_query  # ✅ 你已有的查询函数

def overall_aggregation():

    """
    返回整体房源概览：房源总数、价格均值、最小/最大/中位价格
    """
    # 基础聚合
    summary_sql = """
    SELECT 
        COUNT(*) AS total_listings,
        AVG(price) AS avg_price,
        MAX(price) AS max_price,
        MIN(price) AS min_price
    FROM listings
    """
    df_summary = execute_query(summary_sql)

    # 查询全部价格，计算中位数
    median_sql = "SELECT price FROM listings"
    df_price = execute_query(median_sql)
    print(df_price)
    median_price = df_price['price'].median()

    # 构造结果返回
    return {
        "total_listings": int(df_summary.iloc[0]["total_listings"]),
        "avg_price": round(float(df_summary.iloc[0]["avg_price"]), 2),
        "max_price": float(df_summary.iloc[0]["max_price"]),
        "min_price": float(df_summary.iloc[0]["min_price"]),
        "median_price": round(float(median_price), 2)
    }


def neighbourhood_aggregation(budget_min: int, budget_max: int):
    """
    返回所有 top 区域的 房源数 + 平均价格，并标记哪些在预算范围内（高亮）
    """
    query = """
    SELECT 
        neighbourhood,
        COUNT(*) AS listing_count,
        ROUND(AVG(price), 2) AS avg_price
    FROM listings
    GROUP BY neighbourhood
    ORDER BY listing_count DESC
    LIMIT 10
    """
    df = execute_query(query)

    highlight_neighbourhoods = []
    for _, row in df.iterrows():
        if budget_min <= row["avg_price"] <= budget_max:
            highlight_neighbourhoods.append(row["neighbourhood"])

    return {
        "title": "Top Neighbourhoods (by listings & price)",
        "type": "bar_dual",
        "xAxis": [row["neighbourhood"] for _, row in df.iterrows()],
        "series": {
            "Listings": [int(row["listing_count"]) for _, row in df.iterrows()],
            "Avg Price (€)": [float(row["avg_price"]) for _, row in df.iterrows()]
        },
        "highlight": highlight_neighbourhoods
    }


def room_type_distribution_by_price_bins(user_min=0, user_max=9999, bin_size=100):
    """
    根据用户预算区间动态划分价格段，返回用于堆叠柱状图的数据
    """
    import math
    bins = list(range(0, user_max + bin_size, bin_size))  # 如 [0,100,200,300,...]
    bin_labels = [f"{low}-{low+bin_size-1}" for low in bins[:-1]]

    # 构建 SQL CASE 语句
    case_stmt = "CASE\n"
    for i in range(len(bin_labels)):
        low = bins[i]
        high = bins[i + 1] - 1
        label = bin_labels[i]
        case_stmt += f"  WHEN price BETWEEN {low} AND {high} THEN '{label}'\n"
    case_stmt += "  ELSE 'Other'\nEND AS price_bin"

    sql = f"""
    SELECT 
      {case_stmt},
      room_type,
      COUNT(*) AS count
    FROM listings
    WHERE price BETWEEN {user_min} AND {user_max}
    GROUP BY price_bin, room_type
    ORDER BY price_bin
    """
    
    df = execute_query(sql)

    # 转换成堆叠图结构
    pivot_df = df.pivot(index="price_bin", columns="room_type", values="count").fillna(0).astype(int).reset_index()

    # 计算 xAxis 和 series
    xAxis = list(pivot_df["price_bin"])
    room_types = pivot_df.columns.drop("price_bin")
    series = []
    for rt in room_types:
        series.append({
            "name": rt,
            "data": list(pivot_df[rt])
        })

    # 自动高亮：找到用户预算上限所在区间的 index
    highlight_index = None
    for idx, label in enumerate(xAxis):
        try:
            low, high = map(int, label.split("-"))
            if low <= user_max <= high:
                highlight_index = idx
                break
        except:
            continue

    return {
        "xAxis": xAxis,
        "series": series,
        "highlight": [highlight_index] if highlight_index is not None else [],
        "title": f"Room Type Distribution (by {bin_size}€ bins)"
    }

def word_cloud_rag_retrieve(user_query):
    """
    基于用户查询，返回相关的关键词和对应的房源数
    """