"""SQLite persistence for local crawl and compliance-review results."""

from __future__ import annotations

from datetime import datetime
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any

from app.keyword_matcher import normalize_for_cache
from app.models import ScrapeTask


def data_directory() -> Path:
    override = os.environ.get("LIORAN_DATA_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "Lioran"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Lioran"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "Lioran"


def database_path() -> Path:
    return data_directory() / "lioran.sqlite3"


def _connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS scrape_tasks (
            task_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            review_enabled INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS review_items (
            review_id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL REFERENCES scrape_tasks(task_id) ON DELETE CASCADE,
            ordinal INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS review_items_task_idx ON review_items(task_id, ordinal)"
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS review_extraction_cache (
            intent_key TEXT NOT NULL,
            text_key TEXT NOT NULL,
            title_key TEXT NOT NULL,
            normalized_text TEXT NOT NULL,
            extraction_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (intent_key, text_key)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS review_extraction_cache_intent_idx
        ON review_extraction_cache(intent_key, created_at DESC)
        """
    )
    return connection


@contextmanager
def _database():
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _task_payload(task: ScrapeTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "url": task.url,
        "requirement": task.requirement,
        "columns": task.columns,
        "rows": task.rows,
        "schema": task.schema,
        "created_at": task.created_at.isoformat(),
        "feedback_row_index": task.feedback_row_index,
        "review_enabled": task.review_enabled,
        "review_time": task.review_time,
        "deep_review": task.deep_review,
        "review_summary": task.review_summary,
        "review_records": task.review_records,
    }


def _task_from_payload(payload: dict[str, Any]) -> ScrapeTask:
    return ScrapeTask(
        task_id=payload["task_id"],
        url=payload["url"],
        requirement=payload["requirement"],
        columns=payload["columns"],
        rows=payload["rows"],
        schema=payload["schema"],
        created_at=datetime.fromisoformat(payload["created_at"]),
        feedback_row_index=payload.get("feedback_row_index"),
        review_enabled=bool(payload.get("review_enabled", False)),
        review_time=bool(payload.get("review_time", False)),
        deep_review=bool(payload.get("deep_review", False)),
        review_summary=payload.get("review_summary") or {},
        review_records=payload.get("review_records") or [],
    )


def save_task(task: ScrapeTask) -> None:
    payload = _task_payload(task)
    with _database() as connection:
        connection.execute(
            """
            INSERT INTO scrape_tasks(task_id, created_at, review_enabled, payload_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                created_at = excluded.created_at,
                review_enabled = excluded.review_enabled,
                payload_json = excluded.payload_json
            """,
            (
                task.task_id,
                task.created_at.isoformat(),
                int(task.review_enabled),
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        connection.execute("DELETE FROM review_items WHERE task_id = ?", (task.task_id,))
        connection.executemany(
            """
            INSERT INTO review_items(review_id, task_id, ordinal, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    str(item["review_id"]),
                    task.task_id,
                    index,
                    json.dumps(item, ensure_ascii=False),
                )
                for index, item in enumerate(task.review_records)
                if item.get("review_id")
            ],
        )


def load_task(task_id: str) -> ScrapeTask | None:
    with _database() as connection:
        row = connection.execute(
            "SELECT payload_json FROM scrape_tasks WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        task = _task_from_payload(json.loads(row["payload_json"]))
        if task.review_enabled:
            rows = connection.execute(
                "SELECT payload_json FROM review_items WHERE task_id = ? ORDER BY ordinal",
                (task_id,),
            ).fetchall()
            task.review_records = [json.loads(item["payload_json"]) for item in rows]
        return task


def list_review_tasks(limit: int = 20) -> list[dict[str, Any]]:
    with _database() as connection:
        rows = connection.execute(
            """
            SELECT task_id, created_at, payload_json
            FROM scrape_tasks
            WHERE review_enabled = 1
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    tasks = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        tasks.append({
            "task_id": row["task_id"],
            "created_at": row["created_at"],
            "url": payload["url"],
            "summary": payload.get("review_summary") or {},
            "total": len(payload.get("review_records") or []),
        })
    return tasks


def list_review_items(task_id: str) -> list[dict[str, Any]]:
    with _database() as connection:
        rows = connection.execute(
            "SELECT payload_json FROM review_items WHERE task_id = ? ORDER BY ordinal",
            (task_id,),
        ).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def update_review_item(review_id: str, decision: str, note: str) -> dict[str, Any] | None:
    status_labels = {
        "included": "人工确认保留",
        "excluded": "人工确认排除",
        "future": "待生效",
        "manual_review": "待人工复核",
    }
    with _database() as connection:
        row = connection.execute(
            "SELECT task_id, payload_json FROM review_items WHERE review_id = ?",
            (review_id,),
        ).fetchone()
        if row is None:
            return None
        item = json.loads(row["payload_json"])
        item["task_id"] = row["task_id"]
        item["decision"] = decision
        item["lifecycle_status"] = status_labels[decision]
        item["manual_override"] = True
        item["manual_decision_note"] = note
        item["review_required"] = decision == "manual_review"
        if note.strip():
            item["reason"] = note.strip()
        connection.execute(
            "UPDATE review_items SET payload_json = ? WHERE review_id = ?",
            (json.dumps(item, ensure_ascii=False), review_id),
        )
        return item


def _cache_text(record: dict[str, Any]) -> str:
    return normalize_for_cache(
        "\n".join(
            str(record.get(key) or "")
            for key in ("title", "published_at", "section", "category", "summary", "content")
        )
    )


def _cache_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for chunk in re.findall(r"[\u3400-\u9fff]+|[a-z0-9]+", text):
        if re.fullmatch(r"[\u3400-\u9fff]+", chunk):
            tokens.update(chunk[index:index + 2] for index in range(len(chunk) - 1))
            if len(chunk) == 1:
                tokens.add(chunk)
        else:
            tokens.add(chunk)
    return tokens


def _cache_similarity(first: str, second: str) -> float:
    first_tokens = _cache_tokens(first)
    second_tokens = _cache_tokens(second)
    union = first_tokens | second_tokens
    return len(first_tokens & second_tokens) / len(union) if union else 0.0


def get_cached_extractions(
    intent_key: str,
    records: list[dict[str, Any]],
    similarity_threshold: float = 0.78,
) -> dict[int, dict[str, Any]]:
    """Reuse exact or near-duplicate local model extractions for the same review intent."""
    texts = [_cache_text(record) for record in records]
    with _database() as connection:
        candidates = connection.execute(
            """
            SELECT text_key, title_key, normalized_text, extraction_json
            FROM review_extraction_cache
            WHERE intent_key = ?
            ORDER BY created_at DESC
            LIMIT 5000
            """,
            (intent_key,),
        ).fetchall()

    exact = {row["text_key"]: row for row in candidates}
    output: dict[int, dict[str, Any]] = {}
    for index, (record, text) in enumerate(zip(records, texts)):
        if not text:
            continue
        text_key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        candidate = exact.get(text_key)
        if candidate is None:
            title_key = normalize_for_cache(str(record.get("title") or ""))
            best_score = 0.0
            best_candidate = None
            for row in candidates:
                score = _cache_similarity(text, row["normalized_text"])
                if row["title_key"] == title_key:
                    score = min(1.0, score + 0.03)
                if score > best_score:
                    best_score = score
                    best_candidate = row
            if best_score >= similarity_threshold:
                candidate = best_candidate
        if candidate is not None:
            extraction = json.loads(candidate["extraction_json"])
            evidence = " ".join(str(extraction.get("evidence") or "").split()).casefold()
            source = " ".join(
                " ".join(
                    str(record.get(key) or "")
                    for key in ("title", "published_at", "section", "category", "summary", "content")
                ).split()
            ).casefold()
            if evidence and evidence in source:
                output[index] = extraction
    return output


def save_cached_extractions(
    intent_key: str,
    records: list[dict[str, Any]],
    extractions: dict[int, dict[str, Any]],
) -> None:
    """Persist validated model extractions locally for reuse by later review tasks."""
    created_at = datetime.now().astimezone().isoformat(timespec="seconds")
    cache_rows = []
    for index, extraction in extractions.items():
        if not 0 <= index < len(records):
            continue
        record = records[index]
        text = _cache_text(record)
        if not text:
            continue
        title_key = normalize_for_cache(str(record.get("title") or ""))
        cache_rows.append(
            (
                intent_key,
                hashlib.sha256(text.encode("utf-8")).hexdigest(),
                title_key,
                text,
                json.dumps(extraction, ensure_ascii=False),
                created_at,
            )
        )
    if not cache_rows:
        return
    with _database() as connection:
        connection.executemany(
            """
            INSERT INTO review_extraction_cache(
                intent_key, text_key, title_key, normalized_text, extraction_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(intent_key, text_key) DO UPDATE SET
                extraction_json = excluded.extraction_json,
                created_at = excluded.created_at
            """,
            cache_rows,
        )
        connection.execute(
            """
            DELETE FROM review_extraction_cache
            WHERE rowid NOT IN (
                SELECT rowid FROM review_extraction_cache
                ORDER BY created_at DESC LIMIT 20000
            )
            """
        )
