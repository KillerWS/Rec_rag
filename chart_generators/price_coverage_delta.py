import pandas as pd
from typing import Dict, Optional, List
from db import execute_query


def _build_where(preferences: Dict) -> List[str]:
    where = [
        "price IS NOT NULL",
        "price > 0",
    ]

    min_reviews = preferences.get("min_reviews")
    if isinstance(min_reviews, int) and min_reviews > 0:
        where.append(f"number_of_reviews >= {int(min_reviews)}")

    availability_min = preferences.get("availability_min")
    if isinstance(availability_min, int) and availability_min > 0:
        where.append(f"availability_365 >= {int(availability_min)}")

    room_type = preferences.get("room_type")
    if room_type:
        safe_room_type = str(room_type).replace("'", "''")
        where.append(f"room_type = '{safe_room_type}'")

    ng = preferences.get("neighbourhood_group")
    if ng:
        safe_ng = str(ng).replace("'", "''")
        where.append(f"neighbourhood_group_cleansed = '{safe_ng}'")

    return where


def _compute_coverage_curve(prices: List[int], max_price: int, step: int) -> List[Dict]:
    prices_sorted = sorted(prices)
    n_total = len(prices_sorted)
    ticks = list(range(0, max_price + step, step))
    curve = []

    idx = 0
    for p in ticks:
        while idx < n_total and prices_sorted[idx] <= p:
            idx += 1
        coverage = 0.0 if n_total == 0 else round(idx * 100.0 / n_total, 2)
        curve.append({"price": p, "cum_count": idx, "coverage_pct": coverage})
    return curve


def _area_increments(df: pd.DataFrame, base_budget: int, new_budget: int, has_ng_filter: bool) -> List[Dict]:
    group_field = "neighbourhood_cleansed" if has_ng_filter else "neighbourhood_group_cleansed"
    groups = []
    if df.empty or group_field not in df.columns:
        return groups

    g = df.groupby(group_field)
    for area, d in g:
        base_cnt = int((d["price"] <= base_budget).sum())
        new_cnt = int((d["price"] <= new_budget).sum())
        delta = new_cnt - base_cnt
        denom = base_cnt if base_cnt > 0 else 1
        delta_pct = round(delta * 100.0 / denom, 1)
        groups.append({
            "area": area,
            "base_count": base_cnt,
            "new_count": new_cnt,
            "delta_count": delta,
            "delta_pct_from_base": delta_pct,
        })

    groups.sort(key=lambda x: x["delta_count"], reverse=True)
    return groups[:5]


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    """
    预算覆盖率增量分析：给定 base_budget/new_budget，计算覆盖率曲线与增量概览。
    inputs 使用 preferences 中的字段：base_budget, new_budget, step, neighbourhood_group, room_type, min_reviews, availability_min。
    返回包含 coverage_curve、delta_bar、top_gain_areas 与 narrative，并附带一个覆盖曲线的 echarts_option。
    """
    try:
        base_budget = int(preferences.get("base_budget")) if preferences.get("base_budget") is not None else None
        new_budget = int(preferences.get("new_budget")) if preferences.get("new_budget") is not None else None
        if base_budget is None or new_budget is None:
            return {
                "success": False,
                "error": "Missing required params: base_budget and new_budget",
            }

        step = int(preferences.get("step", 5))
        if step <= 0:
            step = 5

        # 预过滤数据
        where = _build_where(preferences)
        sql = f"""
        SELECT price, neighbourhood_group_cleansed, neighbourhood_cleansed
        FROM listings
        WHERE {' AND '.join(where)}
        """
        df = execute_query(sql)

        n_total = int(len(df))
        if n_total == 0:
            req_min = preferences.get("price_min")
            req_max = preferences.get("price_max")
            inc_amount = None
            if req_min is not None and req_max is not None:
                try:
                    inc_amount = int(req_max) - int(req_min)
                except Exception:
                    inc_amount = None
            if inc_amount is None and base_budget is not None and new_budget is not None:
                inc_amount = new_budget - base_budget
            english_summary = (
                f"Your budget range €{req_min if req_min is not None else base_budget}–"
                f"{req_max if req_max is not None else new_budget} (+€{inc_amount if inc_amount is not None else 0}) "
                f"can cover 0.0% more choices."
            )
            return {
                "success": True,
                "inputs": {
                    "base_budget": base_budget,
                    "new_budget": new_budget,
                    "step": step,
                    "filters": {
                        "neighbourhood_group": preferences.get("neighbourhood_group"),
                        "room_type": preferences.get("room_type"),
                        "min_reviews": preferences.get("min_reviews", 0),
                        "availability_min": preferences.get("availability_min"),
                    }
                },
                "meta": {
                    "denominator_total": 0,
                    "price_max_seen": 0,
                    "data_points": 0
                },
                "coverage_curve": [],
                "delta_summary": {
                    "base_budget": base_budget,
                    "new_budget": new_budget,
                    "base_count": 0,
                    "new_count": 0,
                    "delta_count": 0,
                    "base_coverage_pct": 0.0,
                    "new_coverage_pct": 0.0,
                    "delta_coverage_pct": 0.0
                },
                "delta_bar": [],
                "top_gain_areas": [],
                "narrative": english_summary,
                "narrative_en": english_summary,
                "request_budgets": {
                    "price_min": req_min,
                    "price_max": req_max,
                },
                "echarts_option": {
                    "title": {"text": "Budget Coverage Gain", "left": "center"},
                    "xAxis": {"type": "category", "data": []},
                    "yAxis": {"type": "value", "name": "Coverage %"},
                    "series": [{"type": "line", "data": [], "smooth": True}],
                }
            }

        # 归一化预算（内部计算用），但 inputs 返回原始值
        nb = max(base_budget, new_budget)
        max_price_seen = int(df["price"].max()) if not df.empty else nb
        max_for_curve = max(nb, min(max_price_seen, nb))

        # 覆盖曲线
        prices = [int(p) for p in df["price"].tolist()]
        curve = _compute_coverage_curve(prices, max_for_curve, step)

        # Δ 概览
        base_count = int((df["price"] <= base_budget).sum())
        new_count = int((df["price"] <= new_budget).sum())
        delta_count = new_count - base_count
        base_cov = 0.0 if n_total == 0 else round(base_count * 100.0 / n_total, 1)
        new_cov = 0.0 if n_total == 0 else round(new_count * 100.0 / n_total, 1)
        delta_cov = round(new_cov - base_cov, 1)

        # Top 增量区域
        has_ng_filter = preferences.get("neighbourhood_group") is not None
        top_areas = _area_increments(df, base_budget, new_budget, has_ng_filter)

        # 叙述（中文 + 英文）
        top_names = ", ".join([a["area"] for a in top_areas[:3]]) if top_areas else ""
        narrative = (
            f"从 €{base_budget} 到 €{new_budget}，房源覆盖率由 {base_cov}% 提升至 {new_cov}%（+{delta_cov}%），"
            f"新增 {delta_count} 套。" + (f"增量主要来自 {top_names}。" if top_names else "")
        )
        req_min = preferences.get("price_min")
        req_max = preferences.get("price_max")
        inc_amount = None
        if req_min is not None and req_max is not None:
            try:
                inc_amount = int(req_max) - int(req_min)
            except Exception:
                inc_amount = None
        if inc_amount is None:
            inc_amount = new_budget - base_budget
        english_summary = (
            f"Your budget range €{req_min if req_min is not None else base_budget}–"
            f"{req_max if req_max is not None else new_budget} (+€{inc_amount}) can cover "
            f"{delta_cov}% more choices."
        )

        # ECharts 覆盖曲线（带基准与新预算标记）
        x_prices = [pt["price"] for pt in curve]
        y_cover = [pt["coverage_pct"] for pt in curve]
        mark_lines = []
        for budget, name in [(base_budget, "Base"), (new_budget, "New")]:
            if x_prices:
                mark_lines.append({
                    "name": f"{name} €{budget}",
                    "xAxis": budget
                })

        echarts_option = {
            "title": {"text": "Budget Coverage Curve", "left": "center"},
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "value", "name": "Budget (€)"},
            "yAxis": {"type": "value", "name": "Coverage %"},
            "series": [{
                "name": "Coverage",
                "type": "line",
                "smooth": True,
                "data": [[x_prices[i], y_cover[i]] for i in range(len(x_prices))],
                "markLine": {"data": mark_lines} if mark_lines else None,
            }],
        }

        return {
            "success": True,
            "inputs": {
                "base_budget": base_budget,
                "new_budget": new_budget,
                "step": step,
                "filters": {
                    "neighbourhood_group": preferences.get("neighbourhood_group"),
                    "room_type": preferences.get("room_type"),
                    "min_reviews": preferences.get("min_reviews", 0),
                    "availability_min": preferences.get("availability_min"),
                }
            },
            "meta": {
                "denominator_total": n_total,
                "price_max_seen": max_price_seen,
                "data_points": len(curve)
            },
            "coverage_curve": curve,
            "delta_summary": {
                "base_budget": base_budget,
                "new_budget": new_budget,
                "base_count": base_count,
                "new_count": new_count,
                "delta_count": delta_count,
                "base_coverage_pct": base_cov,
                "new_coverage_pct": new_cov,
                "delta_coverage_pct": delta_cov
            },
            "delta_bar": [
                {"label": f"≤€{base_budget}", "count": base_count, "coverage_pct": base_cov},
                {"label": f"≤€{new_budget}", "count": new_count, "coverage_pct": new_cov},
                {"label": "Δ", "count": delta_count, "coverage_pct": delta_cov},
            ],
            "top_gain_areas": top_areas,
            "narrative": english_summary,
            "narrative_en": english_summary,
            "request_budgets": {
                "price_min": req_min,
                "price_max": req_max,
            },
            "echarts_option": echarts_option,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


