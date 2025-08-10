
import pandas as pd
from sqlalchemy import create_engine
import os

# ✅ 连接你的数据库
db_url = "mysql+pymysql://airbnb_user:123456@localhost:3306/airbnb_db"
engine = create_engine(db_url)

# ✅ 动态获取当前脚本的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))

# ✅ 拼接 reviews.csv 的绝对路径
csv_path = os.path.join(current_dir, "reviews.csv")

# ✅ 读取 CSV
df = pd.read_csv(csv_path)
print("✅ Loaded reviews.csv with shape:", df.shape)

# ✅ 写入数据库
try:
    df.to_sql(name='reviews', con=engine, if_exists='replace', index=False)
    print("✅ Successfully imported reviews table into database.")
except Exception as e:
    print(f"❌ Failed to import: {e}")

