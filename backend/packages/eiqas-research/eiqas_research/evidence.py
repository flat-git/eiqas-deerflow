"""Located evidence, reviewable values and frozen computational datasets."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit

from .service import Conflict, NotFound, ResearchService, canonical, digest, now

# No implicit currency conversion. Ratios are normalized only from explicit units.
UNITS = {
    "元": ("CNY", "1"),
    "千元": ("CNY", "1000"),
    "万元": ("CNY", "10000"),
    "亿元": ("CNY", "100000000"),
    "CNY": ("CNY", "1"),
    "USD": ("USD", "1"),
    "%": ("ratio", "0.01"),
    "ratio": ("ratio", "1"),
    "个": ("count", "1"),
    "项": ("count", "1"),
    "count": ("count", "1"),
    "人": ("people", "1"),
    "台": ("devices", "1"),
    "万台": ("devices", "10000"),
    "小时": ("hours", "1"),
    "kWh": ("kWh", "1"),
    "MWh": ("kWh", "1000"),
    "吨": ("kg", "1000"),
    "kg": ("kg", "1"),
}
NUMBER = re.compile(r"(?<![A-Za-z0-9_.])[-+]?\d[\d,]*(?:\.\d+)?")
QUALIFIERS = {"exact", "about", "more_than", "less_than", "range"}


class EvidenceService:
    def __init__(self, research: ResearchService):
        self.research = research
        with research._connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY, research_id TEXT NOT NULL, kind TEXT NOT NULL, body TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS records_research ON records(research_id, kind);
            """)

    def put(self, rid: str, kind: str, body: dict) -> dict:
        self.research.get(rid)
        row = {**body, "id": uuid.uuid4().hex, "research_id": rid, "created_at": now()}
        with self.research._connection() as db, db:
            db.execute("INSERT INTO records VALUES(?,?,?,?)", (row["id"], rid, kind, canonical(row)))
            self.research._event(db, rid, f"{kind}.created", {"id": row["id"]})
        return row

    def get(self, rid: str, kind: str, record_id: str) -> dict:
        with self.research._connection() as db:
            row = db.execute("SELECT body FROM records WHERE research_id=? AND kind=? AND id=?", (rid, kind, record_id)).fetchone()
        if row is None:
            raise NotFound("记录不存在或不属于当前研究")
        return json.loads(row["body"])

    def list(self, rid: str, kind: str) -> list[dict]:
        self.research.get(rid)
        with self.research._connection() as db:
            rows = db.execute("SELECT body FROM records WHERE research_id=? AND kind=? ORDER BY rowid", (rid, kind)).fetchall()
        return [json.loads(row["body"]) for row in rows]

    def directory(self, rid: str) -> Path:
        research = self.research.get(rid)
        # Thread identifiers are validated when the research is created.
        path = self.research.root / "threads" / research["thread_id"]
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _url(url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            raise ValueError("来源必须是无登录凭据的公开 HTTP(S) URL")

    def register_source(self, rid: str, *, url: str, title: str, organization: str, content: bytes, media_type: str, retrieved_url: str | None = None) -> dict:
        self._url(url)
        self._url(retrieved_url or url)
        if not content or len(content) > 64 * 1024 * 1024:
            raise ValueError("原件为空或超过 64 MiB")
        name = uuid.uuid4().hex
        relative = f"sources/{name}/original.bin"
        original = self.directory(rid) / relative
        original.parent.mkdir(parents=True)
        original.write_bytes(content)
        return self.put(
            rid,
            "source",
            {
                "url": url,
                "retrieved_url": retrieved_url or url,
                "title": title,
                "organization": organization,
                "retrieved_at": now(),
                "status": "acquired",
                "media_type": media_type,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
                "path": relative,
            },
        )

    def record_source_failure(self, rid: str, *, url: str, title: str, organization: str, reason: str, status: str = "failed") -> dict:
        self._url(url)
        if status not in {"failed", "restricted"}:
            raise ValueError("无效的取得状态")
        return self.put(rid, "source", {"url": url, "title": title, "organization": organization, "retrieved_at": now(), "status": status, "reason": reason, "sha256": None, "path": None})

    def original(self, rid: str, source_id: str) -> Path:
        source = self.get(rid, "source", source_id)
        if source["status"] != "acquired":
            raise Conflict("原件尚未取得")
        root = self.directory(rid).resolve()
        path = (root / source["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise Conflict("来源原件缺失或完整性检查失败")
        return path

    def register_extraction(self, rid: str, source_id: str, result: dict) -> dict:
        source = self.get(rid, "source", source_id)
        self.original(rid, source_id)
        blocks = result.get("blocks", [])
        if not blocks or len(blocks) > 200000:
            raise Conflict("解析未取得可定位内容")
        keys = set()
        page_count = result.get("page_count")
        for block in blocks:
            if not isinstance(block.get("text"), str) or not block.get("key") or block["key"] in keys:
                raise Conflict("解析定位缺失或重复")
            keys.add(block["key"])
            page = block.get("page")
            if page is not None and (type(page) is not int or not page_count or not 1 <= page <= page_count):
                raise Conflict("解析物理页码无效")
        return self.put(rid, "extraction", {"source_id": source_id, "source_hash": source["sha256"], "result": result, "sha256": digest(result)})

    def add_observation(self, rid: str, data: dict) -> dict:
        required = {"source_id", "extraction_id", "locator_key", "raw_text", "value", "unit", "subject", "period", "metric", "qualifier"}
        if set(data) != required or data["qualifier"] not in QUALIFIERS:
            raise ValueError("候选数据字段或数值修饰词无效")
        source = self.get(rid, "source", data["source_id"])
        extraction = self.get(rid, "extraction", data["extraction_id"])
        self.original(rid, source["id"])
        if extraction["source_id"] != source["id"] or extraction["source_hash"] != source["sha256"]:
            raise Conflict("提取记录不属于该来源")
        block = next((block for block in extraction["result"]["blocks"] if block["key"] == data["locator_key"]), None)
        if block is None:
            raise Conflict("提取定位不存在")
        if not data["raw_text"] or data["raw_text"] not in block["text"]:
            raise Conflict("摘录不在来源定位内容中")
        for name in ["subject", "period", "metric"]:
            if not isinstance(data[name], str) or not data[name].strip():
                raise ValueError(f"{name} 不能为空")
        value = self._decimal(data["value"])
        tokens = {Decimal(token.replace(",", "")) for token in NUMBER.findall(data["raw_text"])}
        flags = []
        if value not in tokens:
            flags.append("number_mismatch")
        if not data["unit"]:
            flags.append("unit_missing")
        elif data["unit"] not in UNITS:
            flags.append("unit_unrecognized")
        unit_text = re.sub(r"\s+", "", data["raw_text"])
        explicit_units = re.findall(r"亿元|万元|千元|万台|MWh|kWh|USD|CNY|(?<!万|亿|千)元|%|吨|kg|人|台|项|个|小时", unit_text)
        # Annual-report rows often include a neighboring growth-% column. A
        # percentage alone cannot establish that an amount/count unit is wrong.
        competing_units = [unit for unit in explicit_units if unit != "%"]
        if competing_units and data["unit"] not in explicit_units:
            flags.append("unit_conflict")
        for pattern, qualifier in [(r"超过|逾|大于|以上|more than|over\s+\d", "more_than"), (r"少于|低于|不足|以下|less than|under\s+\d", "less_than"), (r"约|大约|近|about|approximately", "about")]:
            if data["qualifier"] == "exact" and re.search(pattern, data["raw_text"], re.IGNORECASE):
                data = {**data, "qualifier": qualifier}
        if data["qualifier"] != "exact":
            flags.append("qualified_number")
        if block.get("ocr"):
            flags.append("ocr_requires_review")
        return self.put(
            rid, "observation", {**data, "value": str(value), "source_hash": source["sha256"], "extraction_hash": extraction["sha256"], "locator": block, "status": "review" if flags else "verified", "flags": flags, "corrections": []}
        )

    @staticmethod
    def _decimal(value) -> Decimal:
        try:
            number = Decimal(str(value))
            if not number.is_finite():
                raise InvalidOperation
            return number
        except (ValueError, InvalidOperation) as exc:
            raise ValueError("数值必须是有限数字") from exc

    def correct_observation(self, rid: str, oid: str, *, value: str, unit: str, reason: str, subject: str | None = None, period: str | None = None, metric: str | None = None, qualifier: str | None = None) -> dict:
        if not reason.strip() or not unit.strip() or len(unit) > 100:
            raise ValueError("人工核对需要明确依据与单位；未注册单位按原文保留，不自动换算")
        if qualifier is not None and qualifier not in QUALIFIERS:
            raise ValueError("数值修饰词无效")
        fields = {key: value for key, value in {"subject": subject, "period": period, "metric": metric, "qualifier": qualifier}.items() if value is not None}
        if any(not isinstance(value, str) or not value.strip() for value in fields.values()):
            raise ValueError("更正后的主体、期间和指标不能为空")
        number = self._decimal(value)
        with self.research._connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            obs = self.get(rid, "observation", oid)
            before = {key: obs[key] for key in ["value", "unit", "status", "flags", "subject", "period", "metric", "qualifier"]}
            after = {"value": str(number), "unit": unit, **fields}
            obs["corrections"].append({"actor": "human", "at": now(), "reason": reason, "before": before, "after": after})
            obs.update(**after, status="verified", flags=[])
            db.execute("UPDATE records SET body=? WHERE id=? AND research_id=?", (canonical(obs), oid, rid))
            self.research._event(db, rid, "observation.corrected", {"id": oid, "reason": reason, "actor": "human"})
        return obs

    def create_dataset(self, rid: str, title: str, observation_ids: list[str]) -> dict:
        if not title.strip() or not observation_ids or len(observation_ids) > 100000:
            raise ValueError("数据集需要名称与数据")
        rows, snapshots, keys, units = [], [], set(), {}
        for oid in observation_ids:
            obs = self.get(rid, "observation", oid)
            self.original(rid, obs["source_id"])
            if obs["status"] != "verified":
                raise Conflict("关键数据尚未核实，请完成核对队列")
            if obs["qualifier"] in {"more_than", "less_than", "range"}:
                raise Conflict("下限、上限或区间不能当作精确数值计算，请保留修饰词并记录数据缺口")
            key = (obs["subject"], obs["metric"], obs["period"])
            if key in keys:
                raise Conflict("数据存在重复或冲突的主体、指标、期间组合")
            keys.add(key)
            normalized, factor = UNITS.get(obs["unit"], (obs["unit"], "1"))
            if obs["metric"] in units and units[obs["metric"]] != normalized:
                raise Conflict("同一指标的单位口径不一致，不能自动换汇或换算")
            units[obs["metric"]] = normalized
            value = format(Decimal(obs["value"]) * Decimal(factor), "f")
            rows.append({"observation_id": oid, "subject": obs["subject"], "period": obs["period"], "metric": obs["metric"], "value": value, "unit": normalized, "qualifier": obs["qualifier"]})
            snapshots.append(obs)
        content = {"title": title, "rows": rows, "observations": snapshots}
        return self.put(rid, "dataset", {**content, "input_hash": digest(content)})

    def withdraw_observation(self, rid: str, oid: str, *, reason: str) -> dict:
        """An agent may retract an invalid registration, never approve or edit it."""
        if not reason.strip():
            raise ValueError("撤回候选数据需要说明登记错误与重新处理方式")
        with self.research._connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            obs = self.get(rid, "observation", oid)
            if obs["status"] != "review" or obs["corrections"]:
                raise Conflict("只能撤回尚未核对、尚未成为可用数据的候选登记；不得撤回人工核对或冻结数据")
            obs.update(status="withdrawn", withdrawal={"actor": "agent", "at": now(), "reason": reason})
            db.execute("UPDATE records SET body=? WHERE id=? AND research_id=?", (canonical(obs), oid, rid))
            self.research._event(db, rid, "observation.withdrawn", {"id": oid, "reason": reason, "actor": "agent"})
        return obs
