import pandas as pd
from typing import Dict, Optional
from db import execute_query
from .utils import generate_error_response


def _generate_review_analysis_echarts(df: pd.DataFrame) -> Dict:
    return {
        "title": {"text": "Review Count Analysis", "left": "center"},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": df["review_range"].tolist()},
        "yAxis": {"type": "value", "name": "Number of Listings"},
        "series": [{
            "name": "Listings",
            "type": "bar",
            "data": df["count"].tolist(),
            "itemStyle": {"color": "#fac858"}
        }]
    }


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    where_conditions = ["number_of_reviews > 0", "price IS NOT NULL"]
    if preferences.get("neighbourhood_group"):
        safe_neighbourhood = preferences["neighbourhood_group"].replace("'", "''")
        where_conditions.append(f"neighbourhood_group_cleansed = '{safe_neighbourhood}'")
    sql = f"""
    SELECT 
        CASE 
            WHEN number_of_reviews BETWEEN 0 AND 10 THEN '0-10 reviews'
            WHEN number_of_reviews BETWEEN 11 AND 50 THEN '11-50 reviews'
            WHEN number_of_reviews BETWEEN 51 AND 100 THEN '51-100 reviews'
            WHEN number_of_reviews BETWEEN 101 AND 200 THEN '101-200 reviews'
            ELSE '200+ reviews' 
        END AS review_range,
        COUNT(*) as count,
        AVG(price) as avg_price
    FROM listings 
    WHERE {' AND '.join(where_conditions)}
    GROUP BY review_range
    ORDER BY MIN(number_of_reviews)
    """
    df = execute_query(sql)
    return {
        "success": True,
        "chart_config": {"type": "bar", "title": "Review Count Analysis", "x_axis": "Review Range", "y_axis": "Number of Listings"},
        "data": {
            "categories": df["review_range"].tolist(),
            "values": df["count"].tolist(),
            "avg_prices": df["avg_price"].round(2).tolist()
        },
        "metadata": {"total_records": int(df["count"].sum())},
        "echarts_option": _generate_review_analysis_echarts(df)
    } 