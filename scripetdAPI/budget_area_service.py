from typing import Optional, Dict, Any, List
from db import execute_query
import pandas as pd


def _sanitize(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.strip().replace("'", "''")


def find_areas_by_budget(
    level: str,
    price_min: float,
    price_max: float,
    parent_district: Optional[str] = None,
    room_type: Optional[str] = None,
    min_reviews: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Find areas whose average listing price falls within [price_min, price_max].
    If none match, return the areas whose average price is just above price_max (ascending).

    Returns per-area fields: name, listing_count, avg_price, median_price, p25_price, p75_price, distance_to_center (for within) or delta_above (for above).
    """
    level = (level or 'district').strip().lower()
    if level not in ('district', 'neighbourhood'):
        raise ValueError("level must be 'district' or 'neighbourhood'")

    where: List[str] = ["price IS NOT NULL", "price > 0"]

    if level == 'neighbourhood' and parent_district:
        safe_parent = _sanitize(parent_district)
        where.append(f"neighbourhood_group_cleansed = '{safe_parent}'")

    if room_type:
        safe_rt = _sanitize(room_type)
        where.append(f"room_type = '{safe_rt}'")

    if min_reviews is not None:
        try:
            where.append(f"number_of_reviews >= {int(min_reviews)}")
        except Exception:
            pass

    group_field = 'neighbourhood_group_cleansed' if level == 'district' else 'neighbourhood_cleansed'
    where_clause = " AND ".join(where) if where else "TRUE"

    # Fetch per-listing prices to compute medians/quantiles accurately
    sql = f"""
    SELECT 
        {group_field} AS area_name,
        price
    FROM listings
    WHERE {where_clause}
    """

    df = execute_query(sql)
    if df is None or df.empty:
        return {
            'success': True,
            'level': level,
            'within': [],
            'above': [],
            'scanned': 0,
        }

    # Clean and convert
    df = df[['area_name', 'price']].copy()
    df = df[df['area_name'].notna() & df['price'].notna()]
    df['price'] = df['price'].astype(float)

    # Group and compute metrics
    grouped = df.groupby('area_name')
    stats = []
    for area_name, g in grouped:
        prices = g['price']
        listing_count = int(len(prices))
        if listing_count == 0:
            continue
        avg_price = float(prices.mean())
        median_price = float(prices.median())
        p25_price = float(prices.quantile(0.25))
        p75_price = float(prices.quantile(0.75))
        stats.append({
            'name': area_name,
            'listing_count': listing_count,
            'avg_price': round(avg_price, 2),
            'median_price': round(median_price, 2),
            'p25_price': round(p25_price, 2),
            'p75_price': round(p75_price, 2),
        })

    # Partition
    try:
        budget_center = (float(price_min) + float(price_max)) / 2.0
    except Exception:
        budget_center = float(price_max)

    within: List[Dict[str, Any]] = []
    above: List[Dict[str, Any]] = []

    for s in stats:
        avg_price = s['avg_price']
        item = dict(s)
        if price_min <= avg_price <= price_max:
            item['distance_to_center'] = round(abs(avg_price - budget_center), 2)
            within.append(item)
        elif avg_price > price_max:
            item['delta_above'] = round(avg_price - price_max, 2)
            above.append(item)

    # Sort
    within.sort(key=lambda x: x.get('distance_to_center', 0.0))
    above.sort(key=lambda x: x.get('avg_price', 0.0))

    return {
        'success': True,
        'level': level,
        'within': within,
        'above': above,
        'scanned': len(stats),
    } 