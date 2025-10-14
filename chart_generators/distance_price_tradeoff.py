from typing import Dict, Any, Optional
import pandas as pd
import math
from db import execute_query
from .utils import generate_error_response


def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute Haversine distance (km) between two coordinates."""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _build_where(preferences: Dict) -> str:
    where = [
        "price > 0",
        "latitude IS NOT NULL",
        "longitude IS NOT NULL",
    ]
    # structural filters; DO NOT use price_min/max here to avoid bias
    if preferences.get("room_type"):
        safe = str(preferences["room_type"]).replace("'", "''")
        where.append(f"room_type = '{safe}'")
    if preferences.get("minimum_nights") is not None:
        try:
            where.append(f"minimum_nights >= {int(preferences['minimum_nights'])}")
        except Exception:
            pass
    if preferences.get("min_reviews") is not None:
        try:
            where.append(f"number_of_reviews >= {int(preferences['min_reviews'])}")
        except Exception:
            pass
    # Optional budget filter if provided by user
    price_min = preferences.get("price_min")
    price_max = preferences.get("price_max")
    if price_min is not None:
        try:
            where.append(f"price >= {int(price_min)}")
        except Exception:
            pass
    if price_max is not None:
        try:
            where.append(f"price <= {int(price_max)}")
        except Exception:
            pass
    return " AND ".join(where)


def _build_sql(granularity: str, where_clause: str, min_listings: int) -> str:
    # Fetch raw rows and aggregate in pandas for MySQL compatibility
    area_col = "neighbourhood_group_cleansed" if granularity == "group" else "neighbourhood_cleansed"
    sql = f"""
    SELECT
        {area_col} AS area,
        price,
        latitude,
        longitude
    FROM listings
    WHERE {where_clause} AND {area_col} IS NOT NULL
    """
    return sql


def _compute_scores(df: pd.DataFrame, center_lat: float, center_lon: float, alpha: float, granularity: str, min_listings: int) -> pd.DataFrame:
    if df.empty:
        return df
    # aggregate in pandas
    grp = df.groupby("area", as_index=False).agg(
        median_price=("price", lambda x: float(pd.Series(x).median(skipna=True))),
        p25=("price", lambda x: float(pd.Series(x).quantile(0.25))),
        p75=("price", lambda x: float(pd.Series(x).quantile(0.75))),
        lat_centroid=("latitude", "mean"),
        lon_centroid=("longitude", "mean"),
        listing_count=("price", "count"),
    )
    if granularity == "neighbourhood":
        grp = grp[grp["listing_count"] >= int(min_listings)]
    if grp.empty:
        return grp

    # distance_km
    grp["distance_km"] = grp.apply(lambda r: _haversine_distance_km(float(r["lat_centroid"]), float(r["lon_centroid"]), center_lat, center_lon), axis=1)

    # normalize to 0-100 (higher is better)
    price_min = float(grp["median_price"].min())
    price_max = float(grp["median_price"].max())
    dist_min = float(grp["distance_km"].min())
    dist_max = float(grp["distance_km"].max())

    if price_max == price_min:
        grp["price_score"] = 50.0
    else:
        grp["price_score"] = 100.0 * (price_max - grp["median_price"]) / (price_max - price_min)

    if dist_max == dist_min:
        grp["dist_score"] = 50.0
    else:
        grp["dist_score"] = 100.0 * (dist_max - grp["distance_km"]) / (dist_max - dist_min)

    grp["price_score"] = grp["price_score"].clip(lower=0, upper=100)
    grp["dist_score"] = grp["dist_score"].clip(lower=0, upper=100)

    grp["tradeoff"] = alpha * grp["price_score"] + (1.0 - alpha) * grp["dist_score"]

    return grp


def _compute_budget_coverage(df: pd.DataFrame, preferences: Dict) -> pd.DataFrame:
    # Only if both provided; compute coverage ratio based on budget boundaries using p25~p75 approximation
    price_min = preferences.get("price_min")
    price_max = preferences.get("price_max")
    if price_min is None or price_max is None or df.empty:
        df["coverage_ratio"] = None
        return df
    df = df.copy()
    # Approximate overlap between [price_min, price_max] and interquartile [p25, p75]
    # If p25/p75 missing (could be NaN), fallback to median +- IQR/2 handling
    p25 = df["p25"].astype(float)
    p75 = df["p75"].astype(float)
    width = (p75 - p25).replace(0, 1.0)
    # overlap length divided by IQR as proxy ratio, clipped to [0,1]
    overlap_left = p25.clip(lower=price_min, upper=price_max)
    overlap_right = p75.clip(lower=price_min, upper=price_max)
    overlap = (overlap_right - overlap_left).clip(lower=0)
    ratio = (overlap / width).clip(lower=0, upper=1)
    df["coverage_ratio"] = ratio.round(3)
    return df


def _build_echarts_option(df: pd.DataFrame, title: str, alpha: float, granularity: str, center: Dict, top_k: Optional[int], sort_by: str, sort_order: str, applied_budget: Optional[Dict[str, Optional[int]]], always_include_areas: Optional[list[str]]) -> Dict[str, Any]:
    # sort already by selected sort_by; slice top_k if provided
    plot_df = df
    if top_k is not None:
        try:
            k = int(top_k)
            if k > 0:
                plot_df = df.head(k)
                # ensure specified areas are included even if not in top_k
                if always_include_areas:
                    extras = df[df["area"].isin(always_include_areas)]
                    if not extras.empty:
                        plot_df = pd.concat([plot_df, extras], ignore_index=True)
                        plot_df = plot_df.drop_duplicates(subset=["area"], keep="first")
        except Exception:
            pass

    categories = plot_df["area"].tolist()
    price_scores = plot_df["price_score"].round(1).tolist()
    dist_scores = plot_df["dist_score"].round(1).tolist()

    # identify best indices for highlighting
    try:
        price_vals = [float(v) for v in price_scores]
        best_price_pos = price_vals.index(max(price_vals)) if len(price_vals) > 0 else None
    except Exception:
        best_price_pos = None
    try:
        dist_vals = [float(v) for v in dist_scores]
        best_dist_pos = dist_vals.index(max(dist_vals)) if len(dist_vals) > 0 else None
    except Exception:
        best_dist_pos = None

    # per-bar styling to highlight maxima
    price_series_data: list[Any] = []
    for i, v in enumerate(price_scores):
        if best_price_pos is not None and i == best_price_pos:
            price_series_data.append({
                "value": v,
                "itemStyle": {"color": "#2b5d73"}
            })
        else:
            price_series_data.append(v)

    dist_series_data: list[Any] = []
    for i, v in enumerate(dist_scores):
        if best_dist_pos is not None and i == best_dist_pos:
            dist_series_data.append({
                "value": v,
                "itemStyle": {"color": "#3b7c3e"}
            })
        else:
            dist_series_data.append(v)

    subtitle_parts = [f"alpha={alpha:.2f}", f"granularity={granularity}", f"sorted by {sort_by} ({sort_order})"]
    if applied_budget and (applied_budget.get("min") is not None or applied_budget.get("max") is not None):
        bmin = applied_budget.get("min")
        bmax = applied_budget.get("max")
        if bmin is not None and bmax is not None:
            subtitle_parts.append(f"budget=[{bmin},{bmax}]")
        elif bmin is not None:
            subtitle_parts.append(f"budget≥{bmin}")
        elif bmax is not None:
            subtitle_parts.append(f"budget≤{bmax}")

    center_name = center.get("name", "中心点")

    option = {
        "title": {"text": title, "left": "center", "subtext": ", ".join(subtitle_parts)},
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"}
        },
        "legend": {"data": ["Price advantage", "Distance advantage"], "top": 24},
        "grid": {"left": "3%", "right": "4%", "bottom": "8%", "containLabel": True},
        "xAxis": {"type": "category", "data": categories, "axisLabel": {"rotate": 45, "interval": 0}},
        "yAxis": {"type": "value", "name": "Score (0-100)"},
        "series": [
            {
                "name": "Price advantage",
                "type": "bar",
                "data": price_series_data,
                "itemStyle": {"color": "#73c0de"},
                "markPoint": {
                    "data": [{"type": "max", "name": "Best Price"}],
                    "label": {"formatter": "Best Price"},
                    "tooltip": {"formatter": "这是价格优势最高的区域（相对更便宜）"}
                }
            },
            {
                "name": "Distance advantage",
                "type": "bar",
                "data": dist_series_data,
                "itemStyle": {"color": "#91cc75"},
                "markPoint": {
                    "data": [{"type": "max", "name": "距离分数最高"}],
                    "label": {"formatter": f"Closest to {center_name}"},
                    "tooltip": {"formatter": f"这是离{center_name}最近的区域"}
                }
            }
        ]
    }
    return option


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Generate distance-price tradeoff analysis with adjustable alpha and area granularity.

    preferences:
      - granularity: "group" or "neighbourhood" (default: group)
      - alpha: float in [0,1], default 0.6
      - center: { lat, lon, name }, default Alexanderplatz
      - min_listings: int, default 20 (only for neighbourhood)
      - room_type, minimum_nights, min_reviews: optional structural filters
      - price_min, price_max: optional (budget info only)
      - top_k: optional int for highlighting/limiting
      - sort_by: one of tradeoff, price_score, dist_score, median_price, distance_km, listing_count (default tradeoff)
      - sort_order: asc|desc (default desc)
      - always_include_areas: optional list of area names to always include in plot even when top_k is set
    """
    try:
        granularity = str(preferences.get("granularity", "group")).lower()
        if granularity not in ("group", "neighbourhood"):
            granularity = "group"
        alpha = float(preferences.get("alpha", 0.6))
        alpha = max(0.0, min(1.0, alpha))
        center = preferences.get("center") or {"lat": 52.5256, "lon": 13.3695, "name": "Berlin Hauptbahnhof"}
        center_lat = float(center.get("lat", 52.5256))
        center_lon = float(center.get("lon", 13.3695))
        min_listings = int(preferences.get("min_listings", 20))
        top_k = preferences.get("top_k")

        # sorting preferences
        sort_by = str(preferences.get("sort_by", "tradeoff")).lower()
        allowed_sorts = {"tradeoff", "price_score", "dist_score", "median_price", "distance_km", "listing_count"}
        if sort_by not in allowed_sorts:
            sort_by = "tradeoff"
        sort_order = str(preferences.get("sort_order", "desc")).lower()
        if sort_order not in ("asc", "desc"):
            sort_order = "desc"

        # budget echo
        budget_min = preferences.get("price_min")
        budget_max = preferences.get("price_max")
        applied_budget = {
            "min": int(budget_min) if budget_min is not None else None,
            "max": int(budget_max) if budget_max is not None else None,
        }

        always_include_areas = preferences.get("always_include_areas") or []
        # normalize names to strings
        always_include_areas = [str(x) for x in always_include_areas if x is not None]

        where_clause = _build_where(preferences)
        sql = _build_sql(granularity, where_clause, min_listings)
        df = execute_query(sql)

        if df is None or df.empty:
            return generate_error_response("No data found for distance-price tradeoff")

        # Ensure correct dtypes and columns
        df = df.rename(columns={"area": "area", "price": "price", "latitude": "latitude", "longitude": "longitude"})
        df = df.dropna(subset=["area", "price", "latitude", "longitude"])  # safety

        agg_df = _compute_scores(df, center_lat, center_lon, alpha, granularity, min_listings)
        if agg_df is None or agg_df.empty:
            return generate_error_response("No data found for distance-price tradeoff after aggregation")

        agg_df = _compute_budget_coverage(agg_df, preferences)

        # correlation between median_price and distance_km
        corr_price_distance = None
        if len(agg_df) >= 2:
            try:
                corr_price_distance = float(pd.Series(agg_df["median_price"]).corr(pd.Series(agg_df["distance_km"])))
            except Exception:
                corr_price_distance = None

        # sort by requested column
        ascending = (sort_order == "asc")
        if sort_by in agg_df.columns:
            agg_df = agg_df.sort_values(by=sort_by, ascending=ascending)
        else:
            agg_df = agg_df.sort_values(by="tradeoff", ascending=False)

        # identify best areas (within current set)
        best_price_area = None
        best_distance_area = None
        try:
            idxp = agg_df["price_score"].astype(float).idxmax()
            best_price_area = str(agg_df.loc[idxp, "area"]) if pd.notna(idxp) else None
        except Exception:
            best_price_area = None
        try:
            idxd = agg_df["dist_score"].astype(float).idxmax()
            best_distance_area = str(agg_df.loc[idxd, "area"]) if pd.notna(idxd) else None
        except Exception:
            best_distance_area = None

        # Prepare a human-friendly subtitle also in chart_config
        subtitle_parts = [f"alpha={alpha:.2f}", f"granularity={granularity}", f"sorted by {sort_by} ({sort_order})"]
        if applied_budget and (applied_budget.get("min") is not None or applied_budget.get("max") is not None):
            bmin = applied_budget.get("min")
            bmax = applied_budget.get("max")
            if bmin is not None and bmax is not None:
                subtitle_parts.append(f"budget=[{bmin},{bmax}]")
            elif bmin is not None:
                subtitle_parts.append(f"budget≥{bmin}")
            elif bmax is not None:
                subtitle_parts.append(f"budget≤{bmax}")
        chart_subtitle_text = ", ".join(subtitle_parts)

        # Build response data
        result = {
            "success": True,
            "chart_config": {
                "type": "bar",
                "title": "Distance vs Price Tradeoff",
                "x_axis": "Area",
                "y_axis": "Score (0-100)",
                "subtitle": chart_subtitle_text
            },
            "data": {
                "areas": agg_df["area"].tolist(),
                "price_scores": agg_df["price_score"].round(1).tolist(),
                "distance_scores": agg_df["dist_score"].round(1).tolist(),
                "tradeoff_scores": agg_df["tradeoff"].round(1).tolist(),
                "median_prices": [float(x) if pd.notna(x) else None for x in agg_df["median_price"].tolist()],
                "distances_km": [float(x) if pd.notna(x) else None for x in agg_df["distance_km"].tolist()],
                "listing_counts": [int(x) for x in agg_df["listing_count"].tolist()],
                "coverage_ratio": agg_df["coverage_ratio"].tolist(),
            },
            "metadata": {
                "total_areas": int(len(agg_df)),
                "granularity": granularity,
                "alpha": alpha,
                "center": {"lat": center_lat, "lon": center_lon, "name": center.get("name", "Center")},
                "min_listings": min_listings,
                "corr_price_distance": corr_price_distance,
                "top_k": int(top_k) if isinstance(top_k, int) else (int(top_k) if (isinstance(top_k, str) and top_k.isdigit()) else None),
                "sorting": {"by": sort_by, "order": sort_order},
                "applied_budget": applied_budget,
                "always_included_areas": always_include_areas,
                "score_explanation": {
                    "price_advantage": "Scaled 0-100: cheapest area ~100, most expensive ~0, based on median price across selected areas.",
                    "distance_advantage": "Scaled 0-100: closest to center ~100, farthest ~0, based on centroid distance.",
                    "tradeoff": "alpha * price_advantage + (1-alpha) * distance_advantage"
                },
                "highlights": {"best_price_area": best_price_area, "best_distance_area": best_distance_area}
            },
        }

        # echo ECharts option
        option = _build_echarts_option(agg_df, "Distance vs Price Tradeoff", alpha, granularity, center, top_k, sort_by, sort_order, applied_budget, always_include_areas)
        result["echarts_option"] = option
        return result

    except Exception as e:
        return generate_error_response(str(e)) 