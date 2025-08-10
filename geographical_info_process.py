# 柏林地区层次结构处理系统 - 完整版
import pandas as pd
import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, List, Tuple, Optional
import logging

class BerlinLocationManager:
    """柏林地区层次结构管理器 - 基于MySQL数据库"""
    
    def __init__(self, db_config: Dict[str, str]):
        """
        初始化地区管理器
        
        Args:
            db_config: 数据库配置字典
                {
                    'host': 'localhost',
                    'port': 3306,
                    'user': 'airbnb_user', 
                    'password': '123456',
                    'database': 'airbnb_db'
                }
        """
        self.db_config = db_config
        self.engine = None
        self.location_cache = {}
        
        # 设置日志
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # 初始化数据库连接和数据
        self._initialize_database()
        self._initialize_location_data()
    
    def _initialize_database(self):
        """初始化数据库连接"""
        try:
            # 创建数据库连接
            connection_string = (
                f"mysql+pymysql://{self.db_config['user']}:{self.db_config['password']}"
                f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
            )
            
            self.engine = create_engine(
                connection_string,
                echo=False,  # 设置为True可以看到SQL语句
                pool_pre_ping=True,  # 自动重连
                pool_recycle=3600    # 连接回收时间
            )
            
            # 测试连接
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                self.logger.info("✅ MySQL数据库连接成功")
                
        except Exception as e:
            self.logger.error(f"❌ 数据库连接失败: {e}")
            raise
    
    def _create_tables_if_not_exists(self):
        """创建必要的数据表（如果不存在）"""
        create_listings_table = """
        CREATE TABLE IF NOT EXISTS listings (
            id INT PRIMARY KEY,
            name VARCHAR(255),
            neighbourhood_group VARCHAR(100),
            neighbourhood VARCHAR(100),
            latitude DECIMAL(10, 8),
            longitude DECIMAL(11, 8),
            price DECIMAL(10, 2),
            minimum_nights INT,
            availability_365 INT,
            INDEX idx_neighbourhood_group (neighbourhood_group),
            INDEX idx_neighbourhood (neighbourhood)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        
        try:
            with self.engine.connect() as conn:
                conn.execute(text(create_listings_table))
                conn.commit()
                self.logger.info("✅ 数据表检查/创建完成")
        except Exception as e:
            self.logger.error(f"❌ 创建数据表失败: {e}")
    
    def execute_query(self, query: str, params: Dict = None) -> pd.DataFrame:
        """
        执行SQL查询并返回DataFrame
        
        Args:
            query: SQL查询语句
            params: 查询参数（可选）
            
        Returns:
            pd.DataFrame: 查询结果
        """
        try:
            with self.engine.connect() as connection:
                if params:
                    df = pd.read_sql(text(query), connection, params=params)
                else:
                    df = pd.read_sql(text(query), connection)
                return df
        except SQLAlchemyError as e:
            self.logger.error(f"❌ SQL查询失败: {e}")
            return pd.DataFrame()
    
    def _initialize_location_data(self):
        """从数据库初始化地区数据"""
        try:
            # 获取所有地区层次信息
            query = """
            SELECT DISTINCT 
                neighbourhood_group, 
                neighbourhood, 
                COUNT(*) as listing_count,
                AVG(price) as avg_price
            FROM listings 
            WHERE neighbourhood_group IS NOT NULL 
                AND neighbourhood IS NOT NULL
                AND price > 0
            GROUP BY neighbourhood_group, neighbourhood
            ORDER BY neighbourhood_group, listing_count DESC
            """
            
            df = self.execute_query(query)
            
            if df.empty:
                self.logger.warning("⚠️  数据库中没有找到地区数据，使用备用数据")
                self._load_fallback_data()
                return
            
            # 构建层次结构缓存
            self._build_location_cache(df)
            
            self.logger.info(f"✅ 已加载 {len(self.location_cache['groups'])} 个地区群组")
            
        except Exception as e:
            self.logger.error(f"❌ 初始化地区数据失败: {e}")
            self._load_fallback_data()
    
    def _build_location_cache(self, df: pd.DataFrame):
        """构建地区缓存数据结构"""
        self.location_cache = {
            'groups': {},
            'neighbourhood_to_group': {},
            'popular_neighbourhoods': {},
            'neighbourhood_stats': {},  # 新增：社区统计信息
            'group_aliases': self._get_group_aliases(),
            'neighbourhood_aliases': self._get_neighbourhood_aliases()
        }
        
        for _, row in df.iterrows():
            group = row['neighbourhood_group']
            neighbourhood = row['neighbourhood']
            count = row['listing_count']
            avg_price = row['avg_price']
            
            # 构建群组映射
            if group not in self.location_cache['groups']:
                self.location_cache['groups'][group] = []
            
            neighbourhood_info = {
                'name': neighbourhood,
                'listing_count': count,
                'avg_price': round(avg_price, 2) if pd.notna(avg_price) else 0
            }
            
            self.location_cache['groups'][group].append(neighbourhood_info)
            
            # 构建反向映射
            self.location_cache['neighbourhood_to_group'][neighbourhood] = group
            
            # 保存社区统计
            self.location_cache['neighbourhood_stats'][neighbourhood] = {
                'group': group,
                'listing_count': count,
                'avg_price': round(avg_price, 2) if pd.notna(avg_price) else 0
            }
            
            # 标记热门社区 (房源数量 > 50)
            if count > 50:
                if group not in self.location_cache['popular_neighbourhoods']:
                    self.location_cache['popular_neighbourhoods'][group] = []
                self.location_cache['popular_neighbourhoods'][group].append(neighbourhood)
        
        # 按房源数量排序热门社区
        for group in self.location_cache['popular_neighbourhoods']:
            self.location_cache['popular_neighbourhoods'][group].sort(
                key=lambda x: self.location_cache['neighbourhood_stats'][x]['listing_count'],
                reverse=True
            )
    
    def _get_group_aliases(self) -> Dict[str, str]:
        """获取地区群组的常见别名映射"""
        return {
            # 常见英文/德文别名 → 标准名称
            "mitte": "Mitte",
            "center": "Mitte", 
            "central": "Mitte",
            "downtown": "Mitte",
            "kreuzberg": "Friedrichshain-Kreuzberg",
            "friedrichshain": "Friedrichshain-Kreuzberg",
            "xberg": "Friedrichshain-Kreuzberg",
            "fhain": "Friedrichshain-Kreuzberg",
            "prenzlauer": "Pankow",
            "prenzlauer berg": "Pankow",
            "p-berg": "Pankow",
            "charlottenburg": "Charlottenburg-Wilm.",
            "wilmersdorf": "Charlottenburg-Wilm.",
            "neukölln": "Neukölln",
            "neukolln": "Neukölln",
            "tempelhof": "Tempelhof - Schöneberg",
            "schöneberg": "Tempelhof - Schöneberg",
            "schoneberg": "Tempelhof - Schöneberg"
        }
    
    def _get_neighbourhood_aliases(self) -> Dict[str, str]:
        """获取具体社区的常见别名"""
        return {
            "potsdamer platz": "Tiergarten",
            "alexander platz": "Mitte",
            "alexanderplatz": "Mitte", 
            "brandenburg gate": "Mitte",
            "museum island": "Mitte",
            "hackescher markt": "Mitte",
            "warschauer": "Friedrichshain",
            "boxhagener": "Friedrichshain",
            "simon-dach": "Friedrichshain",
            "bergmannkiez": "Kreuzberg",
            "graefekiez": "Kreuzberg", 
            "wrangelkiez": "Kreuzberg"
        }
    
    def _load_fallback_data(self):
        """加载备用静态数据"""
        self.location_cache = {
            'groups': {
                'Mitte': [
                    {'name': 'Mitte', 'listing_count': 500, 'avg_price': 85.0},
                    {'name': 'Tiergarten', 'listing_count': 200, 'avg_price': 90.0}
                ],
                'Friedrichshain-Kreuzberg': [
                    {'name': 'Kreuzberg', 'listing_count': 400, 'avg_price': 75.0},
                    {'name': 'Friedrichshain', 'listing_count': 350, 'avg_price': 70.0}
                ],
                'Pankow': [
                    {'name': 'Prenzlauer Berg', 'listing_count': 300, 'avg_price': 80.0}
                ]
            },
            'neighbourhood_to_group': {
                'Mitte': 'Mitte',
                'Tiergarten': 'Mitte',
                'Kreuzberg': 'Friedrichshain-Kreuzberg',
                'Friedrichshain': 'Friedrichshain-Kreuzberg',
                'Prenzlauer Berg': 'Pankow'
            },
            'popular_neighbourhoods': {
                'Mitte': ['Mitte', 'Tiergarten'],
                'Friedrichshain-Kreuzberg': ['Kreuzberg', 'Friedrichshain'],
                'Pankow': ['Prenzlauer Berg']
            },
            'neighbourhood_stats': {
                'Mitte': {'group': 'Mitte', 'listing_count': 500, 'avg_price': 85.0},
                'Tiergarten': {'group': 'Mitte', 'listing_count': 200, 'avg_price': 90.0},
                'Kreuzberg': {'group': 'Friedrichshain-Kreuzberg', 'listing_count': 400, 'avg_price': 75.0},
                'Friedrichshain': {'group': 'Friedrichshain-Kreuzberg', 'listing_count': 350, 'avg_price': 70.0},
                'Prenzlauer Berg': {'group': 'Pankow', 'listing_count': 300, 'avg_price': 80.0}
            },
            'group_aliases': self._get_group_aliases(),
            'neighbourhood_aliases': self._get_neighbourhood_aliases()
        }
        self.logger.info("✅ 已加载备用地区数据")
    
    def resolve_location(self, user_input: str) -> Dict[str, any]:
        """
        解析用户输入的地区信息
        
        Args:
            user_input: 用户提到的地区名称
            
        Returns:
            解析结果字典
        """
        user_input_lower = user_input.lower().strip()
        result = {
            'neighbourhood_group': None,
            'neighbourhood': None,
            'confidence': 'low',
            'suggestions': [],
            'stats': None
        }
        
        # 1. 尝试直接匹配群组别名
        for alias, group in self.location_cache['group_aliases'].items():
            if alias in user_input_lower:
                result['neighbourhood_group'] = group
                result['confidence'] = 'high'
                if group in self.location_cache['popular_neighbourhoods']:
                    result['suggestions'] = self.location_cache['popular_neighbourhoods'][group][:3]
                return result
        
        # 2. 尝试匹配社区别名
        for alias, neighbourhood in self.location_cache['neighbourhood_aliases'].items():
            if alias in user_input_lower:
                result['neighbourhood'] = neighbourhood
                result['neighbourhood_group'] = self.location_cache['neighbourhood_to_group'].get(neighbourhood)
                result['confidence'] = 'high'
                result['stats'] = self.location_cache['neighbourhood_stats'].get(neighbourhood)
                return result
        
        # 3. 精确匹配社区名
        for neighbourhood, group in self.location_cache['neighbourhood_to_group'].items():
            if neighbourhood.lower() == user_input_lower:
                result['neighbourhood'] = neighbourhood
                result['neighbourhood_group'] = group
                result['confidence'] = 'high'
                result['stats'] = self.location_cache['neighbourhood_stats'].get(neighbourhood)
                return result
        
        # 4. 模糊匹配社区名
        for neighbourhood, group in self.location_cache['neighbourhood_to_group'].items():
            if neighbourhood.lower() in user_input_lower or user_input_lower in neighbourhood.lower():
                result['neighbourhood'] = neighbourhood
                result['neighbourhood_group'] = group
                result['confidence'] = 'medium'
                result['stats'] = self.location_cache['neighbourhood_stats'].get(neighbourhood)
                return result
        
        # 5. 模糊匹配群组名
        for group in self.location_cache['groups'].keys():
            if any(part in user_input_lower for part in group.lower().split()):
                result['neighbourhood_group'] = group
                result['confidence'] = 'medium'
                if group in self.location_cache['popular_neighbourhoods']:
                    result['suggestions'] = self.location_cache['popular_neighbourhoods'][group][:3]
                return result
        
        # 6. 通用地区描述处理
        central_keywords = ['central', 'center', 'downtown', 'main', 'city center']
        if any(keyword in user_input_lower for keyword in central_keywords):
            result['neighbourhood_group'] = 'Mitte'
            result['confidence'] = 'medium'
            result['suggestions'] = ['Mitte', 'Tiergarten']
        
        return result
    
    def get_location_suggestions(self, partial_input: str, limit: int = 5) -> List[Dict]:
        """获取地区建议列表"""
        suggestions = []
        partial_lower = partial_input.lower()
        
        # 搜索群组
        for group in self.location_cache['groups'].keys():
            if partial_lower in group.lower():
                neighbourhood_count = len(self.location_cache['groups'][group])
                suggestions.append({
                    'type': 'group',
                    'name': group,
                    'display_name': f"{group} (District)",
                    'neighbourhood_count': neighbourhood_count
                })
        
        # 搜索社区
        for neighbourhood in self.location_cache['neighbourhood_to_group'].keys():
            if partial_lower in neighbourhood.lower():
                group = self.location_cache['neighbourhood_to_group'][neighbourhood]
                stats = self.location_cache['neighbourhood_stats'].get(neighbourhood, {})
                suggestions.append({
                    'type': 'neighbourhood',
                    'name': neighbourhood,
                    'display_name': f"{neighbourhood} ({group})",
                    'group': group,
                    'listing_count': stats.get('listing_count', 0),
                    'avg_price': stats.get('avg_price', 0)
                })
        
        # 按相关性排序（精确匹配优先）
        suggestions.sort(key=lambda x: (
            0 if partial_lower == x['name'].lower() else 1,  # 精确匹配优先
            -x.get('listing_count', 0)  # 房源数量倒序
        ))
        
        return suggestions[:limit]
    
    def get_neighbourhood_details(self, neighbourhood: str) -> Dict:
        """获取社区详细信息"""
        if neighbourhood not in self.location_cache['neighbourhood_stats']:
            return {}
        
        # 从数据库获取更详细的统计信息
        query = """
        SELECT 
            COUNT(*) as total_listings,
            AVG(price) as avg_price,
            MIN(price) as min_price,
            MAX(price) as max_price,
            AVG(minimum_nights) as avg_min_nights,
            AVG(availability_365) as avg_availability
        FROM listings 
        WHERE neighbourhood = :neighbourhood AND price > 0
        """
        
        df = self.execute_query(query, {'neighbourhood': neighbourhood})
        
        if df.empty:
            return self.location_cache['neighbourhood_stats'][neighbourhood]
        
        stats = df.iloc[0].to_dict()
        result = {
            'neighbourhood': neighbourhood,
            'neighbourhood_group': self.location_cache['neighbourhood_to_group'][neighbourhood],
            'total_listings': int(stats['total_listings']),
            'avg_price': round(stats['avg_price'], 2),
            'min_price': round(stats['min_price'], 2),
            'max_price': round(stats['max_price'], 2),
            'avg_min_nights': round(stats['avg_min_nights'], 1),
            'avg_availability': round(stats['avg_availability'], 1)
        }
        
        return result
    
    def search_listings_by_location(self, neighbourhood_group: str = None, 
                                   neighbourhood: str = None, 
                                   max_price: float = None,
                                   min_nights: int = None,
                                   limit: int = 20) -> pd.DataFrame:
        """
        根据地区搜索房源
        
        Args:
            neighbourhood_group: 地区群组
            neighbourhood: 具体社区
            max_price: 最大价格
            min_nights: 最少住宿天数
            limit: 返回结果数量限制
            
        Returns:
            pd.DataFrame: 搜索结果
        """
        # 构建WHERE条件
        conditions = ["price > 0"]
        params = {}
        
        if neighbourhood_group:
            conditions.append("neighbourhood_group = :neighbourhood_group")
            params['neighbourhood_group'] = neighbourhood_group
        
        if neighbourhood:
            conditions.append("neighbourhood = :neighbourhood")
            params['neighbourhood'] = neighbourhood
        
        if max_price:
            conditions.append("price <= :max_price")
            params['max_price'] = max_price
        
        if min_nights:
            conditions.append("minimum_nights >= :min_nights")
            params['min_nights'] = min_nights
        
        # 构建完整查询
        query = f"""
        SELECT 
            id,
            name,
            neighbourhood_group,
            neighbourhood,
            price,
            minimum_nights,
            availability_365,
            latitude,
            longitude
        FROM listings 
        WHERE {' AND '.join(conditions)}
        ORDER BY price ASC
        LIMIT :limit
        """
        
        params['limit'] = limit
        
        return self.execute_query(query, params)
    
    def validate_and_normalize_location(self, preferences: Dict) -> Dict:
        """验证和标准化地区偏好"""
        normalized = preferences.copy()
        
        # 处理用户输入的地区信息
        location_input = preferences.get('neighbourhood') or preferences.get('neighbourhood_group')
        if location_input:
            resolved = self.resolve_location(location_input)
            
            if resolved['neighbourhood_group']:
                normalized['neighbourhood_group'] = resolved['neighbourhood_group']
            
            if resolved['neighbourhood']:
                normalized['neighbourhood'] = resolved['neighbourhood']
            
            # 如果置信度低，添加到missing_dimensions
            if resolved['confidence'] == 'low':
                if 'missing_dimensions' not in normalized:
                    normalized['missing_dimensions'] = []
                normalized['missing_dimensions'].append(f"unclear_location: {location_input}")
                
                # 提供建议
                suggestions = self.get_location_suggestions(location_input)
                if suggestions:
                    normalized['location_suggestions'] = suggestions
        
        return normalized
    
    def get_group_overview(self) -> List[Dict]:
        """获取所有地区群组概览"""
        overview = []
        
        for group, neighbourhoods in self.location_cache['groups'].items():
            total_listings = sum(n['listing_count'] for n in neighbourhoods)
            avg_price = sum(n['avg_price'] * n['listing_count'] for n in neighbourhoods) / total_listings if total_listings > 0 else 0
            
            overview.append({
                'group_name': group,
                'neighbourhood_count': len(neighbourhoods),
                'total_listings': total_listings,
                'avg_price': round(avg_price, 2),
                'popular_neighbourhoods': self.location_cache['popular_neighbourhoods'].get(group, [])[:3]
            })
        
        # 按房源总数排序
        overview.sort(key=lambda x: x['total_listings'], reverse=True)
        return overview


# 数据库初始化和数据导入工具
class DataImporter:
    """数据导入工具类"""
    
    def __init__(self, location_manager: BerlinLocationManager):
        self.location_manager = location_manager
        self.logger = logging.getLogger(__name__)
    
    def import_csv_data(self, csv_file_path: str):
        """从CSV文件导入数据到数据库"""
        try:
            # 读取CSV文件
            df = pd.read_csv(csv_file_path)
            self.logger.info(f"📁 读取CSV文件: {len(df)} 条记录")
            
            # 数据清洗
            df = self._clean_data(df)
            
            # 导入到数据库
            df.to_sql(
                'listings', 
                self.location_manager.engine, 
                if_exists='replace',  # 替换现有表
                index=False,
                method='multi',
                chunksize=1000
            )
            
            self.logger.info(f"✅ 数据导入完成: {len(df)} 条记录")
            
            # 重新初始化地区缓存
            self.location_manager._initialize_location_data()
            
        except Exception as e:
            self.logger.error(f"❌ 数据导入失败: {e}")
            raise
    
    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗数据"""
        # 删除重复记录
        df = df.drop_duplicates(subset=['id'])
        
        # 处理缺失值
        df['neighbourhood_group'] = df['neighbourhood_group'].fillna('Unknown')
        df['neighbourhood'] = df['neighbourhood'].fillna('Unknown')
        
        # 处理价格数据
        df['price'] = pd.to_numeric(df['price'].astype(str).str.replace('$', '').str.replace(',', ''), errors='coerce')
        df = df[df['price'] > 0]  # 移除价格为0或无效的记录
        
        # 处理其他数值字段
        df['minimum_nights'] = pd.to_numeric(df['minimum_nights'], errors='coerce').fillna(1)
        df['availability_365'] = pd.to_numeric(df['availability_365'], errors='coerce').fillna(0)
        
        self.logger.info(f"🧹 数据清洗完成: 保留 {len(df)} 条有效记录")
        return df


# 使用示例和测试
def main():
    """主函数 - 展示完整工作流程"""
    
    # 1. 数据库配置
    db_config = {
        'host': 'localhost',
        'port': 3306,
        'user': 'airbnb_user',
        'password': '123456',
        'database': 'airbnb_db'
    }
    
    try:
        # 2. 初始化地区管理器
        print("🚀 初始化地区管理器...")
        manager = BerlinLocationManager(db_config)
        
        # 3. 可选：导入CSV数据（如果需要）
        # importer = DataImporter(manager)
        # importer.import_csv_data('path/to/airbnb_listings.csv')
        
        # 4. 测试地区解析功能
        print("\n🔍 测试地区解析功能:")
        test_inputs = [
            "mitte",
            "kreuzberg", 
            "central area",
            "prenzlauer berg",
            "near brandenburg gate",
            "friedrichshain"
        ]
        
        for location_input in test_inputs:
            print(f"\n输入: '{location_input}'")
            result = manager.resolve_location(location_input)
            print(f"解析结果: {result}")
            
            # 获取详细信息
            if result['neighbourhood']:
                details = manager.get_neighbourhood_details(result['neighbourhood'])
                print(f"社区详情: {details}")
        
        # 5. 获取地区概览
        print("\n📊 地区概览:")
        overview = manager.get_group_overview()
        for group_info in overview:
            print(f"{group_info['group_name']}: "
                  f"{group_info['total_listings']} 房源, "
                  f"平均价格 €{group_info['avg_price']}")
        
        # 6. 搜索房源示例
        print("\n🏠 搜索房源示例:")
        listings = manager.search_listings_by_location(
            neighbourhood_group='Mitte',
            max_price=100,
            limit=5
        )
        print(f"Mitte地区100欧以下房源: {len(listings)} 条")
        if not listings.empty:
            print(listings[['name', 'neighbourhood', 'price']].head())
        
    except Exception as e:
        print(f"❌ 系统初始化失败: {e}")


if __name__ == "__main__":
    main()