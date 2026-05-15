from pathlib import Path
from typing import Any, Dict, List

import aiosqlite

from .config import config
from .models import VerdictResponse


async def init_db() -> None:
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS verdicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                domain TEXT NOT NULL,
                final_verdict TEXT NOT NULL,
                fail_count INTEGER NOT NULL,
                source TEXT DEFAULT 'unknown',
                content_preview TEXT,
                full_response TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.commit()


async def save_verdict(verdict: VerdictResponse, source: str = "unknown", content: str = "") -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO verdicts
            (request_id, timestamp, domain, final_verdict, fail_count, source, content_preview, full_response)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                verdict.request_id,
                verdict.timestamp.isoformat(),
                verdict.domain.value,
                verdict.final_verdict.value,
                verdict.fail_count,
                source,
                content[:100],
                verdict.model_dump_json(),
            ),
        )
        await db.commit()


async def get_history(limit: int = 20) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM verdicts ORDER BY id DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
