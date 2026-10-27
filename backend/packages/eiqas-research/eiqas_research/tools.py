"""Native config-defined tools use exactly the same service as the web UI."""

from langchain.tools import ToolRuntime, tool

from .models import Plan
from .plugin import active_service, thread_id


def current(runtime):
    service = active_service()
    research = service.for_thread(thread_id(runtime))
    if research is None:
        raise ValueError("先在 EIQAS 工作台建立本线程研究")
    return service, research["id"]


@tool
def eiqas_read_research(runtime: ToolRuntime) -> dict:
    """Read the current thread's question, plan, confirmation, scope and data gaps."""
    service, rid = current(runtime)
    return service.get(rid)


@tool
def eiqas_save_plan(plan: dict, runtime: ToolRuntime) -> dict:
    """Save a question-led plan (question, methods[{name,rationale}], required_data, assumptions, outputs, limitations). User confirms through the workbench."""
    service, rid = current(runtime)
    return service.save_plan(rid, Plan.model_validate(plan))


@tool
def eiqas_update_scope(answerable: list[str], gaps: list[str], runtime: ToolRuntime) -> dict:
    """Record what evidence can answer and what remains missing; this does not mark a research successful."""
    service, rid = current(runtime)
    return service.update_scope(rid, answerable=answerable, gaps=gaps)
