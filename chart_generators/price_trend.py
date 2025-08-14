import pandas as pd
from typing import Dict, Optional
from db import execute_query


def _generate_price_trend_echarts(df: pd.DataFrame) -> Dict:
    return {
        "title": {"text": "Price Trends by Location", "left": "center"},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": df["neighbourhood_group_cleansed"].tolist(), "axisLabel": {"rotate": 45}},
        "yAxis": {"type": "value", "name": "Average Price (€)"},
        "series": [{
            "name": "Average Price",
            "type": "line",
            "data": df["avg_price"].round(2).tolist(),
            "smooth": True,
            "itemStyle": {"color": "#73c0de"}
        }]
    }


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    sql = """
    SELECT 
        neighbourhood_group_cleansed,
        AVG(price) as avg_price,
        COUNT(*) as listing_count,
        MIN(price) as min_price,
        MAX(price) as max_price
    FROM listings 
    WHERE price IS NOT NULL AND neighbourhood_group_cleansed IS NOT NULL
    GROUP BY neighbourhood_group_cleansed
    HAVING COUNT(*) >= 10
    ORDER BY avg_price DESC
    """
    df = execute_query(sql)
    return {
        "success": True,
        "chart_config": {"type": "line", "title": "Price Trends by Location", "x_axis": "Location", "y_axis": "Average Price (€)"},
        "data": {
            "categories": df["neighbourhood_group_cleansed"].tolist(),
            "values": df["avg_price"].round(2).tolist(),
            "listing_counts": df["listing_count"].tolist()
        },
        "metadata": {"total_records": int(df["listing_count"].sum())},
        "echarts_option": _generate_price_trend_echarts(df)
    } 