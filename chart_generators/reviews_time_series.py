from typing import Dict, Optional
from db import execute_query
from .utils import generate_error_response


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    where = ["r.date IS NOT NULL"]
    if preferences.get("neighbourhood_group"):
        ng = preferences["neighbourhood_group"].replace("'", "''")
        where.append(f"l.neighbourhood_group_cleansed = '{ng}'")
    if preferences.get("neighbourhood"):
        nn = preferences["neighbourhood"].replace("'", "''")
        where.append(f"l.neighbourhood_cleansed = '{nn}'")
    sql = f"""
    SELECT to_char(r.date, 'YYYY-MM') AS month,
           COUNT(*) AS count
    FROM reviews r
    JOIN listings l ON l.id = r.listing_id
    WHERE {' AND '.join(where)}
    GROUP BY month
    ORDER BY month;
    """
    df = execute_query(sql)
    if df.empty:
        return generate_error_response("No review time series data found")
    return {
        "success": True,
        "chart_config": {"type": "line", "title": "Review Volume Trend", "x_axis": "Month", "y_axis": "Count"},
        "data": {"categories": df["month"].tolist(), "values": df["count"].tolist()},
        "metadata": {"total_reviews": int(df["count"].sum())}
    } 