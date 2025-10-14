# analytics_schema.py
# 创建用于埋点的基础表结构 + 偏好调整次数视图
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

# =========================
# 数据库初始化（沿用你提供的逻辑）
# =========================
db = SQLAlchemy()

def init_db(app):
    """初始化数据库连接"""
    try:
        app.config["SQLALCHEMY_DATABASE_URI"] = (
            "mysql+pymysql://chris_001:9YNNhrN54Fqne0IF@mysql5.sqlpub.com:3310/chris_db_001"
        )
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
        # 避免时区混乱，统一使用UTC存储
        app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {"pool_pre_ping": True})
        db.init_app(app)
        print("✅ 数据库连接成功")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")

# =========================
# 表模型定义
# =========================
class InteractionEvent(db.Model):
    """
    通用交互事件表：
    - 通过 event_type 区分事件类型（preference_adjust / visualization_trigger / ...）
    - 事件上下文细节写入 context_json（JSON）
    - 为偏好事件预留了 dimension、value 这两个便捷字段（可为空）
      —— 这样“偏好调整次数”既能用 event_type=preference_adjust 统计，
      也能按维度/值做更细的分析，无需每次 JSON_EXTRACT。
    """
    __tablename__ = "interaction_events"
    __table_args__ = (
        # MySQL 存储引擎与字符集
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"},
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    # 可选标识：匿名用户可为空
    user_id = db.Column(db.String(64), index=True, nullable=True, comment="应用层用户ID（可空）")
    session_id = db.Column(db.String(128), index=True, nullable=True, comment="会话ID/前端生成")
    request_id = db.Column(db.String(128), index=True, nullable=True, comment="一次交互的请求ID（可空）")

    event_type = db.Column(db.String(64), index=True, nullable=False, comment="事件类型，如 preference_adjust")
    # 便捷字段（仅当 event_type=preference_adjust 时常用；其他事件可置空）
    dimension = db.Column(db.String(64), index=True, nullable=True, comment="偏好维度，如 budget/room_type")
    value = db.Column(db.String(255), nullable=True, comment="偏好取值，如 80-100/Entire home 等")

    # 通用上下文字段，兼容所有事件的扩展信息（推荐前端/后端都传）
    context_json = db.Column(db.JSON, nullable=True, comment="原始上下文JSON（含触发位置、更多参数）")

    # 独立计数列（便于直接 SQL 统计）
    preference_adjust_count     = db.Column(db.Integer, nullable=False, default=0, server_default="0", comment="偏好调整次数")
    visualization_trigger_count = db.Column(db.Integer, nullable=False, default=0, server_default="0", comment="触发可视化次数")
    rag_query_local_count       = db.Column(db.Integer, nullable=False, default=0, server_default="0", comment="本地RAG查询次数")
    rag_query_global_count      = db.Column(db.Integer, nullable=False, default=0, server_default="0", comment="全局RAG查询次数")
    mode_switch_count           = db.Column(db.Integer, nullable=False, default=0, server_default="0", comment="模式切换次数")

    # 可选元数据：页面/组件/IP等
    page = db.Column(db.String(128), nullable=True)
    component = db.Column(db.String(128), nullable=True)
    ip = db.Column(db.String(45), nullable=True)  # 兼容IPv6

    # 时间字段：统一用UTC
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )

# =========================
# 视图定义（便于直接统计偏好调整次数）
# =========================
CREATE_PREF_ADJUST_VIEW_SQL = """
CREATE OR REPLACE VIEW vw_preference_adjust_count AS
SELECT
  COALESCE(user_id, 'anonymous') AS user_id,
  COALESCE(session_id, '')       AS session_id,
  DATE(created_at)               AS event_date,
  COUNT(*)                       AS adjust_count
FROM interaction_events
WHERE event_type = 'preference_adjust'
GROUP BY COALESCE(user_id, 'anonymous'), COALESCE(session_id, ''), DATE(created_at);
"""

# =========================
# 初始化入口
# =========================
def create_schema(app: Flask):
    with app.app_context():
        try:
            print("🚧 正在创建表结构 ...")
            db.create_all()
            print("✅ 表结构创建完成：interaction_events")

            # 创建或更新视图
            with db.engine.begin() as conn:
                conn.execute(text(CREATE_PREF_ADJUST_VIEW_SQL))
            print("✅ 视图创建完成：vw_preference_adjust_count")
        except SQLAlchemyError as e:
            print(f"❌ 初始化失败：{e}")

if __name__ == "__main__":
    app = Flask(__name__)
    init_db(app)
    create_schema(app)
    print("🎉 初始化完成")
