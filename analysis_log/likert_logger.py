from typing import Dict, Any, Tuple, Optional
from datetime import datetime
import json
from sqlalchemy import text
from db import db

TABLE_NAME = "interaction_events"

# 基础列定义（与 analytics_logger 一致）
_BASE_COLUMN_DDL: Dict[str, str] = {
    "user_id": "VARCHAR(64) NULL",
    "session_id": "VARCHAR(128) NULL",
    "request_id": "VARCHAR(128) NULL",
    "event_type": "VARCHAR(64) NOT NULL",
    "context_json": "JSON NULL",
    "ip": "VARCHAR(45) NULL",
    "created_at": "DATETIME NULL",
}

# Likert 需要的两列：提交来源 + 14题答案列表（JSON）
_LIKERT_COLUMN_DDL: Dict[str, str] = {
    "likert_source": "VARCHAR(32) NULL",   # 'baseline' | 'agent' | 其他
    "likert_answers": "JSON NULL",         # [int,int,...] 长度=14，取值 1~5
    "block_index": "INT NULL",             # 任务块索引
    "likert_avg_score": "DOUBLE NULL",     # 平均分
    "likert_answer_count": "INT NULL",     # 答题数量
}

# 允许的评分范围
_MIN_SCORE = 1
_MAX_SCORE = 5


def _s(v: Any, max_len: int) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s[:max_len] if s else None


def _json(val: Any) -> str:
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


def _to_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except Exception:
        return None


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


def _ensure_likert_columns_exist() -> None:
    try:
        existing_cols = _get_existing_columns()
        if not existing_cols:
            return
        with db.engine.begin() as conn:
            for col, ddl in _LIKERT_COLUMN_DDL.items():
                if col not in existing_cols:
                    try:
                        print(f"🛠️ 尝试添加 Likert 列: {col}")
                        conn.execute(text(f"ALTER TABLE {TABLE_NAME} ADD COLUMN {col} {ddl}"))
                        print(f"✅ 已添加 Likert 列: {col}")
                    except Exception as e:
                        print(f"⚠️ 添加 Likert 列 {col} 失败: {e}")
    except Exception as e:
        print(f"⚠️ 校验/添加 Likert 列失败: {e}")


def _normalize_answers_to_list(answers: Any) -> Optional[list[int]]:
    """将传入的 answers 规范化为 1..5 的整数列表（长度 >= 1）。
    支持两种输入：
      - list: 元素可转 int 且在 1..5 范围内
      - dict: 提取所有值，按 key 排序或原样遍历（不保证顺序），仅保留 1..5 的有效值
    返回 None 表示无效。
    """
    # list 情况
    if isinstance(answers, (list, tuple)):
        try:
            vals = [int(x) for x in answers]
        except Exception:
            return None
        for n in vals:
            if n < _MIN_SCORE or n > _MAX_SCORE:
                return None
        return list(vals) if len(vals) > 0 else None

    # dict 情况
    if isinstance(answers, dict):
        # 优先尝试按 key 排序（若 key 可比较）
        try:
            items = sorted(answers.items(), key=lambda kv: str(kv[0]))
        except Exception:
            items = list(answers.items())
        vals: list[int] = []
        for _, v in items:
            try:
                n = int(v)
                if _MIN_SCORE <= n <= _MAX_SCORE:
                    vals.append(n)
            except Exception:
                continue
        return vals if len(vals) > 0 else None

    return None


def log_likert_feedback(payload: Dict[str, Any]) -> Tuple[bool, str | Dict[str, Any]]:
    """
    写入 14 题 5-Likert 问卷结果到 interaction_events：
      - event_type 固定 'likert_feedback'
      - 仅新增两列：
          likert_source   VARCHAR(32)  —— 提交来源：'baseline' | 'agent' | 其他
          likert_answers  JSON         —— 长度=14 的 1..5 列表
      - 仍在 context_json 中保留镜像（可选）以便兼容其他分析

    期望前端 payload（建议使用 list 传 answers）：
    {
      "session_id": str,                 # required
      "answers": [1,2,3,...14项],        # required list[int] 长度=14, 取值 1..5
      "mode": "baseline"|"agent",        # optional, 提交来源
      "block_index": 0,                  # optional, 当前任务块索引
      "user_id": str,                    # optional
      "request_id": str,                 # optional
      "ip": str,                         # optional
      "extra": { ... }                   # optional
    }
    """
    if not isinstance(payload, dict):
        return False, "Payload must be a JSON object"

    session_id = _s(payload.get("session_id"), 128)
    if not session_id:
        return False, "session_id is required"

    answers_raw = payload.get("answers")
    answers_list = _normalize_answers_to_list(answers_raw)
    if not answers_list:
        return False, "answers must be a list/dict of 1..5 scores"

    # 公共字段
    user_id    = _s(payload.get("user_id"), 128)
    request_id = _s(payload.get("request_id"), 128)
    ip         = _s(payload.get("ip"), 64)
    mode       = _s(payload.get("mode"), 32)
    block_index = _to_int(payload.get("block_index"))
    answers_count = len(answers_list)
    avg_score = round(sum(answers_list) / answers_count, 4) if answers_count else None

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    # 确保列
    _ensure_base_columns_exist()
    _ensure_likert_columns_exist()

    existing_cols = _get_existing_columns()
    if not existing_cols:
        return False, "interaction_events table not found or no columns detected"

    # context_json（可选镜像）
    ctx: Dict[str, Any] = {
        "likert": {
            "answers": answers_raw if isinstance(answers_raw, dict) else answers_list,
            "mode": mode,
            "block_index": block_index,
            "summary": {
                "avg_score": avg_score,
                "answer_count": answers_count,
            },
        }
    }
    extra = payload.get("extra")
    if extra is not None:
        ctx["extra"] = extra

    base_row: Dict[str, Any] = {
        "user_id": user_id,
        "session_id": session_id,
        "request_id": request_id,
        "event_type": "likert_feedback",
        "context_json": _json(ctx),
        "ip": ip,
        "created_at": now_str,
    }

    # 专用列
    if "likert_source" in existing_cols:
        base_row["likert_source"] = mode
    if "likert_answers" in existing_cols:
        answers_payload = answers_raw if isinstance(answers_raw, (dict, list)) else answers_list
        base_row["likert_answers"] = _json(answers_payload)
    if "block_index" in existing_cols:
        base_row["block_index"] = block_index
    if "likert_avg_score" in existing_cols:
        base_row["likert_avg_score"] = avg_score
    if "likert_answer_count" in existing_cols:
        base_row["likert_answer_count"] = answers_count

    preferred_order = [
        "user_id", "session_id", "request_id", "event_type",
        "context_json", "ip", "created_at",
        "likert_source", "likert_answers", "block_index",
        "likert_avg_score", "likert_answer_count",
    ]
    insert_cols = [c for c in preferred_order if c in existing_cols]

    if "event_type" not in insert_cols:
        return False, "interaction_events table missing required column: event_type"

    col_list = ", ".join(insert_cols)
    # 特殊处理 likert_answers：使用 CAST(:likert_answers AS JSON) 强制以 JSON 写入
    placeholders = []
    for c in insert_cols:
        if c == "likert_answers":
            placeholders.append("CAST(:likert_answers AS JSON)")
        else:
            placeholders.append(f":{c}")
    val_list = ", ".join(placeholders)

    sql = text(f"INSERT INTO {TABLE_NAME} ({col_list}) VALUES ({val_list})")

    params = {k: base_row.get(k) for k in insert_cols}

    try:
        with db.engine.begin() as conn:
            result = conn.execute(sql, params)
            try:
                inserted_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            except Exception:
                inserted_id = None
            answers_len = None
            if inserted_id is not None:
                try:
                    row = conn.execute(
                        text(f"SELECT id, session_id, JSON_LENGTH(likert_answers) AS answers_len FROM {TABLE_NAME} WHERE id = :id"),
                        {"id": inserted_id}
                    ).fetchone()
                    if row is not None:
                        answers_len = row[2]
                except Exception as _e:
                    answers_len = None
        print("✅ 已写入 Likert 反馈(14题)", {
            "session_id": session_id,
            "mode": mode,
            "insert_id": inserted_id,
            "answers_len": answers_len,
        })
        return True, {
            "inserted": 1,
            "event_types": ["likert_feedback"],
        }
    except Exception as e:
        print(f"❌ 写入 Likert 反馈失败: {e}")
        return False, str(e) 