"""Reports bind checked rows and frozen input provenance, never Agent numbers."""

import pytest
from eiqas_research.reports import ReportService
from eiqas_research.service import Conflict
from test_eiqas_runs import prepared as prepared
from test_eiqas_runs import receipt, start


def draft(run):
    return {
        "run_id": run["id"],
        "title": "合成研究结果",
        "summary": "合计为100元。",
        "findings": [{"text": "合计为100元。", "kind": "fact", "cells": [{"row": 0, "column": "value"}], "observation_ids": []}],
        "charts": [{"id": "total", "title": "收入合计", "type": "bar", "x": "metric", "y": "value"}],
        "implications": ["只用于流程验收"],
        "limitations": ["合成数据，不代表企业表现"],
    }


def finished(prepared):
    service, rid, dataset, run = start(prepared)
    run = service.complete_run(rid, run["id"], receipt(service, rid, dataset, run), log="actual worker completed")
    return ReportService(service.evidence), rid, run


def test_report_values_and_scope_come_from_checked_run(prepared):
    reports, rid, run = finished(prepared)
    reports.evidence.research.update_scope(rid, answerable=["合计"], gaps=["无法推断实际商业成效"])
    result = reports.submit(rid, draft(run))
    assert result["run"]["output_hash"] == run["output_hash"]
    assert result["findings"][0]["cells"][0]["value"] == 100
    assert result["findings"][0]["cells"][0]["unit"] == "CNY"
    assert result["scope"]["gaps"] == ["无法推断实际商业成效"]
    assert result["sources"][0]["sha256"]


@pytest.mark.parametrize("bad", ["row", "column", "observation", "chart", "missing_evidence"])
def test_dangling_or_untraceable_report_is_rejected(prepared, bad):
    reports, rid, run = finished(prepared)
    body = draft(run)
    if bad == "row":
        body["findings"][0]["cells"][0]["row"] = 999
    if bad == "column":
        body["findings"][0]["cells"][0]["column"] = "subject"
    if bad == "observation":
        body["findings"][0]["observation_ids"] = ["foreign"]
    if bad == "chart":
        body["charts"][0]["y"] = "invented"
    if bad == "missing_evidence":
        body["findings"][0]["cells"] = []
    with pytest.raises((ValueError, Conflict)):
        reports.submit(rid, body)


def test_unexecuted_and_modified_materials_cannot_be_delivered(prepared):
    service, rid, _dataset, run = start(prepared)
    reports = ReportService(service.evidence)
    with pytest.raises(Conflict):
        reports.submit(rid, draft(run))
    service.stop_run(rid, run["id"], "failed", "actual failure")
    with pytest.raises(Conflict):
        reports.submit(rid, draft(run))


def test_export_uses_frozen_observation_after_correction(prepared):
    reports, rid, run = finished(prepared)
    dataset = reports.evidence.get(rid, "dataset", run["dataset_id"])
    reports.evidence.correct_observation(rid, dataset["rows"][0]["observation_id"], value="200", unit="元", reason="后续纠正，不能改写原计算输入")
    result = reports.submit(rid, draft(run))
    assert result["dataset"]["rows"][0]["value"] == "100"
    assert result["findings"][0]["cells"][0]["value"] == 100


def test_source_or_artifact_tampering_blocks_report(prepared):
    reports, rid, run = finished(prepared)
    source = reports.evidence.list(rid, "source")[0]
    reports.evidence.original(rid, source["id"]).write_bytes(b"changed")
    with pytest.raises(Conflict):
        reports.submit(rid, draft(run))


def test_qualitative_finding_can_cite_located_text_outside_numeric_dataset(prepared):
    reports, rid, run = finished(prepared)
    text = "公司自报推出智能家庭方案，但未单独披露其收入。"
    source = reports.evidence.register_source(rid, url="https://example.org/statement", title="合成公司表述", organization="test", content=text.encode(), media_type="text/plain")
    extraction = reports.evidence.register_extraction(rid, source["id"], {"blocks": [{"key": "p1", "text": text, "ocr": False}], "page_count": None, "engine": "synthetic"})
    body = draft(run)
    body["findings"].append(
        {
            "text": "公司自报已有家庭场景应用，实际商业成效仍不可判断。",
            "kind": "company_reported",
            "evidence": [{"source_id": source["id"], "extraction_id": extraction["id"], "locator_key": "p1", "quote": text, "explanation": "披露表明有应用表述，未提供独立成效数据。"}],
        }
    )
    report = reports.submit(rid, body)
    assert len(report["sources"]) == 2
    assert report["findings"][-1]["evidence"][0]["quote"] == text
    body["findings"][-1]["evidence"][0]["quote"] = "来源没有说过的话"
    with pytest.raises(Conflict):
        reports.submit(rid, body)


def test_chart_filters_select_actual_rows_and_reject_empty_selection(prepared):
    reports, rid, run = finished(prepared)
    body = draft(run)
    metric = run["result"]["rows"][0]["metric"]
    body["charts"][0]["filters"] = {"metric": metric}
    result = reports.submit(rid, body)
    assert result["charts"][0]["filters"] == {"metric": metric}
    body["charts"][0]["filters"] = {"metric": "not present"}
    with pytest.raises(Conflict):
        reports.submit(rid, body)


def test_report_rechecks_frozen_dataset_content(prepared):
    from eiqas_research.service import canonical

    reports, rid, run = finished(prepared)
    dataset = reports.evidence.get(rid, "dataset", run["dataset_id"])
    dataset["rows"][0]["value"] = "999"
    with reports.evidence.research._connection() as db, db:
        db.execute("UPDATE records SET body=? WHERE id=?", (canonical(dataset), dataset["id"]))
    with pytest.raises(Conflict):
        reports.submit(rid, draft(run))
