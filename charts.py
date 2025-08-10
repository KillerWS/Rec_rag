from db import execute_query

def generate_price_distribution():
    """生成价格分布数据"""
    query = """
    SELECT 
        CASE 
            WHEN price < 50 THEN '0-50'
            WHEN price BETWEEN 50 AND 100 THEN '50-100'
            WHEN price BETWEEN 100 AND 150 THEN '100-150'
            WHEN price BETWEEN 150 AND 200 THEN '150-200'
            ELSE '200+'
        END AS price_range,
        COUNT(*) AS count
    FROM listings
    GROUP BY price_range
    """
    df = execute_query(query)
    print(df)
    return {
        "title": "Price Distribution",
        "type": "pie",
        "data": [{"name": row["price_range"], "value": row["count"]} for _, row in df.iterrows()]
    }


def generate_neighbourhood_aggregation(min_price, max_price):
    """生成某价格区间的房源区域分布"""
    query = f"""
    SELECT neighbourhood, COUNT(*) AS listing_count
    FROM listings
    WHERE price BETWEEN {min_price} AND {max_price}
    GROUP BY neighbourhood
    ORDER BY listing_count DESC
    """
    df = execute_query(query)
    return {
        "title": "Neighbourhood Distribution",
        "type": "bar",
        "data": [{"name": row["neighbourhood"], "value": row["listing_count"]} for _, row in df.iterrows()]
    }

from db import execute_query

def generate_chart_data(chart_type, min_price=0, max_price=9999, neighbourhood=None, budget_min=None, budget_max=None):
    """根据图表类型生成 ECharts 兼容的数据"""

    if chart_type == "price_pie":
        query = """
        SELECT 
            CASE 
                WHEN price < 100 THEN '0-100'
                WHEN price >= 100 AND price < 200 THEN '100-200'
                WHEN price >= 200 AND price < 300 THEN '200-300'
                WHEN price >= 300 AND price < 400 THEN '300-400'
                ELSE '400+'
            END AS price_range,
            COUNT(*) AS count
        FROM listings
        GROUP BY price_range
        ORDER BY 
            MIN(CASE 
                WHEN price < 100 THEN 0
                WHEN price >= 100 AND price < 200 THEN 100
                WHEN price >= 200 AND price < 300 THEN 200
                WHEN price >= 300 AND price < 400 THEN 300
                ELSE 400
            END)
        """
        df = execute_query(query)

        # ✅ 如果希望支持高亮预算段（可选，暂返回空数组）
        def get_range_labels(budget_min, budget_max):
            if budget_min is None or budget_max is None:
                return []

            bins = [
                ("0-100", 0, 100),
                ("100-200", 100, 200),
                ("200-300", 200, 300),
                ("300-400", 300, 400),
                ("400+", 400, float("inf")),
            ]
            overlap_bins = []
            for label, low, high in bins:
                if not (budget_max < low or budget_min > high):
                    overlap_bins.append(label)
            return overlap_bins

        highlight_ranges = get_range_labels(budget_min, budget_max)

        return {
            "title": "Price Segments (Pie)",
            "type": "pie",
            "data": [{"name": row["price_range"], "value": int(row["count"])} for _, row in df.iterrows()],
            "highlight": highlight_ranges
        }

    elif chart_type == "price_histogram":
        print(budget_min, budget_max)

        query = """
        SELECT 
            CASE 
                WHEN price < 50 THEN '0-50'
                WHEN price >= 50 AND price < 100 THEN '50-100'
                WHEN price >= 100 AND price < 150 THEN '100-150'
                WHEN price >= 150 AND price < 200 THEN '150-200'
                WHEN price >= 200 AND price < 250 THEN '200-250'
                WHEN price >= 250 AND price < 300 THEN '250-300'
                WHEN price >= 300 AND price < 400 THEN '300-400'
                ELSE '400+'
            END AS price_range,
            COUNT(*) AS count
        FROM listings
        GROUP BY price_range
        ORDER BY 
            MIN(CASE 
                WHEN price < 50 THEN 0
                WHEN price >= 50 AND price < 100 THEN 50
                WHEN price >= 100 AND price < 150 THEN 100
                WHEN price >= 150 AND price < 200 THEN 150
                WHEN price >= 200 AND price < 250 THEN 200
                WHEN price >= 250 AND price < 300 THEN 250
                WHEN price >= 300 AND price < 400 THEN 300
                ELSE 400
            END)
        """
        df = execute_query(query)

        # 聚合总数和主力区间
        total = df['count'].sum()
        top_range = df.loc[df['count'].idxmax()]['price_range']
        top_count = df['count'].max()
        top_percent = round((top_count / total) * 100, 1)

        # ✅ 匹配用户预算区间到区间标签
        def get_range_labels(budget_min, budget_max):
            if budget_min is None or budget_max is None:
                return []

            bins = [
                ("0-50", 0, 50),
                ("50-100", 50, 100),
                ("100-150", 100, 150),
                ("150-200", 150, 200),
                ("200-250", 200, 250),
                ("250-300", 250, 300),
                ("300-400", 300, 400),
                ("400+", 400, float("inf")),
            ]
            overlap_bins = []
            for label, low, high in bins:
                if not (budget_max < low or budget_min > high):
                    overlap_bins.append(label)
            return overlap_bins

        highlight_ranges = get_range_labels(budget_min, budget_max)

        return {
            "title": "Price Histogram",
            "type": "bar",
            "data": [{"name": row["price_range"], "value": int(row["count"])} for _, row in df.iterrows()],
            "highlight": highlight_ranges,
            "description": f"The majority of listings fall into the '{top_range}' price range, accounting for approx. {top_percent}%."
        }


    # elif chart_type == "price_histogram":
    #     # budget = request.args.get('budget', default=None, type=int)
    #     print(budget_min, budget_max)
    #     query = """
    #     SELECT 
    #         CASE 
    #             WHEN price < 50 THEN '0-50'
    #             WHEN price BETWEEN 50 AND 100 THEN '50-100'
    #             WHEN price BETWEEN 100 AND 150 THEN '100-150'
    #             WHEN price BETWEEN 150 AND 200 THEN '150-200'
    #             WHEN price BETWEEN 200 AND 200 THEN '200-250'
    #             WHEN price BETWEEN 250 AND 200 THEN '250-300'
    #             ELSE '300+'
    #         END AS price_range,
    #         COUNT(*) AS count
    #     FROM listings
    #     GROUP BY price_range
    #     ORDER BY 
    #         MIN(CASE 
    #             WHEN price < 50 THEN 0
    #             WHEN price BETWEEN 50 AND 100 THEN 50
    #             WHEN price BETWEEN 100 AND 150 THEN 100
    #             WHEN price BETWEEN 150 AND 200 THEN 150
    #             WHEN price BETWEEN 200 AND 250 THEN 200
    #             WHEN price BETWEEN 250 AND 300 THEN '250
    #             ELSE 300
    #         END)
    #     """
    #     df = execute_query(query)

    #     # 计算最主要区间用于说明
    #     total = df['count'].sum()
    #     top_range = df.loc[df['count'].idxmax()]['price_range']
    #     top_count = df['count'].max()
    #     top_percent = round((top_count / total) * 100, 1)

    #     # ✅ 判断预算所在区间
    #     def get_range_labels(budget_min, budget_max):
    #         if budget_min is None or budget_max is None:
    #             return []

    #         bins = [
    #             ("0-50", 0, 50),
    #             ("50-100", 50, 100),
    #             ("100-150", 100, 150),
    #             ("150-200", 150, 200),
    #             ("200+", 200, float("inf")),
    #         ]
    #         overlap_bins = []
    #         for label, low, high in bins:
    #             # 区间有交集就算
    #             if not (budget_max < low or budget_min > high):
    #                 overlap_bins.append(label)
    #         return overlap_bins
    
    #     highlight_ranges = get_range_labels(budget_min, budget_max)

    #     return {
    #         "title": "Price Histogram",
    #         "type": "bar",
    #         "data": [{"name": row["price_range"], "value": int(row["count"])} for _, row in df.iterrows()],
    #         "highlight": highlight_ranges,
    #         "description": f"当前房源主要集中在“{top_range}”价格段，占总房源的约 {top_percent}%。"
    #     }
    
    elif chart_type == "neighbourhood_distribution":
        query = f"""
        SELECT neighbourhood, COUNT(*) AS listing_count
        FROM listings
        WHERE price BETWEEN {min_price} AND {max_price}
        GROUP BY neighbourhood
        ORDER BY listing_count DESC
        LIMIT 10
        """
        df = execute_query(query)
        return {
            "title": "Neighbourhood Distribution",
            "type": "bar",
            "data": [{"name": row["neighbourhood"], "value": int(row["listing_count"])} for _, row in df.iterrows()]
        }

    elif chart_type == "review_topN":
        if not neighbourhood:
            return {"error": "Missing neighbourhood parameter for review_topN chart"}

        query = f"""
        SELECT l.id, l.name, COUNT(r.id) AS review_count
        FROM listings AS l
        JOIN reviews AS r ON l.id = r.listing_id
        WHERE l.neighbourhood = %s 
          AND l.price BETWEEN %s AND %s
        GROUP BY l.id, l.name
        ORDER BY review_count DESC
        LIMIT 10
        """
        df = execute_query(query, (neighbourhood, min_price, max_price))
        return {
            "title": f"Top 10 Reviewed Listings in {neighbourhood}",
            "type": "bar",
            "data": [{"name": row["name"], "value": int(row["review_count"])} for _, row in df.iterrows()]
        }

    return {"error": "Invalid chart type"}

