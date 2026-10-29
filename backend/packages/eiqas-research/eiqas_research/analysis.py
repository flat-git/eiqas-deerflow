"""Persist actual execution materials; terminal writes are cancellation-fenced."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from . import worker
from .evidence import EvidenceService
from .service import Conflict, canonical, digest, now

METHODS = {"python", "aggregate", "growth", "structure", "contribution", "correlation", "cost_benefit", "sensitivity"}


class AnalysisService:
    def __init__(self, evidence: EvidenceService):
        self.evidence = evidence

    def run_directory(self, rid: str, run_id: str) -> Path:
        self.evidence.get(rid, "run", run_id)
        path = self.evidence.directory(rid) / "runs" / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def start_run(self, rid: str, dataset_id: str, spec: dict, *, native_run_id: str | None, method_id: str | None = None) -> dict:
        plan = self.evidence.research.require_confirmed(rid)
        worker.validate_spec(spec)
        if spec.get("method") not in {method["operation"] for method in plan["content"]["methods"] if method.get("selected", True)}:
            raise Conflict("计算方法不在已确认方案中，请更新方法后重新确认")
        dataset = self.evidence.get(rid, "dataset", dataset_id)
        from .planning import PlanningService

        method_id = PlanningService(self.evidence).validate_input(rid, plan, dataset, spec["method"], method_id)
        if digest({key: dataset[key] for key in ["title", "rows", "observations"]}) != dataset["input_hash"]:
            raise Conflict("数据集输入哈希不一致")
        for observation in dataset["observations"]:
            self.evidence.original(rid, observation["source_id"])
        if spec.get("method") not in METHODS or set(spec) - {"method", "parameters"}:
            raise ValueError("方法未注册或参数结构无效")
        if not isinstance(spec.get("parameters", {}), dict):
            raise ValueError("方法参数必须是对象")
        request = {"dataset": dataset, "spec": spec}
        request_bytes = canonical(request).encode()
        script = Path(worker.__file__).read_bytes()
        run = self.evidence.put(
            rid,
            "run",
            {
                "dataset_id": dataset_id,
                "input_hash": dataset["input_hash"],
                "spec": spec,
                "plan_hash": plan["hash"],
                "method_id": method_id,
                "native_run_id": native_run_id,
                "status": "running",
                "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
                "worker_sha256": hashlib.sha256(script).hexdigest(),
                "started_at": now(),
                "completed_at": None,
                "verified_at": None,
            },
        )
        directory = self.run_directory(rid, run["id"])
        (directory / "input.json").write_bytes(request_bytes)
        (directory / "script.py").write_bytes(script)
        if spec["method"] == "python":
            for name, key in [("analysis.py", "code"), ("check.py", "check_code")]:
                code = spec["parameters"].get(key)
                if isinstance(code, str):
                    (directory / name).write_text(code, encoding="utf-8")
        self.evidence.research.set_stage(rid, "analysis")
        return run

    def _terminal(self, rid: str, run_id: str, fields: dict) -> dict:
        research = self.evidence.research
        with research._connection() as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = self.evidence.get(rid, "run", run_id)
            if row["status"] != "running":
                return row
            row.update(**fields, completed_at=now())
            db.execute("UPDATE records SET body=? WHERE id=? AND research_id=?", (canonical(row), run_id, rid))
            research._event(db, rid, "run.finished", {"id": run_id, "status": row["status"]})
        return row

    def complete_run(self, rid: str, run_id: str, output: dict, *, log: str) -> dict:
        run = self.evidence.get(rid, "run", run_id)
        if run["status"] != "running":
            return run
        directory = self.run_directory(rid, run_id)
        (directory / "execution.log").write_text(log, encoding="utf-8")
        errors = []
        for key in ["request_sha256", "worker_sha256"]:
            if output.get(key) != run[key]:
                errors.append(f"{key} 不匹配")
        if output.get("status") not in {"verified", "partial"} or not output.get("rows"):
            errors.append(output.get("error", "没有已计算结果"))
        checks = output.get("checks")
        if not isinstance(checks, list) or not checks or any(check.get("passed") is not True for check in checks):
            errors.append("结果检查未通过或没有检查")
        try:
            output_text = canonical(output)
        except (TypeError, ValueError):
            errors.append("结果不是有限、可序列化的数据")
            output_text = canonical({"error": "invalid result"})
        (directory / "result.json").write_text(output_text, encoding="utf-8")
        if errors:
            return self._terminal(rid, run_id, {"status": "failed", "errors": errors})
        rows = output["rows"]
        with (directory / "result.csv").open("w", newline="", encoding="utf-8-sig") as handle:
            columns = list(dict.fromkeys(key for row in rows for key in row))
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        return self._terminal(
            rid,
            run_id,
            {
                "status": output["status"],
                "result": output,
                "output_hash": digest(output),
                "verified_at": now(),
                "artifact_hashes": {
                    name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                    for name in ["input.json", "script.py", "execution.log", "result.json", "result.csv", *(["analysis.py", "check.py"] if run["spec"]["method"] == "python" else [])]
                },
            },
        )

    def stop_run(self, rid: str, run_id: str, status: str, reason: str) -> dict:
        if status not in {"cancelled", "failed", "interrupted"}:
            raise ValueError("无效的运行终止状态")
        return self._terminal(rid, run_id, {"status": status, "errors": [reason]})

    def recover_interrupted(self) -> int:
        with self.evidence.research._connection() as db:
            rows = db.execute("SELECT id,research_id FROM records WHERE kind='run' AND json_extract(body,'$.status')='running'").fetchall()
        for row in rows:
            self.stop_run(row["research_id"], row["id"], "interrupted", "Gateway 重启，尚无完成计算的回执；请重新运行")
        return len(rows)
