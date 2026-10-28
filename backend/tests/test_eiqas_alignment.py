"""A checked calculation does not establish research-plan fulfillment."""

import json
import zipfile

import pytest
from eiqas_research.service import Conflict, digest
from test_eiqas_reports import draft, finished
from test_eiqas_runs import prepared as prepared


def reference(reports, rid):
    source = reports.evidence.list(rid, "source")[0]
    extraction = reports.evidence.list(rid, "extraction")[0]
    return {"source_id": source["id"], "extraction_id": extraction["id"], "locator_key": "line:1", "quote": "100", "explanation": "合成原值定位"}


def table(reports, rid):
    return {
        "title": "通用证据对照",
        "columns": [{"key": "subject", "label": "对象", "filterable": True}, {"key": "answer", "label": "判断"}],
        "rows": [{"values": {"subject": "合成对象", "answer": "原件为100"}, "kind": "fact", "explanation": "只验证来源，不代表能力", "evidence": [reference(reports, rid)]}],
    }


def test_unmapped_report_is_not_research_complete_even_when_math_passed(prepared):
    reports, rid, run = finished(prepared)
    report = reports.submit(rid, draft(run))
    assert report["run"]["status"] == "verified"
    assert report["coverage"]["status"] == "not_assessed"
    assert {(item["kind"], item["index"], item["status"]) for item in report["coverage"]["items"]} == {("method", 0, "not_addressed"), ("output", 0, "not_addressed")}


def test_plan_coverage_checks_real_artifacts_and_does_not_invent_human_acceptance(prepared):
    from eiqas_research.delivery import ReviewService

    reports, rid, run = finished(prepared)
    body = draft(run)
    body["plan_coverage"] = {
        "plan_hash": run["plan_hash"],
        "items": [{"kind": kind, "index": 0, "status": "completed", "explanation": "实际合计与所需输出一致", "run_ids": [run["id"]], "finding_indices": [0]} for kind in ["method", "output"]],
    }
    report = reports.submit(rid, body)
    assert report["coverage"]["status"] == "declared_complete"
    assert ReviewService(reports.evidence).latest(rid, report["id"])["status"] == "pending"
    before = digest(report)
    review = ReviewService(reports.evidence).record(rid, report["id"], status="needs_revision", comment="结果并未支撑研究计划", origin="codex_chat")
    assert review["status"] == "needs_revision" and review["actor"] == "user"
    assert digest(reports.evidence.get(rid, "result", report["id"])) == before


@pytest.mark.parametrize("bad", ["hash", "index", "duplicate", "foreign_run", "empty_completed", "dangling_finding"])
def test_coverage_cannot_claim_missing_or_foreign_work(prepared, bad):
    reports, rid, run = finished(prepared)
    body = draft(run)
    item = {"kind": "method", "index": 0, "status": "completed", "explanation": "实际计算", "run_ids": [run["id"]]}
    coverage = {"plan_hash": run["plan_hash"], "items": [item]}
    if bad == "hash":
        coverage["plan_hash"] = "old"
    if bad == "index":
        item["index"] = 99
    if bad == "duplicate":
        coverage["items"].append(dict(item))
    if bad == "foreign_run":
        item["run_ids"] = ["foreign"]
    if bad == "empty_completed":
        item["run_ids"] = []
    if bad == "dangling_finding":
        item["finding_indices"] = [999]
    body["plan_coverage"] = coverage
    with pytest.raises((ValueError, LookupError)):
        reports.submit(rid, body)


def test_evidence_table_is_located_frozen_and_in_every_narrative_export(prepared):
    from eiqas_research.delivery import EvidenceTableService
    from eiqas_research.exporter import ExportService

    reports, rid, run = finished(prepared)
    saved = EvidenceTableService(reports.evidence).save(rid, table(reports, rid))
    body = draft(run)
    body["table_ids"] = [saved["id"]]
    report = reports.submit(rid, body)
    assert report["tables"][0]["rows"][0]["evidence"][0]["locator"]["key"] == "line:1"
    exports = ExportService(reports.evidence)
    for kind in ["html", "md"]:
        text = exports.build(rid, report["id"], kind).read_text()
        assert "通用证据对照" in text and "原件为100" in text
        assert "未核对方案" in text
    with zipfile.ZipFile(exports.build(rid, report["id"], "zip")) as archive:
        assert f"tables/{saved['id']}.csv" in archive.namelist()
        assert json.loads(archive.read("report.json"))["tables"][0]["content_hash"] == saved["content_hash"]


def test_evidence_table_rejects_unsupported_claim_and_bad_location(prepared):
    from eiqas_research.delivery import EvidenceTableService

    reports, rid, _run = finished(prepared)
    service = EvidenceTableService(reports.evidence)
    body = table(reports, rid)
    body["rows"][0]["evidence"] = []
    with pytest.raises(Conflict):
        service.save(rid, body)
    body["rows"][0]["kind"] = "unknown"
    assert service.save(rid, body)["rows"][0]["kind"] == "unknown"
    body = table(reports, rid)
    body["rows"][0]["evidence"][0]["locator_key"] = "not-present"
    with pytest.raises(Conflict):
        service.save(rid, body)


def test_reader_feedback_is_a_scoped_web_action_and_survives_reopening(prepared):
    from eiqas_research.api import build_router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    reports, rid, run = finished(prepared)
    report = reports.submit(rid, draft(run))
    app = FastAPI()
    app.include_router(build_router(reports.evidence.research))
    with TestClient(app) as client:
        url = f"/api/eiqas/research/{rid}/results/{report['id']}/review"
        assert client.get(url).json()["status"] == "pending"
        assert client.post(url, json={"status": "needs_revision", "comment": "需要补齐原方案"}).status_code == 200
        assert client.get(f"/api/eiqas/research/{rid}/records/results/{report['id']}").json()["review"]["status"] == "needs_revision"
        assert client.post(url.replace(rid, "foreign"), json={"status": "accepted", "comment": "跨项目"}).status_code == 404
        assert reports.evidence.get(rid, "result", report["id"])["run"]["status"] == "verified"


def test_native_table_tool_is_bounded_and_cannot_accept_its_own_report(prepared, monkeypatch):
    from types import SimpleNamespace

    from eiqas_research import tools

    reports, rid, run = finished(prepared)
    monkeypatch.setattr(tools, "current", lambda runtime: (reports.evidence.research, rid))
    runtime = SimpleNamespace()
    saved = tools.eiqas_save_evidence_table.func(table(reports, rid), runtime)
    assert saved["row_count"] == 1 and "rows" not in saved
    read = tools.eiqas_read_records.func("evidence_table", runtime, record_id=saved["id"])
    assert read["rows"][0]["values"]["answer"] == "原件为100"
    assert "locator" not in read["rows"][0]["evidence"][0]
    assert not hasattr(tools, "eiqas_accept_result")
    result = reports.submit(rid, draft(run))
    assert tools.eiqas_read_result.func(result["id"], runtime)["review"]["status"] == "pending"


def test_auxiliary_run_is_packaged_and_tampering_fails_export(prepared):
    from eiqas_research.exporter import ExportService

    reports, rid, run = finished(prepared)
    from test_eiqas_runs import receipt

    service, _rid, dataset, _plan = prepared
    auxiliary = service.start_run(rid, dataset["id"], {"method": "aggregate", "parameters": {"group_by": ["subject", "period", "metric", "unit"]}}, native_run_id="second-run")
    auxiliary = service.complete_run(rid, auxiliary["id"], receipt(service, rid, dataset, auxiliary), log="Independent second actual fixture run")
    body = draft(run)
    body["plan_coverage"] = {"plan_hash": run["plan_hash"], "items": [{"kind": "output", "index": 0, "status": "partial", "explanation": "仅部分产出", "run_ids": [auxiliary["id"]]}]}
    report = reports.submit(rid, body)
    with zipfile.ZipFile(ExportService(reports.evidence).build(rid, report["id"], "zip")) as archive:
        assert f"runs/{auxiliary['id']}/script.py" in archive.namelist()
    assert report["auxiliary_runs"][0]["id"] == auxiliary["id"]
    path = reports.evidence.directory(rid) / "runs" / auxiliary["id"] / "script.py"
    path.write_text("tampered")
    with pytest.raises(Conflict):
        ExportService(reports.evidence).build(rid, report["id"], "html")


def test_submit_tool_separates_calculation_fulfillment_and_reader_review(prepared, monkeypatch):
    from types import SimpleNamespace

    from eiqas_research import tools
    from eiqas_research.reports import ReportDraft

    reports, rid, run = finished(prepared)
    monkeypatch.setattr(tools, "current", lambda runtime: (reports.evidence.research, rid))
    response = tools.eiqas_submit_result.func(ReportDraft.model_validate(draft(run)), SimpleNamespace())
    assert response["calculation_status"] == "verified"
    assert response["plan_fulfillment"] == "not_assessed"
    assert response["reader_review"] == "pending"
    assert "status" not in response


def test_gateway_rejects_ignored_denominator_before_creating_a_run(prepared):
    service, rid, dataset, plan = prepared
    service.evidence.research.confirm_plan(rid, plan["hash"])
    with pytest.raises(ValueError, match="total_metric"):
        service.start_run(rid, dataset["id"], {"method": "structure", "parameters": {"metric": "收入", "total_metric": "收入"}}, native_run_id=None)
    assert service.evidence.list(rid, "run") == []
