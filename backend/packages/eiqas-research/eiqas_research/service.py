"""Transactional research service shared by HTTP and native Agent tools."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import Plan, ResearchCreate, Stage


class Conflict(ValueError):
    """The caller used stale intent or has not satisfied a business gate."""


class NotFound(LookupError):
    """An object is absent from this research."""


def now() -> str:
    return datetime.now(UTC).isoformat()


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class ResearchService:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "research.sqlite3"
        with self._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS research (
                    id TEXT PRIMARY KEY, thread_id TEXT UNIQUE NOT NULL, body TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, research_id TEXT NOT NULL,
                    kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_research ON events(research_id, seq);
            """)

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        try:
            yield db
        finally:
            db.close()

    def _event(self, db: sqlite3.Connection, rid: str, kind: str, payload: dict) -> None:
        db.execute("INSERT INTO events(research_id,kind,payload,created_at) VALUES(?,?,?,?)", (rid, kind, canonical(payload), now()))

    def create(self, data: ResearchCreate) -> dict:
        rid = uuid.uuid4().hex
        body = {"id": rid, **data.model_dump(), "stage": "question", "status": "draft", "plan": None, "answerable": [], "gaps": [], "created_at": now(), "updated_at": now()}
        try:
            with self._connection() as db, db:
                db.execute("INSERT INTO research VALUES(?,?,?)", (rid, data.thread_id, canonical(body)))
                self._event(db, rid, "research.created", {"thread_id": data.thread_id})
        except sqlite3.IntegrityError as exc:
            raise Conflict("一个线程只能对应一项研究") from exc
        return body

    def get(self, rid: str) -> dict:
        with self._connection() as db:
            return self._read(db, rid)

    def _read(self, db: sqlite3.Connection, rid: str) -> dict:
        row = db.execute("SELECT body FROM research WHERE id=?", (rid,)).fetchone()
        if row is None:
            raise NotFound("研究不存在")
        return json.loads(row["body"])

    def for_thread(self, thread_id: str) -> dict | None:
        with self._connection() as db:
            row = db.execute("SELECT body FROM research WHERE thread_id=?", (thread_id,)).fetchone()
        return json.loads(row["body"]) if row else None

    def list(self) -> list[dict]:
        with self._connection() as db:
            rows = db.execute("SELECT body FROM research ORDER BY rowid DESC LIMIT 1000").fetchall()
        return [json.loads(row["body"]) for row in rows]

    def _mutate(self, rid: str, kind: str, payload: dict, update: Callable[[dict], None]) -> dict:
        with self._connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            body = self._read(db, rid)
            update(body)
            body["updated_at"] = now()
            db.execute("UPDATE research SET body=? WHERE id=?", (canonical(body), rid))
            self._event(db, rid, kind, payload)
        return body

    def update_question(self, rid: str, question: str) -> dict:
        def update(body):
            if body["question"] != question and body["plan"]:
                body["plan"]["confirmed_at"] = None
                body["status"] = "draft"
            body["question"] = question

        return self._mutate(rid, "question.updated", {"question": question}, update)

    def save_plan(self, rid: str, plan: Plan) -> dict:
        content = plan.model_dump()
        plan_hash = digest(content)

        def update(body):
            previous = body["plan"]
            if previous and previous["hash"] == plan_hash:
                return
            body["plan"] = {"content": content, "hash": plan_hash, "revision": (previous["revision"] + 1 if previous else 1), "confirmed_at": None}
            body["status"] = "draft"

        return self._mutate(rid, "plan.saved", {"hash": plan_hash}, update)["plan"]

    def confirm_plan(self, rid: str, plan_hash: str) -> dict:
        def update(body):
            plan = body["plan"]
            if not plan or plan["hash"] != plan_hash:
                raise Conflict("方案已更新，请核对当前方案后确认")
            if plan["content"]["question"] != body["question"]:
                raise Conflict("研究问题已变化，请更新方案")
            plan["confirmed_at"] = plan["confirmed_at"] or now()
            body["status"] = "ready"

        return self._mutate(rid, "plan.confirmed", {"hash": plan_hash, "actor": "human"}, update)["plan"]

    def require_confirmed(self, rid: str) -> dict:
        body = self.get(rid)
        plan = body["plan"]
        if not plan or not plan["confirmed_at"] or plan["content"]["question"] != body["question"]:
            raise Conflict("请先在工作台确认当前研究方案")
        return plan

    def set_stage(self, rid: str, stage: Stage) -> dict:
        return self._mutate(rid, "stage.changed", {"stage": stage}, lambda body: body.update(stage=stage))

    def update_scope(self, rid: str, *, answerable: list[str], gaps: list[str]) -> dict:
        return self._mutate(rid, "scope.updated", {"answerable": answerable, "gaps": gaps}, lambda body: body.update(answerable=answerable, gaps=gaps))

    def events(self, rid: str, after: int = 0) -> list[dict]:
        self.get(rid)
        with self._connection() as db:
            rows = db.execute("SELECT * FROM events WHERE research_id=? AND seq>? ORDER BY seq LIMIT 1000", (rid, after)).fetchall()
        return [{**dict(row), "payload": json.loads(row["payload"])} for row in rows]
