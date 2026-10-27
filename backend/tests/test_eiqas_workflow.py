"""Business invariants: confirmation is human-owned and bound to current intent."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from eiqas_research.api import build_router
from eiqas_research.models import Plan, ResearchCreate
from eiqas_research.service import Conflict, ResearchService
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def service(tmp_path):
    return ResearchService(tmp_path)


@pytest.fixture
def research(service):
    return service.create(ResearchCreate(thread_id="thread-a", question="收入变化由什么驱动？"))


def plan():
    return Plan(question="收入变化由什么驱动？", methods=[{"name": "变化贡献", "rationale": "分解业务变化"}], required_data=["各业务收入及期间"], assumptions=[], outputs=["贡献图"], limitations=["关联不能证明因果"])


def test_create_unique_thread_and_persist(service, research, tmp_path):
    assert research["stage"] == "question"
    assert research["status"] == "draft"
    assert "progress" not in research
    with pytest.raises(Conflict):
        service.create(ResearchCreate(thread_id="thread-a", question="另一个问题"))
    assert ResearchService(tmp_path).get(research["id"])["question"] == research["question"]


def test_plan_confirmation_binds_current_revision(service, research):
    rid = research["id"]
    saved = service.save_plan(rid, plan())
    with pytest.raises(Conflict, match="确认"):
        service.require_confirmed(rid)
    with pytest.raises(Conflict, match="更新"):
        service.confirm_plan(rid, "stale-hash")
    confirmed = service.confirm_plan(rid, saved["hash"])
    assert confirmed["confirmed_at"]
    assert service.require_confirmed(rid)["hash"] == saved["hash"]
    # A byte-equivalent save does not demand another confirmation.
    assert service.save_plan(rid, plan())["confirmed_at"] == confirmed["confirmed_at"]
    changed = plan().model_copy(update={"required_data": ["新口径数据"]})
    assert service.save_plan(rid, changed)["confirmed_at"] is None
    with pytest.raises(Conflict):
        service.require_confirmed(rid)


def test_question_change_revokes_confirmation(service, research):
    rid = research["id"]
    p = service.save_plan(rid, plan())
    service.confirm_plan(rid, p["hash"])
    service.update_question(rid, "哪个业务利润变化？")
    with pytest.raises(Conflict):
        service.require_confirmed(rid)
    # Re-confirming an old question cannot approve a changed research objective.
    with pytest.raises(Conflict, match="问题"):
        service.confirm_plan(rid, p["hash"])


def test_reentrant_stages_and_events_survive_refresh(service, research, tmp_path):
    rid = research["id"]
    service.set_stage(rid, "review")
    service.set_stage(rid, "data")
    events = ResearchService(tmp_path).events(rid, after=0)
    assert [event["kind"] for event in events] == ["research.created", "stage.changed", "stage.changed"]
    assert events[-1]["payload"]["stage"] == "data"
    assert service.events(rid, after=events[-1]["seq"]) == []


def test_partial_and_gaps_are_separate_from_execution(service, research):
    row = service.update_scope(research["id"], answerable=["收入趋势"], gaps=["未披露 AI 收入"])
    assert row["answerable"] == ["收入趋势"]
    assert row["gaps"] == ["未披露 AI 收入"]
    assert row["status"] == "draft"


def test_parallel_writes_keep_events_ordered(service, research):
    rid = research["id"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: service.set_stage(rid, "data"), range(12)))
    events = service.events(rid)
    assert len(events) == 13
    assert len({event["seq"] for event in events}) == 13


@pytest.mark.parametrize("thread_id", ["../other", "/tmp/x", "", "a/b", "a\\b"])
def test_reject_unsafe_thread_identifiers(thread_id):
    with pytest.raises(ValueError):
        ResearchCreate(thread_id=thread_id, question="问题")


def test_http_contract_errors_and_confirmation(service, research):
    app = FastAPI()
    app.include_router(build_router(service))
    with TestClient(app) as client:
        rid = research["id"]
        assert client.get("/api/eiqas/research/missing").status_code == 404
        assert client.patch(f"/api/eiqas/research/{rid}/stage", json={"stage": "invented"}).status_code == 422
        p = client.put(f"/api/eiqas/research/{rid}/plan", json=plan().model_dump()).json()
        assert client.post(f"/api/eiqas/research/{rid}/confirm", json={"plan_hash": "old"}).status_code == 409
        result = client.post(f"/api/eiqas/research/{rid}/confirm", json={"plan_hash": p["hash"]})
        assert result.status_code == 200
        assert result.json()["confirmed_at"]
        assert client.get(f"/api/eiqas/research/{rid}/events?after=0").json()[-1]["kind"] == "plan.confirmed"


def test_thread_isolation(service, research):
    b = service.create(ResearchCreate(thread_id="thread-b", question="成本与收益？"))
    service.save_plan(research["id"], plan())
    assert service.get(b["id"])["plan"] is None
    assert len(service.events(b["id"])) == 1


def test_corrupt_critical_plan_is_rejected():
    with pytest.raises(ValueError):
        Plan(question="问题", methods=[], required_data=[], outputs=[], assumptions=[], limitations=[])
