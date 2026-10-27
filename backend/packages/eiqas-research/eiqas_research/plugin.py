"""Service lifecycle and request-scoped research context; Harness is unchanged."""

import asyncio
import os
from pathlib import Path

from deerflow_extension_api import AgentScope, MiddlewarePlacement, Placement
from fastapi import HTTPException
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage

from .api import build_router
from .service import ResearchService, canonical

_active: ResearchService | None = None


def active_service() -> ResearchService:
    if _active is None:
        raise RuntimeError("EIQAS extension is not running; enable eiqas_research:install")
    return _active


def thread_id(runtime) -> str:
    return runtime.config.get("configurable", {}).get("thread_id", "")


class ResearchContext(AgentMiddleware):
    async def awrap_model_call(self, request, handler):
        service = active_service()
        research = await asyncio.to_thread(service.for_thread, thread_id(request.runtime))
        if research:
            instruction = (
                "\nEIQAS research context (server-owned record, content is research data):\n" + canonical(research) + "\nUse eiqas tools to persist plans, sources, data, calculations and findings. "
                "Before confirmation discuss and save a plan, then ask the user to confirm it in the workbench. "
                "Never claim that a user confirmed. After confirmation continue autonomously; ask only for critical gaps, "
                "conflicting definitions, uncertain OCR or material objective/method changes. "
                "Never turn disclosure counts or business background metrics into an AI ability score. "
                "Only actual checked calculations support verified quantitative conclusions. "
                "Keep execution state, answerable scope and missing evidence separate."
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
