# map_markers_service.py - 地图标记数据服务模块

from typing import List, Dict, Any, Optional
import json
import math
from db import execute_query


class MapMarkersService:
    """地图标记数据服务类"""
    
    @staticmethod
    def get_large_district_markers(
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        room_type: Optional[str] = None,
        min_reviews: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取大区域标记数据
        
        Args:
            price_min: 最低价格筛选
            price_max: 最高价格筛选
            room_type: 房间类型筛选
            min_reviews: 最少评论数筛选
        
        Returns:
            List[Dict]: 大区域标记数据列表
        """
        
        # 🔍 构建SQL查询条件
        where_conditions = []
        if price_min is not None:
            where_conditions.append(f"price >= {price_min}")
        if price_max is not None:
            where_conditions.append(f"price <= {price_max}")
        if room_type:
            where_conditions.append(f"room_type = '{room_type}'")
        if min_reviews and min_reviews > 0:
            where_conditions.append(f"number_of_reviews >= {min_reviews}")
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # 🗄️ SQL查询 - 大区域聚合数据
        sql = f"""
        SELECT 
            neighbourhood_group_cleansed as district_name,
            COUNT(*) as listing_count,
            ROUND(AVG(price), 1) as avg_price,
            SUM(number_of_reviews) as total_reviews,
            ROUND(AVG(latitude), 6) as center_lat,
            ROUND(AVG(longitude), 6) as center_lng,
            COUNT(DISTINCT neighbourhood_cleansed) as neighbourhood_count
        FROM listings 
        {where_clause}
        GROUP BY neighbourhood_group_cleansed
        HAVING listing_count > 0
        ORDER BY listing_count DESC
        """
        
        try:
            results = execute_query(sql)
            
            # 🔧 修复：安全的结果检查
            # 处理DataFrame或列表两种可能的返回类型
            if hasattr(results, 'empty'):
                # 如果是pandas DataFrame
                if results.empty:
                    return []
                # 转换为字典列表
                results = results.to_dict('records')
            elif not results or len(results) == 0:
                # 如果是普通列表或None
                return []
            
            # 📊 计算总数用于流行度计算
            total_listings = sum(row['listing_count'] for row in results)
            max_listings = max(row['listing_count'] for row in results) if results else 1
            
            markers = []
            for row in results:
                # 🔥 计算流行度百分比
                popularity_percentage = round((row['listing_count'] / total_listings) * 100, 1) if total_listings > 0 else 0
                
                # 🎨 计算标记样式
                intensity = row['listing_count'] / max_listings if max_listings > 0 else 0
                marker_size = max(30, min(60, 30 + (intensity * 30)))
                
                marker = {
                    "district": row['district_name'],
                    "position": {
                        "lat": float(row['center_lat']),
                        "lng": float(row['center_lng'])
                    },
                    "display_number": row['listing_count'],
                    "popup_info": {
                        "listing_count": row['listing_count'],
                        "avg_price": row['avg_price'],
                        "total_reviews": row['total_reviews'],
                        "popularity_percentage": popularity_percentage
                    },
                    "marker_style": {
                        "size": int(marker_size),
                        "color_intensity": intensity,
                        "z_index": row['listing_count']
                    },
                    "neighbourhood_count": row['neighbourhood_count'],
                    "parent_district": None
                }
                markers.append(marker)
            
            return markers
            
        except Exception as e:
            print(f"❌ 获取大区域标记数据失败: {str(e)}")
            raise Exception(f"Database query failed: {str(e)}")
    
    @staticmethod
    def get_small_district_markers(
        district_name: str,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
        room_type: Optional[str] = None,
        min_reviews: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取小区域标记数据
        
        Args:
            district_name: 大区域名称
            price_min: 最低价格筛选
            price_max: 最高价格筛选
            room_type: 房间类型筛选
            min_reviews: 最少评论数筛选
        
        Returns:
            List[Dict]: 小区域标记数据列表
        """
        
        # 🔍 构建SQL查询条件
        where_conditions = [f"neighbourhood_group_cleansed = '{district_name}'"]
        
        if price_min is not None:
            where_conditions.append(f"price >= {price_min}")
        if price_max is not None:
            where_conditions.append(f"price <= {price_max}")
        if room_type:
            where_conditions.append(f"room_type = '{room_type}'")
        if min_reviews and min_reviews > 0:
            where_conditions.append(f"number_of_reviews >= {min_reviews}")
        
        where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # 🗄️ SQL查询 - 小区域聚合数据
        sql = f"""
        SELECT 
            neighbourhood_cleansed as neighbourhood_name,
            neighbourhood_group_cleansed as parent_district,
            COUNT(*) as listing_count,
            ROUND(AVG(price), 1) as avg_price,
            SUM(number_of_reviews) as total_reviews,
            ROUND(AVG(latitude), 6) as center_lat,
            ROUND(AVG(longitude), 6) as center_lng
        FROM listings 
        {where_clause}
        GROUP BY neighbourhood_cleansed, neighbourhood_group_cleansed
        HAVING listing_count > 0
        ORDER BY listing_count DESC
        """
        
        try:
            results = execute_query(sql)
            
            # 🔧 修复：安全的结果检查
            # 处理DataFrame或列表两种可能的返回类型
            if hasattr(results, 'empty'):
                # 如果是pandas DataFrame
                if results.empty:
                    return []
                # 转换为字典列表
                results = results.to_dict('records')
            elif not results or len(results) == 0:
                # 如果是普通列表或None
                return []
            
            # 📊 计算该大区域内的总数用于流行度计算
            total_listings = sum(row['listing_count'] for row in results)
            max_listings = max(row['listing_count'] for row in results) if results else 1
            
            markers = []
            for row in results:
                # 🔥 计算流行度百分比
                popularity_percentage = round((row['listing_count'] / total_listings) * 100, 1) if total_listings > 0 else 0
                
                # 🎨 计算标记样式
                intensity = row['listing_count'] / max_listings if max_listings > 0 else 0
                marker_size = max(20, min(40, 20 + (intensity * 20)))
                
                marker = {
                    "district": row['neighbourhood_name'],
                    "position": {
                        "lat": float(row['center_lat']),
                        "lng": float(row['center_lng'])
                    },
                    "display_number": row['listing_count'],
                    "popup_info": {
                        "listing_count": row['listing_count'],
                        "avg_price": row['avg_price'],
                        "total_reviews": row['total_reviews'],
                        "popularity_percentage": popularity_percentage
                    },
                    "marker_style": {
                        "size": int(marker_size),
                        "color_intensity": intensity,
                        "z_index": row['listing_count']
                    },
                    "neighbourhood_count": None,
                    "parent_district": row['parent_district']
                }
                markers.append(marker)
            
            return markers
            
        except Exception as e:
            print(f"❌ 获取小区域标记数据失败: {str(e)}")
            raise Exception(f"Database query failed: {str(e)}")
    
    @staticmethod
    def get_district_center(district_name: str) -> Dict[str, Any]:
        """
        获取区域中心坐标
        
        Args:
            district_name: 区域名称
        
        Returns:
            Dict: 包含中心坐标的字典
        """
        
        # 🗄️ SQL查询 - 查找区域中心坐标（支持大区域和小区域）
        sql = f"""
        SELECT 
            ROUND(AVG(latitude), 6) as center_lat,
            ROUND(AVG(longitude), 6) as center_lng,
            COUNT(*) as listing_count
        FROM listings 
        WHERE neighbourhood_group_cleansed = '{district_name}' 
           OR neighbourhood_cleansed = '{district_name}'
        """
        
        try:
            results = execute_query(sql)
            
            # 🔧 修复：安全的结果检查
            if hasattr(results, 'empty'):
                # 如果是pandas DataFrame
                if results.empty:
                    raise Exception(f"District '{district_name}' not found")
                # 转换为字典列表
                results = results.to_dict('records')
            elif not results or len(results) == 0:
                # 如果是普通列表或None
                raise Exception(f"District '{district_name}' not found")
            
            result = results[0]
            
            if result['listing_count'] == 0:
                raise Exception(f"District '{district_name}' has no listings")
            
            return {
                "success": True,
                "district_name": district_name,
                "center": {
                    "lat": float(result['center_lat']),
                    "lng": float(result['center_lng'])
                },
                "listing_count": result['listing_count']
            }
            
        except Exception as e:
            print(f"❌ 获取区域中心坐标失败: {str(e)}")
            raise Exception(f"Failed to get district center: {str(e)}")
    
    @staticmethod
    def validate_level(level: str) -> bool:
        """验证层级参数"""
        return level in ['neighbourhood_group', 'neighbourhood']
    
    @staticmethod
    def validate_filters(price_min, price_max, room_type, min_reviews) -> Dict[str, str]:
        """
        验证筛选参数
        
        Returns:
            Dict: 错误信息字典，如果为空则验证通过
        """
        errors = {}
        
        if price_min is not None and price_min < 0:
            errors['price_min'] = 'Price minimum must be non-negative'
        
        if price_max is not None and price_max < 0:
            errors['price_max'] = 'Price maximum must be non-negative'
        
        if price_min is not None and price_max is not None and price_min > price_max:
            errors['price_range'] = 'Price minimum cannot be greater than maximum'
        
        if room_type and room_type not in ['Entire home/apt', 'Private room', 'Shared room', 'Hotel room']:
            errors['room_type'] = 'Invalid room type'
        
        if min_reviews is not None and min_reviews < 0:
            errors['min_reviews'] = 'Minimum reviews must be non-negative'
        
        return errors


# 🧪 测试工具函数
def test_map_markers_service():
    """测试地图标记服务功能"""
    
    try:
        print("🧪 测试大区域标记数据...")
        large_markers = MapMarkersService.get_large_district_markers()
        print(f"✅ 获取到 {len(large_markers)} 个大区域标记")
        
        if large_markers:
            print("📊 示例大区域标记:")
            print(json.dumps(large_markers[0], indent=2, ensure_ascii=False))
        
        print("\n🧪 测试小区域标记数据...")
        if large_markers:
            first_district = large_markers[0]['district']
            small_markers = MapMarkersService.get_small_district_markers(first_district)
            print(f"✅ 获取到 {len(small_markers)} 个小区域标记 (在 {first_district})")
            
            if small_markers:
                print("📊 示例小区域标记:")
                print(json.dumps(small_markers[0], indent=2, ensure_ascii=False))
        
        print("\n🧪 测试区域中心坐标...")
        if large_markers:
            district_name = large_markers[0]['district']
            center = MapMarkersService.get_district_center(district_name)
            print(f"✅ 获取到 {district_name} 中心坐标:")
            print(json.dumps(center, indent=2, ensure_ascii=False))
        
        print("\n🎉 所有测试通过!")
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")


if __name__ == "__main__":
    # 运行测试
    test_map_markers_service()