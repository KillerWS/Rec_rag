# -*- coding: utf-8 -*-
"""
analytics_logger.py
===================
前端在会话结束（例如“确认推荐”）时，将**会话级**统计一次性提交。
本模块负责：
1) 校验 payload（字段齐全、类型正确、非负等）
2) 确保表存在：session_metrics
3) 幂等 Upsert：同一 session_id 多次提交会覆盖

📊 核心指标（Minimal set）
------------------------------------------------
- preference_adjust_count        (RQ2)
- visualization_trigger_count    (RQ1/RQ3)
- rag_query_local_count          (RQ1/RQ3)
- rag_query_global_count         (RQ1/RQ3)
- mode_switch_count              (RQ1/RQ2)

🌍 Location 维度（简化）
------------------------------------------------
- location_interaction_seconds   (extra_json)
- location_interaction_episodes  (extra_json)

🧩 实验元信息（extra_json）
------------------------------------------------
- mode: "agent" | "scripted"
- script_id: 脚本版本（脚本式）
- planned:   {五项 planned 值}
- actual:    {五项 actual 值}
- adherence: {五项 actual/planned 或 null}
- 任意扩展键（模型版本、A/B组、task_success 等）

使用方式：
- 应用启动后调用一次 ensure_session_metrics_table(db)
- 接口中调用 validate_and_commit_session_metrics(db, payload)
"""

from __future__ import annotations
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy import text
import json
import re

# --------- 指标口径 & 允许的取值 ---------
INDICATOR_KEYS = [
    "preference_adjust_count",
    "visualization_trigger_count",
    "rag_query_local_count",
    "rag_query_global_count",
    "mode_switch_count",
]

ALLOWED_MODES = {"agent", "scripted"}

# --------- DDL：会话级汇总表 ---------
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS session_metrics (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(64) NULL,
    session_id VARCHAR(128) NOT NULL UNIQUE,

    started_at DATETIME NULL,
    ended_at   DATETIME NULL,

    -- 五项最小必要集指标（会话级实际值）
    preference_adjust_count INT NOT NULL DEFAULT 0,
    visualization_trigger_count INT NOT NULL DEFAULT 0,
    rag_query_local_count INT NOT NULL DEFAULT 0,
    rag_query_global_count INT NOT NULL DEFAULT 0,
    mode_switch_count INT NOT NULL DEFAULT 0,

    -- 附加信息（JSON）：mode/script_id/planned/actual/adherence/location 时长等
    extra_json JSON NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

# =======================
# 公共：确保表存在
# =======================
def ensure_session_metrics_table(db) -> bool:
    """应用启动时调用一次，保证 session_metrics 表存在。"""
    with db.engine.begin() as conn:
        conn.execute(text(CREATE_TABLE_SQL))
    return True

# =======================
# 工具：数据规整/校验
# =======================
def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    """允许 ISO8601 字符串；传 None/空返回 None。"""
    if not s or not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def _int_or_zero(x) -> int:
    try:
        v = int(x)
        return max(0, v)  # 非负约束
    except Exception:
        return 0

def _sanitize_metrics(d: Optional[Dict[str, Any]]) -> Dict[str, int]:
    d = d or {}
    out = {}
    for k in INDICATOR_KEYS:
        out[k] = _int_or_zero(d.get(k, 0))
    return out

def _compute_adherence(planned: Optional[Dict[str, int]], actual: Dict[str, int]) -> Optional[Dict[str, Optional[float]]]:
    """adherence = actual/planned，仅对 planned>0 计算，否则 None。"""
    if planned is None:
        return None
    res = {}
    for k in INDICATOR_KEYS:
        p = _int_or_zero(planned.get(k))
        a = _int_or_zero(actual.get(k))
        res[k] = round(a / float(p), 2) if p > 0 else None
    return res

def _json_len_ok(obj: Dict[str, Any], max_bytes: int = 512 * 1024) -> bool:
    """限制 extra_json 体积，默认 512KB（充足）。"""
    try:
        s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        return len(s.encode("utf-8")) <= max_bytes
    except Exception:
        return False

def _merge_shallow(old: Optional[Dict[str, Any]], new: Dict[str, Any]) -> Dict[str, Any]:
    """浅合并 JSON：新值覆盖同名键。"""
    if old is None:
        return new
    m = dict(old)
    m.update(new)
    return m

def _err(msg: str, field: Optional[str] = None) -> Tuple[bool, Dict[str, Any]]:
    return False, {"ok": False, "error": msg, "field": field}

# =======================
# 主入口：校验 + Upsert
# =======================
def validate_and_commit_session_metrics(db, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    """
    👇 你在路由里直接调用这个函数即可。
    1) 校验必填/类型/范围
    2) 计算 adherence、组装 extra_json
    3) 幂等 Upsert 到 session_metrics

    需要的 payload 结构（示例见 routes.py）：
    {
      "session_id": "...",                   # 必填
      "user_id": "P007",                     # 可选
      "mode": "agent" | "scripted",          # 可选，建议传
      "script_id": "baseline_v1",            # 脚本式才传
      "metrics": { ... },                    # 五项 actual，缺省补0
      "planned": { ... },                    # 脚本式 baseline 可选
      "location_interaction_seconds": 46,    # 可选
      "location_interaction_episodes": 2,    # 可选
      "started_at": "2025-08-14T12:00:12Z",  # 可选
      "ended_at": "2025-08-14T12:03:02Z",    # 可选
      "extra_json": { ... }                  # 可选，透传
    }
    """
    if not isinstance(payload, dict):
        return _err("payload 必须是 JSON 对象", "payload")

    # --- 基本字段 ---
    session_id = payload.get("session_id")
    if not session_id or not isinstance(session_id, str):
        return _err("session_id 不能为空且必须为字符串", "session_id")
    if len(session_id) > 128:
        return _err("session_id 过长（<=128）", "session_id")

    user_id = payload.get("user_id")
    if user_id is not None:
        if not isinstance(user_id, str):
            return _err("user_id 必须为字符串", "user_id")
        if len(user_id) > 64:
            return _err("user_id 过长（<=64）", "user_id")

    mode = payload.get("mode")
    if mode is not None:
        if not isinstance(mode, str) or mode.lower() not in ALLOWED_MODES:
            return _err("mode 仅允许 'agent' 或 'scripted'", "mode")
        mode = mode.lower()

    script_id = payload.get("script_id")
    if script_id is not None:
        if not isinstance(script_id, str):
            return _err("script_id 必须为字符串", "script_id")
        if len(script_id) > 64:
            return _err("script_id 过长（<=64）", "script_id")
        # 可选：脚本版本简单校验
        if not re.match(r"^[A-Za-z0-9_\-\.]+$", script_id):
            return _err("script_id 仅允许字母数字、_ - .", "script_id")

    # --- 指标 ---
    actual = _sanitize_metrics(payload.get("metrics"))
    planned = _sanitize_metrics(payload.get("planned")) if payload.get("planned") is not None else None
    adherence = _compute_adherence(planned, actual)

    # --- 时间 ---
    started_at = _parse_dt(payload.get("started_at"))
    ended_at = _parse_dt(payload.get("ended_at")) or datetime.utcnow()
    if started_at and ended_at and ended_at < started_at:
        return _err("ended_at 不能早于 started_at", "ended_at")

    # --- Location 简化指标 ---
    loc_secs = payload.get("location_interaction_seconds")
    if loc_secs is not None:
        loc_secs = _int_or_zero(loc_secs)
    loc_eps = payload.get("location_interaction_episodes")
    if loc_eps is not None:
        loc_eps = _int_or_zero(loc_eps)

    # --- 透传 extra_json 合并 ---
    extra_json = payload.get("extra_json") or {}
    if not isinstance(extra_json, dict):
        return _err("extra_json 必须为对象", "extra_json")

    # 组装新的 extra 片段
    extra_new = dict(extra_json)
    if mode:
        extra_new["mode"] = mode
    if script_id:
        extra_new["script_id"] = script_id
    if planned is not None:
        extra_new["planned"] = planned
    extra_new["actual"] = actual
    if adherence is not None:
        extra_new["adherence"] = adherence
    if loc_secs is not None:
        extra_new["location_interaction_seconds"] = loc_secs
    if loc_eps is not None:
        extra_new["location_interaction_episodes"] = loc_eps

    if not _json_len_ok(extra_new):
        return _err("extra_json 体积过大（>512KB）", "extra_json")

    # --- 幂等 Upsert ---
    with db.engine.begin() as conn:
        row = conn.execute(
            text("SELECT id, extra_json FROM session_metrics WHERE session_id = :sid"),
            {"sid": session_id},
        ).fetchone()

        if row is None:
            # INSERT
            sql = text(
                """
                INSERT INTO session_metrics
                (user_id, session_id, started_at, ended_at,
                 preference_adjust_count, visualization_trigger_count,
                 rag_query_local_count, rag_query_global_count, mode_switch_count,
                 extra_json)
                VALUES
                (:user_id, :session_id, :started_at, :ended_at,
                 :pref, :viz, :rag_local, :rag_global, :mode_sw,
                 CAST(:extra_json AS JSON))
                """
            )
            conn.execute(
                sql,
                dict(
                    user_id=user_id,
                    session_id=session_id,
                    started_at=started_at,
                    ended_at=ended_at,
                    pref=actual["preference_adjust_count"],
                    viz=actual["visualization_trigger_count"],
                    rag_local=actual["rag_query_local_count"],
                    rag_global=actual["rag_query_global_count"],
                    mode_sw=actual["mode_switch_count"],
                    extra_json=json.dumps(extra_new, ensure_ascii=False, separators=(",", ":")),
                ),
            )
        else:
            # UPDATE：合并历史 extra_json
            old_extra = row[1] if isinstance(row[1], dict) else None
            merged = _merge_shallow(old_extra, extra_new)
            if not _json_len_ok(merged):
                return _err("合并后的 extra_json 体积过大（>512KB）", "extra_json")

            sql = text(
                """
                UPDATE session_metrics
                SET user_id = COALESCE(:user_id, user_id),
                    started_at = COALESCE(:started_at, started_at),
                    ended_at = COALESCE(:ended_at, ended_at),
                    preference_adjust_count = :pref,
                    visualization_trigger_count = :viz,
                    rag_query_local_count = :rag_local,
                    rag_query_global_count = :rag_global,
                    mode_switch_count = :mode_sw,
                    extra_json = CAST(:extra_json AS JSON)
                WHERE session_id = :session_id
                """
            )
            conn.execute(
                sql,
                dict(
                    user_id=user_id,
                    session_id=session_id,
                    started_at=started_at,
                    ended_at=ended_at,
                    pref=actual["preference_adjust_count"],
                    viz=actual["visualization_trigger_count"],
                    rag_local=actual["rag_query_local_count"],
                    rag_global=actual["rag_query_global_count"],
                    mode_sw=actual["mode_switch_count"],
                    extra_json=json.dumps(merged, ensure_ascii=False, separators=(",", ":")),
                ),
            )

    return True, {
        "ok": True,
        "session_id": session_id,
        "user_id": user_id,
        "mode": mode,
        "script_id": script_id,
        "committed": {
            **actual,
            "location_interaction_seconds": loc_secs,
            "location_interaction_episodes": loc_eps,
        },
    }
