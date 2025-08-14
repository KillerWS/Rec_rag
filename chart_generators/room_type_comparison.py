import pandas as pd
from typing import Dict, Optional
from db import execute_query
from .utils import generate_error_response


def _generate_room_type_pie_echarts(df: pd.DataFrame) -> Dict:
    return {
        "title": {"text": "Room Type Distribution", "left": "center"},
        "tooltip": {"trigger": "item", "formatter": "{a} <br/>{b}: {c} ({d}%)"},
        "legend": {"orient": "vertical", "left": "left"},
        "series": [{
            "name": "Room Type",
            "type": "pie",
            "radius": "50%",
            "data": [
                {"value": int(row["count"]), "name": row["room_type"]}
                for _, row in df.iterrows()
            ],
            "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0, 0, 0, 0.5)"}}
        }]
    }


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    where_conditions = ["room_type IS NOT NULL"]
    if preferences.get("neighbourhood_group"):
        safe_neighbourhood = preferences["neighbourhood_group"].replace("'", "''")
        where_conditions.append(f"neighbourhood_group_cleansed = '{safe_neighbourhood}'")
    if preferences.get("price_min") and preferences.get("price_max"):
        where_conditions.append(f"price BETWEEN {preferences['price_min']} AND {preferences['price_max']}")
    sql = f"""
    SELECT 
        room_type,
        COUNT(*) as count,
        AVG(price) as avg_price,
        AVG(number_of_reviews) as avg_reviews,
        AVG(availability_365) as avg_availability,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
    FROM listings 
    WHERE {' AND '.join(where_conditions)}
    GROUP BY room_type
    ORDER BY count DESC
    """
    df = execute_query(sql)
    if df.empty:
        return generate_error_response("No room type data found")
    return {
        "success": True,
        "chart_config": {"type": "pie", "title": "Room Type Distribution", "subtitle": f"Total {df['count'].sum()} listings"},
        "data": {
            "categories": df["room_type"].tolist(),
            "values": df["count"].tolist(),
            "percentages": df["percentage"].tolist(),
            "additional_metrics": {
                "avg_prices": df["avg_price"].round(2).tolist(),
                "avg_reviews": df["avg_reviews"].round(1).tolist()
            }
        },
        "metadata": {
            "total_records": int(df["count"].sum()),
            "most_common_type": df.iloc[0]["room_type"],
            "type_variety": len(df)
        },
        "echarts_option": _generate_room_type_pie_echarts(df)
    } 