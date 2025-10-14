import pandas as pd
from typing import Dict, Optional
from db import execute_query
from .utils import generate_error_response


def _generate_location_popularity_echarts(df: pd.DataFrame, preferences: Optional[Dict] = None) -> Dict:
    preferences = preferences or {}

    categories = df["neighbourhood_group_cleansed"].tolist()

    # Build dataset source with all fields for tooltip template references
    source = []
    for _, row in df.iterrows():
        source.append({
            "neighbourhood_group_cleansed": row["neighbourhood_group_cleansed"],
            "popularity_percent": int(row.get("popularity_percent", 0) or 0),
            "avg_rating": float(round(row.get("avg_rating", 0.0) or 0.0, 2)) if pd.notna(row.get("avg_rating", None)) else None,
            "avg_reviews_per_month": float(round(row.get("avg_reviews_per_month", 0.0) or 0.0, 2)) if pd.notna(row.get("avg_reviews_per_month", None)) else None,
            "total_reviews_ltm": int(row.get("total_reviews_ltm", 0) or 0) if pd.notna(row.get("total_reviews_ltm", None)) else 0,
            "superhost_ratio_percent": int(round((row.get("superhost_ratio", 0.0) or 0.0) * 100)),
            "occupancy_proxy": float(round(row.get("occupancy_proxy", 0.0) or 0.0, 2)) if pd.notna(row.get("occupancy_proxy", None)) else None,
            "listing_count": int(row.get("listing_count", 0) or 0),
            "avg_price": float(round(row.get("avg_price", 0.0) or 0.0, 2)) if pd.notna(row.get("avg_price", None)) else None,
        })

    # Determine rating range for color mapping
    if "avg_rating" in df and df["avg_rating"].notna().any():
        rating_min = float(df["avg_rating"].min())
        rating_max = float(df["avg_rating"].max())
        if rating_min == rating_max:
            rating_min = max(0.0, rating_min - 0.1)
            rating_max = rating_max + 0.1
    else:
        rating_min, rating_max = 0.0, 5.0

    option: Dict = {
        "title": {"text": "Popularity by District", "left": "center"},
        "legend": {"data": ["Popularity"], "top": 28},
        "tooltip": {
            "trigger": "item",
            # Use ECharts string template with dataset fields
            "formatter": (
                "{b}<br/>\ud83d\udd25 Popularity Score: {@popularity_percent}"
                "<br/>\u2b50 Avg Rating: {@avg_rating}"
                "<br/>\ud83d\udcac Avg Reviews per Month: {@avg_reviews_per_month}"
                "<br/>\ud83d\udcc8 Reviews (12m): {@total_reviews_ltm}"
                "<br/>\ud83c\udfe0 Superhost Ratio: {@superhost_ratio_percent}%"
                "<br/>\ud83d\uddd3 Occupancy Proxy: {@occupancy_proxy}"
            )
        },
        # Horizontal bar: x = value, y = category
        "xAxis": {"type": "value", "name": "Popularity (0-100)", "min": 0, "max": 100},
        "yAxis": {"type": "category", "data": categories, "axisLabel": {"rotate": 0}},
        "grid": {"left": 120, "right": 40, "top": 60, "bottom": 40},
        # Provide dataset so tooltip template can reference fields
        "dataset": {"source": source},
        "series": [
            {
                "name": "Popularity",
                "type": "bar",
                "encode": {"y": "neighbourhood_group_cleansed", "x": "popularity_percent"},
                "itemStyle": {"color": "#5470C6"},
                "emphasis": {"focus": "series"}
            }
        ],
        # Color by rating: orange (low) to green (high)
        "visualMap": {
            "show": False,
            "type": "continuous",
            "dimension": "avg_rating",
            "min": rating_min,
            "max": rating_max,
            "inRange": {"color": ["#ff7f0e", "#91cc75"]}
        }
    }

    return option


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    # 按要求：不加过滤条件，返回全区域（仅保证基础有效性）
    where_conditions = ["neighbourhood_group_cleansed IS NOT NULL", "price > 0"]

    sql = f"""
    SELECT 
        neighbourhood_group_cleansed,
        COUNT(*) as listing_count,
        AVG(price) as avg_price,
        AVG(number_of_reviews) as avg_reviews,
        AVG(reviews_per_month) as avg_reviews_per_month,
        SUM(number_of_reviews_ltm) as total_reviews_ltm,
        AVG(review_scores_rating) as avg_rating,
        AVG(CASE 
                WHEN LOWER(CAST(host_is_superhost AS CHAR)) IN ('t','true','1','y','yes') OR host_is_superhost = 1 OR host_is_superhost = TRUE THEN 1 
                ELSE 0 
            END) as superhost_ratio,
        AVG(1 - (availability_365 / 365.0)) as occupancy_proxy,
        COUNT(DISTINCT host_id) as unique_hosts
    FROM listings 
    WHERE {' AND '.join(where_conditions)}
    GROUP BY neighbourhood_group_cleansed
    """
    df = execute_query(sql)
    if df.empty:
        return generate_error_response("No location data found")

    # Compute weighted popularity score via min-max normalization
    def _min_max_norm(s: pd.Series) -> pd.Series:
        s = s.astype(float)
        min_v, max_v = s.min(), s.max()
        if pd.isna(min_v) or pd.isna(max_v) or max_v == min_v:
            return pd.Series([0.5] * len(s), index=s.index)
        return (s - min_v) / (max_v - min_v)

    reviews_per_month_norm = _min_max_norm(df["avg_reviews_per_month"]) if "avg_reviews_per_month" in df else pd.Series([0.5] * len(df))
    rating_norm = _min_max_norm(df["avg_rating"]) if "avg_rating" in df else pd.Series([0.5] * len(df))
    ltm_reviews_norm = _min_max_norm(df["total_reviews_ltm"]) if "total_reviews_ltm" in df else pd.Series([0.5] * len(df))
    occupancy_norm = _min_max_norm(df["occupancy_proxy"]) if "occupancy_proxy" in df else pd.Series([0.5] * len(df))
    superhost_norm = _min_max_norm(df["superhost_ratio"]) if "superhost_ratio" in df else pd.Series([0.5] * len(df))

    df["popularity_score"] = (
        0.30 * reviews_per_month_norm
        + 0.25 * rating_norm
        + 0.20 * ltm_reviews_norm
        + 0.15 * occupancy_norm
        + 0.10 * superhost_norm
    ).clip(0, 1)
    df["popularity_percent"] = (df["popularity_score"] * 100).round(0).astype(int)

    # Sorting logic（仍允许外部传参选择排序，不影响全量覆盖）
    sort_by = (preferences.get("sort_by") or "popularity").lower()
    if sort_by == "price":
        df_sorted = df.sort_values(by=["avg_price", "popularity_score"], ascending=[True, False])
    elif sort_by == "listings":
        df_sorted = df.sort_values(by=["listing_count", "popularity_score"], ascending=[False, False])
    else:  # popularity
        df_sorted = df.sort_values(by=["popularity_score", "listing_count"], ascending=[False, False])

    # Limit to top 12
    df_out = df_sorted.head(12).reset_index(drop=True)

    # Determine most popular by popularity_score for metadata
    most_popular_row = df.loc[df["popularity_score"].idxmax()] if not df.empty else None
    most_popular = most_popular_row["neighbourhood_group_cleansed"] if most_popular_row is not None else None

    if df_out.empty:
        return generate_error_response("No location data found")

    return {
        "success": True,
        "chart_config": {"type": "bar", "title": "Location Popularity", "x_axis": "Popularity", "y_axis": "Location"},
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