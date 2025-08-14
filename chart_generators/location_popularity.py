import pandas as pd
from typing import Dict, Optional
from db import execute_query
from .utils import generate_error_response


def _generate_location_popularity_echarts(df: pd.DataFrame) -> Dict:
    return {
        "title": {"text": "Location Popularity", "left": "center"},
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "xAxis": {"type": "category", "data": df["neighbourhood_group_cleansed"].tolist(), "axisLabel": {"rotate": 45}},
        "yAxis": {"type": "value", "name": "Number of Listings"},
        "series": [{"name": "Listings", "type": "bar", "data": df["listing_count"].tolist(), "itemStyle": {"color": "#91cc75"}}]
    }


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    where_conditions = ["neighbourhood_group_cleansed IS NOT NULL"]
    if preferences.get("price_min"):
        where_conditions.append(f"price >= {preferences['price_min']}")
    if preferences.get("price_max"):
        where_conditions.append(f"price <= {preferences['price_max']}")
    if preferences.get("room_type"):
        safe_room_type = preferences["room_type"].replace("'", "''")
        where_conditions.append(f"room_type = '{safe_room_type}'")
    sql = f"""
    SELECT 
        neighbourhood_group_cleansed,
        COUNT(*) as listing_count,
        AVG(price) as avg_price,
        AVG(number_of_reviews) as avg_reviews,
        AVG(availability_365) as avg_availability,
        COUNT(DISTINCT host_id) as unique_hosts
    FROM listings 
    WHERE {' AND '.join(where_conditions)}
    GROUP BY neighbourhood_group_cleansed
    ORDER BY listing_count DESC
    LIMIT 12
    """
    df = execute_query(sql)
    if df.empty:
        return generate_error_response("No location data found")
    return {
        "success": True,
        "chart_config": {"type": "bar", "title": "Location Popularity Analysis", "x_axis": "Location", "y_axis": "Number of Listings"},
        "data": {
            "categories": df["neighbourhood_group_cleansed"].tolist(),
            "values": df["listing_count"].tolist(),
            "additional_metrics": {
                "avg_prices": df["avg_price"].round(2).tolist(),
                "avg_reviews": df["avg_reviews"].round(1).tolist(),
                "unique_hosts": df["unique_hosts"].tolist()
            }
        },
        "metadata": {
            "total_locations": len(df),
            "most_popular": df.iloc[0]["neighbourhood_group_cleansed"],
            "total_listings": int(df["listing_count"].sum())
        },
        "echarts_option": _generate_location_popularity_echarts(df)
    } 