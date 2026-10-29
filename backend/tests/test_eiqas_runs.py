"""Execution receipts cannot be manufactured from Agent prose or process exits."""

import hashlib

import pytest
from eiqas_research.analysis import AnalysisService
from eiqas_research.evidence import EvidenceService
from eiqas_research.models import Plan, ResearchCreate
from eiqas_research.service import Conflict, ResearchService
from eiqas_research.worker import analyze


@pytest.fixture
def prepared(tmp_path):
    research = ResearchService(tmp_path)
    rid = research.create(ResearchCreate(thread_id="runs-thread", question="合成数据求和"))["id"]
    # Pre-design fixture isolates calculation/receipt invariants; v2 gates have separate tests.
    research._mutate(rid, "fixture.pre_design", {}, lambda body: body.update(workflow_version=1))
    p = research.save_plan(rid, Plan(question="合成数据求和", methods=[{"name": "聚合", "rationale": "求合计", "operation": "aggregate"}], required_data=["原始值"], outputs=["合计"]))
    evidence = EvidenceService(research)
    source = evidence.register_source(rid, url="https://example.org/synthetic.txt", title="合成数据", organization="test", content=b"100", media_type="text/plain")
    extraction = evidence.register_extraction(rid, source["id"], {"blocks": [{"key": "line:1", "text": "100", "ocr": False}], "page_count": None, "engine": "synthetic"})
    obs = evidence.add_observation(rid, dict(source_id=source["id"], extraction_id=extraction["id"], locator_key="line:1", raw_text="100", value="100", unit="元", subject="A", period="2024", metric="收入", qualifier="exact"))
    dataset = evidence.create_dataset(rid, "合成输入", [obs["id"]])
    return AnalysisService(evidence), rid, dataset, p


def start(prepared):
    service, rid, dataset, plan = prepared
    service.evidence.research.confirm_plan(rid, plan["hash"])
    run = service.start_run(rid, dataset["id"], {"method": "aggregate", "parameters": {}}, native_run_id="native-1")
    return service, rid, dataset, run


def receipt(service, rid, dataset, run):
    output = analyze(dataset, run["spec"])
    output.update(worker_sha256=run["worker_sha256"], request_sha256=run["request_sha256"])
    return output


def test_unconfirmed_never_starts(prepared):
    service, rid, dataset, _ = prepared
    with pytest.raises(Conflict):
        service.start_run(rid, dataset["id"], {"method": "aggregate", "parameters": {}}, native_run_id="native-1")
    assert service.evidence.list(rid, "run") == []


def test_real_inputs_scripts_results_and_checks_are_retained(prepared):
    service, rid, dataset, run = start(prepared)
    assert run["status"] == "running"
    files = service.run_directory(rid, run["id"])
    assert hashlib.sha256((files / "input.json").read_bytes()).hexdigest() == run["request_sha256"]
    assert hashlib.sha256((files / "script.py").read_bytes()).hexdigest() == run["worker_sha256"]
    completed = service.complete_run(rid, run["id"], receipt(service, rid, dataset, run), log="actual worker completed")
    assert completed["status"] == "verified"
    assert completed["native_run_id"] == "native-1"
    assert completed["output_hash"]
    assert (files / "result.csv").is_file()
    assert (files / "execution.log").read_text() == "actual worker completed"


@pytest.mark.parametrize("change", ["input_hash", "script_hash", "failed_check", "missing_check"])
def test_invalid_receipts_are_failed(prepared, change):
    service, rid, dataset, run = start(prepared)
    output = receipt(service, rid, dataset, run)
    if change == "input_hash":
        output["request_sha256"] = "wrong"
    if change == "script_hash":
        output["worker_sha256"] = "wrong"
    if change == "failed_check":
        output["checks"][0]["passed"] = False
    if change == "missing_check":
        output["checks"] = []
    completed = service.complete_run(rid, run["id"], output, log="worker output")
    assert completed["status"] == "failed"
    assert not completed.get("verified_at")


def test_cancellation_fences_late_result(prepared):
    service, rid, dataset, run = start(prepared)
    service.stop_run(rid, run["id"], "cancelled", "用户取消原生运行")
    late = service.complete_run(rid, run["id"], receipt(service, rid, dataset, run), log="late")
    assert late["status"] == "cancelled"


def test_restart_never_promotes_lost_execution_to_success(prepared):
    service, rid, _dataset, run = start(prepared)
    service.recover_interrupted()
    assert service.evidence.get(rid, "run", run["id"])["status"] == "interrupted"


def test_no_missing_sources_or_modified_input_can_run(prepared):
    service, rid, dataset, plan = prepared
    service.evidence.research.confirm_plan(rid, plan["hash"])
    source_id = dataset["observations"][0]["source_id"]
    service.evidence.original(rid, source_id).unlink()
    with pytest.raises(Conflict):
        service.start_run(rid, dataset["id"], {"method": "aggregate", "parameters": {}}, native_run_id="native-1")
