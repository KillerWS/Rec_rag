from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import pymysql
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, Dict, Any, List, Union

db = SQLAlchemy()

def init_db(app):
    """初始化数据库连接"""
    try:
        app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://chris_001:9YNNhrN54Fqne0IF@mysql5.sqlpub.com:3310/chris_db_001"
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        db.init_app(app)
        print("✅ 数据库连接成功")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")

def execute_query(query):
    """执行 SQL 查询并返回 Pandas DataFrame，带异常处理"""
    print("execute_query called")
    try:
        with db.engine.connect() as connection:
            df = pd.read_sql(query, connection)
        return df
    except SQLAlchemyError as e:
        print(f"❌ SQL 查询失败: {e}")
        return pd.DataFrame()  # 返回空数据防止系统崩溃

def get_listing_by_id(listing_id: Union[int, str]) -> Optional[Dict[str, Any]]:
    """
    根据 listing_id 查询 listings 表并返回结构化数据
    
    参数:
        listing_id: 房源ID，可以是整数或字符串
    
    返回:
        Dict[str, Any]: 包含房源信息的字典，如果查询失败或无结果返回 None
    """
    print(f"查询 listing_id: {listing_id}")
    
    try:
        # 构建安全的 SQL 查询（使用参数化查询防止 SQL 注入）
        query = """
            SELECT * FROM listings 
            WHERE id = %(listing_id)s
        """
        
        with db.engine.connect() as connection:
            # 使用参数化查询
            df = pd.read_sql(query, connection, params={'listing_id': listing_id})
        
        if df.empty:
            print(f"❌ 未找到 listing_id 为 {listing_id} 的记录")
            return None
            
        # 将 DataFrame 转换为字典格式
        result = df.iloc[0].to_dict()
        
        # 处理 NaN 值，转换为 None
        for key, value in result.items():
            if pd.isna(value):
                result[key] = None
                
        print(f"✅ 成功查询到 listing_id: {listing_id}")
        return result
        
    except SQLAlchemyError as e:
        print(f"❌ 查询 listing 失败: {e}")
        return None
    except Exception as e:
        print(f"❌ 查询过程中发生错误: {e}")
        return None

def get_listings_by_ids(listing_ids: List[Union[int, str]]) -> List[Dict[str, Any]]:
    """
    根据多个 listing_id 批量查询 listings 表
    
    参数:
        listing_ids: 房源ID列表
    
    返回:
        List[Dict[str, Any]]: 包含房源信息的字典列表
    """
    print(f"批量查询 listing_ids: {listing_ids}")
    
    if not listing_ids:
        print("❌ listing_ids 列表为空")
        return []
    
    try:
        # 构建 IN 查询的占位符
        placeholders = ','.join(['%s'] * len(listing_ids))
        query = f"""
            SELECT * FROM listings 
            WHERE id IN ({placeholders})
        """
        
        with db.engine.connect() as connection:
            df = pd.read_sql(query, connection, params=listing_ids)
        
        if df.empty:
            print(f"❌ 未找到任何匹配的记录")
            return []
            
        # 将 DataFrame 转换为字典列表
        results = []
        for _, row in df.iterrows():
            result = row.to_dict()
            # 处理 NaN 值
            for key, value in result.items():
                if pd.isna(value):
                    result[key] = None
            results.append(result)
                
        print(f"✅ 成功查询到 {len(results)} 条记录")
        return results
        
    except SQLAlchemyError as e:
        print(f"❌ 批量查询 listings 失败: {e}")
        return []
    except Exception as e:
        print(f"❌ 批量查询过程中发生错误: {e}")
        return []

def test_db_connection():
    """
    测试数据库连接并执行简单查询
    
    返回:
        bool: 连接成功返回True，失败返回False
    """
    try:
        print("测试数据库连接...")
        query = "SELECT COUNT(*) as count FROM listings"
        result = execute_query(query)
        
        if result.empty:
            print("❌ 数据库连接测试失败：查询返回空结果")
            return False
        
        count = result['count'].iloc[0]
        print(f"✅ 数据库连接测试成功！listings 表包含 {count} 条记录")
        
        # 查询一条示例数据
        sample_query = "SELECT * FROM listings LIMIT 1"
        sample = execute_query(sample_query)
        
        if not sample.empty:
            print("✅ 示例数据：")
            print(sample)
        
        return True
    except Exception as e:
        print(f"❌ 数据库连接测试失败：{e}")
        return False
