import pandas as pd
from typing import Dict, Optional
from db import execute_query
from .utils import generate_error_response


def _generate_location_popularity_echarts(df: pd.DataFrame, preferences: Optional[Dict] = None) -> Dict:
    preferences = preferences or {}
    budget_min = preferences.get("budget_min")
    budget_max = preferences.get("budget_max")

    categories = df["neighbourhood_group_cleansed"].tolist()

    # Build dataset source with all fields for tooltip template references
    source = []
    for _, row in df.iterrows():
        source.append({
            "neighbourhood_group_cleansed": row["neighbourhood_group_cleansed"],
            "listing_count": int(row["listing_count"]) if pd.notna(row["listing_count"]) else 0,
            "avg_price": float(round(row["avg_price"], 2)) if pd.notna(row["avg_price"]) else None,
            "avg_reviews": float(round(row.get("avg_reviews", 0.0), 1)) if pd.notna(row.get("avg_reviews", None)) else None,
            "unique_hosts": int(row.get("unique_hosts", 0)) if pd.notna(row.get("unique_hosts", None)) else None,
            "popularity_percent": int(round((row.get("popularity_score", 0.0) or 0.0) * 100)),
        })

    option: Dict = {
        "title": {"text": "Location Popularity vs Price", "left": "center"},
        "legend": {"data": ["Listings", "Avg Price"], "top": 28},
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
            # Use ECharts string template with dataset fields
            "formatter": "{b}<br/>\ud83c\udfe0 Listings: {@listing_count}<br/>\ud83d\udcb0 Avg Price: \u20ac{@avg_price}<br/>\u2b50 Reviews: {@avg_reviews}<br/>\ud83d\udc64 Hosts: {@unique_hosts}<br/>Popularity: {@popularity_percent}%"
        },
        "xAxis": {"type": "category", "data": categories, "axisLabel": {"rotate": 45}},
        "yAxis": [
            {"type": "value", "name": "Number of Listings"},
            {"type": "value", "name": "Avg Price (€)", "position": "right"}
        ],
        # Provide dataset so tooltip template can reference fields
        "dataset": {"source": source},
        "series": [
            {
                "name": "Listings",
                "type": "bar",
                "encode": {"x": "neighbourhood_group_cleansed", "y": "listing_count"},
                "itemStyle": {"color": "#5470C6"},
                "emphasis": {"focus": "series"}
            },
            {
                "name": "Avg Price",
                "type": "line",
                "encode": {"x": "neighbourhood_group_cleansed", "y": "avg_price"},
                "yAxisIndex": 1,
                "smooth": True,
                "lineStyle": {"color": "#ee6666"},
                "itemStyle": {"color": "#ee6666"}
            }
        ]
    }

    # Budget highlighting via visualMap on bar series (index 0)
    if budget_min is not None and budget_max is not None:
        option["visualMap"] = {
            "show": False,
            "type": "piecewise",
            "seriesIndex": 0,
            "dimension": "avg_price",
            "inRange": {"color": ["#91cc75"]},
            "outOfRange": {"color": ["#5470C6"]},
            "pieces": [
                {"min": budget_min, "max": budget_max}
            ]
        }

    return option


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    where_conditions = ["neighbourhood_group_cleansed IS NOT NULL"]
    # Price filtering based on explicit price_min/price_max only (budget_* used for highlighting)
    if preferences.get("price_min") is not None:
        where_conditions.append(f"price >= {preferences['price_min']}")
    if preferences.get("price_max") is not None:
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
    """
    df = execute_query(sql)
    if df.empty:
        return generate_error_response("No location data found")

    # Compute popularity score via min-max normalization on listing_count and avg_reviews
    def _min_max_norm(s: pd.Series) -> pd.Series:
        s = s.astype(float)
        min_v, max_v = s.min(), s.max()
        if pd.isna(min_v) or pd.isna(max_v) or max_v == min_v:
            return pd.Series([0.5] * len(s), index=s.index)
        return (s - min_v) / (max_v - min_v)

    listing_norm = _min_max_norm(df["listing_count"]) if "listing_count" in df else pd.Series([0.5] * len(df))
    reviews_norm = _min_max_norm(df["avg_reviews"]) if "avg_reviews" in df else pd.Series([0.5] * len(df))
    df["popularity_score"] = ((listing_norm + reviews_norm) / 2.0).clip(0, 1)

    # Sorting logic based on preferences
    sort_by = (preferences.get("sort_by") or "listings").lower()
    if sort_by == "price":
        df_sorted = df.sort_values(by=["avg_price", "listing_count"], ascending=[True, False])
    elif sort_by == "popularity":
        df_sorted = df.sort_values(by=["popularity_score", "listing_count"], ascending=[False, False])
    else:  # default: listings
        df_sorted = df.sort_values(by=["listing_count", "avg_price"], ascending=[False, True])

    # Limit to top 12 for Berlin's 12 boroughs (or fewer if less data)
    df_out = df_sorted.head(12).reset_index(drop=True)

    # Determine most popular by listing_count irrespective of current sort for metadata
    most_popular_row = df.loc[df["listing_count"].idxmax()] if not df.empty else None
    most_popular = most_popular_row["neighbourhood_group_cleansed"] if most_popular_row is not None else None

    if df_out.empty:
        return generate_error_response("No location data found")

    return {
        "success": True,
        "chart_config": {"type": "bar+line", "title": "Location Popularity vs Price", "x_axis": "Location", "y_axis": "Number of Listings"},
        "data": {
            "categories": df_out["neighbourhood_group_cleansed"].tolist(),
            "values": df_out["listing_count"].tolist(),
            "additional_metrics": {
                "avg_prices": df_out["avg_price"].round(2).tolist(),
                "avg_reviews": df_out["avg_reviews"].round(1).tolist(),
                "unique_hosts": df_out["unique_hosts"].astype(int).tolist()
            }
        },
        "metadata": {
            "total_locations": len(df_out),
            "most_popular": most_popular,
            "total_listings": int(df_out["listing_count"].sum())
        },
        "echarts_option": _generate_location_popularity_echarts(df_out, preferences)
    } 