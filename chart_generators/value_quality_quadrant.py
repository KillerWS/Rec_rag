import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from db import execute_query
from .utils import generate_error_response


def _normalize(value: float, reference: float, clip_max: float) -> float:
    if reference is None or reference <= 0:
        return 0.0
    try:
        norm = float(value) / float(reference)
    except Exception:
        return 0.0
    # clamp to [0, clip_max]
    norm = max(0.0, min(norm, clip_max))
    return float(round(norm, 3))


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    """
    Value-Quality Quadrant chart data.
    - X axis: value_score = quality_index / price_index (higher is better value)
    - Y axis: quality_index (popularity proxy)
    - size: listing_count
    - Supports area filters via 'area' (auto-resolve group/neighbourhood), plus room_type/min_reviews.

    Returns a scatter-like payload suitable for quadrant rendering.
    """
    # Build WHERE clause
    where: List[str] = ["price IS NOT NULL", "price > 0"]

    # Area auto-detect (case-insensitive exact match)
    area_val = preferences.get("area")
    if isinstance(area_val, str) and area_val.strip():
        area_trim = area_val.strip()
        safe_area = area_trim.replace("'", "''")
        # also prepare LIKE-safe pattern
        like_area = safe_area.replace("%", "\\%").replace("_", "\\_")
        try:
            small = execute_query(
                f"SELECT 1 AS ok FROM listings WHERE LOWER(neighbourhood_cleansed) = LOWER('{safe_area}') LIMIT 1"
            )
        except Exception:
            small = None
        if small is not None and not small.empty:
            where.append(f"LOWER(neighbourhood_cleansed) = LOWER('{safe_area}')")
        else:
            try:
                grp = execute_query(
                    f"SELECT 1 AS ok FROM listings WHERE LOWER(neighbourhood_group_cleansed) = LOWER('{safe_area}') LIMIT 1"
                )
            except Exception:
                grp = None
            if grp is not None and not grp.empty:
                where.append(f"LOWER(neighbourhood_group_cleansed) = LOWER('{safe_area}')")
            else:
                # Fallback: try LIKE matching (case-insensitive)
                try:
                    small_like = execute_query(
                        f"SELECT 1 AS ok FROM listings WHERE LOWER(neighbourhood_cleansed) LIKE LOWER('%{like_area}%') ESCAPE '\\' LIMIT 1"
                    )
                except Exception:
                    small_like = None
                if small_like is not None and not small_like.empty:
                    where.append(f"LOWER(neighbourhood_cleansed) LIKE LOWER('%{like_area}%') ESCAPE '\\'")
                else:
                    try:
                        grp_like = execute_query(
                            f"SELECT 1 AS ok FROM listings WHERE LOWER(neighbourhood_group_cleansed) LIKE LOWER('%{like_area}%') ESCAPE '\\' LIMIT 1"
                        )
                    except Exception:
                        grp_like = None
                    if grp_like is not None and not grp_like.empty:
                        where.append(f"LOWER(neighbourhood_group_cleansed) LIKE LOWER('%{like_area}%') ESCAPE '\\'")

    # Legacy filters
    if preferences.get("neighbourhood_group"):
        safe_ng = preferences["neighbourhood_group"].replace("'", "''")
        where.append(f"LOWER(neighbourhood_group_cleansed) = LOWER('{safe_ng}')")
    if preferences.get("neighbourhood"):
        safe_n = preferences["neighbourhood"].replace("'", "''")
        where.append(f"LOWER(neighbourhood_cleansed) = LOWER('{safe_n}')")

    if preferences.get("room_type"):
        safe_rt = preferences["room_type"].replace("'", "''")
        where.append(f"room_type = '{safe_rt}'")
    if preferences.get("min_reviews") is not None:
        try:
            mr = int(preferences.get("min_reviews") or 0)
            if mr > 0:
                where.append(f"GREATEST(0, COALESCE(CAST(NULLIF(number_of_reviews_l30d, '') AS SIGNED), 0)) >= {mr}")
        except Exception:
            pass

    where_clause = " AND ".join(where) if where else "1=1"

    # Query listing-level fields; compute per-listing value-quality metrics
    sql = f"""
    SELECT
        id,
        name,
        neighbourhood_group_cleansed AS district,
        neighbourhood_cleansed AS neighbourhood,
        room_type,
        price,
        COALESCE(CAST(NULLIF(review_scores_rating, '') AS DECIMAL(5,2)), NULL) AS review_scores_rating,
        COALESCE(CAST(NULLIF(number_of_reviews, '') AS SIGNED), 0) AS number_of_reviews
    FROM listings
    WHERE {where_clause}
    """
    df = execute_query(sql)
    if df is None or df.empty:
        return generate_error_response("No data for value-quality quadrant")

    # Coerce dtypes
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["review_scores_rating"] = pd.to_numeric(df["review_scores_rating"], errors="coerce")
    df["number_of_reviews"] = pd.to_numeric(df["number_of_reviews"], errors="coerce").fillna(0.0)

    # Drop invalid rows
    df = df.dropna(subset=["price"])  # ensure price available
    if df.empty:
        return generate_error_response("No data after cleaning for quadrant")

    # Define grouping for "similar listings": district + room_type
    df["district"] = df["district"].astype(str)
    df["room_type"] = df["room_type"].astype(str)
    group_cols = ["district", "room_type"]

    # Compute group median price for premium
    group_median = (
        df.groupby(group_cols)["price"].median().rename("group_median_price").reset_index()
    )
    df = df.merge(group_median, on=group_cols, how="left")
    df["premium_pct"] = 0.0
    valid_median = df["group_median_price"].fillna(0) > 0
    df.loc[valid_median, "premium_pct"] = (
        (df.loc[valid_median, "price"] - df.loc[valid_median, "group_median_price"]) / df.loc[valid_median, "group_median_price"]
    )

    # Compute group mean/std for z-scores (price and rating)
    def _safe_std(s: pd.Series) -> float:
        try:
            v = float(s.std(ddof=0))
        except Exception:
            v = 0.0
        return v

    agg = (
        df.groupby(group_cols)
        .agg(
            price_mean=("price", "mean"),
            price_std=("price", _safe_std),
            rating_mean=("review_scores_rating", "mean"),
            rating_std=("review_scores_rating", _safe_std),
        )
        .reset_index()
    )
    df = df.merge(agg, on=group_cols, how="left")

    # Price z and quality z
    df["price_z"] = 0.0
    df["quality_z"] = 0.0
    nonzero_price_std = df["price_std"].fillna(0) > 1e-9
    nonzero_rating_std = df["rating_std"].fillna(0) > 1e-9
    df.loc[nonzero_price_std, "price_z"] = (
        (df.loc[nonzero_price_std, "price"] - df.loc[nonzero_price_std, "price_mean"]) / df.loc[nonzero_price_std, "price_std"]
    )
    df.loc[nonzero_rating_std, "quality_z"] = (
        (df.loc[nonzero_rating_std, "review_scores_rating"] - df.loc[nonzero_rating_std, "rating_mean"]) / df.loc[nonzero_rating_std, "rating_std"]
    )

    # Preserve a full copy for trend computation (before sampling)
    df_full_for_trend = df.copy()

    # Value score = z_quality - z_price
    df["value_score"] = df["quality_z"].fillna(0.0) - df["price_z"].fillna(0.0)

    # Sampling to limit number of points
    total_rows = int(len(df))
    max_points_pref = preferences.get("max_points")
    try:
        max_points = int(max_points_pref) if max_points_pref is not None else 400
    except Exception:
        max_points = 400
    max_points = max(50, min(max_points, 2000))
    sampled = False
    if total_rows > max_points:
        seed = preferences.get("seed")
        try:
            seed = None if seed is None else int(seed)
        except Exception:
            seed = 42
        df = df.sample(n=max_points, random_state=seed)
        sampled = True

    # Build items
    items: List[Dict] = []
    for _, r in df.iterrows():
        title = str(r.get("name") or "")
        price = r.get("price")
        rating = r.get("review_scores_rating")
        premium = r.get("premium_pct")
        vs = r.get("value_score")
        items.append({
            "title": title,
            "price": 0 if pd.isna(price) else int(round(float(price))),
            "premium_pct": 0.0 if pd.isna(premium) else float(round(float(premium) * 100.0, 1)),
            "rating": None if pd.isna(rating) else float(round(float(rating), 2)),
            "value_score": 0.0 if pd.isna(vs) else float(round(float(vs), 2)),
            "district": str(r.get("district") or ""),
            "room_type": str(r.get("room_type") or ""),
            "neighbourhood": None if pd.isna(r.get("neighbourhood")) else str(r.get("neighbourhood")),
            "review_count": int(r.get("number_of_reviews") or 0)
        })

    # Sort: high value first, then by review_count desc
    items.sort(key=lambda x: (x["value_score"], x["review_count"]), reverse=True)

    # Build ECharts scatter series to ensure /test/chart-option returns data
    scatter_points: List[Dict] = []
    for it in items:
        scatter_points.append({
            "name": it["title"],
            "value": [it["value_score"], (it["rating"] or 0.0)],
            "price": it["price"],
            "premium_pct": it["premium_pct"],
            "district": it["district"],
            "neighbourhood": it.get("neighbourhood"),
            "room_type": it["room_type"],
            "reviews": it["review_count"]
        })

    # --- Trend line stats (price vs rating) ---
    # Compute on full filtered dataset (not sampled)
    trend = {
        "method": "wls_weighted_by_reviews",
        "slope_z": 0.0,
        "intercept_z": 0.0,
        "r": 0.0,
        "slope_eur_per_0p1": 0.0,
        "n_weighted": 0
    }
    try:
        df_t = df_full_for_trend.dropna(subset=["price", "review_scores_rating"]).copy()
        if not df_t.empty:
            # weights by review count (bounded)
            w = np.clip(pd.to_numeric(df_t["number_of_reviews"], errors="coerce").fillna(0.0).astype(float), 0.0, 500.0) + 1.0
            x_rating = pd.to_numeric(df_t["review_scores_rating"], errors="coerce").astype(float)
            y_price = pd.to_numeric(df_t["price"], errors="coerce").astype(float)

            # Weighted means
            w_sum = float(np.sum(w)) if np.isfinite(np.sum(w)) else 0.0
            if w_sum > 0:
                x_mean = float(np.sum(w * x_rating) / w_sum)
                y_mean = float(np.sum(w * y_price) / w_sum)
                # Weighted covariance and variances
                cov_xy = float(np.sum(w * (x_rating - x_mean) * (y_price - y_mean)) / w_sum)
                var_x = float(np.sum(w * (x_rating - x_mean) ** 2) / w_sum)
                var_y = float(np.sum(w * (y_price - y_mean) ** 2) / w_sum)
                # WLS slope/intercept in real units
                if var_x > 1e-12:
                    slope = cov_xy / var_x
                else:
                    slope = 0.0
                intercept = y_mean - slope * x_mean
                # Weighted Pearson r
                denom = (var_x * var_y) ** 0.5
                r_val = 0.0 if denom <= 1e-12 else float(cov_xy / denom)

                # z-standardized slope/intercept (global z)
                std_x = var_x ** 0.5
                std_y = var_y ** 0.5
                slope_z = 0.0 if std_x <= 1e-12 or std_y <= 1e-12 else float((slope * std_x) / std_y)
                intercept_z = 0.0  # with z-standardization around means, intercept ~0

                trend.update({
                    "slope_z": float(round(slope_z, 3)),
                    "intercept_z": float(round(intercept_z, 3)),
                    "r": float(round(r_val, 3)),
                    "slope_eur_per_0p1": float(round(slope * 0.1, 2)),
                    "n_weighted": int(round(w_sum))
                })
    except Exception:
        pass

    return {
        "success": True,
        "data": {
            "type": "value_quality_quadrant",
            "items": items,
            "trend": trend
        },
        "echarts_option": {
            "type": "value_quality_quadrant",
            "title": {"text": "Value vs Quality (Listings)", "left": "center"},
            "xAxis": {"type": "value", "name": "Value Score (z_quality - z_price)"},
            "yAxis": {"type": "value", "name": "Rating"},
            "tooltip": {"trigger": "item"},
            "series": [
                {
                    "type": "scatter",
                    "name": "Listings",
                    "data": scatter_points,
                    "symbolSize": 8
                }
            ]
        },
        "metadata": {
            "total_records": int(len(df)),
            "sampling": {
                "enabled": sampled,
                "max_points": max_points,
                "original_count": total_rows,
                "returned_count": int(len(df))
            }
        }
    }


