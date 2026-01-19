from typing import Dict, Any, Optional, Tuple, Iterable
from datetime import datetime
from sqlalchemy import text
from db import db

TABLE_NAME = "study_sessions"


def _now_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _ensure_table_exists() -> None:
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
        session_id VARCHAR(128) PRIMARY KEY,
        group_id INT NULL,
        block_index INT NOT NULL DEFAULT 0,
        created_at DATETIME NULL,
        updated_at DATETIME NULL
    )
    """
    try:
        with db.engine.begin() as conn:
            conn.execute(text(create_sql))
    except Exception as e:
        print(f"⚠️ 创建/检查 {TABLE_NAME} 表失败: {e}")


def create_session(session_id: str, group_id: int, block_index: int = 0) -> Tuple[bool, Optional[str]]:
    _ensure_table_exists()
    now_str = _now_str()
    try:
        with db.engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {TABLE_NAME} (session_id, group_id, block_index, created_at, updated_at)
                    VALUES (:session_id, :group_id, :block_index, :created_at, :updated_at)
                    """
                ),
                {
                    "session_id": session_id,
                    "group_id": group_id,
                    "block_index": block_index,
                    "created_at": now_str,
                    "updated_at": now_str,
                },
            )
        print(f"✅ study_sessions inserted session_id={session_id} group_id={group_id} block_index={block_index}")
        return True, None
    except Exception as e:
        print(f"❌ 创建会话失败: {e}")
        return False, str(e)


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    _ensure_table_exists()
    try:
        with db.engine.begin() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT session_id, group_id, block_index, created_at, updated_at
                    FROM {TABLE_NAME}
                    WHERE session_id = :session_id
                    """
                ),
                {"session_id": session_id},
            ).fetchone()
        if not row:
            print(f"⚠️ study_sessions not found session_id={session_id}")
            return None
        return {
            "session_id": row[0],
            "group_id": row[1],
            "block_index": row[2],
            "created_at": row[3],
            "updated_at": row[4],
        }
    except Exception as e:
        print(f"❌ 读取会话失败: {e}")
        return None


def increment_block(session_id: str, max_block: int = 4) -> Optional[Dict[str, Any]]:
    _ensure_table_exists()
    now_str = _now_str()
    try:
        with db.engine.begin() as conn:
            result = conn.execute(
                text(
                    f"""
                    UPDATE {TABLE_NAME}
                    SET block_index = LEAST(block_index + 1, :max_block),
                        updated_at = :updated_at
                    WHERE session_id = :session_id
                    """
                ),
                {
                    "session_id": session_id,
                    "max_block": max_block,
                    "updated_at": now_str,
                },
            )
            if result.rowcount == 0:
                print(f"⚠️ study_sessions update miss session_id={session_id}")
                return None
            row = conn.execute(
                text(
                    f"""
                    SELECT session_id, group_id, block_index, created_at, updated_at
                    FROM {TABLE_NAME}
                    WHERE session_id = :session_id
                    """
                ),
                {"session_id": session_id},
            ).fetchone()
        if not row:
            return None
        return {
            "session_id": row[0],
            "group_id": row[1],
            "block_index": row[2],
            "created_at": row[3],
            "updated_at": row[4],
        }
    except Exception as e:
        print(f"❌ 更新 block_index 失败: {e}")
        return None


def get_group_counts(group_ids: Iterable[int]) -> Dict[int, int]:
    _ensure_table_exists()
    counts: Dict[int, int] = {int(gid): 0 for gid in group_ids}
    try:
        with db.engine.begin() as conn:
            rows = conn.execute(
                text(
                    f"""
                    SELECT group_id, COUNT(*) AS cnt
                    FROM {TABLE_NAME}
                    WHERE group_id IS NOT NULL
                    GROUP BY group_id
                    """
                )
            ).fetchall()
        for row in rows:
            gid = int(row[0])
            if gid in counts:
                counts[gid] = int(row[1])
        return counts
    except Exception as e:
        print(f"⚠️ 读取组计数失败: {e}")
        return counts
