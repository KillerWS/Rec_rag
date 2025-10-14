# analytics_logger.py
from typing import Dict, Any, Tuple, Optional
from datetime import datetime
import json
from sqlalchemy import text
from db import db  # 使用你项目里初始化好的 SQLAlchemy 实例

# 核心五项事件的白名单（用于校验 & 映射）
CORE_EVENT_TYPES = {
    "preference_adjust",
    "visualization_trigger",
    "rag_query_local",
    "rag_query_global",
    "mode_switch",
}

# 前端 metrics 的 key 到事件名的映射
COUNT_MAPPING = {
    "preference_adjust_count":     "preference_adjust",
    "visualization_trigger_count": "visualization_trigger",
    "rag_query_local_count":       "rag_query_local",
    "rag_query_global_count":      "rag_query_global",
    "mode_switch_count":           "mode_switch",
}

# 与数据库列名一一对应（目前列名与前端 key 一致）
METRIC_COLUMNS = [
    "preference_adjust_count",
    "visualization_trigger_count",
    "rag_query_local_count",
    "rag_query_global_count",
]

# 需要落到独立列的新增会话指标
EXTRA_PERSIST_COLUMNS = [
    "task_completion_time",  # 秒数，非负整型
]

# 需要落到独立列的位置信息（为兼容现有库结构，镜像写入列与 context_json）
LOCATION_PERSIST_COLUMNS = [
    "location_interaction_seconds",
    "location_interaction_episodes",
]

TABLE_NAME = "interaction_events"

# —— 小工具：最小清洗 —— #
def _s(v: Any, max_len: int) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s[:max_len] if s else None

def _json(val: Any) -> str:
    """将对象/字符串稳妥转为 JSON 字符串（始终返回字符串）。"""
    if val is None:
        return "null"
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return json.dumps(parsed, ensure_ascii=False)
        except Exception:
            return json.dumps({"raw": val}, ensure_ascii=False)
    return json.dumps(val, ensure_ascii=False)

# —— 通用：读取现有列 —— #
def _get_existing_columns() -> set[str]:
    try:
        cols_sql = text(
            """
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table
            """
        )
        with db.engine.begin() as conn:
            return {row[0] for row in conn.execute(cols_sql, {"table": TABLE_NAME})}
    except Exception as e:
        print(f"⚠️ 读取 {TABLE_NAME} 列失败: {e}")
        return set()

# —— 确保交互事件表存在基础列（不包含 dimension/value/page/component） —— #
_BASE_COLUMN_DDL: Dict[str, str] = {
    "user_id": "VARCHAR(64) NULL",
    "session_id": "VARCHAR(128) NULL",
    "request_id": "VARCHAR(128) NULL",
    "context_json": "JSON NULL",
    "ip": "VARCHAR(45) NULL",
    "created_at": "DATETIME NULL",
}

def _ensure_base_columns_exist() -> None:
    try:
        existing_cols = _get_existing_columns()
        if not existing_cols:
            return
        with db.engine.begin() as conn:
            for col, ddl in _BASE_COLUMN_DDL.items():
                if col not in existing_cols:
                    try:
                        print(f"🛠️ 尝试添加缺失基础列: {col}")
                        conn.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {col} {ddl}"))
                        print(f"✅ 已添加基础列: {col}")
                    except Exception as e:
                        print(f"⚠️ 添加基础列 {col} 失败: {e}")
    except Exception as e:
        print(f"⚠️ 校验/添加基础列失败: {e}")

# —— 确保交互事件表存在指标列 —— #
def _ensure_metrics_columns_exist() -> None:
    try:
        existing_cols = _get_existing_columns()
        if not existing_cols:
            return
        with db.engine.begin() as conn:
            for col in [*METRIC_COLUMNS, *EXTRA_PERSIST_COLUMNS, *LOCATION_PERSIST_COLUMNS]:
                if col not in existing_cols:
                    try:
                        alter_sql = text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {col} INT NOT NULL DEFAULT 0")
                        print(f"🛠️ 尝试添加缺失列: {col}")
                        conn.execute(alter_sql)
                        print(f"✅ 已添加列: {col}")
                    except Exception as e:
                        print(f"⚠️ 添加计数列 {col} 失败: {e}")
    except Exception as e:
        print(f"⚠️ 校验/添加计数列失败: {e}")


def log_session_metrics(payload: Dict[str, Any]) -> Tuple[bool, str | Dict[str, Any]]:
    """
    接收前端聚合的会话级统计，写入 interaction_events：
      - 不再依赖/写入 event_type（兼容历史数据）
      - 四个核心计数写入独立列（preference_adjust_count、visualization_trigger_count、
        rag_query_local_count、rag_query_global_count），同时保留到 context_json.metrics 中
      - 额外会话指标 visualization_diversity、task_completion_time、total_turns、conversation_mode 仅写入
        context_json.metrics（不建独立列）
      - 位置交互：location_interaction_seconds、location_interaction_episodes 仅写入
        context_json.location_interaction（不建独立列）
      - 不使用 dimension/value/page/component 这四列
      - created_at 由后端生成（UTC -> 'YYYY-MM-DD HH:MM:SS'）
      - 幂等性：同一 session_id 的摘要行先删后写，后一次覆盖前一次
    实际写入列（存在即写）：
      user_id, session_id, request_id, context_json, ip, created_at,
      preference_adjust_count, visualization_trigger_count, rag_query_local_count,
      rag_query_global_count
    """
    print("📩 收到 metrics 提交请求: ", payload)

    if not isinstance(payload, dict):
        return False, "Payload must be a JSON object"

    session_id = _s(payload.get("session_id"), 128)
    if not session_id:
        return False, "session_id is required"

    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        return False, "metrics must be an object"

    # 公共字段（可选）
    user_id    = _s(payload.get("user_id"), 128)
    request_id = _s(payload.get("request_id"), 128)
    ip         = _s(payload.get("ip"), 64)

    # 解析四个核心计数：可转为 int 的项，<0 归零
    parsed_counts: Dict[str, int] = {}
    for metric_key in METRIC_COLUMNS:
        v = metrics.get(metric_key)
        try:
            n = int(v) if v is not None else 0
            parsed_counts[metric_key] = n if n >= 0 else 0
        except Exception:
            parsed_counts[metric_key] = 0

    # 解析仅入 context_json 的额外指标（若提供则镜像到 metrics 中，不占独立列）
    context_only_keys = [
        "visualization_diversity",
        "task_completion_time",
        "total_turns",
    ]
    extra_metrics: Dict[str, int] = {}
    for k in context_only_keys:
        candidate = metrics.get(k) if isinstance(metrics, dict) else None
        if candidate is None:
            candidate = payload.get(k)
        if candidate is None:
            continue
        try:
            n = int(candidate)
            extra_metrics[k] = n if n >= 0 else 0
        except Exception:
            # 忽略无法转为数字的值
            pass

    # 模式：conversation_mode（字符串类型，仅写入 context_json.metrics）
    conversation_mode: Optional[str] = None
    try:
        if isinstance(metrics, dict) and metrics.get("conversation_mode") is not None:
            conversation_mode = _s(metrics.get("conversation_mode"), 32)
        elif payload.get("conversation_mode") is not None:
            conversation_mode = _s(payload.get("conversation_mode"), 32)
    except Exception:
        conversation_mode = None

    # 位置交互聚合（若存在任意一项）
    loc_ctx: Dict[str, int] = {}
    if payload.get("location_interaction_seconds") is not None:
        try:
            n_sec = int(payload.get("location_interaction_seconds"))
            if n_sec >= 0:
                loc_ctx["location_interaction_seconds"] = n_sec
        except Exception:
            pass
    if payload.get("location_interaction_episodes") is not None:
        try:
            n_ep = int(payload.get("location_interaction_episodes"))
            if n_ep >= 0:
                loc_ctx["location_interaction_episodes"] = n_ep
        except Exception:
            pass

    # 若前端完全未提供任意一个指标键，且也没有位置信息，则拒绝写库
    has_any_metric_key = any(k in metrics for k in METRIC_COLUMNS)
    if not has_any_metric_key and not loc_ctx:
        return False, "No metric keys provided to insert"

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # 汇总上下文：metrics = 四个核心计数 + 额外会话指标（若提供）
    metrics_ctx: Dict[str, Any] = {**parsed_counts, **extra_metrics}
    if conversation_mode:
        metrics_ctx["conversation_mode"] = conversation_mode
    summary_ctx: Dict[str, Any] = {"metrics": metrics_ctx}
    if loc_ctx:
        summary_ctx["location_interaction"] = loc_ctx

    # 优先尝试补齐缺失列（不会阻断流程）
    _ensure_base_columns_exist()
    _ensure_metrics_columns_exist()

    # 动态检测可用列，构建 INSERT 字段集合
    existing_cols = _get_existing_columns()
    if not existing_cols:
        return False, "interaction_events table not found or no columns detected"
    include_event_type = "event_type" in existing_cols

    # 构建待写入的数据字典（不包含 dimension/value/page/component）
    base_row: Dict[str, Any] = {
        "user_id": user_id,
        "session_id": session_id,
        "request_id": request_id,
        "context_json": _json(summary_ctx),
        "ip": ip,
        "created_at": now_str,
    }
    # 兼容历史：若存在 event_type 非空约束，则写入固定值但逻辑上不使用
    if include_event_type:
        base_row["event_type"] = "core_event_summary"
    for c in METRIC_COLUMNS:
        base_row[c] = parsed_counts.get(c, 0)
    # 需要单独入列的额外指标
    for c in EXTRA_PERSIST_COLUMNS:
        base_row[c] = extra_metrics.get(c, 0)
    # 位置信息若需要镜像到列
    for c in LOCATION_PERSIST_COLUMNS:
        base_row[c] = loc_ctx.get(c, 0)

    # 仅选择当前表实际存在的列（不包含 dimension/value/page/component）
    preferred_order = [
        "user_id", "session_id", "request_id",
        *( ["event_type"] if include_event_type else [] ),
        "context_json", "ip", "created_at",
        *METRIC_COLUMNS,
        *EXTRA_PERSIST_COLUMNS,
        *LOCATION_PERSIST_COLUMNS,
    ]
    insert_cols = [c for c in preferred_order if c in existing_cols]

    # 不再依赖 event_type 列

    # 组装 INSERT SQL（不使用 CAST，兼容 TEXT/JSON）
    col_list = ", ".join(insert_cols)
    val_list = ", ".join([f":{c}" for c in insert_cols])
    insert_sql = text(f"INSERT INTO {TABLE_NAME} ({col_list}) VALUES ({val_list})")

    # 仅传递实际需要的参数
    row_params = {k: base_row.get(k) for k in insert_cols}

    try:
        with db.engine.begin() as conn:
            # 幂等删除（两步，尽量清理旧摘要行）：
            # 1) 若存在 event_type 列，先删除 legacy 的 core_event_summary
            if "session_id" in existing_cols and "event_type" in existing_cols:
                try:
                    conn.execute(
                        text(
                            f"DELETE FROM {TABLE_NAME} WHERE session_id = :sid AND event_type = 'core_event_summary'"
                        ),
                        {"sid": session_id},
                    )
                except Exception as e:
                    print(f"⚠️ 删除旧 core_event_summary 失败（忽略继续）: {e}")
            # 2) 再根据 JSON 指标键删除同 session_id 的摘要行
            if "session_id" in existing_cols and "context_json" in existing_cols:
                try:
                    delete_json_sql = text(
                        f"""
                        DELETE FROM {TABLE_NAME}
                        WHERE session_id = :sid
                          AND (
                            JSON_EXTRACT(context_json, '$.metrics.preference_adjust_count') IS NOT NULL OR
                            JSON_EXTRACT(context_json, '$.metrics.visualization_trigger_count') IS NOT NULL OR
                            JSON_EXTRACT(context_json, '$.metrics.rag_query_local_count') IS NOT NULL OR
                            JSON_EXTRACT(context_json, '$.metrics.rag_query_global_count') IS NOT NULL
                          )
                        """
                    )
                    conn.execute(delete_json_sql, {"sid": session_id})
                except Exception as e:
                    print(f"⚠️ 基于 JSON 的摘要删除失败（忽略继续）: {e}")
            conn.execute(insert_sql, [row_params])
        print(
            "✅ 成功写入 interaction_events 摘要: ",
            {k: row_params.get(k) for k in [
                "session_id",
                "preference_adjust_count",
                "visualization_trigger_count",
                "rag_query_local_count",
                "rag_query_global_count",
            ] if k in insert_cols}
        )
        return True, {
            "inserted": 1,
            "counts": {k: row_params.get(k, 0) for k in METRIC_COLUMNS if k in insert_cols},
            # 回显位置交互与关键会话指标（便于前端校验）
            "location_interaction": summary_ctx.get("location_interaction"),
            "metrics": metrics_ctx,
        }
    except Exception as e:
        print(f"❌ 写入 interaction_events 失败: {e}")
        return False, str(e)
