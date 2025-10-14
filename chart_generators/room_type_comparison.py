import pandas as pd
import numpy as np
from typing import Dict, Optional, List
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
    """
    Generate room type boxplot data with winsorized five-number summaries, budget coverage, and meta hints.

    Returns top-level fields per frontend contract:
    - room_types: list of per-type stats {room_type, count, min,q1,median,q3,max, p95_cap}
    - coverage: list aligned with room_types {room_type, count_in_budget, share_in_budget}
    - budget: {min, max}
    - totals: {overall_coverage}
    - meta: {winsorize, y_axis_cap, sample_notes}

    Notes:
    - Prices are cleaned (price > 0). Five-number stats are computed on per-type winsorized series (P2/P98).
    - p95_cap computed on cleaned (non-winsorized) per-type prices.
    - overall_coverage uses total listings after structural filters (not budget filtered).
    """

    # Structural filters only (do NOT apply budget here)
    where: List[str] = [
        "room_type IS NOT NULL",
        "price IS NOT NULL",
        "price > 0"
    ]
    if preferences.get("neighbourhood_group"):
        safe_ng = preferences["neighbourhood_group"].replace("'", "''")
        where.append(f"neighbourhood_group_cleansed = '{safe_ng}'")
    if preferences.get("neighbourhood"):
        safe_n = preferences["neighbourhood"].replace("'", "''")
        where.append(f"neighbourhood_cleansed = '{safe_n}'")

    sql = f"""
    SELECT room_type, price
    FROM listings
    WHERE {' AND '.join(where)}
    """

    df = execute_query(sql)
    if df is None or df.empty:
        return generate_error_response("No room type data found")

    # Normalize types
    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["price", "room_type"])  # ensure clean
    df = df[df["price"] > 0]

    # Allowed/fixed room type order
    fixed_order: List[str] = [
        "Shared room",
        "Private room",
        "Entire home/apt",
        "Hotel room",
    ]
    df = df[df["room_type"].isin(fixed_order)].copy()

    # Early exit if no data after filters
    if df.empty:
        return generate_error_response("No room type data found after filters")

    # Budget
    bmin = preferences.get("price_min")
    bmax = preferences.get("price_max")
    try:
        bmin_f = None if bmin is None else float(bmin)
        bmax_f = None if bmax is None else float(bmax)
    except Exception:
        bmin_f, bmax_f = None, None

    # Helper: winsorize series by percentiles
    def _winsorize(series: pd.Series, p_low: float = 2.0, p_high: float = 98.0) -> pd.Series:
        if series.dropna().empty:
            return series
        lo = float(np.percentile(series, p_low))
        hi = float(np.percentile(series, p_high))
        if hi < lo:
            lo, hi = hi, lo
        return series.clip(lower=lo, upper=hi)

    def _five_number(series: pd.Series) -> Dict[str, Optional[float]]:
        s = series.dropna()
        if s.empty:
            return {"min": None, "q1": None, "median": None, "q3": None, "max": None}
        q1, med, q3 = np.percentile(s, [25, 50, 75])
        return {
            "min": float(np.min(s)),
            "q1": float(q1),
            "median": float(med),
            "q3": float(q3),
            "max": float(np.max(s))
        }

    # Compute per-type stats
    room_types_payload: List[Dict] = []
    coverage_payload: List[Dict] = []
    p95_caps: List[float] = []
    counts_per_type: Dict[str, int] = {}
    budget_counts_per_type: Dict[str, int] = {}

    # Precompute global totals (within fixed types)
    listings_total = int(len(df))

    # If budget both present, compute global in-budget denominator later; else set to 0
    listings_in_budget_total = 0

    for rt in fixed_order:
        sub = df[df["room_type"] == rt]["price"].astype(float)
        count = int(sub.shape[0])
        counts_per_type[rt] = count

        # Winsorized five-number summary
        w = _winsorize(sub, 2.0, 98.0)
        five = _five_number(w)

        # p95 cap on cleaned (non-winsorized)
        p95_cap = None
        if not sub.dropna().empty:
            p95_cap = float(np.percentile(sub, 95))
            p95_caps.append(p95_cap)
        else:
            p95_cap = None

        # Budget coverage per type
        cnt_in_budget = 0
        if bmin_f is not None and bmax_f is not None and not sub.dropna().empty:
            cnt_in_budget = int(((sub >= bmin_f) & (sub <= bmax_f)).sum())
            listings_in_budget_total += cnt_in_budget
        budget_counts_per_type[rt] = cnt_in_budget

        # Round numeric results to integers consistently (prices)
        def _round_price(x: Optional[float]) -> Optional[float]:
            if x is None or pd.isna(x):
                return None
            return float(int(round(x)))

        room_types_payload.append({
            "room_type": rt,
            "count": count,
            "min": _round_price(five.get("min")),
            "q1": _round_price(five.get("q1")),
            "median": _round_price(five.get("median")),
            "q3": _round_price(five.get("q3")),
            "max": _round_price(five.get("max")),
            "p95_cap": _round_price(p95_cap)
        })

    # Compute per-type share_in_budget after we know global denominator
    if not (bmin_f is not None and bmax_f is not None):
        listings_in_budget_total = 0

    for rt in fixed_order:
        cnt_in_budget = budget_counts_per_type.get(rt, 0) if listings_in_budget_total > 0 else 0
        share = 0.0 if listings_in_budget_total == 0 else round(cnt_in_budget / listings_in_budget_total, 2)
        coverage_payload.append({
            "room_type": rt,
            "count_in_budget": int(cnt_in_budget),
            "share_in_budget": float(share)
        })

    # overall coverage
    overall_coverage = 0.0
    if (bmin_f is not None and bmax_f is not None) and listings_total > 0:
        overall_coverage = round(float(listings_in_budget_total) / float(listings_total), 2)

    # y-axis cap (suggested): max of per-type p95 caps, or 0 if none
    y_axis_cap = int(round(max(p95_caps))) if p95_caps else 0

    # Sample notes: sparse types (count < threshold)
    sparse_threshold = 20
    sparse_types = [rt for rt in fixed_order if counts_per_type.get(rt, 0) < sparse_threshold]

    # Build items in fixed order for frontend Format A
    items: List[Dict] = []
    for rt in fixed_order:
        rec = next((x for x in room_types_payload if x.get("room_type") == rt), None)
        if rec is None:
            items.append({
                "room_type": rt,
                "min": None,
                "q1": None,
                "median": None,
                "q3": None,
                "max": None,
                "p95": None,
                "n": 0
            })
        else:
            items.append({
                "room_type": rt,
                "min": rec.get("min"),
                "q1": rec.get("q1"),
                "median": rec.get("median"),
                "q3": rec.get("q3"),
                "max": rec.get("max"),
                "p95": rec.get("p95_cap"),
                "n": rec.get("count", 0)
            })

    # Build top-level room_types array as requested (five-number summaries)
    room_types_top: List[Dict] = []
    for rt in fixed_order:
        rec = next((x for x in room_types_payload if x.get("room_type") == rt), None)
        if rec is None:
            continue
        room_types_top.append({
            "room_type": rt,
            "count": rec.get("count", 0),
            "min": rec.get("min"),
            "q1": rec.get("q1"),
            "median": rec.get("median"),
            "q3": rec.get("q3"),
            "max": rec.get("max"),
            "p95_cap": rec.get("p95_cap")
        })

    # Build ECharts boxplot option (Format B) from items for /test/chart-option endpoint
    box_categories: List[str] = []
    box_values: List[List[float]] = []
    for it in items:
        # skip types without stats
        if it.get("min") is None:
            continue
        box_categories.append(it.get("room_type"))
        box_values.append([
            it.get("min"),
            it.get("q1"),
            it.get("median"),
            it.get("q3"),
            it.get("max"),
        ])

    echarts_option = {
        "type": "room_type_comparison",
        "title": {"text": "Room Type Comparison", "left": "center"},
        "tooltip": {"trigger": "item"},
        "xAxis": {"type": "category", "data": box_categories},
        "yAxis": {
            "type": "value",
            "name": "€ / night",
            **({"max": y_axis_cap} if y_axis_cap else {})
        },
        "series": [
            {"name": "Price", "type": "boxplot", "data": box_values}
        ]
    }

    # Assemble response following Format A and also provide top-level fields for direct consumption
    response = {
        "success": True,
        "data": {
            "type": "room_type_comparison",
            "items": items
        },
        "room_types": room_types_top,
        "coverage": coverage_payload,
        "budget": {"min": (None if bmin_f is None else float(int(round(bmin_f)))),
                    "max": (None if bmax_f is None else float(int(round(bmax_f))))},
        "totals": {
            "listings_total": listings_total,
            "listings_in_budget_total": listings_in_budget_total,
            "overall_coverage": overall_coverage
        },
        "meta": {
            "winsorize": {"lower_pct": 0.02, "upper_pct": 0.98},
            "y_axis_cap": "p95",
            "units": "€ per night",
            "sample_notes": {"min_count_threshold": sparse_threshold, "sparse_types": sparse_types}
        },
        "echarts_option": echarts_option,
        "metadata": {
            "total_records": listings_total
        }
    }

    return response