import pandas as pd
import numpy as np
import math
from typing import Dict, List, Optional, Tuple
from db import execute_query
from .utils import generate_error_response


def _format_cdf_tooltip(params, bin_labels: List[str]) -> str:
    """Format CDF tooltip to show cumulative percentage meaning."""
    if not params or len(params) == 0:
        return ""
    
    # Get the data point info
    data_index = params.get('dataIndex', 0)
    value = params.get('value', 0)
    
    if data_index >= len(bin_labels):
        return ""
    
    # Extract price range from label (e.g., "50-100€" -> "100€")
    price_label = bin_labels[data_index]
    if '€' in price_label:
        # Extract the upper bound from price range
        if '-' in price_label:
            upper_bound = price_label.split('-')[1].replace('€', '')
        elif '≥' in price_label:
            upper_bound = price_label.replace('≥', '').replace('€', '')
        else:
            upper_bound = price_label.replace('€', '')
        
        return f"<div style='padding: 8px;'>" \
               f"<strong>CDF: {value}%</strong><br/>" \
               f"<span style='color: #666;'>{value}% of properties are priced below {upper_bound}€ </span>" \
               f"</div>"
    else:
        return f"<div style='padding: 8px;'><strong>CDF: {value}%</strong></div>"


def _format_combined_tooltip(params, bin_labels: List[str]) -> str:
    """Format combined tooltip for both bars and CDF line."""
    if not params or len(params) == 0:
        return ""
    
    # Get the first data point to determine the price range
    first_param = params[0]
    data_index = first_param.get('dataIndex', 0)
    
    if data_index >= len(bin_labels):
        return ""
    
    price_label = bin_labels[data_index]
    
    # Extract upper bound for CDF explanation
    upper_bound = ""
    if '€' in price_label:
        if '-' in price_label:
            upper_bound = price_label.split('-')[1].replace('€', '')
        elif '≥' in price_label:
            upper_bound = price_label.replace('≥', '').replace('€', '')
        else:
            upper_bound = price_label.replace('€', '')
    
    # Build tooltip content
    tooltip_content = f"<div style='padding: 8px;'>"
    tooltip_content += f"<strong>价格区间: {price_label}</strong><br/>"
    
    # Add bar data (room types)
    for param in params:
        if param.get('seriesName') != 'CDF':
            series_name = param.get('seriesName', '')
            value = param.get('value', 0)
            color = param.get('color', '#000')
            tooltip_content += f"<span style='color: {color};'>●</span> {series_name}: {value}<br/>"
    
    # Add CDF explanation
    cdf_param = next((p for p in params if p.get('seriesName') == 'CDF'), None)
    if cdf_param and upper_bound:
        cdf_value = cdf_param.get('value', 0)
        tooltip_content += f"<br/><strong>CDF: {cdf_value}%</strong><br/>"
        tooltip_content += f"<span style='color: #666;'>在 {upper_bound}€ 以下有 {cdf_value}% 的房源</span>"
    
    tooltip_content += "</div>"
    return tooltip_content


def _build_tooltip_formatter(bin_labels: List[str]) -> str:
    """Build JavaScript formatter function for tooltip."""
    # Escape the bin_labels for JavaScript
    js_bin_labels = str(bin_labels).replace("'", '"')
    
    return f"""
    function(params) {{
        if (!params || params.length === 0) return '';
        
        var dataIndex = params[0].dataIndex;
        var binLabels = {js_bin_labels};
        
        if (dataIndex >= binLabels.length) return '';
        
        var priceLabel = binLabels[dataIndex];
        var upperBound = '';
        
        if (priceLabel.indexOf('€') !== -1) {{
            if (priceLabel.indexOf('-') !== -1) {{
                upperBound = priceLabel.split('-')[1].replace('€', '');
            }} else if (priceLabel.indexOf('≥') !== -1) {{
                upperBound = priceLabel.replace('≥', '').replace('€', '');
            }} else {{
                upperBound = priceLabel.replace('€', '');
            }}
        }}
        
        var content = '<div style="padding: 8px;">';
        content += '<strong>价格区间: ' + priceLabel + '</strong><br/>';
        
        for (var i = 0; i < params.length; i++) {{
            var param = params[i];
            if (param.seriesName !== 'CDF') {{
                content += '<span style="color: ' + param.color + ';">●</span> ' + param.seriesName + ': ' + param.value + '<br/>';
            }}
        }}
        
        var cdfParam = null;
        for (var i = 0; i < params.length; i++) {{
            if (params[i].seriesName === 'CDF') {{
                cdfParam = params[i];
                break;
            }}
        }}
        
        if (cdfParam && upperBound) {{
            content += '<br/><strong>CDF: ' + cdfParam.value + '%</strong><br/>';
            content += '<span style="color: #666;">在 ' + upperBound + '€ 以下有 ' + cdfParam.value + '% 的房源</span>';
        }}
        
        content += '</div>';
        return content;
    }}
    """


def _compute_display_window(prices: pd.Series) -> Tuple[float, float]:
    """Compute an optimal display window using Tukey's IQR whiskers, rounded.
    Returns (low, high) bounds.
    """
    prices_clean = prices.dropna()
    if prices_clean.empty:
        return 0.0, 0.0
    pmin = float(prices_clean.min())
    pmax = float(prices_clean.max())
    q1, q3 = np.percentile(prices_clean, [25, 75])
    iqr = max(q3 - q1, 1e-6)
    low = max(pmin, q1 - 1.5 * iqr)
    high = min(pmax, q3 + 1.5 * iqr)
    # Fallback if degenerate
    if high <= low:
        p5, p95 = np.percentile(prices_clean, [5, 95])
        low, high = float(p5), float(p95)
    # Round to friendly boundaries (50€ steps)
    low = float(max(0.0, math.floor(low / 50.0) * 50.0))
    high = float(math.ceil(high / 50.0) * 50.0)
    # Ensure span at least 50€
    if high - low < 50.0:
        mid = (low + high) / 2.0
        low = max(0.0, mid - 25.0)
        high = mid + 25.0
    return low, high


def _build_bins(prices: pd.Series, strategy: str) -> Tuple[np.ndarray, List[str]]:
    """Compute bin edges and labels using Auto (Freedman–Diaconis) or Fixed 100€ bins.
    Returns (edges, labels). Labels are like 'min-max€' aligned with edges intervals.
    """
    prices_clean = prices.dropna()
    if prices_clean.empty:
        return np.array([]), []

    p_min = float(prices_clean.min())
    p_max = float(prices_clean.max())
    if p_max <= p_min:
        # single-value fallback
        edges = np.array([math.floor(p_min), math.ceil(p_max + 1)])
        labels = [f"{int(edges[0])}-{int(edges[1])}€"]
        return edges, labels

    if strategy.lower() == "fixed":
        width = 50.0
        start = math.floor(p_min / width) * width
        end = math.ceil(p_max / width) * width
        edges = np.arange(start, end + width, width)
    else:
        # Freedman–Diaconis
        q25, q75 = np.percentile(prices_clean, [25, 75])
        iqr = max(q75 - q25, 1e-6)
        n = max(len(prices_clean), 1)
        width = 2.0 * iqr / (n ** (1.0 / 3.0))
        # clamp width and bin count (min 50€)
        width = float(np.clip(width, 50.0, 150.0))
        start = math.floor(p_min / width) * width
        end = math.ceil(p_max / width) * width
        bin_count = int(math.ceil((end - start) / width))
        bin_count = int(np.clip(bin_count, 10, 50))
        width = (end - start) / max(bin_count, 1)
        edges = np.array([start + i * width for i in range(bin_count + 1)])

    # Ensure integer-like labels
    labels: List[str] = []
    for i in range(len(edges) - 1):
        lo = int(round(edges[i]))
        hi = int(round(edges[i + 1]))
        labels.append(f"{lo}-{hi}€")
    return edges, labels


def _stack_by_room_type(df: pd.DataFrame, bin_labels: List[str]) -> Dict[str, List[int]]:
    """Pivot counts by room_type across ordered bin labels."""
    if df.empty:
        return {}
    pivot = (
        df.groupby(["bin_label", "room_type"])['price']
        .count()
        .reset_index(name='count')
    )
    room_types = sorted(pivot["room_type"].unique().tolist())
    stack: Dict[str, List[int]] = {rt: [0] * len(bin_labels) for rt in room_types}
    for _, row in pivot.iterrows():
        label = row['bin_label']
        rt = row['room_type']
        cnt = int(row['count'])
        if label in bin_labels:
            idx = bin_labels.index(label)
            stack[rt][idx] = cnt
    return stack


def _compute_bin_metrics(df: pd.DataFrame, bin_labels: List[str]) -> Dict[str, List[Optional[float]]]:
    """Compute bin-level quality metrics: rating, rpm, occupancy proxy."""
    if df.empty:
        return {"rating": [], "rpm": [], "occ": []}
    agg = (
        df.groupby("bin_label")
        .agg(
            avg_rating=("review_scores_rating", "mean"),
            avg_rpm=("reviews_per_month", "mean"),
            avg_avail=("availability_365", "mean"),
        )
        .reset_index()
    )
    metrics = {"rating": [None] * len(bin_labels), "rpm": [None] * len(bin_labels), "occ": [None] * len(bin_labels)}
    for _, row in agg.iterrows():
        label = row['bin_label']
        if label in bin_labels:
            idx = bin_labels.index(label)
            rating = None if pd.isna(row['avg_rating']) else float(row['avg_rating'])
            rpm = None if pd.isna(row['avg_rpm']) else float(row['avg_rpm'])
            occ = None
            if not pd.isna(row['avg_avail']):
                occ = float(max(0.0, min(1.0, 1.0 - (row['avg_avail'] / 365.0))))
            metrics['rating'][idx] = rating
            metrics['rpm'][idx] = rpm
            metrics['occ'][idx] = occ
    return metrics


def _compute_global_stats(prices: pd.Series, bin_labels: List[str], totals: List[int]) -> Dict:
    if prices.empty:
        return {"median": None, "iqr": [None, None], "mode_bin": None}
    median = float(np.median(prices))
    q25, q75 = np.percentile(prices.dropna(), [25, 75])
    mode_bin = None
    if totals:
        max_idx = int(np.argmax(totals))
        mode_bin = bin_labels[max_idx] if 0 <= max_idx < len(bin_labels) else None
    return {
        "median": round(median, 2),
        "iqr": [round(float(q25), 2), round(float(q75), 2)],
        "mode_bin": mode_bin
    }


def _budget_analysis(
    df: pd.DataFrame,
    bin_edges: np.ndarray,
    bin_labels: List[str],
    user_min: Optional[float],
    user_max: Optional[float],
    display_low: Optional[float],
    display_high: Optional[float]
) -> Tuple[List[str], Dict]:
    """Return (highlighted_labels, budget_context_extended).
    Includes tail labels if budget intersects tails.
    """
    highlighted: List[str] = []
    budget_ctx: Dict = {}
    if user_min is None or user_max is None or df.empty:
        return highlighted, budget_ctx

    # Determine intersecting mid bins
    for i in range(len(bin_edges) - 1):
        lo = float(bin_edges[i])
        hi = float(bin_edges[i + 1])
        if (lo <= user_max) and (hi >= user_min):
            label = f"{int(round(lo))}-{int(round(hi))}€"
            highlighted.append(label)

    # Tails
    if display_low is not None and user_min <= display_low:
        highlighted.insert(0, f"≤{int(round(display_low))}€")
    if display_high is not None and user_max >= display_high:
        highlighted.append(f"≥{int(round(display_high))}€")

    # Budget coverage and quality
    budget_df = df[(df['price'] >= user_min) & (df['price'] <= user_max)]
    total = int(len(df))
    coverage_count = int(len(budget_df))
    coverage_pct = 0.0 if total == 0 else (coverage_count / total) * 100.0
    top_room = None
    if not budget_df.empty and 'room_type' in budget_df:
        top_room = budget_df['room_type'].value_counts().idxmax()
    avg_rating = None if budget_df['review_scores_rating'].dropna().empty else float(budget_df['review_scores_rating'].mean())
    avg_rpm = None if budget_df['reviews_per_month'].dropna().empty else float(budget_df['reviews_per_month'].mean())
    avg_occ = None
    if not budget_df['availability_365'].dropna().empty:
        avg_occ = float(max(0.0, min(1.0, 1.0 - (budget_df['availability_365'].mean() / 365.0))))

    budget_ctx = {
        "title": f"Your Budget Analysis ({int(user_min)}-{int(user_max)}€)",
        "description": f"There are {coverage_count} listings within your budget range, representing {coverage_pct:.1f}% of the total",
        "budget_note": "Price ranges highlighted in red match your budget",
        "coverage_pct": round(coverage_pct, 1),
        "top_room_type": top_room,
        "avg_rating": None if avg_rating is None else round(avg_rating, 2),
        "avg_rpm": None if avg_rpm is None else round(avg_rpm, 2),
        "avg_occ": None if avg_occ is None else round(avg_occ, 3)
    }
    return highlighted, budget_ctx


def _build_echarts(bin_labels: List[str], stack: Dict[str, List[int]], cdf_pct: List[float], highlighted: List[str], global_stats: Dict) -> Dict:
    """Build stacked bar + CDF line ECharts option with budget highlight and annotations."""
    # Colors for common room types; fallback palette
    room_type_colors = {
        "Entire home/apt": "#4e79a7",
        "Private room": "#f28e2b",
        "Shared room": "#e15759",
        "Hotel room": "#76b7b2",
    }
    palette = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc949", "#af7aa1", "#ff9da7"]

    series: List[Dict] = []
    # Stacked bars by room type
    for idx, (rt, values) in enumerate(stack.items()):
        color = room_type_colors.get(rt, palette[idx % len(palette)])
        series.append({
            "name": rt,
            "type": "bar",
            "stack": "total",
            "data": values,
            "itemStyle": {"color": color}
        })
    # CDF line (right axis, 0-100)
    series.append({
        "name": "CDF",
        "type": "line",
        "yAxisIndex": 1,
        "data": [round(v, 2) for v in cdf_pct],
        "smooth": True,
        "lineStyle": {"color": "#333", "width": 2},
        "symbol": "circle",
        "symbolSize": 6
    })

    option: Dict = {
        "title": {"text": "Price Distribution (Stacked by Room Type)", "left": "center"},
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "cross"},
            "formatter": _build_tooltip_formatter(bin_labels)
        },
        "legend": {"type": "scroll", "top": 6},
        "grid": {"left": 60, "right": 60, "bottom": 60, "top": 70},
        "xAxis": {"type": "category", "data": bin_labels, "name": "Price Range"},
        "yAxis": [
            {"type": "value", "name": "Listings"},
            {"type": "value", "name": "Cumulative %", "min": 0, "max": 100, "axisLabel": {"formatter": "{value}%"}}
        ],
        "series": series
    }

    # Budget area highlight
    if highlighted:
        idxs = [bin_labels.index(lbl) for lbl in highlighted if lbl in bin_labels]
        if idxs:
            first_idx = min(idxs)
            last_idx = max(idxs)
            start_label = bin_labels[first_idx]
            end_label = bin_labels[last_idx]
            # Add markArea to the first bar series for shading
            for s in option["series"]:
                if s.get("type") == "bar":
                    s.setdefault("markArea", {"itemStyle": {"color": "rgba(255,107,107,0.12)"}, "data": []})
                    s["markArea"]["data"] = [[[{"xAxis": start_label}], [{"xAxis": end_label}]]]
                    break

    # Median line annotation
    if global_stats.get("median") is not None:
        median_value = float(global_stats["median"])  # find nearest bin label
        # locate bin index by numeric position
        def _label_mid(lbl: str) -> float:
            if lbl.startswith("≤") or lbl.startswith("≥"):
                # push tails far
                return -1e9 if lbl.startswith("≤") else 1e9
            lo_hi = lbl.replace("€", "").replace("≤", "").replace("≥", "")
            lo, hi = lo_hi.split("-")
            return (float(lo) + float(hi)) / 2.0
        closest_idx = int(np.argmin([abs(_label_mid(lbl) - median_value) for lbl in bin_labels])) if bin_labels else 0
        median_label = bin_labels[closest_idx] if bin_labels else None
        if median_label is not None:
            for s in option["series"]:
                if s.get("type") == "bar":
                    s.setdefault("markLine", {"data": []})
                    s["markLine"]["data"].append({"xAxis": median_label, "label": {"formatter": "Median", "position": "insideEndTop"}})
                    break

    return option


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    # Structural filters only (no budget filtering)
    where = ["price IS NOT NULL", "price > 0"]
    params_desc: List[str] = []
    area_label = None

    # Geography
    if preferences.get("neighbourhood_group"):
        ng = preferences["neighbourhood_group"].replace("'", "''")
        where.append(f"neighbourhood_group_cleansed = '{ng}'")
        area_label = ng
    if preferences.get("neighbourhood"):
        nn = preferences["neighbourhood"].replace("'", "''")
        where.append(f"neighbourhood_cleansed = '{nn}'")
        area_label = nn

    # 房型不作为过滤条件：始终统计全房型的分布（改）
    # 仅保留到可视化层做堆叠拆分，不在SQL阶段过滤房型

    sql = f"""
    SELECT 
        price,
        room_type,
        neighbourhood_group_cleansed,
        neighbourhood_cleansed,
        availability_365,
        CAST(NULLIF(review_scores_rating, '') AS FLOAT) AS review_scores_rating,
        CAST(NULLIF(reviews_per_month, '') AS FLOAT) AS reviews_per_month,
        CAST(NULLIF(review_scores_accuracy, '') AS FLOAT) AS review_scores_accuracy,
        CAST(NULLIF(review_scores_cleanliness, '') AS FLOAT) AS review_scores_cleanliness,
        CAST(NULLIF(review_scores_checkin, '') AS FLOAT) AS review_scores_checkin,
        CAST(NULLIF(review_scores_communication, '') AS FLOAT) AS review_scores_communication,
        CAST(NULLIF(review_scores_location, '') AS FLOAT) AS review_scores_location,
        CAST(NULLIF(review_scores_value, '') AS FLOAT) AS review_scores_value
    FROM listings
    WHERE {' AND '.join(where)}
    """
    df = execute_query(sql)
    if df.empty:
        return generate_error_response("No price data found matching the criteria")

    # Normalize dtypes
    for col in ["price", "availability_365", "review_scores_rating", "reviews_per_month"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Compute display window and separate tails
    display_low, display_high = _compute_display_window(df['price'])
    # Force to 0-1000 window as requested
    display_low = 0.0
    display_high = 1000.0
    mid_df = df[(df['price'] >= display_low) & (df['price'] <= display_high)].copy()
    lower_tail = df[df['price'] < display_low].copy()
    upper_tail = df[df['price'] > display_high].copy()

    # Explicit 50€ bins from 0 to 1000
    edges = np.arange(0.0, 1000.0 + 50.0, 50.0)
    labels = [f"{int(edges[i])}-{int(edges[i + 1])}€" for i in range(len(edges) - 1)]

    if len(labels) == 0:
        return generate_error_response("Unable to compute price bins")

    # Assign bins to mid range
    bins_assigned = pd.cut(mid_df['price'], bins=edges, labels=labels, include_lowest=True, right=True)
    mid_df = mid_df.assign(bin_label=bins_assigned.astype(str))

    # Prepare labels with tails (only upper tail relevant now)
    final_labels: List[str] = []
    final_labels.extend(labels)
    if not upper_tail.empty:
        final_labels.append(f"≥{int(round(display_high))}€")

    # Totals per bin (mid) and tails
    mid_totals_series = mid_df.groupby('bin_label')['price'].count().reindex(labels, fill_value=0)
    mid_totals = [int(x) for x in mid_totals_series.tolist()]
    totals: List[int] = []
    totals.extend(mid_totals)
    if not upper_tail.empty:
        totals.append(int(len(upper_tail)))

    total_records = int(sum(totals))
    if total_records == 0:
        return generate_error_response("No price data after binning")

    # Stack by room type: mid
    stack_mid = _stack_by_room_type(mid_df, labels)
    # Ensure all known room types
    room_types_all = sorted(set(stack_mid.keys()) | set(df['room_type'].dropna().unique().tolist()))
    stack_full: Dict[str, List[int]] = {rt: [0] * len(final_labels) for rt in room_types_all}

    # Fill mid stack
    for rt in room_types_all:
        if rt in stack_mid:
            vals = stack_mid[rt]
        else:
            vals = [0] * len(labels)
        for i, v in enumerate(vals):
            stack_full[rt][i] = int(v)

    # Fill upper tail stack
    if not upper_tail.empty:
        ut_counts = upper_tail.groupby('room_type')['price'].count().to_dict()
        last_idx = len(final_labels) - 1
        for rt in room_types_all:
            stack_full[rt][last_idx] = int(ut_counts.get(rt, 0))

    # Percent and CDF
    percentages = [0.0 if total_records == 0 else (v / total_records) * 100.0 for v in totals]
    cdf_pct = list(np.cumsum(percentages))
    cdf_pct = [min(100.0, float(round(v, 2))) for v in cdf_pct]

    # Bin-level quality: mid + upper tail
    bin_quality_mid = _compute_bin_metrics(mid_df, labels)
    bin_quality = {
        "rating": [None] * len(final_labels),
        "rpm": [None] * len(final_labels),
        "occ": [None] * len(final_labels)
    }
    for i in range(len(labels)):
        bin_quality['rating'][i] = bin_quality_mid['rating'][i]
        bin_quality['rpm'][i] = bin_quality_mid['rpm'][i]
        bin_quality['occ'][i] = bin_quality_mid['occ'][i]
    if not upper_tail.empty:
        idx = len(final_labels) - 1
        bin_quality['rating'][idx] = None if upper_tail['review_scores_rating'].dropna().empty else round(float(upper_tail['review_scores_rating'].mean()), 2)
        bin_quality['rpm'][idx] = None if upper_tail['reviews_per_month'].dropna().empty else round(float(upper_tail['reviews_per_month'].mean()), 2)
        if not upper_tail['availability_365'].dropna().empty:
            occ = 1.0 - float(upper_tail['availability_365'].mean()) / 365.0
            bin_quality['occ'][idx] = round(float(max(0.0, min(1.0, occ))), 3)

    # Per-bin price stats (avg/min/max) for compatibility: mid + tail
    def _stats(series: pd.Series) -> Tuple[float, float, float]:
        if series.dropna().empty:
            return 0.0, 0.0, 0.0
        return round(float(series.mean()), 2), float(series.min()), float(series.max())

    avg_prices_mid = mid_df.groupby('bin_label')['price'].mean().reindex(labels, fill_value=np.nan).tolist()
    min_prices_mid = mid_df.groupby('bin_label')['price'].min().reindex(labels, fill_value=np.nan).tolist()
    max_prices_mid = mid_df.groupby('bin_label')['price'].max().reindex(labels, fill_value=np.nan).tolist()
    avg_prices_mid = [0.0 if pd.isna(x) else round(float(x), 2) for x in avg_prices_mid]
    min_prices_mid = [0.0 if pd.isna(x) else float(x) for x in min_prices_mid]
    max_prices_mid = [0.0 if pd.isna(x) else float(x) for x in max_prices_mid]
    avg_prices: List[float] = []
    min_prices: List[float] = []
    max_prices: List[float] = []
    avg_prices.extend(avg_prices_mid); min_prices.extend(min_prices_mid); max_prices.extend(max_prices_mid)
    if not upper_tail.empty:
        a, mi, ma = _stats(upper_tail['price'])
        avg_prices.append(a); min_prices.append(mi); max_prices.append(ma)

    # Global stats
    global_stats = _compute_global_stats(df['price'], final_labels, totals)
    global_stats.update({
        "bin_strategy": "fixed-50-0-1000",
        "area": area_label,
        "room_type_filter": preferences.get("room_types") or ([preferences.get("room_type")] if preferences.get("room_type") else []),
        "display_range": [0, 1000]
    })

    # Budget highlight and context
    user_price_min = preferences.get("price_min")
    user_price_max = preferences.get("price_max")
    try:
        user_min_f = None if user_price_min is None else float(user_price_min)
        user_max_f = None if user_price_max is None else float(user_price_max)
    except Exception:
        user_min_f, user_max_f = None, None

    highlighted_ranges, budget_context = _budget_analysis(
        df, edges, final_labels, user_min_f, user_max_f, display_low, display_high
    )

    # ECharts option (stacked + CDF)
    echarts_option = _build_echarts(final_labels, stack_full, cdf_pct, highlighted_ranges, global_stats)

    # Compute overall averages for detailed review dimensions (filtered dataset scope)
    # Safely coerce to numeric if present
    detailed_cols = [
        "review_scores_accuracy",
        "review_scores_cleanliness",
        "review_scores_checkin",
        "review_scores_communication",
        "review_scores_location",
        "review_scores_value"
    ]
    for col in detailed_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    review_scores_avg = {
        "rating": None if df.get("review_scores_rating") is None or df["review_scores_rating"].dropna().empty else round(float(df["review_scores_rating"].mean()), 2),
        "accuracy": None if "review_scores_accuracy" not in df or df["review_scores_accuracy"].dropna().empty else round(float(df["review_scores_accuracy"].mean()), 2),
        "cleanliness": None if "review_scores_cleanliness" not in df or df["review_scores_cleanliness"].dropna().empty else round(float(df["review_scores_cleanliness"].mean()), 2),
        "checkin": None if "review_scores_checkin" not in df or df["review_scores_checkin"].dropna().empty else round(float(df["review_scores_checkin"].mean()), 2),
        "communication": None if "review_scores_communication" not in df or df["review_scores_communication"].dropna().empty else round(float(df["review_scores_communication"].mean()), 2),
        "location": None if "review_scores_location" not in df or df["review_scores_location"].dropna().empty else round(float(df["review_scores_location"].mean()), 2),
        "value": None if "review_scores_value" not in df or df["review_scores_value"].dropna().empty else round(float(df["review_scores_value"].mean()), 2)
    }

    # Response preserving existing structure + add new fields
    return {
        "success": True,
        "chart_config": {
            "type": "histogram",
            "title": "Price Distribution Analysis",
            "x_axis": "Price Range",
            "y_axis": "Number of Listings"
        },
        "data": {
            "categories": final_labels,
            "values": totals,
            "additional_metrics": {
                "avg_prices": avg_prices,
                "min_prices": min_prices,
                "max_prices": max_prices
            },
            # New, backward-compatible additions for richer UI
            "stack_by_room_type": stack_full,
            "cdf": cdf_pct,
            "bin_quality": bin_quality,
            "y_modes": ["count", "percentage"],
            "percentages": [round(v, 2) for v in percentages],
            "review_scores_avg": review_scores_avg
        },
        "metadata": {
            "total_records": total_records,
            "avg_price_overall": float(np.nanmean(df['price'])) if total_records > 0 else 0.0,
            "most_common_range": global_stats.get("mode_bin"),
            "global_stats": global_stats
        },
        "highlighted_ranges": highlighted_ranges,
        "budget_context": budget_context,
        "echarts_option": echarts_option
    } 