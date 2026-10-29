"""Native-loop continuation is bounded, scoped, and never manufactures success."""

from types import SimpleNamespace

import pytest
from eiqas_research import plugin
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from test_eiqas_design import add_synthetic_data, assess_available, design_plan


@pytest.mark.asyncio
async def test_native_advance_continues_missing_work_but_waits_for_human(tmp_path, monkeypatch):
    from eiqas_research.evidence import EvidenceService
    from eiqas_research.models import ResearchCreate
    from eiqas_research.planning import PlanningService
    from eiqas_research.service import ResearchService

    service = ResearchService(tmp_path)
    rid = service.create(ResearchCreate(thread_id="native", question="良率改善能否节约成本？"))["id"]
    saved = service.save_plan(rid, design_plan())
    planning = PlanningService(EvidenceService(service))
    dataset, ref = add_synthetic_data(planning.evidence, rid)
    assess_available(planning, rid, "d-yield", dataset, ref)
    service.confirm_plan(rid, saved["hash"])
    monkeypatch.setattr(plugin, "active_service", lambda: service)
    middleware = plugin.ResearchContext()
    runtime = SimpleNamespace(context={"thread_id": "native", "run_id": "run-a"})
    state = {"messages": [HumanMessage(content="继续", additional_kwargs={"eiqas_advance": True}), AIMessage(content="还需要计算")]}
    assert await middleware.aafter_model(state, runtime) == {"jump_to": "model"}
    assert await middleware.aafter_model(state, runtime) == {"jump_to": "model"}
    exhausted = await middleware.aafter_model(state, runtime)
    assert exhausted is None or exhausted.get("jump_to") is None
    assert planning.workflow(rid)["action"] != "delivered"
    assert len([e for e in service.events(rid) if e["kind"] == "workflow.continuation"]) == 2
    planning.request_input(rid, kind="critical_data", questions=["是否有完整数据？"], impact="不能继续", requirement_ids=["d-yield"])
    runtime.context["run_id"] = "run-b"
    assert await middleware.aafter_model(state, runtime) is None
    state["messages"][0] = HumanMessage(content="解释一下指标")
    assert await middleware.aafter_model(state, runtime) is None


@pytest.mark.asyncio
async def test_malformed_tool_calls_do_not_trigger_continuation(tmp_path, monkeypatch):
    monkeypatch.setattr(plugin, "active_service", lambda: (_ for _ in ()).throw(AssertionError("must not read business state")))
    middleware = plugin.ResearchContext()
    message = AIMessage(content="", invalid_tool_calls=[{"name": "bad", "args": "{", "id": "t", "error": "parse"}])
    assert await middleware.aafter_model({"messages": [HumanMessage(content="继续", additional_kwargs={"eiqas_advance": True}), message]}, SimpleNamespace()) is None


@pytest.mark.asyncio
async def test_draft_repairs_continue_but_native_safety_and_real_questions_stop(tmp_path, monkeypatch):
    from eiqas_research.evidence import EvidenceService
    from eiqas_research.models import ResearchCreate
    from eiqas_research.planning import PlanningService
    from eiqas_research.service import ResearchService

    service = ResearchService(tmp_path)
    rid = service.create(ResearchCreate(thread_id="draft", question="良率改善能否节约成本？"))["id"]
    service.save_plan(rid, design_plan())
    monkeypatch.setattr(plugin, "active_service", lambda: service)
    middleware = plugin.ResearchContext()
    runtime = SimpleNamespace(context={"thread_id": "draft", "run_id": "draft-run"})
    state = {
        "messages": [
            HumanMessage(content="完善方案"),
            ToolMessage(content="saved", name="eiqas_save_plan", tool_call_id="save"),
            HumanMessage(content="hidden reminder", additional_kwargs={"hide_from_ui": True}),
            AIMessage(content="是否要我补齐校验？"),
        ]
    }
    assert await middleware.aafter_model(state, runtime) == {"jump_to": "model"}
    runtime.context["stop_reason"] = "loop_capped"
    assert await middleware.aafter_model(state, runtime) is None
    runtime.context.pop("stop_reason")
    plan = design_plan().model_copy(update={"open_questions": ["是否允许购买报告？"]})
    service.save_plan(rid, plan)
    assert PlanningService(EvidenceService(service)).workflow(rid)["automatic"] is False
    assert await middleware.aafter_model(state, runtime) is None
