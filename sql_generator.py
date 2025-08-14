from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
# from langchain_community.chat_models import ChatOllama
from load_llm import load_llm  # 从load_llm模块导入加载函数
from typing import Dict, Union, List, Tuple, Optional, Any

# 🔹 LLM 初始化
# sql_llm = ChatOllama(
#     model="llama3.1:8b",
#     base_url='http://localhost:11434',
#     temperature=0.3
# )
sql_llm = load_llm()  # 使用load_llm函数加载LLM实例

# 🔹 SQL 生成模板
SQL_PROMPT_TEMPLATE = """
You are an AI assistant that generates a single valid SQL query from the user’s preferences about Airbnb listings.

The user has six possible preference fields:
1. room_type: (Entire home/apt or Private room)
2. budget: The daily budget, possibly with > or < operators. (e.g. \"< 100\" or \"> 50\")
3. minimum_stay: The minimum number of days the user wants to stay.
4. maximum_stay: The maximum number of days the user can stay.
5. neighbourhood_group_cleansed: Larger district or administrative area within the city (e.g., \"Manhattan\", \"Brooklyn\").
6. neighbourhood_cleansed: More specific area or neighborhood name.

However, the database schema only has the following columns:
- room_type (TEXT)
- price (INT or DOUBLE)
- minimum_nights (INT)
- neighbourhood_group_cleansed (TEXT)
- neighbourhood_cleansed (TEXT)

Any mention of “maximum_stay” must be ignored in the SQL, since there is no matching database column.

In other words, only use:
- room_type to match user’s room_type
- price to match user’s budget
- minimum_nights to match user’s minimum_stay
- neighbourhood_group_cleansed only if explicitly mentioned by user
- neighbourhood_cleansed only if explicitly mentioned by user

Instructions:
1. Generate exactly one valid SELECT SQL query.
2. Use “SELECT * FROM listings WHERE ...” format.
3. Combine conditions with AND if multiple fields are specified.
4. If the user’s budget is e.g. “< 80”, reflect it as price < 80 in SQL.
5. For minimum_stay, reflect it as minimum_nights >= user’s minimum_stay.
6. Only include neighbourhood_group_cleansed or neighbourhood_cleansed conditions if explicitly and clearly mentioned by the user. 
   Never include conditions like \"neighbourhood_group_cleansed IS NULL\" or \"neighbourhood_cleansed IS NULL\ or \"xxx IS NULL\".
7. If a field is not explicitly mentioned, do not use it in WHERE clause.
8. Do not return explanations or commentary—only the final SQL statement.

User’s Preferences:
{user_preferences}
"""

sql_prompt_template = PromptTemplate(
    input_variables=["user_preferences"],
    template=SQL_PROMPT_TEMPLATE
)

def generate_sql_query(user_preferences):
    """使用 LLM 生成 SQL 查询"""
    sql_generation_chain = LLMChain(
        llm=sql_llm,
        prompt=sql_prompt_template
    )
    return sql_generation_chain.run(user_preferences=user_preferences)


import re
from db import execute_query

# 添加函数检查location是否存在于数据库
def is_valid_location(location):
    """
    检查location是否存在于数据库中的neighbourhood或neighbourhood_group
    
    Args:
        location (str): 要检查的位置
        
    Returns:
        tuple: (是否有效, 匹配类型, 匹配值) - 匹配类型可以是 'neighbourhood_group', 'neighbourhood' 或 None
    """
    if not location:
        return False, None, None
    
    # 规范化处理
    clean_location = location.strip().lower()
    
    # 特殊处理"Berlin"关键词
    if clean_location == "berlin":
        return False, "city", "Berlin"
    
    # 查询所有可能的区域
    try:
        query = """
        SELECT DISTINCT neighbourhood_group_cleansed, neighbourhood_cleansed
        FROM listings
        WHERE 
            neighbourhood_group_cleansed IS NOT NULL AND 
            neighbourhood_cleansed IS NOT NULL AND
            neighbourhood_group_cleansed != '' AND
            neighbourhood_cleansed != ''
        """
        results = execute_query(query)
        
        # 检查neighbourhood_group_cleansed匹配
        for _, row in results.iterrows():
            ng = row['neighbourhood_group_cleansed']
            if ng is not None and isinstance(ng, str) and clean_location == ng.lower():
                return True, 'neighbourhood_group_cleansed', ng
                
        # 检查neighbourhood_cleansed匹配
        for _, row in results.iterrows():
            n = row['neighbourhood_cleansed']
            if n is not None and isinstance(n, str) and clean_location == n.lower():
                return True, 'neighbourhood_cleansed', n
        
        return False, None, None
    except Exception as e:
        print(f"❌ 检查location有效性时出错: {e}")
        return False, None, None

# 添加函数验证房型是否有效
def is_valid_room_type(room_type):
    """
    验证房型是否是数据库中有效的类型
    
    Args:
        room_type (str): 要验证的房型
        
    Returns:
        tuple: (是否有效, 规范化房型) 
    """
    if not room_type:
        return False, None
        
    # 规范化房型名称映射
    valid_room_types = {
        "entire home/apt": "Entire home/apt",
        "private room": "Private room",
        "shared room": "Shared room",
        "hotel room": "Hotel room"
    }
    
    clean_room_type = room_type.strip().lower()
    
    # 检查是否是有效的房型
    if clean_room_type in valid_room_types:
        return True, valid_room_types[clean_room_type]
    
    # 检查是否可以近似匹配
    for key in valid_room_types:
        if key in clean_room_type or clean_room_type in key:
            return True, valid_room_types[key]
    
    return False, None

# Valid Berlin districts (neighbourhood_groups)
VALID_NEIGHBOURHOOD_GROUPS = [
    "Pankow",
    "Friedrichshain-Kreuzberg",
    "Neukölln",
    "Mitte",
    "Charlottenburg-Wilm.",
    "Tempelhof - Schöneberg",
    "Lichtenberg",
    "Steglitz - Zehlendorf",
    "Treptow - Köpenick",
    "Spandau",
    "Reinickendorf",
    "Marzahn - Hellersdorf"
]

# Valid room types
VALID_ROOM_TYPES = [
    "Entire home/apt",
    "Private room",
    "Shared room",
    "Hotel room"
]

# Valid Berlin neighborhoods
VALID_NEIGHBOURHOODS = [
    "Prenzlauer Berg Südwest",
    "Prenzlauer Berg Nordwest",
    "nördliche Luisenstadt",
    "Reuterstraße",
    "Brunnenstr. Süd",
    "Tempelhofer Vorstadt",
    "Helmholtzplatz",
    "Düsseldorfer Straße",
    "Schöneberg-Nord",
    "Regierungsviertel",
    "südliche Luisenstadt",
    "Frankfurter Allee Süd FK",
    "Neue Kantstraße",
    "Prenzlauer Berg Süd",
    "Brunnenstr. Nord",
    "Prenzlauer Berg Nord",
    "Kantstraße",
    "Schmargendorf",
    "Alexanderplatz",
    "Blankenfelde/Niederschönhausen",
    "Frankfurter Allee Nord",
    "Schöneberg-Süd",
    "Südliche Friedrichstadt",
    "Wiesbadener Straße",
    "Rixdorf",
    "Blankenburg/Heinersdorf/Märchenland",
    "Pankow Zentrum",
    "Prenzlauer Berg Ost",
    "Buckow Nord",
    "Pankow Süd",
    "Karlshorst",
    "Karl-Marx-Allee-Nord",
    "Zehlendorf  Nord",
    "Rudow",
    "Mierendorffplatz",
    "Otto-Suhr-Allee",
    "Wedding Zentrum",
    "Moabit West",
    "Altglienicke",
    "Moabit Ost",
    "Lichtenrade",
    "Westend",
    "Zehlendorf  Südwest",
    "Johannisthal",
    "Marienfelde",
    "Friedenau",
    "Tiergarten Süd",
    "Heerstraße Nord",
    "Karl-Marx-Allee-Süd",
    "Baumschulenweg",
    "Halensee",
    "Neuköllner Mitte/Zentrum",
    "Schillerpromenade",
    "Tempelhof",
    "Rahnsdorf/Hessenwinkel",
    "Ost 2",
    "Parkviertel",
    "Volkspark Wilmersdorf",
    "Schönholz/Wilhelmsruh/Rosenthal",
    "Alt-Hohenschönhausen Nord",
    "Albrechtstr.",
    "Ostpreußendamm",
    "Britz",
    "Oberschöneweide",
    "Heerstrasse",
    "Nord 1",
    "Adlershof",
    "Mahlsdorf",
    "Friedrichshagen",
    "Forst Grunewald",
    "Barstraße",
    "Ost 1",
    "Schloß Charlottenburg",
    "Osloer Straße",
    "Köllnische Heide",
    "Neu Lichtenberg",
    "Kurfürstendamm",
    "Weißensee",
    "Alt  Treptow",
    "Rummelsburger Bucht",
    "Schloßstr.",
    "West 4",
    "Köpenick-Nord",
    "Frankfurter Allee Süd",
    "MV 2",
    "Teltower Damm",
    "Biesdorf",
    "Fennpfuhl",
    "Schmöckwitz/Karolinenhof/Rauchfangswerder",
    "Alt-Lichtenberg",
    "Mariendorf",
    "Charlottenburg Nord",
    "Buch",
    "Buckow",
    "Drakestr.",
    "Grunewald",
    "Nord 2",
    "Karow",
    "Neu-Hohenschönhausen Nord",
    "Buchholz",
    "Gatow / Kladow",
    "Niederschöneweide",
    "Falkenhagener Feld",
    "West 5",
    "Hellersdorf-Süd",
    "Spandau Mitte",
    "Kaulsdorf",
    "Plänterwald",
    "Bohnsdorf",
    "West 2",
    "Weißensee Ost",
    "Altstadt-Kietz",
    "Köpenick-Süd",
    "Lankwitz",
    "Friedrichsfelde Süd",
    "Haselhorst",
    "Gropiusstadt",
    "Alt-Hohenschönhausen Süd",
    "Brunsbütteler Damm",
    "Grünau",
    "Friedrichsfelde Nord",
    "West 1",
    "MV 1",
    "Dammvorstadt",
    "Müggelheim",
    "West 3",
    "Hakenfelde",
    "Marzahn-Süd",
    "Malchow, Wartenberg und Falkenberg",
    "Wilhelmstadt",
    "Siemensstadt",
    "Allende-Viertel",
    "Marzahn-Mitte",
    "Hellersdorf-Nord",
    "Kölln. Vorstadt/Spindlersf.",
    "Neu-Hohenschönhausen Süd",
    "Marzahn-Nord",
    "Hellersdorf-Ost"
]

def validate_preferences(preferences: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and clean preferences to ensure they contain only valid values.
    
    Args:
        preferences: Dictionary containing user preferences
        
    Returns:
        Dictionary with validated and cleaned preferences
    """
    validated_prefs = preferences.copy()
    
    # Validate price_min and price_max
    if 'price_min' in validated_prefs and 'price_max' in validated_prefs:
        price_min = validated_prefs.get('price_min')
        price_max = validated_prefs.get('price_max')
        
        # Ensure both are numbers
        if price_min is not None and price_max is not None:
            try:
                price_min = float(price_min)
                price_max = float(price_max)
                
                # Ensure proper relationship
                if price_min > price_max:
                    # Swap values if min is greater than max
                    validated_prefs['price_min'] = price_max
                    validated_prefs['price_max'] = price_min
            except (ValueError, TypeError):
                # If conversion fails, remove invalid values
                if not isinstance(price_min, (int, float)):
                    validated_prefs.pop('price_min', None)
                if not isinstance(price_max, (int, float)):
                    validated_prefs.pop('price_max', None)
    
    # Validate room_type
    if 'room_type' in validated_prefs:
        room_type = validated_prefs.get('room_type')
        if room_type not in VALID_ROOM_TYPES:
            validated_prefs.pop('room_type', None)
    
    # Validate neighbourhood_group_cleansed
    if 'neighbourhood_group_cleansed' in validated_prefs:
        neighbourhood_group = validated_prefs.get('neighbourhood_group_cleansed')
        if neighbourhood_group not in VALID_NEIGHBOURHOOD_GROUPS:
            validated_prefs.pop('neighbourhood_group_cleansed', None)
    
    # Validate neighbourhood_cleansed
    if 'neighbourhood_cleansed' in validated_prefs:
        neighbourhood = validated_prefs.get('neighbourhood_cleansed')
        if neighbourhood not in VALID_NEIGHBOURHOODS:
            # Invalid neighborhood value (like "city center"), remove it
            validated_prefs.pop('neighbourhood_cleansed', None)
    
    return validated_prefs

def build_sql_with_fallback(preferences: Dict[str, Any], limit: int = 300) -> Tuple[str, Dict[str, Any]]:
    """
    Build SQL query from preferences with fallback logic when no results are found.
    
    Args:
        preferences: Dictionary containing user preferences
        limit: Maximum number of results to return
        
    Returns:
        Tuple of (SQL query, validated preferences used for the query)
    """
    # First validate all preferences
    validated_prefs = validate_preferences(preferences)
    
    # Build the initial query with all validated preferences
    sql = build_sql_from_preferences(validated_prefs, limit)
    
    # Return both the SQL query and the validated preferences used
    return sql, validated_prefs

def build_sql_from_preferences(preferences: Dict[str, Any], limit: int = 300) -> str:
    """
    Build SQL query from validated preferences.
    
    Args:
        preferences: Dictionary containing validated user preferences
        limit: Maximum number of results to return
        
    Returns:
        SQL query string
    """
    where_clauses = []
    
    # Price range
    if preferences.get('price_min') is not None and preferences.get('price_max') is not None:
        where_clauses.append(f"price BETWEEN {preferences['price_min']} AND {preferences['price_max']}")
    elif preferences.get('price_min') is not None:
        where_clauses.append(f"price >= {preferences['price_min']}")
    elif preferences.get('price_max') is not None:
        where_clauses.append(f"price <= {preferences['price_max']}")

    # Reviews count
    if preferences.get('min_reviews') is not None:
        where_clauses.append(f"number_of_reviews >= {preferences['min_reviews']}")

    # Room type
    if preferences.get("room_type"):
        where_clauses.append(f"room_type = '{preferences['room_type']}'")

    # Neighborhood group (district)
    if preferences.get("neighbourhood_group_cleansed"):
        where_clauses.append(
            f"neighbourhood_group_cleansed = '{preferences['neighbourhood_group_cleansed']}'")

    # Neighborhood
    if preferences.get("neighbourhood_cleansed"):
        where_clauses.append(
            f"neighbourhood_cleansed = '{preferences['neighbourhood_cleansed']}'")
    
    # Ensure at least one condition exists
    if not where_clauses:
        where_clauses.append("1=1")  # Always true condition

    sql = f"""
    SELECT id
    FROM listings
    WHERE {' AND '.join(where_clauses)}
    ORDER BY number_of_reviews DESC
    LIMIT {limit}
    """
    
    return sql

# Function to apply fallback logic by removing min_reviews constraint
def apply_fallback_for_empty_results(preferences: Dict[str, Any], limit: int = 300) -> Tuple[str, Dict[str, Any]]:
    """
    Apply fallback logic by removing min_reviews constraint if no results found.
    
    Args:
        preferences: Dictionary containing validated user preferences
        limit: Maximum number of results to return
        
    Returns:
        Tuple of (SQL query with fallback applied, modified preferences dictionary)
    """
    fallback_prefs = preferences.copy()
    
    # Remove min_reviews constraint as fallback strategy
    if 'min_reviews' in fallback_prefs:
        fallback_prefs.pop('min_reviews')
        
    # Build new SQL with fallback preferences
    sql = build_sql_from_preferences(fallback_prefs, limit)
    
    return sql, fallback_prefs

def generate_sql_query_from_selectedDimensions(selected_dimensions: list) -> dict:
    """
    根据前端发送的 selectedDimensions 生成 SQL 查询和抽取出的偏好信息
    
    前端数据格式示例：
    [
        {key: "Stay Duration", value: "3 days", icon: "📅"},
        {key: "Budget", value: "€150-200", icon: "💰"},
        {key: "Location", value: "Pankow", icon: "🗺️"},
        {key: "Room Type", value: "Private room", icon: "🚪"}
    ]
    
    Returns:
        dict: 包含SQL查询和提取的偏好信息
    """
    print("🔍 generate_sql_query_from_selected called")
    print(f"📋 接收到的维度: {selected_dimensions}")
    
    conditions = []
    # 创建提取的偏好对象
    extracted_preferences = {}
    # 聚合所有房型选择（跨多个条目），避免 AND 多次 room_type
    aggregated_room_types = []
    aggregated_room_types_set = set()

    for item in selected_dimensions:
        key = item["key"].strip()
        value = item["value"].strip()
        
        print(f"🔧 处理维度: {key} = {value}")

        # 🎯 处理预算 (Budget)
        if key in ("Budget", "Price"):
            # 移除货币符号并匹配数字范围
            clean_value = value.replace("€", "").replace("$", "").strip()
            
            # 匹配 "150-200" 格式
            match = re.match(r"(\d+)\s*-\s*(\d+)", clean_value)
            if match:
                low, high = match.groups()
                conditions.append(f"price BETWEEN {low} AND {high}")
                # 存储提取的预算值
                extracted_preferences["price_min"] = int(low)
                extracted_preferences["price_max"] = int(high)
                print(f"✅ 预算条件: price BETWEEN {low} AND {high}")
            else:
                # 匹配单个数字，如 "< 100" 或 "> 50"
                single_match = re.search(r"([<>]?)\s*(\d+)", clean_value)
                if single_match:
                    operator, price_val = single_match.groups()
                    if operator == "<":
                        conditions.append(f"price < {price_val}")
                        extracted_preferences["price_max"] = int(price_val)
                    elif operator == ">":
                        conditions.append(f"price > {price_val}")
                        extracted_preferences["price_min"] = int(price_val)
                    else:
                        conditions.append(f"price <= {price_val}")  # 默认作为最大预算
                        extracted_preferences["price_max"] = int(price_val)
                    print(f"✅ 预算条件: {conditions[-1]}")

        # 🏠 处理房型 (Room Type)
        elif key == "Room Type":
            # 处理多个房型，以逗号分隔
            room_types = [rt.strip() for rt in value.split(",")]
            for room_type in room_types:
                is_valid, normalized_value = is_valid_room_type(room_type)
                if is_valid and normalized_value and normalized_value not in aggregated_room_types_set:
                    aggregated_room_types.append(normalized_value)
                    aggregated_room_types_set.add(normalized_value)
                    # 保存第一个有效房型作为偏好
                    if "room_type" not in extracted_preferences:
                        extracted_preferences["room_type"] = normalized_value
            if not aggregated_room_types:
                print(f"⚠️ 无效房型: '{value}'，查询所有房型")

        # 🗺️ 处理地区 (Location)
        elif key == "Location":
            if value and value.lower() not in ["any", "anywhere", "all"]:
                # 检查location是否有效
                is_valid, location_type, matched_value = is_valid_location(value)
                
                if is_valid and matched_value:
                    # 安全处理字符串，防止SQL注入
                    safe_location = matched_value.replace("'", "''")
                    
                    if location_type == 'neighbourhood_group_cleansed':
                        conditions.append(f"neighbourhood_group_cleansed = '{safe_location}'")
                        extracted_preferences["neighbourhood_group_cleansed"] = safe_location
                        print(f"✅ 大区域条件: neighbourhood_group_cleansed = '{safe_location}'")
                    elif location_type == 'neighbourhood_cleansed':
                        conditions.append(f"neighbourhood_cleansed = '{safe_location}'")
                        extracted_preferences["neighbourhood_cleansed"] = safe_location
                        print(f"✅ 小区域条件: neighbourhood_cleansed = '{safe_location}'")
                else:
                    # 特殊处理"Berlin"或其他无效区域
                    if location_type == "city":
                        print(f"⚠️ 检测到整个城市查询: '{value}'，不添加区域筛选条件")
                        # 不添加筛选条件，相当于查询所有区域
                    else:
                        print(f"⚠️ 未知区域: '{value}'，不添加区域筛选条件")

        # 📅 处理住宿时长 (Stay Duration)
        elif key == "Stay Duration":
            # 提取数字
            duration_match = re.search(r"(\d+)", value)
            if duration_match:
                days = int(duration_match.group(1))
                conditions.append(f"minimum_nights <= {days}")
                extracted_preferences["minimum_nights"] = days
                print(f"✅ 住宿时长条件: minimum_nights <= {days}")

        # 💝 处理特殊需求 (User Care)
        elif key == "User Care":
            # 存储用户关怀信息
            extracted_preferences["user_care"] = value
            # 这里可以根据特殊需求添加相应的筛选条件
            if "premium" in value.lower():
                # 可能增加高评分或超赞房东的条件
                conditions.append("number_of_reviews > 10")
                extracted_preferences["min_reviews"] = 10
                print("💝 检测到优质服务需求，增加评论数筛选")

    # 在遍历完所有维度后，统一添加房型条件（使用 IN 或 OR）
    if aggregated_room_types:
        if len(aggregated_room_types) == 1:
            conditions.append(f"room_type = '{aggregated_room_types[0]}'")
            print(f"✅ 房型条件: room_type = '{aggregated_room_types[0]}'")
        else:
            room_list_sql = ", ".join([f"'{rt}'" for rt in aggregated_room_types])
            conditions.append(f"room_type IN ({room_list_sql})")
            print(f"✅ 多房型条件(聚合): room_type IN ({room_list_sql})")

    # 🔧 构建最终的WHERE子句
    if conditions:
        where_clause = " AND ".join(conditions)
        query = f"SELECT * FROM listings WHERE {where_clause}"
    else:
        print("⚠️ 没有生成任何条件，使用默认查询")
        query = "SELECT * FROM listings WHERE 1=1"
    
    print(f"🎯 最终生成的SQL查询: {query}")
    print(f"📊 提取的偏好信息: {extracted_preferences}")
    
    # 返回包含SQL查询和提取的偏好的对象
    return {
        "sql_query": query,
        "extracted_preferences": extracted_preferences
    }

# 🧪 测试函数
def test_sql_generation():
    """测试SQL生成函数"""
    print("🧪 开始测试SQL生成...")
    
    test_data = [
        {
            "name": "完整条件测试",
            "data": [
                {"key": "Stay Duration", "value": "3 days", "icon": "📅"},
                {"key": "Budget", "value": "€150-200", "icon": "💰"},
                {"key": "Location", "value": "Mitte", "icon": "🗺️"},
                {"key": "Room Type", "value": "Private room", "icon": "🚪"}
            ]
        },
        {
            "name": "预算单一值测试",
            "data": [
                {"key": "Budget", "value": "< 100", "icon": "💰"},
                {"key": "Room Type", "value": "Entire home/apt", "icon": "🚪"}
            ]
        },
        {
            "name": "最小条件测试",
            "data": [
                {"key": "Location", "value": "Kreuzberg", "icon": "🗺️"}
            ]
        },
        {
            "name": "多房型测试",
            "data": [
                {"key": "Budget", "value": "< 150", "icon": "💰"},
                {"key": "Room Type", "value": "Private room, Hotel room", "icon": "🚪"}
            ]
        }
    ]
    
    for test_case in test_data:
        print(f"\n{'='*50}")
        print(f"测试: {test_case['name']}")
        print(f"输入: {test_case['data']}")
        
        result_query = generate_sql_query_from_selectedDimensions(test_case['data'])
        print(f"输出: {result_query}")

if __name__ == "__main__":
    test_sql_generation()