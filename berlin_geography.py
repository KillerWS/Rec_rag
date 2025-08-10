# dynamic_berlin_geography.py

"""
动态柏林地理信息管理模块
基于数据库实际数据构建地理层次关系，替代硬编码方式
"""

import json
import time
import pandas as pd
from typing import Dict, List, Tuple, Optional
from functools import lru_cache
from db import execute_query

class DynamicBerlinGeography:
    """动态柏林地理信息管理器 - 基于数据库实际数据"""
    
    def __init__(self):
        self._hierarchy = None
        self._complete_mapping = None
        self._last_update = None
        self._cache_duration = 3600  # 1小时缓存
        self._update_in_progress = False
        
        # 🎯 基础别名（不依赖数据库的通用映射）
        self.base_aliases = {
            # 英文常见说法
            "central": ("neighbourhood_group", "Mitte"),
            "center": ("neighbourhood_group", "Mitte"),
            "downtown": ("neighbourhood_group", "Mitte"),
            "city center": ("neighbourhood_group", "Mitte"),
            "city centre": ("neighbourhood_group", "Mitte"),
            
            # 著名地标到地区的映射
            "brandenburg gate": ("neighbourhood_group", "Mitte"),
            "brandenburger tor": ("neighbourhood_group", "Mitte"),
            "potsdamer platz": ("neighbourhood_group", "Mitte"),
            "alexanderplatz": ("neighbourhood_group", "Mitte"),
            "hackescher markt": ("neighbourhood_group", "Mitte"),
            "checkpoint charlie": ("neighbourhood_group", "Mitte"),
        }
        
        # 🎯 初始化时加载地理数据
        self._load_geography_data()
    
    def _load_geography_data(self) -> bool:
        """从数据库加载地理层次关系"""
        
        if self._update_in_progress:
            print("⏳ 地理数据更新进行中，跳过重复加载")
            return False
            
        try:
            self._update_in_progress = True
            print("🗺️ 从数据库加载地理层次关系...")
            
            # 🎯 查询数据库获取实际的地理分布
            query = """
            SELECT DISTINCT 
                neighbourhood_group, 
                neighbourhood,
                COUNT(*) as listing_count
            FROM listings 
            WHERE neighbourhood_group IS NOT NULL 
            AND neighbourhood IS NOT NULL
            AND neighbourhood_group != ''
            AND neighbourhood != ''
            GROUP BY neighbourhood_group, neighbourhood
            ORDER BY neighbourhood_group, listing_count DESC
            """
            
            df = execute_query(query)
            
            if df.empty:
                print("❌ 数据库查询无结果，使用后备数据")
                self._use_fallback_data()
                return False
            
            # 🎯 构建层次关系
            hierarchy = {}
            total_mappings = 0
            
            for _, row in df.iterrows():
                group = str(row['neighbourhood_group']).strip()
                neighbourhood = str(row['neighbourhood']).strip()
                listing_count = int(row['listing_count'])
                
                if group not in hierarchy:
                    hierarchy[group] = []
                
                if neighbourhood not in hierarchy[group]:
                    hierarchy[group].append(neighbourhood)
                    total_mappings += 1
            
            # 🎯 构建完整映射字典
            complete_mapping = {}
            
            # 添加大区映射
            for group in hierarchy.keys():
                complete_mapping[group.lower()] = ("neighbourhood_group", group)
            
            # 添加社区映射  
            for group, neighbourhoods in hierarchy.items():
                for neighbourhood in neighbourhoods:
                    complete_mapping[neighbourhood.lower()] = ("neighbourhood", neighbourhood)
            
            # 添加基础别名
            for alias, (field_type, value) in self.base_aliases.items():
                complete_mapping[alias.lower()] = (field_type, value)
            
            # 🎯 更新实例变量
            self._hierarchy = hierarchy
            self._complete_mapping = complete_mapping
            self._last_update = time.time()
            
            print(f"✅ 地理数据加载成功: {len(hierarchy)} 个大区, {total_mappings} 个社区映射")
            print(f"📋 大区列表: {list(hierarchy.keys())}")
            
            return True
            
        except Exception as e:
            print(f"❌ 地理数据加载失败: {e}")
            self._use_fallback_data()
            return False
        finally:
            self._update_in_progress = False
    
    def _use_fallback_data(self):
        """使用后备的静态数据"""
        print("🔄 使用静态后备地理数据")
        
        # 🎯 简化的后备层次关系（主要大区）
        fallback_hierarchy = {
            "Mitte": ["Mitte", "Tiergarten", "Wedding", "Gesundbrunnen", "Moabit"],
            "Friedrichshain-Kreuzberg": ["Friedrichshain", "Kreuzberg"],
            "Pankow": ["Prenzlauer Berg", "Pankow", "Weissensee"],
            "Charlottenburg-Wilm.": ["Charlottenburg", "Wilmersdorf"],
            "Neukölln": ["Neukölln"],
            "Tempelhof - Schöneberg": ["Tempelhof", "Schöneberg"],
            "Spandau": ["Spandau"],
            "Steglitz-Zehlendorf": ["Steglitz", "Zehlendorf"],
            "Treptow - Köpenick": ["Treptow", "Köpenick"],
            "Marzahn - Hellersdorf": ["Marzahn", "Hellersdorf"],
            "Lichtenberg": ["Lichtenberg"],
            "Reinickendorf": ["Reinickendorf", "Tegel"]
        }
        
        # 构建映射
        complete_mapping = {}
        for group, neighbourhoods in fallback_hierarchy.items():
            complete_mapping[group.lower()] = ("neighbourhood_group", group)
            for neighbourhood in neighbourhoods:
                complete_mapping[neighbourhood.lower()] = ("neighbourhood", neighbourhood)
        
        # 添加基础别名
        for alias, (field_type, value) in self.base_aliases.items():
            complete_mapping[alias.lower()] = (field_type, value)
        
        self._hierarchy = fallback_hierarchy
        self._complete_mapping = complete_mapping
        self._last_update = time.time()
    
    def _should_refresh_data(self) -> bool:
        """判断是否需要刷新数据"""
        if self._last_update is None:
            return True
        return (time.time() - self._last_update) > self._cache_duration
    
    def _ensure_data_loaded(self):
        """确保地理数据已加载且是最新的"""
        if self._hierarchy is None or self._should_refresh_data():
            self._load_geography_data()
    
    def find_area(self, user_input: str) -> Tuple[str, str, float, str]:
        """
        根据用户输入找到对应的地区
        
        Args:
            user_input: 用户输入的地区名称
            
        Returns:
            (field_type, field_value, confidence, reason)
        """
        
        self._ensure_data_loaded()
        
        if not user_input:
            return "", "", 0.0, "empty_input"
        
        user_input_lower = user_input.lower().strip()
        
        # 🎯 精确匹配
        if user_input_lower in self._complete_mapping:
            field_type, field_value = self._complete_mapping[user_input_lower]
            return field_type, field_value, 1.0, "exact_match"
        
        # 🎯 部分匹配（用户输入包含地区名）
        best_match = None
        best_score = 0.0
        
        for mapped_name, (field_type, field_value) in self._complete_mapping.items():
            # 检查用户输入是否包含地区名
            if mapped_name in user_input_lower:
                score = len(mapped_name) / len(user_input_lower)
                if score > best_score:
                    best_score = score
                    best_match = (field_type, field_value, score, "partial_match")
            
            # 检查地区名是否包含用户输入
            elif user_input_lower in mapped_name and len(user_input_lower) >= 3:
                score = len(user_input_lower) / len(mapped_name)
                if score > best_score:
                    best_score = score
                    best_match = (field_type, field_value, score, "fuzzy_match")
        
        if best_match and best_score >= 0.3:
            return best_match
        
        # 🎯 未找到匹配
        return "", "", 0.0, "no_match"
    
    def get_neighbourhood_group_areas(self, neighbourhood_group: str) -> List[str]:
        """获取大区下的所有社区"""
        self._ensure_data_loaded()
        return self._hierarchy.get(neighbourhood_group, [])
    
    def get_all_neighbourhood_groups(self) -> List[str]:
        """获取所有大区列表"""
        self._ensure_data_loaded()
        return list(self._hierarchy.keys()) if self._hierarchy else []
    
    def get_all_neighbourhoods(self) -> List[str]:
        """获取所有社区列表"""
        self._ensure_data_loaded()
        
        if not self._hierarchy:
            return []
        
        all_neighbourhoods = []
        for neighbourhoods in self._hierarchy.values():
            all_neighbourhoods.extend(neighbourhoods)
        return all_neighbourhoods
    
    def suggest_areas(self, partial_input: str, limit: int = 5) -> List[Dict]:
        """根据部分输入推荐地区"""
        self._ensure_data_loaded()
        
        if not partial_input or len(partial_input) < 2:
            return []
        
        partial_lower = partial_input.lower()
        suggestions = []
        
        if not self._complete_mapping:
            return []
        
        for mapped_name, (field_type, field_value) in self._complete_mapping.items():
            if partial_lower in mapped_name:
                score = len(partial_lower) / len(mapped_name)
                suggestions.append({
                    "name": field_value,
                    "type": field_type,
                    "display_type": "大区" if field_type == "neighbourhood_group" else "社区",
                    "score": score
                })
        
        # 按评分排序并去重
        suggestions.sort(key=lambda x: x["score"], reverse=True)
        
        seen = set()
        unique_suggestions = []
        for suggestion in suggestions:
            key = (suggestion["name"], suggestion["type"])
            if key not in seen and len(unique_suggestions) < limit:
                seen.add(key)
                unique_suggestions.append(suggestion)
        
        return unique_suggestions
    
    def is_user_specified_location(self, text: str) -> bool:
        """判断用户是否明确指定了地理位置"""
        text_lower = text.lower()
        
        # 检查基本位置指示词
        location_indicators = [
            "in", "at", "near", "around", "close to", "located in"
        ]
        
        has_location_indicator = any(indicator in text_lower for indicator in location_indicators)
        
        # 检查是否提到了任何已知地区
        self._ensure_data_loaded()
        
        if self._complete_mapping:
            has_known_area = any(area_name in text_lower for area_name in self._complete_mapping.keys())
        else:
            has_known_area = False
        
        return has_location_indicator or has_known_area
    
    def get_database_stats(self) -> Dict:
        """获取数据库地理统计信息"""
        self._ensure_data_loaded()
        
        return {
            "total_groups": len(self._hierarchy) if self._hierarchy else 0,
            "total_neighbourhoods": len(self.get_all_neighbourhoods()),
            "total_mappings": len(self._complete_mapping) if self._complete_mapping else 0,
            "last_update": self._last_update,
            "cache_duration": self._cache_duration,
            "data_source": "database" if self._last_update else "fallback"
        }

# 🎯 全局实例
berlin_geo = DynamicBerlinGeography()

def find_berlin_area(user_input: str) -> Tuple[str, str, float, str]:
    """查找柏林地区的便捷函数"""
    return berlin_geo.find_area(user_input)

def get_area_suggestions(partial_input: str) -> List[Dict]:
    """获取地区建议的便捷函数"""
    return berlin_geo.suggest_areas(partial_input)

def is_location_mentioned(text: str) -> bool:
    """判断是否提到了地理位置的便捷函数"""
    return berlin_geo.is_user_specified_location(text)

def refresh_geography_data() -> bool:
    """手动刷新地理数据的便捷函数"""
    return berlin_geo._load_geography_data()

def get_geography_stats() -> Dict:
    """获取地理数据统计信息的便捷函数"""
    return berlin_geo.get_database_stats()

# 🧪 测试函数
def test_dynamic_berlin_geography():
    """测试动态地理信息功能"""
    print("=" * 60)
    print("🗺️ 动态柏林地理信息测试")
    print("=" * 60)
    
    # 显示统计信息
    stats = get_geography_stats()
    print(f"\n📊 地理数据统计:")
    for key, value in stats.items():
        print(f"  - {key}: {value}")
    
    # 测试地区查找
    test_inputs = [
        "Mitte", "mitte", "central", "Kreuzberg", 
        "prenzlauer berg", "charlottenburg", "alexanderplatz",
        "downtown", "friedrichshain", "unknown area"
    ]
    
    print("\n📍 地区查找测试:")
    for test_input in test_inputs:
        field_type, field_value, confidence, reason = find_berlin_area(test_input)
        print(f"'{test_input}' → {field_type}: '{field_value}' (置信度: {confidence:.2f}, 原因: {reason})")
    
    # 测试地理位置检测
    print("\n🎯 地理位置提及检测:")
    test_texts = [
        "I want a room in Mitte",
        "Looking for accommodation",
        "Something near central Berlin",
        "I need wifi and kitchen",
        "Around Alexanderplatz would be great"
    ]
    
    for text in test_texts:
        is_mentioned = is_location_mentioned(text)
        print(f"'{text}' → 地理位置提及: {is_mentioned}")
    
    # 测试建议功能
    print("\n💡 地区建议测试:")
    suggestions = get_area_suggestions("mit")
    print(f"'mit' 的建议: {suggestions}")

if __name__ == "__main__":
    test_dynamic_berlin_geography()