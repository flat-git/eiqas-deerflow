"""Evidence tables, explicit plan fulfillment and independent reader feedback."""

from typing import Literal

from pydantic import Field

from .evidence import EvidenceService
from .models import Contract, Identifier, Text
from .service import Conflict, digest


class LocatedEvidence(Contract):
    source_id: Identifier
    extraction_id: Identifier
    locator_key: Text
    quote: Text
    explanation: Text


def resolve_reference(evidence: EvidenceService, rid: str, raw: dict) -> tuple[dict, dict, dict]:
    reference = LocatedEvidence.model_validate({key: raw[key] for key in LocatedEvidence.model_fields})
    source = evidence.get(rid, "source", reference.source_id)
    evidence.original(rid, source["id"])
    extraction = evidence.get(rid, "extraction", reference.extraction_id)
    if extraction["source_id"] != source["id"] or extraction["source_hash"] != source["sha256"] or digest(extraction["result"]) != extraction["sha256"]:
        raise Conflict("证据表的来源或提取完整性不一致")
    block = next((block for block in extraction["result"]["blocks"] if block["key"] == reference.locator_key), None)
    if block is None or reference.quote not in block["text"]:
        raise Conflict("证据摘录不在指定来源定位中")
    return {**reference.model_dump(), "locator": block, "source_hash": source["sha256"], "extraction_hash": extraction["sha256"]}, source, extraction


class EvidenceColumn(Contract):
    key: Identifier
    label: Text
    filterable: bool = False


class EvidenceRow(Contract):
    values: dict[str, Text] = Field(min_length=1, max_length=20)
    kind: Literal["fact", "company_reported", "inference", "unknown"]
    explanation: Text
    evidence: list[LocatedEvidence] = Field(default_factory=list, max_length=10)


class EvidenceTableDraft(Contract):
    title: Text
    columns: list[EvidenceColumn] = Field(min_length=1, max_length=20)
    rows: list[EvidenceRow] = Field(min_length=1, max_length=1000)


class EvidenceTableService:
    def __init__(self, evidence: EvidenceService):
        self.evidence = evidence

    def save(self, rid: str, data: dict) -> dict:
        plan = self.evidence.research.require_confirmed(rid)
        table = EvidenceTableDraft.model_validate(data)
        keys = [column.key for column in table.columns]
        if len(set(keys)) != len(keys):
            raise Conflict("证据表列标识重复")
        rows = []
        for row in table.rows:
            if set(row.values) != set(keys):
                raise Conflict("证据表行必须完整对应声明的列；未知内容请明确写明")
            if row.kind != "unknown" and not row.evidence:
                raise Conflict("支持性证据表行需要具体来源；没有依据时只能保留无法判断")
            refs = [resolve_reference(self.evidence, rid, ref.model_dump())[0] for ref in row.evidence]
            rows.append({**row.model_dump(), "evidence": refs})
        content = {"title": table.title, "columns": [column.model_dump() for column in table.columns], "rows": rows, "plan_hash": plan["hash"]}
        return self.evidence.put(rid, "evidence_table", {**content, "content_hash": digest(content)})

    def verify(self, rid: str, table_id: str, plan_hash: str) -> dict:
        table = self.evidence.get(rid, "evidence_table", table_id)
        if table["plan_hash"] != plan_hash or digest({key: table[key] for key in ["title", "columns", "rows", "plan_hash"]}) != table["content_hash"]:
            raise Conflict("证据表不属于当前方案或完整性不一致")
        for row in table["rows"]:
            for ref in row["evidence"]:
                resolved, _source, _extraction = resolve_reference(self.evidence, rid, ref)
                if resolved["source_hash"] != ref["source_hash"] or resolved["extraction_hash"] != ref["extraction_hash"]:
                    raise Conflict("证据表的冻结引用已失效")
        return table


class PlanItemReview(Contract):
    kind: Literal["method", "output"]
    index: int = Field(ge=0)
    status: Literal["completed", "partial", "blocked", "not_applicable"]
    explanation: Text
    run_ids: list[Identifier] = Field(default_factory=list, max_length=30)
    table_ids: list[Identifier] = Field(default_factory=list, max_length=30)
    finding_indices: list[int] = Field(default_factory=list, max_length=30)
    plan_ref: bool = False


class PlanCoverage(Contract):
    plan_hash: Text
    items: list[PlanItemReview] = Field(default_factory=list, max_length=200)


def resolve_coverage(research: dict, content, tables: list[dict], verify_run) -> tuple[dict, list[dict]]:
    plan = research["plan"]
    supplied = content.plan_coverage
    if supplied and supplied.plan_hash != plan["hash"]:
        raise Conflict("履行核对不属于当前已确认方案")
    declarations, auxiliary = {}, {}
    for item in supplied.items if supplied else []:
        key = (item.kind, item.index)
        choices = plan["content"]["methods" if item.kind == "method" else "outputs"]
        if item.index >= len(choices) or key in declarations:
            raise Conflict("履行核对条目越界或重复")
        if any(index < 0 or index >= len(content.findings) for index in item.finding_indices):
            raise Conflict("履行核对引用了不存在的发现")
        if not set(item.table_ids).issubset({table["id"] for table in tables}):
            raise Conflict("履行核对引用了未交付的证据表")
        runs = [verify_run(run_id) for run_id in item.run_ids]
        for run in runs:
            auxiliary[run["id"]] = run
        if item.status in {"completed", "not_applicable"} and not (item.run_ids or item.table_ids or item.finding_indices or item.plan_ref):
            raise Conflict("完成或条件不适用的声明需要可复核产物，不接受空声明")
        if item.kind == "method" and item.status == "completed":
            operation = choices[item.index]["operation"]
            if operation != "evidence_review" and not any(run["spec"]["method"] in {operation, "python"} for run in runs):
                raise Conflict("计算方法完成声明需要实际对应计算或定制脚本回执")
        declarations[key] = item.model_dump()
    items = []
    for kind, choices in [("method", plan["content"]["methods"]), ("output", plan["content"]["outputs"])]:
        for index, choice in enumerate(choices):
            name = choice["name"] if kind == "method" else choice
            item = declarations.get((kind, index), {"kind": kind, "index": index, "status": "not_addressed", "explanation": "尚未提交本项履行情况，不推定已完成", "run_ids": [], "table_ids": [], "finding_indices": [], "plan_ref": False})
            items.append({**item, "name": name})
    status = "not_assessed" if not declarations else "declared_complete" if all(item["status"] in {"completed", "not_applicable"} for item in items) else "partial"
    return {"status": status, "plan_hash": plan["hash"], "items": items, "note": "这是AI的履行申报与引用核对，不等同于读者确认已回答研究问题。"}, list(auxiliary.values())


class ReviewRequest(Contract):
    status: Literal["accepted", "needs_revision"]
    comment: Text


class ReviewService:
    def __init__(self, evidence: EvidenceService):
        self.evidence = evidence

    def latest(self, rid: str, result_id: str) -> dict:
        self.evidence.get(rid, "result", result_id)
        records = [row for row in self.evidence.list(rid, "result_review") if row["result_id"] == result_id]
        return records[-1] if records else {"status": "pending", "comment": "尚无读者复核反馈"}

    def record(self, rid: str, result_id: str, *, status: str, comment: str, origin: str = "workbench") -> dict:
        request = ReviewRequest(status=status, comment=comment)
        report = self.evidence.get(rid, "result", result_id)
        return self.evidence.put(rid, "result_review", {**request.model_dump(), "result_id": result_id, "result_hash": digest(report), "actor": "user", "origin": origin})
