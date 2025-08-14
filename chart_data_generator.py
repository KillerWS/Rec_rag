# chart_data_generator.py
"""
图表数据生成模块 - 根据用户偏好和查询生成可视化数据
"""

import pandas as pd
from typing import Dict, List, Any, Optional
from db import execute_query
import json

# 新增：引入模块化的图表生成函数
from chart_generators.price_distribution import generate as generate_price_distribution
from chart_generators.location_popularity import generate as generate_location_popularity
from chart_generators.room_type_comparison import generate as generate_room_type_comparison
from chart_generators.neighbourhood_comparison import generate as generate_neighbourhood_comparison
from chart_generators.review_analysis import generate as generate_review_analysis
from chart_generators.price_trend import generate as generate_price_trend
from chart_generators.availability_analysis import generate as generate_availability_analysis
from chart_generators.host_analysis import generate as generate_host_analysis
from chart_generators.reviews_time_series import generate as generate_reviews_time_series
from chart_generators.comments_wordcloud import generate as generate_comments_wordcloud

class ChartDataGenerator:
    """
    图表数据生成器 - 负责根据用户偏好和可视化意图生成图表数据
    """
    
    def __init__(self):
        self.supported_charts = {
            "price_distribution": generate_price_distribution,
            "location_popularity": generate_location_popularity,
            "room_type_comparison": generate_room_type_comparison,
            "neighbourhood_comparison": generate_neighbourhood_comparison,
            "review_analysis": generate_review_analysis,
            "price_trend": generate_price_trend,
            "availability_analysis": generate_availability_analysis,
            "host_analysis": generate_host_analysis,
            # 新增：
            "reviews_time_series": generate_reviews_time_series,
            "comments_wordcloud": generate_comments_wordcloud
        }
    
    def generate_chart_data(self, chart_type: str, user_preferences: Dict, context: Optional[Dict] = None) -> Dict:
        """
        生成指定类型的图表数据
        
        Args:
            chart_type: 图表类型
            user_preferences: 用户偏好设置
            context: 额外上下文信息
            
        Returns:
            包含图表数据的字典
        """
        try:
            print(f"🎨 Generating chart data: {chart_type}")
            print(f"📊 User preferences: {user_preferences}")
            
            # 错误处理
            if chart_type not in self.supported_charts:
                return self._generate_error_response(f"Unsupported chart type: {chart_type}")
            
            # 调用对应的数据生成函数
            chart_data = self.supported_charts[chart_type](user_preferences, context)
            
            # 添加通用元数据
            if chart_data and chart_data.get("success", True):
                chart_data.update({
                    "chart_type": chart_type,
                    "generated_at": pd.Timestamp.now().isoformat(),
                    "user_preferences": user_preferences,
                    "total_records": chart_data.get("metadata", {}).get("total_records", 0)
                })
            
            print(f"✅ Chart data generated successfully: {chart_type}")
            return chart_data
            
        except Exception as e:
            print(f"❌ Chart data generation failed: {chart_type} - {str(e)}")
            return self._generate_error_response(str(e))
    
    # 价格分布图: 柱状图（histogram）
    def _generate_price_distribution(self, preferences: Dict, context: Optional[Dict] = None) -> Dict:
        """生成价格分布图数据"""
        # 构建基础查询条件 - 不包含价格条件
        where_conditions = ["price IS NOT NULL", "price > 0"]
        
        # 只使用非价格相关的用户偏好筛选条件
        if preferences.get("neighbourhood_group"):
            # 简单的SQL注入防护：转义单引号
            safe_neighbourhood = preferences["neighbourhood_group"].replace("'", "''")
            where_conditions.append(f"neighbourhood_group_cleansed = '{safe_neighbourhood}'")
        
        if preferences.get("room_type"):
            safe_room_type = preferences["room_type"].replace("'", "''")
            where_conditions.append(f"room_type = '{safe_room_type}'")
        
        # 获取用户价格偏好 - 用于后续高亮显示，而非过滤数据
        user_price_min = preferences.get("price_min")
        user_price_max = preferences.get("price_max")
        
        # 执行查询 - 不用价格条件过滤，查询所有价格区间的分布
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
            return self._generate_error_response("No price data found matching the criteria")
        
        # 定义所有标准价格区间
        standard_ranges = [
            '0-100€', '101-200€', '201-300€', '301-400€', '401-500€',
            '501-600€', '601-700€', '701-800€', '801-900€', '901-1000€',
            '1001-1500€', '1501-2000€', '2000€+'
        ]
        
        # 将查询结果转换为字典，以便按区间名称查找
        result_dict = {row['price_range']: row for _, row in df.iterrows()}
        
        # 创建包含所有标准区间的完整DataFrame
        complete_data = []
        for price_range in standard_ranges:
            if price_range in result_dict:
                # 该区间有数据，使用实际数据
                complete_data.append({
                    'price_range': price_range,
                    'count': result_dict[price_range]['count'],
                    'avg_price': result_dict[price_range]['avg_price'],
                    'min_price': result_dict[price_range]['min_price'],
                    'max_price': result_dict[price_range]['max_price']
                })
            else:
                # 该区间没有数据，填充为0
                complete_data.append({
                    'price_range': price_range,
                    'count': 0,
                    'avg_price': 0.0,
                    'min_price': 0.0,
                    'max_price': 0.0
                })
        
        # 创建新的DataFrame
        complete_df = pd.DataFrame(complete_data)
        
        # 标记符合用户价格偏好的区间
        highlighted_ranges = []
        if user_price_min is not None and user_price_max is not None:
            for price_range in complete_df['price_range']:
                # 解析价格区间的上下限
                if '-' in price_range:
                    range_parts = price_range.replace('€', '').split('-')
                    range_min = int(range_parts[0])
                    try:
                        range_max = int(range_parts[1])
                    except ValueError:  # 处理"2000+"这种情况
                        range_max = 10000  # 假设上限为10000
                    
                    # 检查区间是否与用户价格偏好有交集
                    if (range_min <= user_price_max and range_max >= user_price_min):
                        highlighted_ranges.append(price_range)
        
        # 计算符合预算的房源数量和百分比
        budget_count = 0
        total_count = int(complete_df["count"].sum())
        
        for i, row in complete_df.iterrows():
            if row['price_range'] in highlighted_ranges:
                budget_count += int(row['count'])
        
        budget_percentage = 0 if total_count == 0 else (budget_count / total_count) * 100
        
        # 构建预算分析信息
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
            "echarts_option": self._generate_price_distribution_echarts(complete_df, highlighted_ranges)
        }
    
    # 地区受欢迎程度: 柱状图（bar）
    #     用户："哪个地区最受欢迎？能给我看个对比图吗？"
    # 系统："📊 为您展示各地区受欢迎程度分析，绿色柱子表示平均价格符合您预算的地区"
    def _generate_location_popularity(self, preferences: Dict, context: Optional[Dict] = None) -> Dict:
        """生成地区受欢迎程度图数据"""
        # 按neighbourhood_group分析
        where_conditions = ["neighbourhood_group_cleansed IS NOT NULL"]
        
        # 🔧 适配你的 execute_query 函数 - 直接拼接SQL字符串
        if preferences.get("price_min"):
            where_conditions.append(f"price >= {preferences['price_min']}")
        
        if preferences.get("price_max"):
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
        ORDER BY listing_count DESC
        LIMIT 12
        """
        
        df = execute_query(sql)
        
        if df.empty:
            return self._generate_error_response("No location data found")
        
        return {
            "success": True,
            "chart_config": {
                "type": "bar",
                "title": "Location Popularity Analysis",
                "x_axis": "Location",
                "y_axis": "Number of Listings"
            },
            "data": {
                "categories": df["neighbourhood_group_cleansed"].tolist(),
                "values": df["listing_count"].tolist(),
                "additional_metrics": {
                    "avg_prices": df["avg_price"].round(2).tolist(),
                    "avg_reviews": df["avg_reviews"].round(1).tolist(),
                    "unique_hosts": df["unique_hosts"].tolist()
                }
            },
            "metadata": {
                "total_locations": len(df),
                "most_popular": df.iloc[0]["neighbourhood_group_cleansed"],
                "total_listings": int(df["listing_count"].sum())
            },
            "echarts_option": self._generate_location_popularity_echarts(df)
        }
    
    # 不同房间类型的价格和数量对比: 饼图（pie）
    def _generate_room_type_comparison(self, preferences: Dict, context: Optional[Dict] = None) -> Dict:
        """生成房型对比图数据"""
        where_conditions = ["room_type IS NOT NULL"]
        
        # 🔧 适配你的 execute_query 函数 - 直接拼接SQL字符串
        if preferences.get("neighbourhood_group"):
            safe_neighbourhood = preferences["neighbourhood_group"].replace("'", "''")
            where_conditions.append(f"neighbourhood_group_cleansed = '{safe_neighbourhood}'")
        
        if preferences.get("price_min") and preferences.get("price_max"):
            where_conditions.append(f"price BETWEEN {preferences['price_min']} AND {preferences['price_max']}")
        
        sql = f"""
        SELECT 
            room_type,
            COUNT(*) as count,
            AVG(price) as avg_price,
            AVG(number_of_reviews) as avg_reviews,
            AVG(availability_365) as avg_availability,
            ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
        FROM listings 
        WHERE {' AND '.join(where_conditions)}
        GROUP BY room_type
        ORDER BY count DESC
        """
        
        df = execute_query(sql)
        
        if df.empty:
            return self._generate_error_response("No room type data found")
        
        return {
            "success": True,
            "chart_config": {
                "type": "pie",
                "title": "Room Type Distribution",
                "subtitle": f"Total {df['count'].sum()} listings"
            },
            "data": {
                "categories": df["room_type"].tolist(),
                "values": df["count"].tolist(),
                "percentages": df["percentage"].tolist(),
                "additional_metrics": {
                    "avg_prices": df["avg_price"].round(2).tolist(),
                    "avg_reviews": df["avg_reviews"].round(1).tolist()
                }
            },
            "metadata": {
                "total_records": int(df["count"].sum()),
                "most_common_type": df.iloc[0]["room_type"],
                "type_variety": len(df)
            },
            "echarts_option": self._generate_room_type_pie_echarts(df)
        }
    
    # 社区详细对比: 柱状图（bar）
    def _generate_neighbourhood_comparison(self, preferences: Dict, context: Optional[Dict] = None) -> Dict:
        """生成具体社区对比图"""
        where_conditions = ["neighbourhood IS NOT NULL"]
        
        # 🔧 适配你的 execute_query 函数 - 直接拼接SQL字符串
        if preferences.get("neighbourhood_group"):
            safe_neighbourhood = preferences["neighbourhood_group"].replace("'", "''")
            where_conditions.append(f"neighbourhood_group_cleansed = '{safe_neighbourhood}'")
        
        if preferences.get("room_type"):
            safe_room_type = preferences["room_type"].replace("'", "''")
            where_conditions.append(f"room_type = '{safe_room_type}'")
        
        sql = f"""
        SELECT 
            neighbourhood_cleansed,
            neighbourhood_group_cleansed,
            COUNT(*) as listing_count,
            AVG(price) as avg_price,
            AVG(number_of_reviews) as avg_reviews
        FROM listings 
        WHERE {' AND '.join(where_conditions)}
        GROUP BY neighbourhood_cleansed, neighbourhood_group_cleansed
        HAVING COUNT(*) >= 5
        ORDER BY listing_count DESC
        LIMIT 15
        """
        
        df = execute_query(sql)
        
        if df.empty:
            return self._generate_error_response("No neighborhood data found")
        
        return {
            "success": True,
            "chart_config": {
                "type": "bar",
                "title": "Neighborhood Comparison",
                "x_axis": "Neighborhood",
                "y_axis": "Number of Listings"
            },
            "data": {
                "categories": df["neighbourhood_cleansed"].tolist(),
                "values": df["listing_count"].tolist(),
                "groups": df["neighbourhood_group_cleansed"].tolist(),
                "additional_metrics": {
                    "avg_prices": df["avg_price"].round(2).tolist(),
                    "avg_reviews": df["avg_reviews"].round(1).tolist()
                }
            },
            "metadata": {
                "total_neighbourhoods": len(df),
                "most_active": df.iloc[0]["neighbourhood_cleansed"]
            },
            "echarts_option": self._generate_neighbourhood_bar_echarts(df)
        }
    

    # 评论分析: 柱状图（bar）
    # 用户："我想看看高评价房源的分布情况"
    # 系统："📊 为您展示评论数量分析，帮助您了解房源的受欢迎程度"
    def _generate_review_analysis(self, preferences: Dict, context: Optional[Dict] = None) -> Dict:
        """生成评论分析图数据"""
        where_conditions = ["number_of_reviews > 0", "price IS NOT NULL"]
        
        # 🔧 适配你的 execute_query 函数 - 直接拼接SQL字符串
        if preferences.get("neighbourhood_group"):
            safe_neighbourhood = preferences["neighbourhood_group"].replace("'", "''")
            where_conditions.append(f"neighbourhood_group_cleansed = '{safe_neighbourhood}'")
        
        sql = f"""
        SELECT 
            CASE 
                WHEN number_of_reviews BETWEEN 0 AND 10 THEN '0-10 reviews'
                WHEN number_of_reviews BETWEEN 11 AND 50 THEN '11-50 reviews'
                WHEN number_of_reviews BETWEEN 51 AND 100 THEN '51-100 reviews'
                WHEN number_of_reviews BETWEEN 101 AND 200 THEN '101-200 reviews'
                ELSE '200+ reviews' 
            END AS review_range,
            COUNT(*) as count,
            AVG(price) as avg_price
        FROM listings 
        WHERE {' AND '.join(where_conditions)}
        GROUP BY review_range
        ORDER BY MIN(number_of_reviews)
        """
        
        df = execute_query(sql)
        
        return {
            "success": True,
            "chart_config": {
                "type": "bar",
                "title": "Review Count Analysis",
                "x_axis": "Review Range",
                "y_axis": "Number of Listings"
            },
            "data": {
                "categories": df["review_range"].tolist(),
                "values": df["count"].tolist(),
                "avg_prices": df["avg_price"].round(2).tolist()
            },
            "metadata": {
                "total_records": int(df["count"].sum())
            },
            "echarts_option": self._generate_review_analysis_echarts(df)
        }
    
    # 价格趋势: 折线图（line）
    def _generate_price_trend(self, preferences: Dict, context: Optional[Dict] = None) -> Dict:
        """生成价格趋势分析 - 按地区分组"""
        sql = """
        SELECT 
            neighbourhood_group_cleansed,
            AVG(price) as avg_price,
            COUNT(*) as listing_count,
            MIN(price) as min_price,
            MAX(price) as max_price
        FROM listings 
        WHERE price IS NOT NULL AND neighbourhood_group_cleansed IS NOT NULL
        GROUP BY neighbourhood_group_cleansed
        HAVING COUNT(*) >= 10
        ORDER BY avg_price DESC
        """
        
        df = execute_query(sql)
        
        return {
            "success": True,
            "chart_config": {
                "type": "line",
                "title": "Price Trends by Location",
                "x_axis": "Location",
                "y_axis": "Average Price (€)"
            },
            "data": {
                "categories": df["neighbourhood_group_cleansed"].tolist(),
                "values": df["avg_price"].round(2).tolist(),
                "listing_counts": df["listing_count"].tolist()
            },
            "metadata": {
                "total_records": int(df["listing_count"].sum())
            },
            "echarts_option": self._generate_price_trend_echarts(df)
        }
    
    # 可用性分析: 环形饼图（pie）
    def _generate_availability_analysis(self, preferences: Dict, context: Optional[Dict] = None) -> Dict:
        """生成可用性分析图"""
        where_conditions = ["availability_365 IS NOT NULL"]
        
        # 🔧 适配你的 execute_query 函数 - 直接拼接SQL字符串
        if preferences.get("neighbourhood_group"):
            safe_neighbourhood = preferences["neighbourhood_group"].replace("'", "''")
            where_conditions.append(f"neighbourhood_group_cleansed = '{safe_neighbourhood}'")
        
        sql = f"""
        SELECT 
            CASE 
                WHEN availability_365 = 0 THEN 'Not available'
                WHEN availability_365 BETWEEN 1 AND 90 THEN '1-90 days'
                WHEN availability_365 BETWEEN 91 AND 180 THEN '91-180 days'
                WHEN availability_365 BETWEEN 181 AND 270 THEN '181-270 days'
                ELSE '271-365 days' 
            END AS availability_range,
            COUNT(*) as count,
            AVG(price) as avg_price
        FROM listings 
        WHERE {' AND '.join(where_conditions)}
        GROUP BY availability_range
        ORDER BY MIN(availability_365)
        """
        
        df = execute_query(sql)
        
        return {
            "success": True,
            "chart_config": {
                "type": "pie",
                "title": "Availability Analysis"
            },
            "data": {
                "categories": df["availability_range"].tolist(),
                "values": df["count"].tolist(),
                "avg_prices": df["avg_price"].round(2).tolist()
            },
            "metadata": {
                "total_records": int(df["count"].sum())
            },
            "echarts_option": self._generate_availability_pie_echarts(df)
        }
    
    # 房东分析: 散点图（scatter）
    def _generate_host_analysis(self, preferences: Dict, context: Optional[Dict] = None) -> Dict:
        """生成房东分析图数据"""
        sql = """
        SELECT 
            calculated_host_listings_count,
            COUNT(*) as host_count,
            AVG(price) as avg_price,
            SUM(number_of_reviews) as total_reviews
        FROM listings 
        WHERE calculated_host_listings_count IS NOT NULL 
        AND calculated_host_listings_count <= 20
        GROUP BY calculated_host_listings_count
        ORDER BY calculated_host_listings_count
        """
        
        df = execute_query(sql)
        
        return {
            "success": True,
            "chart_config": {
                "type": "scatter",
                "title": "Host Listing Count Analysis",
                "x_axis": "Number of Listings per Host",
                "y_axis": "Number of Hosts"
            },
            "data": {
                "categories": df["calculated_host_listings_count"].tolist(),
                "values": df["host_count"].tolist(),
                "avg_prices": df["avg_price"].round(2).tolist()
            },
            "metadata": {
                "total_records": int(df["host_count"].sum())
            },
            "echarts_option": self._generate_host_scatter_echarts(df)
        }
    

    def _generate_reviews_time_series(self, preferences: Dict, context: Optional[Dict] = None) -> Dict:
        """
        生成「评论量时间序列」——按月统计某区域内各月的 review 数量
        """
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
            return self._generate_error_response("No review time series data found")
        return {
            "success": True,
            "chart_config": {"type": "line", "title": "Review Volume Trend", "x_axis": "Month", "y_axis": "Count"},
            "data": {"categories": df["month"].tolist(), "values": df["count"].tolist()},
            "metadata": {"total_reviews": int(df["count"].sum())}
        }


    def _generate_comments_wordcloud(self, preferences: Dict, context: Optional[Dict] = None) -> Dict:
        """
        生成「评论关键词词云」数据——计算评论中最常出现的词
        """
        where = []
        if preferences.get("neighbourhood_group"):
            ng = preferences["neighbourhood_group"].replace("'", "''")
            where.append(f"neighbourhood_group_cleansed = '{ng}'")
        wc_where = " AND ".join(where) or "TRUE"
        # 这里示例用最简单的 SQL 分词统计
        sql = f"""
        WITH tokenized AS (
          SELECT unnest(string_to_array(regexp_replace(lower(comments), '[^a-z0-9 ]', '', 'g'), ' ')) AS word
          FROM reviews
          WHERE {wc_where}
        )
        SELECT word, COUNT(*) AS count
        FROM tokenized
        WHERE length(word) > 2
        GROUP BY word
        ORDER BY count DESC
        LIMIT 50;
        """
        df = execute_query(sql)
        if df.empty:
            return self._generate_error_response("No review keyword data found")
        return {
            "success": True,
            "chart_config": {"type": "wordcloud", "title": "Review Keywords Wordcloud"},
            "data": {"words": df["word"].tolist(), "counts": df["count"].tolist()},
            "metadata": {"distinct_words": len(df)}
        }
    
    # ===== ECharts配置生成方法 =====
    
    def _generate_price_distribution_echarts(self, df: pd.DataFrame, highlighted_ranges: Optional[List[str]] = None) -> Dict:
        """生成价格分布的ECharts配置"""
        if highlighted_ranges is None:
            highlighted_ranges = []
            
        # 创建高亮区间的索引列表
        highlighted_indices = [i for i, range_name in enumerate(df["price_range"].tolist()) if range_name in highlighted_ranges]
        
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
                "itemStyle": {
                    "color": "#5470c6"
                }
            }]
        }
        
        # 如果有用户预算区间，添加预算标记
        if highlighted_ranges:
            try:
                min_budget = min([int(r.split("-")[0].replace("€", "")) for r in highlighted_ranges])
                # 处理2000+这样的情况
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
                pass  # 如果无法解析价格范围，就不添加预算标记
            
        return echarts_config
    
    def _generate_location_popularity_echarts(self, df: pd.DataFrame) -> Dict:
        """生成地区受欢迎程度的ECharts配置"""
        return {
            "title": {"text": "Location Popularity", "left": "center"},
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {"type": "shadow"}
            },
            "xAxis": {
                "type": "category",
                "data": df["neighbourhood_group_cleansed"].tolist(),
                "axisLabel": {"rotate": 45}
            },
            "yAxis": {"type": "value", "name": "Number of Listings"},
            "series": [{
                "name": "Listings",
                "type": "bar",
                "data": df["listing_count"].tolist(),
                "itemStyle": {
                    "color": "#91cc75"
                }
            }]
        }
    
    def _generate_room_type_pie_echarts(self, df: pd.DataFrame) -> Dict:
        """生成房型分布饼图的ECharts配置"""
        return {
            "title": {"text": "Room Type Distribution", "left": "center"},
            "tooltip": {
                "trigger": "item",
                "formatter": "{a} <br/>{b}: {c} ({d}%)"
            },
            "legend": {
                "orient": "vertical",
                "left": "left"
            },
            "series": [{
                "name": "Room Type",
                "type": "pie",
                "radius": "50%",
                "data": [
                    {"value": int(row["count"]), "name": row["room_type"]}
                    for _, row in df.iterrows()
                ],
                "emphasis": {
                    "itemStyle": {
                        "shadowBlur": 10,
                        "shadowOffsetX": 0,
                        "shadowColor": "rgba(0, 0, 0, 0.5)"
                    }
                }
            }]
        }
    
    def _generate_neighbourhood_bar_echarts(self, df: pd.DataFrame) -> Dict:
        """生成社区对比柱状图的ECharts配置"""
        return {
            "title": {"text": "Neighborhood Comparison", "left": "center"},
            "tooltip": {"trigger": "axis"},
            "xAxis": {
                "type": "category",
                "data": df["neighbourhood_cleansed"].tolist(),
                "axisLabel": {"rotate": 45, "interval": 0}
            },
            "yAxis": {"type": "value", "name": "Number of Listings"},
            "series": [{
                "name": "Listings",
                "type": "bar",
                "data": df["listing_count"].tolist(),
                "itemStyle": {"color": "#ee6666"}
            }]
        }
    
    def _generate_review_analysis_echarts(self, df: pd.DataFrame) -> Dict:
        """生成评论分析的ECharts配置"""
        return {
            "title": {"text": "Review Count Analysis", "left": "center"},
            "tooltip": {"trigger": "axis"},
            "xAxis": {
                "type": "category",
                "data": df["review_range"].tolist()
            },
            "yAxis": {"type": "value", "name": "Number of Listings"},
            "series": [{
                "name": "Listings",
                "type": "bar",
                "data": df["count"].tolist(),
                "itemStyle": {"color": "#fac858"}
            }]
        }
    
    def _generate_price_trend_echarts(self, df: pd.DataFrame) -> Dict:
        """生成价格趋势的ECharts配置"""
        return {
            "title": {"text": "Price Trends by Location", "left": "center"},
            "tooltip": {"trigger": "axis"},
            "xAxis": {
                "type": "category",
                "data": df["neighbourhood_group_cleansed"].tolist(),
                "axisLabel": {"rotate": 45}
            },
            "yAxis": {"type": "value", "name": "Average Price (€)"},
            "series": [{
                "name": "Average Price",
                "type": "line",
                "data": df["avg_price"].round(2).tolist(),
                "smooth": True,
                "itemStyle": {"color": "#73c0de"}
            }]
        }
    
    def _generate_availability_pie_echarts(self, df: pd.DataFrame) -> Dict:
        """生成可用性饼图的ECharts配置"""
        return {
            "title": {"text": "Availability Analysis", "left": "center"},
            "tooltip": {
                "trigger": "item",
                "formatter": "{a} <br/>{b}: {c} ({d}%)"
            },
            "series": [{
                "name": "Availability",
                "type": "pie",
                "radius": ["40%", "70%"],
                "avoidLabelOverlap": False,
                "data": [
                    {"value": int(row["count"]), "name": row["availability_range"]}
                    for _, row in df.iterrows()
                ]
            }]
        }
    
    def _generate_host_scatter_echarts(self, df: pd.DataFrame) -> Dict:
        """生成房东分析散点图的ECharts配置"""
        return {
            "title": {"text": "Host Listing Count Analysis", "left": "center"},
            "tooltip": {"trigger": "item"},
            "xAxis": {
                "type": "value",
                "name": "Number of Listings per Host"
            },
            "yAxis": {
                "type": "value",
                "name": "Number of Hosts"
            },
            "series": [{
                "name": "Host Distribution",
                "type": "scatter",
                "data": [
                    [int(row["calculated_host_listings_count"]), int(row["host_count"])]
                    for _, row in df.iterrows()
                ],
                "symbolSize": 8,
                "itemStyle": {"color": "#9a60b4"}
            }]
        }
    
    def _generate_error_response(self, error_message: str) -> Dict:
        """生成错误响应"""
        return {
            "success": False,
            "error": error_message,
            "chart_config": None,
            "data": None,
            "echarts_option": None
        }
    
    def get_supported_chart_types(self) -> List[str]:
        """获取支持的图表类型列表"""
        return list(self.supported_charts.keys())
    
    def batch_generate_charts(self, chart_types: List[str], user_preferences: Dict) -> Dict[str, Dict]:
        """批量生成多个图表的数据"""
        results = {}
        for chart_type in chart_types:
            results[chart_type] = self.generate_chart_data(chart_type, user_preferences)
        return results

# ===== 辅助函数 =====

def extract_visualization_filters(preferences: Dict) -> Dict:
    """从用户偏好中提取可视化过滤器"""
    filters = {}
    
    # 价格相关
    if preferences.get('price_min'):
        filters['price_min'] = preferences['price_min']
    if preferences.get('price_max'):
        filters['price_max'] = preferences['price_max']
    
    # 地理相关
    if preferences.get('neighbourhood_group'):
        filters['neighbourhood_group_cleansed'] = preferences['neighbourhood_group']
    if preferences.get('neighbourhood'):
        filters['neighbourhood_cleansed'] = preferences['neighbourhood']
    
    # 房型相关
    if preferences.get('room_type'):
        filters['room_type'] = preferences['room_type']
    
    # 其他筛选条件
    if preferences.get('minimum_nights'):
        filters['minimum_nights'] = preferences['minimum_nights']
    if preferences.get('min_reviews'):
        filters['min_reviews'] = preferences['min_reviews']
    
    return filters

if __name__ == "__main__":
    print("🚀 Chart Data Generator Module Loaded")
    
    # 测试
    generator = ChartDataGenerator()
    test_preferences = {
        "price_min": 50,
        "price_max": 200,
        "neighbourhood_group": "Mitte"
    }
    
    chart_data = generator.generate_chart_data("price_distribution", test_preferences)
    print(f"Test result: {chart_data.get('success', False)}")