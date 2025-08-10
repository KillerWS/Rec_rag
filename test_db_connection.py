from flask import Flask
from db import init_db, test_db_connection

# 创建一个简单的 Flask 应用
app = Flask(__name__)

# 初始化数据库连接
init_db(app)

# 在应用上下文中测试连接
with app.app_context():
    test_db_connection()

print("测试完成") 