import pandas as pd
from typing import Dict, Optional
from db import execute_query
from .utils import generate_error_response


def _generate_neighbourhood_bar_echarts(df: pd.DataFrame) -> Dict:
    return {
        "title": {"text": "Neighborhood Comparison", "left": "center"},
        "tooltip": {"trigger": "axis"},
        "xAxis": {
            "type": "category",
            "data": df["neighbourhood_cleansed"].tolist(),
            "axisLabel": {"rotate": 45, "interval": 0}
        },
        "yAxis": {"type": "value", "name": "Number of Listings"},
        "series": [{
            "name": "Listings",
            "type": "bar",
            "data": df["listing_count"].tolist(),
            "itemStyle": {"color": "#ee6666"}
        }]
    }


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    where_conditions = ["neighbourhood IS NOT NULL"]
    if preferences.get("neighbourhood_group"):
        safe_neighbourhood = preferences["neighbourhood_group"].replace("'", "''")
        where_conditions.append(f"neighbourhood_group_cleansed = '{safe_neighbourhood}'")
    if preferences.get("room_type"):
        safe_room_type = preferences["room_type"].replace("'", "''")
        where_conditions.append(f"room_type = '{safe_room_type}'")
    sql = f"""
    SELECT 
        neighbourhood_cleansed,
        neighbourhood_group_cleansed,
        COUNT(*) as listing_count,
        AVG(price) as avg_price,
        AVG(number_of_reviews) as avg_reviews
    FROM listings 
    WHERE {' AND '.join(where_conditions)}
    GROUP BY neighbourhood_cleansed, neighbourhood_group_cleansed
    HAVING COUNT(*) >= 5
    ORDER BY listing_count DESC
    LIMIT 15
    """
    df = execute_query(sql)
    if df.empty:
        return generate_error_response("No neighborhood data found")
    return {
        "success": True,
        "chart_config": {"type": "bar", "title": "Neighborhood Comparison", "x_axis": "Neighborhood", "y_axis": "Number of Listings"},
        "data": {
            "categories": df["neighbourhood_cleansed"].tolist(),
            "values": df["listing_count"].tolist(),
            "groups": df["neighbourhood_group_cleansed"].tolist(),
            "additional_metrics": {
                "avg_prices": df["avg_price"].round(2).tolist(),
                "avg_reviews": df["avg_reviews"].round(1).tolist()
            }
        },
        "metadata": {
            "total_neighbourhoods": len(df),
            "most_active": df.iloc[0]["neighbourhood_cleansed"]
        },
        "echarts_option": _generate_neighbourhood_bar_echarts(df)
    } 