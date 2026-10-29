"""Problem/method/data feasibility, separate from formal calculation and approval."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import Field

from .delivery import LocatedEvidence, resolve_reference
from .evidence import EvidenceService
from .models import Contract, Identifier, Plan, Text
from .service import Conflict, NotFound, canonical, digest, now


class DataAssessment(Contract):
    requirement_id: Identifier
    requirement_hash: Text
    status: Literal["suggested", "located", "sample_checked", "available", "unavailable", "restricted", "quality_issue"]
    reason: Text
    next_action: Text
    gap_types: list[Literal["missing_values", "grain", "period", "definition", "unit", "quality", "access", "coverage"]] = Field(default_factory=list, max_length=8)
    evidence: list[LocatedEvidence] = Field(default_factory=list, max_length=30)
    dataset_ids: list[Identifier] = Field(default_factory=list, max_length=30)


class InputRequest(Contract):
    kind: Literal["critical_data", "definition_conflict", "ocr_review", "scope_change"]
    questions: list[Text] = Field(min_length=1, max_length=10)
    impact: Text
    requirement_ids: list[Identifier] = Field(default_factory=list, max_length=30)


class InputReply(Contract):
    request_hash: Text
    response: Text


def design_errors(content: dict) -> list[str]:
    plan = Plan.model_validate(content)
    errors = []
    if not plan.decision_use or not plan.scope or not plan.research_questions:
        errors.append("请补齐研究设计任务书：决策用途、范围和具体研究问题")
    if plan.open_questions:
        errors.append("关键问题尚未澄清：" + "；".join(plan.open_questions))
    questions = [q.id for q in plan.research_questions]
    methods = [m.id for m in plan.methods]
    needs = [r.id for r in plan.data_requirements]
    if len(set(questions)) != len(questions) or len(set(methods)) != len(methods) or len(set(needs)) != len(needs):
        errors.append("问题、方法或数据要求的标识重复")
    decisions = [d.question_id for d in plan.question_decisions]
    if set(decisions) != set(questions) or len(decisions) != len(set(decisions)):
        errors.append("每个研究问题都需要明确可回答、部分回答或无法判断的范围")
    if any(d.status != "answer" for d in plan.question_decisions) and not plan.scope_changes:
        errors.append("数据限制导致的研究范围调整需要明确说明，不能静默删去问题")
    selected = [m for m in plan.methods if m.selected]
    if not any(m.operation != "evidence_review" and m.role == "primary" for m in selected):
        errors.append("至少选择一个直接回应研究问题的主要量化方法")
    for method in plan.methods:
        if not method.id or not method.question_ids or not set(method.question_ids).issubset(questions):
            errors.append(f"方法 {method.name} 需要唯一标识并关联已有研究问题")
        if not method.selected:
            continue
        if not all([method.basis, method.calculation, method.applicability, method.expected_outputs]):
            errors.append(f"方法 {method.name} 缺少依据、计算逻辑、适用条件或预期图表")
        linked = [r for r in plan.data_requirements if method.id in r.method_ids and r.required]
        if not linked or (method.operation != "evidence_review" and not any(r.kind == "quantitative" for r in linked)):
            errors.append(f"方法 {method.name} 缺少必要的数据要求")
    for need in plan.data_requirements:
        if not set(need.method_ids).issubset(methods) or (need.kind == "quantitative" and not need.metrics):
            errors.append(f"数据要求 {need.title} 的方法关联或量化指标缺失")
    for decision in plan.question_decisions:
        if decision.status != "unanswerable" and not any(m.role == "primary" and m.operation != "evidence_review" and decision.question_id in m.question_ids for m in selected):
            errors.append(f"问题 {decision.question_id} 缺少直接回应的主要量化方法")
    if not any(d.status != "unanswerable" for d in plan.question_decisions):
        errors.append("当前没有可量化回答的问题，请先重拟研究方案")
    return errors


class PlanningService:
    def __init__(self, evidence: EvidenceService):
        self.evidence = evidence
        self.research = evidence.research

    def _requirement(self, rid: str, requirement_id: str) -> dict:
        plan = self.research.get(rid)["plan"]
        requirement = next((r for r in (plan or {}).get("content", {}).get("data_requirements", []) if r["id"] == requirement_id), None)
        if requirement is None:
            raise NotFound("数据要求不存在或不属于当前研究方案")
        return requirement

    def _verify_assessment(self, rid: str, requirement: dict, assessment: dict) -> None:
        if assessment["requirement_hash"] != digest(requirement):
            raise Conflict("数据要求已更新，请重新核查可得性")
        refs = [resolve_reference(self.evidence, rid, ref)[0] for ref in assessment["evidence"]]
        status = assessment["status"]
        if status in {"available", "sample_checked"}:
            if not refs:
                raise Conflict("数据可得性需要已取得原件中的具体定位样本")
            if assessment["gap_types"]:
                raise Conflict("尚有数据口径或质量缺口，不能声明可执行")
        if status == "sample_checked" and requirement["category"] != "public":
            raise Conflict("内部、专家或商业数据需要实际取得，不能仅凭样本承诺可用")
        metrics = set()
        ref_sources = {ref["source_id"] for ref in refs}
        for did in assessment["dataset_ids"]:
            dataset = self.evidence.get(rid, "dataset", did)
            if digest({k: dataset[k] for k in ["title", "rows", "observations"]}) != dataset["input_hash"]:
                raise Conflict("数据集完整性不一致")
            for observation in dataset["observations"]:
                self.evidence.original(rid, observation["source_id"])
                if observation["source_id"] in ref_sources:
                    metrics.add(observation["metric"])
        if status == "available" and requirement["kind"] == "quantitative" and not set(requirement["metrics"]).issubset(metrics):
            raise Conflict("实际数据集没有覆盖数据要求中的量化指标")

    def assess(self, rid: str, assessment: DataAssessment) -> dict:
        payload = assessment.model_dump()
        with self.research._connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            requirement = self._requirement(rid, assessment.requirement_id)
            self._verify_assessment(rid, requirement, payload)
            return self._put(db, rid, "data_assessment", {**payload, "content_hash": digest(payload)})

    def _put(self, db, rid: str, kind: str, payload: dict) -> dict:
        row = {**payload, "id": uuid.uuid4().hex, "research_id": rid, "created_at": now()}
        db.execute("INSERT INTO records VALUES(?,?,?,?)", (row["id"], rid, kind, canonical(row)))
        self.research._event(db, rid, f"{kind}.created", {"id": row["id"]})
        return row

    def inspect(self, rid: str, *, plan: dict | None = None) -> dict:
        research = self.research.get(rid)
        plan = plan or research["plan"]
        if not plan:
            return {"can_confirm": False, "errors": ["请先通过对话明确研究问题并保存候选方案"], "requirements": [], "methods": [], "question_decisions": []}
        content = plan["content"]
        errors = design_errors(content)
        assessments = self.evidence.list(rid, "data_assessment")
        requirements = []
        for need in content.get("data_requirements", []):
            current = next((a for a in reversed(assessments) if a["requirement_id"] == need["id"] and a["requirement_hash"] == digest(need)), None)
            issue = ""
            if current:
                try:
                    if current["content_hash"] != digest({k: current[k] for k in DataAssessment.model_fields}):
                        raise Conflict("数据评估完整性不一致")
                    self._verify_assessment(rid, need, current)
                except (ValueError, LookupError) as exc:
                    issue = str(exc)
            requirements.append({**need, "requirement_hash": digest(need), "status": "invalid" if issue else current["status"] if current else "unknown", "assessment": current, "issue": issue})
        methods = []
        for method in content["methods"]:
            linked = [r for r in requirements if method.get("id") in r["method_ids"] and r["required"]]
            ready = bool(linked) and all(r["status"] in {"available", "sample_checked"} for r in linked)
            methods.append({**method, "readiness": "feasible" if ready else "needs_data", "missing_requirement_ids": [r["id"] for r in linked if r["status"] not in {"available", "sample_checked"}]})
            if method.get("selected", True) and not ready:
                errors.append(f"方法 {method['name']} 的必要数据尚未核实；请补充数据或重拟方案")
        return {"can_confirm": not errors, "errors": errors, "requirements": requirements, "methods": methods, "question_decisions": content.get("question_decisions", []), "plan_hash": plan["hash"]}

    def validate_confirmation(self, rid: str, plan: dict) -> dict:
        view = self.inspect(rid, plan=plan)
        if not view["can_confirm"]:
            raise Conflict("；".join(view["errors"]))
        if self.pending_request(rid):
            raise Conflict("关键问题仍待用户回答，请先处理研究追问")
        return view

    def validate_input(self, rid: str, plan: dict, dataset: dict, operation: str, method_id: str | None) -> str | None:
        if self.research.get(rid).get("workflow_version", 1) < 2:
            return None
        matches = [m for m in plan["content"]["methods"] if m.get("selected", True) and m["operation"] == operation and (not method_id or m.get("id") == method_id)]
        if len(matches) != 1:
            raise Conflict("请选择已确认的具体方法；同类方法有多个时需要 method_id")
        if self.pending_request(rid):
            raise Conflict("关键数据或口径问题尚待用户回答")
        selected = matches[0]
        view = self.inspect(rid)
        if any(m.get("id") == selected["id"] and m["readiness"] != "feasible" for m in view["methods"]):
            raise Conflict("方法所需数据出现新的缺口或口径问题，请先核实")
        needs = [r for r in view["requirements"] if selected["id"] in r["method_ids"] and r["required"] and r["kind"] == "quantitative"]
        allowed = set()
        for need in needs:
            if need["status"] != "available":
                raise Conflict(f"请先核实并登记方法所需的实际数据：{need['title']}")
            sources = {ref["source_id"] for ref in need["assessment"]["evidence"]}
            found = {(o["source_id"], o["metric"]) for o in dataset["observations"] if o["source_id"] in sources and o["metric"] in need["metrics"]}
            if not set(need["metrics"]).issubset({metric for _source, metric in found}):
                raise Conflict(f"运行数据未覆盖方法需要的指标：{need['title']}")
            allowed.update(found)
        # Additional data must also have been declared for this method.
        for need in self.inspect(rid)["requirements"]:
            if selected["id"] in need["method_ids"] and need["status"] == "available":
                allowed.update((ref["source_id"], metric) for ref in need["assessment"]["evidence"] for metric in need["metrics"])
        if any((o["source_id"], o["metric"]) not in allowed for o in dataset["observations"]):
            raise Conflict("运行包含未关联当前方法的数据或指标，请先核实研究设计")
        return selected["id"]

    def pending_request(self, rid: str) -> dict | None:
        self.research.get(rid)
        replies = {r["request_id"] for r in self.evidence.list(rid, "input_reply")}
        return next((r for r in reversed(self.evidence.list(rid, "input_request")) if r["id"] not in replies), None)

    def request_input(self, rid: str, **kwargs) -> dict:
        request = InputRequest.model_validate(kwargs)
        with self.research._connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            research = self.research._read(db, rid)
            if not research["plan"]:
                raise Conflict("请先保存问题和候选方案，再登记具体数据或范围追问")
            for requirement_id in request.requirement_ids:
                self._requirement(rid, requirement_id)
            if self.pending_request(rid):
                raise Conflict("已有待回答的问题，请等待用户答复")
            payload = {**request.model_dump(), "plan_hash": research["plan"]["hash"]}
            return self._put(db, rid, "input_request", {**payload, "content_hash": digest(payload)})

    def reply(self, rid: str, request_id: str, *, request_hash: str, response: str) -> dict:
        validated = InputReply(request_hash=request_hash, response=response)
        with self.research._connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            pending = self.pending_request(rid)
            if not pending or pending["id"] != request_id or pending["content_hash"] != validated.request_hash:
                raise Conflict("研究追问已更新，请刷新后回答")
            row = self._put(db, rid, "input_reply", {"request_id": request_id, "response": validated.response, "request_hash": request_hash, "actor": "human"})
            if pending["kind"] == "scope_change":
                body = self.research._read(db, rid)
                body["plan"]["confirmed_at"] = None
                body.update(status="draft", stage="plan", updated_at=now())
                db.execute("UPDATE research SET body=? WHERE id=?", (canonical(body), rid))
                self.research._event(db, rid, "plan.reconsidered", {"request_id": request_id})
        return row

    def workflow(self, rid: str) -> dict:
        research = self.research.get(rid)
        pending = self.pending_request(rid)
        if pending:
            return {"action": "needs_input", "request": pending, "automatic": False}
        view = self.inspect(rid)
        plan = research["plan"]
        if not plan or not plan["confirmed_at"]:
            if plan and plan["content"].get("open_questions"):
                return {"action": "clarify_question", "automatic": False, "questions": plan["content"]["open_questions"]}
            return {"action": "confirm_plan" if view["can_confirm"] else "refine_design", "automatic": not view["can_confirm"], "errors": view["errors"]}
        if not view["can_confirm"]:
            return {"action": "resolve_data_gaps", "automatic": True, "errors": view["errors"]}
        runs = [r for r in self.evidence.list(rid, "run") if r["plan_hash"] == plan["hash"]]
        if any(r["status"] == "running" for r in runs):
            return {"action": "running", "automatic": False}
        missing = [m for m in view["methods"] if m.get("selected", True) and m["operation"] != "evidence_review" and not any(r.get("method_id") == m.get("id") and r["status"] in {"verified", "partial"} for r in runs)]
        if missing:
            return {"action": "prepare_and_calculate", "automatic": True, "method_ids": [m["id"] for m in missing]}
        reports = [r for r in self.evidence.list(rid, "result") if r["plan"]["hash"] == plan["hash"]]
        if not reports or reports[-1].get("coverage", {}).get("status") != "declared_complete":
            return {"action": "review_and_deliver", "automatic": True}
        return {"action": "delivered", "automatic": False, "result_id": reports[-1]["id"], "note": "数值和结构检查通过；语义支持仍需真实研究验收"}
