import pandas as pd
from typing import Dict, Optional
from db import execute_query


def _generate_host_scatter_echarts(df: pd.DataFrame) -> Dict:
    return {
        "title": {"text": "Host Listing Count Analysis", "left": "center"},
        "tooltip": {"trigger": "item"},
        "xAxis": {"type": "value", "name": "Number of Listings per Host"},
        "yAxis": {"type": "value", "name": "Number of Hosts"},
        "series": [{
            "name": "Host Distribution",
            "type": "scatter",
            "data": [
                [int(row["calculated_host_listings_count"]), int(row["host_count"])]
                for _, row in df.iterrows()
            ],
            "symbolSize": 8,
            "itemStyle": {"color": "#9a60b4"}
        }]
    }


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    sql = """
    SELECT 
        calculated_host_listings_count,
        COUNT(*) as host_count,
        AVG(price) as avg_price,
        SUM(number_of_reviews) as total_reviews
    FROM listings 
    WHERE calculated_host_listings_count IS NOT NULL 
    AND calculated_host_listings_count <= 20
    GROUP BY calculated_host_listings_count
    ORDER BY calculated_host_listings_count
    """
    df = execute_query(sql)
    return {
        "success": True,
        "chart_config": {"type": "scatter", "title": "Host Listing Count Analysis", "x_axis": "Number of Listings per Host", "y_axis": "Number of Hosts"},
        "data": {
            "categories": df["calculated_host_listings_count"].tolist(),
            "values": df["host_count"].tolist(),
            "avg_prices": df["avg_price"].round(2).tolist()
        },
        "metadata": {"total_records": int(df["host_count"].sum())},
        "echarts_option": _generate_host_scatter_echarts(df)
    } 