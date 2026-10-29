"""Synthetic manufacturing research: feasible redesign precedes final approval."""

import copy

import pytest
from eiqas_research.analysis import AnalysisService
from eiqas_research.evidence import EvidenceService
from eiqas_research.models import Plan, ResearchCreate
from eiqas_research.planning import DataAssessment, PlanningService
from eiqas_research.service import Conflict, ResearchService, digest


def design_plan(question="良率改善能否节约成本？"):
    return Plan.model_validate(
        {
            "question": question,
            "decision_use": "判断是否值得进一步投入产线改善",
            "scope": "同一产线，2024—2025；先核实公开披露，金额测算取决于内部数据",
            "research_questions": [{"id": "q-yield", "text": "良率发生了什么变化？"}, {"id": "q-cost", "text": "可节约多少成本？"}],
            "question_decisions": [{"question_id": "q-yield", "status": "answer", "explanation": "可以描述年度变化"}, {"question_id": "q-cost", "status": "unanswerable", "explanation": "缺少内部成本与产量，不能估造金额"}],
            "data_constraints": ["本次仅有公开披露，没有内部成本和批次数据"],
            "scope_changes": ["保留原成本问题，当前仅执行良率变化分析，金额测算无法完成"],
            "methods": [
                {
                    "id": "m-yield",
                    "name": "年度良率变化",
                    "rationale": "量化公开披露的变化",
                    "operation": "growth",
                    "role": "primary",
                    "selected": True,
                    "question_ids": ["q-yield"],
                    "basis": "同口径比例的年度变化",
                    "calculation": "本年良率减上年良率，同时标明百分点与相对增幅的差别",
                    "applicability": "同一产线和良率定义；不支持因果解释",
                    "expected_outputs": ["年度变化图"],
                },
                {
                    "id": "m-cost",
                    "name": "成本收益情景",
                    "rationale": "测算改善可能节约的成本",
                    "operation": "cost_benefit",
                    "role": "primary",
                    "selected": False,
                    "question_ids": ["q-cost"],
                    "basis": "成本与收益的显式情景比较",
                    "calculation": "节约金额减改善投入",
                    "applicability": "需要内部产量、单位成本和投入",
                    "expected_outputs": ["情景表"],
                },
            ],
            "data_requirements": [
                {
                    "id": "d-yield",
                    "title": "年度良率",
                    "method_ids": ["m-yield"],
                    "kind": "quantitative",
                    "required": True,
                    "category": "public",
                    "fields": ["主体", "期间", "良率"],
                    "metrics": ["良率"],
                    "grain": "产线×年度",
                    "period": "2024—2025",
                    "units": "%",
                    "channels": ["公司公开报告"],
                    "impact_if_missing": "不能比较良率变化",
                    "fallback": "保留无法判断，不用集团营收替代",
                },
                {
                    "id": "d-cost",
                    "title": "成本与投入",
                    "method_ids": ["m-cost"],
                    "kind": "quantitative",
                    "required": True,
                    "category": "internal",
                    "fields": ["产量", "单位成本", "改善投入"],
                    "metrics": ["cost", "benefit"],
                    "grain": "产线×批次",
                    "period": "改善前后",
                    "units": "元",
                    "channels": ["生产和财务台账"],
                    "impact_if_missing": "不能测算节约金额",
                    "fallback": "取得后再研究",
                },
            ],
            "required_data": ["同口径年度良率"],
            "assumptions": ["年度披露定义一致"],
            "outputs": ["年度变化图"],
            "limitations": ["不能计算金额或判断因果"],
            "open_questions": [],
        }
    )


def add_synthetic_data(evidence, rid, metric="良率"):
    source = evidence.register_source(rid, url="https://example.org/synthetic-yield.txt", title="明确标注的合成样例", organization="test", content=b"2024: 90%; 2025: 95%", media_type="text/plain")
    extraction = evidence.register_extraction(rid, source["id"], {"engine": "synthetic", "page_count": None, "blocks": [{"key": "line:1", "text": "2024: 90%; 2025: 95%"}]})
    observations = [
        evidence.add_observation(
            rid,
            {
                "source_id": source["id"],
                "extraction_id": extraction["id"],
                "locator_key": "line:1",
                "raw_text": "2024: 90%; 2025: 95%",
                "value": value,
                "unit": "%",
                "subject": "产线A",
                "period": period,
                "metric": metric,
                "qualifier": "exact",
            },
        )
        for period, value in [("2024", "90"), ("2025", "95")]
    ]
    dataset = evidence.create_dataset(rid, "合成年度良率", [row["id"] for row in observations])
    ref = {"source_id": source["id"], "extraction_id": extraction["id"], "locator_key": "line:1", "quote": "2024: 90%; 2025: 95%", "explanation": "样例实际含年度良率；数据为合成，不是企业事实"}
    return dataset, ref


def assess_available(planning, rid, requirement_id, dataset, ref):
    requirement = next(item for item in planning.research.get(rid)["plan"]["content"]["data_requirements"] if item["id"] == requirement_id)
    return planning.assess(
        rid, DataAssessment(requirement_id=requirement_id, requirement_hash=digest(requirement), status="available", reason="已查看实际数据与口径", next_action="按批准方法计算", evidence=[ref], dataset_ids=[dataset["id"]])
    )


@pytest.fixture
def designed(tmp_path):
    research = ResearchService(tmp_path)
    rid = research.create(ResearchCreate(thread_id="manufacturing-design", question="良率改善能否节约成本？"))["id"]
    planning = PlanningService(EvidenceService(research))
    saved = research.save_plan(rid, design_plan())
    dataset, ref = add_synthetic_data(planning.evidence, rid)
    return research, planning, rid, saved, dataset, ref


def test_new_research_cannot_confirm_an_unexamined_prose_plan(tmp_path):
    research = ResearchService(tmp_path)
    rid = research.create(ResearchCreate(thread_id="new", question="研究问题"))["id"]
    plan = research.save_plan(rid, Plan(question="研究问题", methods=[{"name": "加总", "rationale": "算总量", "operation": "aggregate"}], required_data=["值"], outputs=["表"]))
    with pytest.raises(Conflict, match="研究设计|任务书"):
        research.confirm_plan(rid, plan["hash"])


def test_gap_categories_and_original_question_survive_feasible_redesign(designed):
    research, planning, rid, saved, dataset, ref = designed
    before = planning.inspect(rid)
    assert before["can_confirm"] is False
    assert before["requirements"][0]["status"] == "unknown"
    assess_available(planning, rid, "d-yield", dataset, ref)
    view = planning.inspect(rid)
    assert view["can_confirm"] is True
    assert view["requirements"][1]["category"] == "internal"
    assert view["methods"][1]["selected"] is False
    assert view["question_decisions"][1]["status"] == "unanswerable"
    assert research.get(rid)["question"] == "良率改善能否节约成本？"
    assert research.confirm_plan(rid, saved["hash"])["confirmed_at"]


@pytest.mark.parametrize("status", ["suggested", "located", "unavailable", "restricted", "quality_issue"])
def test_a_lead_or_gap_never_counts_as_available(designed, status):
    research, planning, rid, saved, _dataset, _ref = designed
    requirement = saved["content"]["data_requirements"][0]
    planning.assess(rid, DataAssessment(requirement_id="d-yield", requirement_hash=digest(requirement), status=status, reason="仅有渠道或存在问题", next_action="进一步核实", gap_types=["missing_values"]))
    assert not planning.inspect(rid)["can_confirm"]
    with pytest.raises(Conflict, match="数据"):
        research.confirm_plan(rid, saved["hash"])


def test_obtainable_public_data_requires_a_real_located_sample(designed):
    research, planning, rid, saved, _dataset, ref = designed
    requirement = saved["content"]["data_requirements"][0]
    payload = dict(requirement_id="d-yield", requirement_hash=digest(requirement), status="sample_checked", reason="已核实公开样本，完整提取待执行", next_action="取得完整年度序列")
    with pytest.raises(Conflict, match="定位|样本"):
        planning.assess(rid, DataAssessment(**payload))
    planning.assess(rid, DataAssessment(**payload, evidence=[ref]))
    assert planning.inspect(rid)["can_confirm"]
    research.confirm_plan(rid, saved["hash"])
    assert planning.inspect(rid)["requirements"][0]["status"] == "sample_checked"


def test_internal_or_expert_data_cannot_be_promised_from_a_sample(designed):
    research, planning, rid, saved, _dataset, ref = designed
    requirement = saved["content"]["data_requirements"][1]
    with pytest.raises(Conflict, match="内部|实际取得"):
        planning.assess(rid, DataAssessment(requirement_id="d-cost", requirement_hash=digest(requirement), status="sample_checked", reason="可能索取", next_action="索取", evidence=[ref]))


def test_available_claim_checks_data_metrics_and_current_original(designed):
    _research, planning, rid, _saved, dataset, ref = designed
    wrong_dataset, wrong_ref = add_synthetic_data(planning.evidence, rid, metric="营收")
    with pytest.raises(Conflict, match="指标"):
        assess_available(planning, rid, "d-yield", wrong_dataset, wrong_ref)
    assess_available(planning, rid, "d-yield", dataset, ref)
    planning.evidence.original(rid, ref["source_id"]).unlink()
    assert not planning.inspect(rid)["can_confirm"]


def test_cross_research_and_stale_requirement_evidence_are_rejected(designed):
    research, planning, rid, saved, dataset, ref = designed
    other = research.create(ResearchCreate(thread_id="other-design", question="其他研究"))["id"]
    research.save_plan(other, design_plan("其他研究"))
    with pytest.raises(LookupError):
        assess_available(planning, other, "d-yield", dataset, ref)
    payload = copy.deepcopy(saved["content"])
    payload["data_requirements"][0]["period"] = "2020—2025"
    research.save_plan(rid, Plan.model_validate(payload))
    with pytest.raises(Conflict, match="更新"):
        planning.assess(rid, DataAssessment(requirement_id="d-yield", requirement_hash=digest(saved["content"]["data_requirements"][0]), status="available", reason="旧评估", next_action="计算", evidence=[ref], dataset_ids=[dataset["id"]]))


def test_data_progress_does_not_revoke_approval_but_design_changes_do(designed):
    research, planning, rid, saved, dataset, ref = designed
    assess_available(planning, rid, "d-yield", dataset, ref)
    confirmed = research.confirm_plan(rid, saved["hash"])
    assess_available(planning, rid, "d-yield", dataset, ref)
    assert research.require_confirmed(rid)["confirmed_at"] == confirmed["confirmed_at"]
    changed = copy.deepcopy(saved["content"])
    changed["data_constraints"].append("改为包含专家估计")
    assert research.save_plan(rid, Plan.model_validate(changed))["confirmed_at"] is None


@pytest.mark.parametrize("mutation", ["missing_question_decision", "silent_scope_change", "no_primary", "selected_unavailable", "open_questions", "no_quantitative"])
def test_confirmation_checks_business_design_not_just_a_method_name(designed, mutation):
    research, planning, rid, saved, dataset, ref = designed
    assess_available(planning, rid, "d-yield", dataset, ref)
    data = copy.deepcopy(saved["content"])
    if mutation == "missing_question_decision":
        data["question_decisions"].pop()
    elif mutation == "silent_scope_change":
        data["scope_changes"] = []
    elif mutation == "no_primary":
        data["methods"][0]["role"] = "supporting"
    elif mutation == "selected_unavailable":
        data["methods"][1]["selected"] = True
    elif mutation == "open_questions":
        data["open_questions"] = ["良率定义是什么？"]
    else:
        data["methods"][0]["operation"] = "evidence_review"
    revised = research.save_plan(rid, Plan.model_validate(data))
    with pytest.raises(Conflict):
        research.confirm_plan(rid, revised["hash"])


def test_formal_run_uses_the_selected_method_and_its_actual_data(designed):
    research, planning, rid, saved, dataset, ref = designed
    assess_available(planning, rid, "d-yield", dataset, ref)
    research.confirm_plan(rid, saved["hash"])
    analysis = AnalysisService(planning.evidence)
    wrong_dataset, _wrong_ref = add_synthetic_data(planning.evidence, rid, "营收")
    with pytest.raises(Conflict, match="数据|指标"):
        analysis.start_run(rid, wrong_dataset["id"], {"method": "growth", "parameters": {"metric": "营收"}}, native_run_id="native")
    with pytest.raises(Conflict, match="方法"):
        analysis.start_run(rid, dataset["id"], {"method": "cost_benefit", "parameters": {}}, native_run_id="native")
    run = analysis.start_run(rid, dataset["id"], {"method": "growth", "parameters": {"metric": "良率"}}, native_run_id="native")
    assert run["method_id"] == "m-yield"


def test_human_request_is_persisted_and_only_a_reply_unblocks_it(designed):
    research, planning, rid, saved, dataset, ref = designed
    assess_available(planning, rid, "d-yield", dataset, ref)
    research.confirm_plan(rid, saved["hash"])
    request = planning.request_input(rid, kind="scope_change", questions=["两年的良率分母是否一致？"], impact="影响年度比较", requirement_ids=["d-yield"])
    assert planning.workflow(rid)["action"] == "needs_input"
    with pytest.raises(Conflict):
        planning.reply(rid, request["id"], request_hash="stale", response="一致")
    planning.reply(rid, request["id"], request_hash=request["content_hash"], response="请改为只研究2025，2024定义不同")
    assert planning.workflow(rid)["action"] != "needs_input"
    assert planning.pending_request(rid) is None
    assert planning.evidence.list(rid, "input_reply")[-1]["actor"] == "human"
    assert not research.get(rid)["plan"]["confirmed_at"]


def test_a_plan_revision_cannot_erase_a_pending_human_decision(designed):
    research, planning, rid, saved, _dataset, _ref = designed
    request = planning.request_input(rid, kind="critical_data", questions=["是否能补充内部数据？"], impact="决定研究范围", requirement_ids=["d-cost"])
    content = copy.deepcopy(saved["content"])
    content["limitations"].append("等待补数决定")
    research.save_plan(rid, Plan.model_validate(content))
    assert planning.pending_request(rid)["id"] == request["id"]


def test_http_planning_and_human_reply_are_scoped_and_stale_checked(designed):
    from eiqas_research.api import build_router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    research, planning, rid, _saved, _dataset, _ref = designed
    request = planning.request_input(rid, kind="critical_data", questions=["有什么数据？"], impact="决定方法", requirement_ids=[])
    app = FastAPI()
    app.include_router(build_router(research))
    with TestClient(app) as client:
        assert client.get(f"/api/eiqas/research/{rid}/planning").json()["workflow"]["action"] == "needs_input"
        url = f"/api/eiqas/research/{rid}/input-requests/{request['id']}/reply"
        assert client.post(url, json={"request_hash": "stale", "response": "仅公开"}).status_code == 409
        assert client.post(url, json={"request_hash": request["content_hash"], "response": "仅公开"}).status_code == 200
        assert client.post(url, json={"request_hash": request["content_hash"], "response": "重复"}).status_code == 409
        assert client.get("/api/eiqas/research/other/planning").status_code == 404


def test_native_public_acquisition_can_explore_before_approval(designed, monkeypatch):
    from types import SimpleNamespace

    from eiqas_research import acquisition, tools

    research, _planning, rid, _saved, _dataset, _ref = designed
    monkeypatch.setattr(tools, "current", lambda runtime: (research, rid))
    monkeypatch.setattr(acquisition, "acquire_source", lambda *args: {"status": "acquired", "id": "sample"})
    assert tools.eiqas_acquire_source.func("https://example.org/sample", "样本", "合成测试", SimpleNamespace())["status"] == "acquired"
    assert research.get(rid)["stage"] == "plan"
    assert research.get(rid)["plan"]["confirmed_at"] is None


def test_uploaded_original_is_thread_scoped_and_not_falsely_public(designed, tmp_path, monkeypatch):
    from types import SimpleNamespace

    from eiqas_research import tools

    from deerflow.config import paths

    research, planning, rid, _saved, _dataset, _ref = designed
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    (uploads / "internal.csv").write_text("metric,value\n良率,95", encoding="utf-8")
    monkeypatch.setattr(tools, "current", lambda runtime: (research, rid))
    monkeypatch.setattr(paths, "get_paths", lambda: SimpleNamespace(sandbox_uploads_dir=lambda *args, **kwargs: uploads))
    runtime = SimpleNamespace(context={"user_id": "owner", "thread_id": "manufacturing-design"})
    source = tools.eiqas_import_upload.func("internal.csv", runtime)
    assert source["origin"] == "upload" and source["url"] == ""
    assert planning.evidence.original(rid, source["id"]).read_text(encoding="utf-8").startswith("metric,value")
    for name in ["../outside", "/etc/passwd", "other.csv", "x\\y"]:
        with pytest.raises(ValueError):
            tools.eiqas_import_upload.func(name, runtime)


def test_plan_and_assessment_tools_return_fresh_gates_without_repeated_reads(designed, monkeypatch):
    from types import SimpleNamespace

    from eiqas_research import tools

    research, _planning, rid, saved, dataset, ref = designed
    monkeypatch.setattr(tools, "current", lambda runtime: (research, rid))
    result = tools.eiqas_save_plan.func(Plan.model_validate(saved["content"]), SimpleNamespace())
    assert result["design"]["can_confirm"] is False
    need = result["design"]["requirements"][0]
    response = tools.eiqas_assess_data.func(
        DataAssessment(requirement_id=need["id"], requirement_hash=need["requirement_hash"], status="available", reason="实际数据核对", next_action="等待最终确认", evidence=[ref], dataset_ids=[dataset["id"]]), SimpleNamespace()
    )
    assert response["design"]["can_confirm"] is True
    assert response["workflow"]["action"] == "confirm_plan"
    with pytest.raises(ValueError, match="更新"):
        tools.eiqas_read_planning.func(SimpleNamespace(), plan_hash="stale")
