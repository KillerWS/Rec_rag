# waitress-serve --listen=0.0.0.0:5000 server:app
from flask import Flask
from flask_cors import CORS
import os
from dotenv import load_dotenv

# 加载环境变量，从.env文件或系统环境变量
load_dotenv()  # 这会从项目根目录的.env文件加载环境变量

# 检查必要的环境变量（不再写入默认值）
if "GOOGLE_API_KEY" not in os.environ:
    print("⚠️ 未检测到 GOOGLE_API_KEY，请在项目根目录 .env 中设置 GOOGLE_API_KEY=YOUR_KEY")

from db import init_db
from load_llm import load_llm
from aggregation import register_aggregation_functions
from api.routes import api
# from api.visualization_api import visualization_bp
# from load_embedding_model import load_embeddings
from load_embedding_model_api import load_embeddings

app = Flask(__name__)
CORS(app)  # 允许跨域访问

# 🔹 初始化数据库
init_db(app)

# 🔹 load llm module !!!
load_llm()

# 🔹 load embedding module!!!
load_embeddings()

# 🔹 注册聚合函数（SQL 查询）
register_aggregation_functions()

# 🔹 注册 API 端点
app.register_blueprint(api, url_prefix='/api')

# app.register_blueprint(visualization_bp, url_prefix='/visualization_bp')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
