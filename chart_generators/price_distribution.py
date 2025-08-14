import pandas as pd
from typing import Dict, List, Optional
from db import execute_query
from .utils import generate_error_response


def _generate_price_distribution_echarts(df: pd.DataFrame, highlighted_ranges: Optional[List[str]] = None) -> Dict:
    if highlighted_ranges is None:
        highlighted_ranges = []
    echarts_config = {
        "title": {"text": "Price Distribution Analysis", "left": "center"},
        "tooltip": {
            "trigger": "axis",
            "formatter": "{b}<br/>Listings: {@[0]}<br/>Average price: €{@[1]}{@[2]}"
        },
        "xAxis": {
            "type": "category",
            "data": df["price_range"].tolist(),
            "name": "Price Range"
        },
        "yAxis": {
            "type": "value",
            "name": "Number of Listings"
        },
        "series": [{
            "name": "Listings",
            "type": "bar",
            "encode": {"y": 0},
            "data": [
                {
                    "value": [
                        int(row["count"]),
                        round(float(row["avg_price"]), 2),
                        (" ✓ Matches your budget" if row["price_range"] in highlighted_ranges else "")
                    ],
                    "itemStyle": {
                        "color": "#ff6b6b" if row["price_range"] in highlighted_ranges else "#5470c6",
                        "borderColor": "#fff",
                        "borderWidth": 2,
                        "shadowBlur": 10,
                        "shadowColor": "rgba(255, 107, 107, 0.5)" if row["price_range"] in highlighted_ranges else "rgba(0, 0, 0, 0)"
                    },
                    "emphasis": {
                        "itemStyle": {
                            "color": "#ff5252" if row["price_range"] in highlighted_ranges else "#3a56a8"
                        }
                    }
                }
                for _, row in df.iterrows()
            ],
            "itemStyle": {"color": "#5470c6"}
        }]
    }
    if highlighted_ranges:
        try:
            min_budget = min([int(r.split("-")[0].replace("€", "")) for r in highlighted_ranges])
            max_parts = [r.split("-")[1] if "-" in r else r for r in highlighted_ranges]
            max_budget = max([int(p.replace("€", "").replace("+", "")) for p in max_parts])
            echarts_config["graphic"] = [{
                "type": "text",
                "left": "10%",
                "top": "10%",
                "style": {
                    "text": f"Your Budget: {min_budget}-{max_budget}€",
                    "fontSize": 14,
                    "fontWeight": "bold",
                    "fill": "#ff6b6b"
                }
            }]
        except (ValueError, IndexError):
            pass
    return echarts_config


def generate(preferences: Dict, context: Optional[Dict] = None) -> Dict:
    where_conditions = ["price IS NOT NULL", "price > 0"]
    if preferences.get("neighbourhood_group"):
        safe_neighbourhood = preferences["neighbourhood_group"].replace("'", "''")
        where_conditions.append(f"neighbourhood_group_cleansed = '{safe_neighbourhood}'")
    if preferences.get("room_type"):
        safe_room_type = preferences["room_type"].replace("'", "''")
        where_conditions.append(f"room_type = '{safe_room_type}'")
    user_price_min = preferences.get("price_min")
    user_price_max = preferences.get("price_max")
    sql = f"""
    SELECT 
        CASE 
            WHEN price BETWEEN 0 AND 100 THEN '0-100€'
            WHEN price BETWEEN 101 AND 200 THEN '101-200€'
            WHEN price BETWEEN 201 AND 300 THEN '201-300€'
            WHEN price BETWEEN 301 AND 400 THEN '301-400€'
            WHEN price BETWEEN 401 AND 500 THEN '401-500€'
            WHEN price BETWEEN 501 AND 600 THEN '501-600€'
            WHEN price BETWEEN 601 AND 700 THEN '601-700€'
            WHEN price BETWEEN 701 AND 800 THEN '701-800€'
            WHEN price BETWEEN 801 AND 900 THEN '801-900€'
            WHEN price BETWEEN 901 AND 1000 THEN '901-1000€'
            WHEN price BETWEEN 1001 AND 1500 THEN '1001-1500€'
            WHEN price BETWEEN 1501 AND 2000 THEN '1501-2000€'
            ELSE '2000€+' 
        END AS price_range,
        COUNT(*) as count,
        AVG(price) as avg_price,
        MIN(price) as min_price,
        MAX(price) as max_price
    FROM listings 
    WHERE {' AND '.join(where_conditions)}
    GROUP BY price_range
    ORDER BY MIN(price)
    """
    df = execute_query(sql)
    if df.empty:
        return generate_error_response("No price data found matching the criteria")
    standard_ranges = [
        '0-100€', '101-200€', '201-300€', '301-400€', '401-500€',
        '501-600€', '601-700€', '701-800€', '801-900€', '901-1000€',
        '1001-1500€', '1501-2000€', '2000€+'
    ]
    result_dict = {row['price_range']: row for _, row in df.iterrows()}
    complete_data = []
    for price_range in standard_ranges:
        if price_range in result_dict:
            complete_data.append({
                'price_range': price_range,
                'count': result_dict[price_range]['count'],
                'avg_price': result_dict[price_range]['avg_price'],
                'min_price': result_dict[price_range]['min_price'],
                'max_price': result_dict[price_range]['max_price']
            })
        else:
            complete_data.append({
                'price_range': price_range,
                'count': 0,
                'avg_price': 0.0,
                'min_price': 0.0,
                'max_price': 0.0
            })
    complete_df = pd.DataFrame(complete_data)
    highlighted_ranges: List[str] = []
    if user_price_min is not None and user_price_max is not None:
        for price_range in complete_df['price_range']:
            if '-' in price_range:
                range_parts = price_range.replace('€', '').split('-')
                range_min = int(range_parts[0])
                try:
                    range_max = int(range_parts[1])
                except ValueError:
                    range_max = 10000
                if (range_min <= user_price_max and range_max >= user_price_min):
                    highlighted_ranges.append(price_range)
    budget_count = 0
    total_count = int(complete_df["count"].sum())
    for _, row in complete_df.iterrows():
        if row['price_range'] in highlighted_ranges:
            budget_count += int(row['count'])
    budget_percentage = 0 if total_count == 0 else (budget_count / total_count) * 100
    budget_context = {}
    if user_price_min is not None and user_price_max is not None:
        budget_context = {
            "title": f"Your Budget Analysis ({user_price_min}-{user_price_max}€)",
            "description": f"There are {budget_count} listings within your budget range, representing {budget_percentage:.1f}% of the total",
            "budget_note": "Price ranges highlighted in red match your budget"
        }
    return {
        "success": True,
        "chart_config": {
            "type": "histogram",
            "title": "Price Distribution Analysis",
            "x_axis": "Price Range",
            "y_axis": "Number of Listings"
        },
        "data": {
            "categories": complete_df["price_range"].tolist(),
            "values": complete_df["count"].tolist(),
            "additional_metrics": {
                "avg_prices": complete_df["avg_price"].tolist(),
                "min_prices": complete_df["min_price"].tolist(),
                "max_prices": complete_df["max_price"].tolist()
            }
        },
        "metadata": {
            "total_records": int(complete_df["count"].sum()),
            "avg_price_overall": float(df["avg_price"].mean()) if not df.empty else 0.0,
            "most_common_range": df.loc[df["count"].idxmax(), "price_range"] if not df.empty else ""
        },
        "highlighted_ranges": highlighted_ranges,
        "budget_context": budget_context,
        "echarts_option": _generate_price_distribution_echarts(complete_df, highlighted_ranges)
    } 