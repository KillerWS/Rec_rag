import pandas as pd
from typing import Dict, Optional
from db import execute_query


def _generate_availability_pie_echarts(df: pd.DataFrame) -> Dict:
    return {
        "title": {"text": "Availability Analysis", "left": "center"},
        "tooltip": {"trigger": "item", "formatter": "{a} <br/>{b}: {c} ({d}%)"},
        "series": [{
            "name": "Availability",
            "type": "pie",
            "radius": ["40%", "70%"],
            "avoidLabelOverlap": False,
            "data": [
                {"value": int(row["count"]), "name": row["availability_range"]}
                for _, row in df.iterrows()
            ]
        }]
    }


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    where_conditions = ["availability_365 IS NOT NULL"]
    if preferences.get("neighbourhood_group"):
        safe_neighbourhood = preferences["neighbourhood_group"].replace("'", "''")
        where_conditions.append(f"neighbourhood_group_cleansed = '{safe_neighbourhood}'")
    sql = f"""
    SELECT 
        CASE 
            WHEN availability_365 = 0 THEN 'Not available'
            WHEN availability_365 BETWEEN 1 AND 90 THEN '1-90 days'
            WHEN availability_365 BETWEEN 91 AND 180 THEN '91-180 days'
            WHEN availability_365 BETWEEN 181 AND 270 THEN '181-270 days'
            ELSE '271-365 days' 
        END AS availability_range,
        COUNT(*) as count,
        AVG(price) as avg_price
    FROM listings 
    WHERE {' AND '.join(where_conditions)}
    GROUP BY availability_range
    ORDER BY MIN(availability_365)
    """
    df = execute_query(sql)
    return {
        "success": True,
        "chart_config": {"type": "pie", "title": "Availability Analysis"},
        "data": {
            "categories": df["availability_range"].tolist(),
            "values": df["count"].tolist(),
            "avg_prices": df["avg_price"].round(2).tolist()
        },
        "metadata": {"total_records": int(df["count"].sum())},
        "echarts_option": _generate_availability_pie_echarts(df)
    } 