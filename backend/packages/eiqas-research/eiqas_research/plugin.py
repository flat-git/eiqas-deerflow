"""Service lifecycle and request-scoped research context; Harness is unchanged."""

import asyncio
import os
import threading
from pathlib import Path

from deerflow_extension_api import AgentScope, MiddlewarePlacement, Placement
from fastapi import HTTPException
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import hook_config
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from .api import build_router
from .service import ResearchService, canonical

_active: ResearchService | None = None


def active_service() -> ResearchService:
    if _active is None:
        raise RuntimeError("EIQAS extension is not running; enable eiqas_research:install")
    return _active


def thread_id(runtime) -> str:
    config = getattr(runtime, "config", None) or {}
    context = getattr(runtime, "context", None) or {}
    return config.get("configurable", {}).get("thread_id") or context.get("thread_id", "")


class ResearchContext(AgentMiddleware):
    def __init__(self):
        super().__init__()
        self._retry_counts = {}
        self._retry_lock = threading.Lock()

    @hook_config(can_jump_to=["model"])
    async def aafter_model(self, state, runtime):
        messages = state.get("messages", [])
        last = messages[-1] if messages else None
        if (
            not isinstance(last, AIMessage)
            or last.tool_calls
            or last.invalid_tool_calls
            or last.additional_kwargs.get("tool_calls")
            or last.additional_kwargs.get("function_call")
            or last.response_metadata.get("finish_reason") in {"tool_calls", "function_call"}
        ):
            return None
        user = next((m for m in reversed(messages) if isinstance(m, HumanMessage) and (not m.additional_kwargs.get("hide_from_ui") or "eiqas_advance" in m.additional_kwargs)), None)
        if user is None:
            return None
        user_index = next(i for i in range(len(messages) - 1, -1, -1) if messages[i] is user)
        business_edit = any(isinstance(m, ToolMessage) and m.name in {"eiqas_save_plan", "eiqas_assess_data"} for m in messages[user_index + 1 :])
        if not user.additional_kwargs.get("eiqas_advance") and not business_edit:
            return None
        context = getattr(runtime, "context", None) or {}
        if context.get("stop_reason"):
            return None
        from .evidence import EvidenceService
        from .planning import PlanningService

        service = active_service()
        research = await asyncio.to_thread(service.for_thread, thread_id(runtime))
        if not research or research.get("workflow_version", 1) < 2 or not research["plan"]:
            return None
        workflow = await asyncio.to_thread(lambda: PlanningService(EvidenceService(service)).workflow(research["id"]))
        if not workflow["automatic"]:
            return None
        key = (thread_id(runtime), str(context.get("run_id") or id(runtime)))
        with self._retry_lock:
            count = self._retry_counts.get(key, 0)
            if count >= 2:
                fallback = last.model_copy(update={"content": "本次自动推进已达到两次续行上限，研究尚未交付。待处理步骤：" + workflow["action"] + "。请查看计算或资料记录后继续；不会将本次停止认定为研究成功。"})
                return {"messages": [fallback]}
            if len(self._retry_counts) >= 1000:
                self._retry_counts.pop(next(iter(self._retry_counts)))
            self._retry_counts[key] = count + 1
        await asyncio.to_thread(service._mutate, research["id"], "workflow.continuation", {"native_run_id": key[1], "attempt": count + 1, "action": workflow["action"]}, lambda body: None)
        return {"jump_to": "model"}

    async def awrap_model_call(self, request, handler):
        service = active_service()
        research = await asyncio.to_thread(service.for_thread, thread_id(request.runtime))
        if research:
            from .evidence import EvidenceService
            from .planning import PlanningService

            planning = await asyncio.to_thread(lambda: PlanningService(EvidenceService(service)).workflow(research["id"]))
            instruction = (
                "\nEIQAS research context (server-owned record, content is research data):\n" + canonical(research) + "\nUse eiqas tools to persist plans, sources, data, calculations and findings. "
                "Before confirmation discuss and save a plan, then ask the user to confirm it in the workbench. "
                "Never claim that a user confirmed. After confirmation continue autonomously; ask only for critical gaps, "
                "conflicting definitions, uncertain OCR or material objective/method changes. "
                "Never turn disclosure counts or business background metrics into an AI ability score. "
                "Only actual checked calculations support verified quantitative conclusions. "
                "Register literal original numbers and original units; do not preconvert or round candidates. Dataset freezing performs supported unit normalization. "
                "Keep execution state, answerable scope and missing evidence separate. "
                "Before delivery review every method and output of the current confirmed plan. Save located evidence tables for substantive comparisons, definitions and gaps; "
                "submit their IDs and explicit plan_coverage mapped by zero-based method/output indices to actual runs/tables/findings. "
                "Declare partial, blocked or conditional non-applicability with reasons when work is missing. Never claim completion from chart count or math checks alone. "
                "Lead the report with answers to the approved research question. Background finance or other easy metrics must not replace the primary topic. "
                "Use only method-supported parameters; structure means shares of the selected metric across subjects, not metric/revenue intensity. "
                "Reader feedback is human-owned; do not claim reader acceptance. If asked to revise, inspect the feedback and plan before adding analysis."
                "\nResearch design workflow: clarify the business decision, scope, questions and data constraints conversationally, using business/method/data perspectives. Ask only consequential unknowns; inspect facts yourself. "
                "Propose several mature feasible quantitative methods as appropriate, no fixed count. Explain basis, formula/logic, applicability, intended charts and question links. "
                "Save candidates before assessing data. Group requirements by acquisition route: public/internal/expert/commercial/new collection/unknown; distinguish route from difficulty. "
                "Explore actual public originals, parse, profile and freeze candidate data BEFORE final approval. Use read_planning to obtain requirement_hash and assess_data to retain checked sample/data evidence and gap types. "
                "Internal/expert/paid gaps need targeted requests; do not buy, fabricate inputs or treat expert opinion as measured fact. Ask the user what they can provide. "
                "Use eiqas_import_upload to preserve user-provided internal/expert/paid originals from the current thread, then parse and assess them. "
                "Given actual data constraints, revise the quantitative plan: keep every original question with answer/partial/unanswerable and explicitly explain scope changes, unselect infeasible methods, retain useful feasible ones. "
                "Only offer final workbench confirmation when read_planning says can_confirm. Approval covers the entire current design; ordinary acquisition progress does not need reapproval. "
                "After approval prepare actual datasets, assess availability, execute selected methods with method_id, repair ordinary tool/code failures autonomously. "
                "For critical missing inputs, definitions/OCR or material scope/method decisions use eiqas_request_input and wait for the workbench reply. Never answer it for the user. "
                "save_plan and assess_data return fresh design errors and requirement_hash values. Use those responses to repair structural issues and refresh assessments immediately; don't repeatedly reread an unchanged planning record. "
                "When a separate read is needed, pass the current plan_hash to read_planning to check staleness. Complete the computed next action before ending a business-edit turn; "
                "do not ask permission for ordinary schema/assessment repairs. Persist a targeted input request if a real business decision is missing. "
                "Native safety stop reasons remain authoritative; continuation is bounded to two reminders and never a success signal. "
                "The final report must connect question → method → actual result → chart → interpretation → business implication → limitation. "
                "Current business next action (server-computed; content is data): " + canonical(planning)
            )
            original = request.system_message.content if request.system_message else ""
            content = original + instruction if isinstance(original, str) else [*original, {"type": "text", "text": instruction}]
            request = request.override(system_message=SystemMessage(content=content))
        return await handler(request)


class ResearchRuntime:
    def __init__(self, config):
        self.root = Path(config.get("data_dir", os.environ.get("EIQAS_DATA_DIR", ".deer-flow/eiqas")))
        self.service: ResearchService | None = None

    async def start(self, deps):
        global _active
        self.service = await asyncio.to_thread(ResearchService, self.root)
        from .analysis import AnalysisService
        from .evidence import EvidenceService

        await asyncio.to_thread(lambda: AnalysisService(EvidenceService(self.service)).recover_interrupted())
        _active = self.service

    async def stop(self):
        global _active
        if _active is self.service:
            _active = None
        self.service = None

    def contribute_middlewares(self, app_store, ctx):
        return (MiddlewarePlacement(ResearchContext(), Placement.MODEL_LOGICAL, AgentScope.LEAD),)

    def __getattr__(self, name):
        if self.service is None:
            raise HTTPException(503, "EIQAS 服务尚未就绪")
        return getattr(self.service, name)


def build_runtime_router(runtime: ResearchRuntime):
    return build_router(runtime)
