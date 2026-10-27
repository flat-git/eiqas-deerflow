"""Native config-defined tools use exactly the same service as the web UI."""

import asyncio

from langchain.tools import ToolRuntime, tool

from .analysis import AnalysisService
from .evidence import EvidenceService
from .models import Plan
from .plugin import active_service, thread_id
from .reports import ReportDraft, ReportService
from .sandbox_jobs import execute_job


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
def eiqas_save_plan(plan: Plan, runtime: ToolRuntime) -> dict:
    """Save a question-led plan (question, methods[{name,rationale,operation}], required_data, assumptions, outputs, limitations). User confirms through the workbench."""
    service, rid = current(runtime)
    return service.save_plan(rid, Plan.model_validate(plan))


@tool
def eiqas_update_scope(answerable: list[str], gaps: list[str], runtime: ToolRuntime) -> dict:
    """Record what evidence can answer and what remains missing; this does not mark a research successful."""
    service, rid = current(runtime)
    return service.update_scope(rid, answerable=answerable, gaps=gaps)


@tool
def eiqas_acquire_source(url: str, title: str, organization: str, runtime: ToolRuntime) -> dict:
    """Download an actual public original with URL/title/organization, preserving failures. Search snippets cannot be used as numeric evidence."""
    from .acquisition import acquire_source

    service, rid = current(runtime)
    service.require_confirmed(rid)
    result = acquire_source(EvidenceService(service), rid, url, title, organization)
    service.set_stage(rid, "data")
    return result


@tool
async def eiqas_parse_source(source_id: str, runtime: ToolRuntime) -> dict:
    """Parse a current-research original in its native AIO sandbox (PDF/OCR, web, CSV, Excel, JSON). Save complete locators; use inspect_extraction for relevant blocks."""
    from deerflow.sandbox.tools import ensure_sandbox_initialized_async

    service, rid = await asyncio.to_thread(current, runtime)
    await asyncio.to_thread(service.require_confirmed, rid)
    evidence = await asyncio.to_thread(EvidenceService, service)
    source = await asyncio.to_thread(evidence.get, rid, "source", source_id)
    path = await asyncio.to_thread(evidence.original, rid, source_id)
    data = await asyncio.to_thread(path.read_bytes)
    job = None
    try:
        sandbox = await ensure_sandbox_initialized_async(runtime)
        job = asyncio.create_task(asyncio.to_thread(execute_job, sandbox, "parse", data, source["media_type"]))
        result, _log = await asyncio.shield(job)
        if result.get("status") == "failed":
            raise ValueError(result.get("error", "解析失败"))
        extraction = await asyncio.to_thread(evidence.register_extraction, rid, source_id, result)
        return {"id": extraction["id"], "source_id": source_id, "block_count": len(result["blocks"]), "page_count": result["page_count"], "engine": result["engine"], "sample_blocks": result["blocks"][:10]}
    except asyncio.CancelledError:
        if job is not None:
            try:
                await asyncio.shield(job)
            except Exception:
                pass
        raise
    except Exception as exc:
        failure = await asyncio.to_thread(evidence.put, rid, "extraction", {"source_id": source_id, "source_hash": source["sha256"], "status": "failed", "sha256": None, "result": {"blocks": [], "page_count": None, "error": str(exc)}})
        return failure


@tool
def eiqas_inspect_extraction(extraction_id: str, query: str, runtime: ToolRuntime, offset: int = 0, limit: int = 25) -> dict:
    """Read located original text/table cells, filtered by a literal keyword (empty reads all), with pagination. Retain returned block keys as observation locators."""
    service, rid = current(runtime)
    record = EvidenceService(service).get(rid, "extraction", extraction_id)
    blocks = [block for block in record["result"]["blocks"] if query.casefold() in block["text"].casefold()]
    offset, limit = max(0, offset), max(1, min(100, limit))
    return {"extraction_id": extraction_id, "total_matches": len(blocks), "blocks": blocks[offset : offset + limit], "next_offset": offset + limit if offset + limit < len(blocks) else None}


@tool
def eiqas_add_observations(observations: list[dict], runtime: ToolRuntime) -> dict:
    """Register candidate numeric facts. Each requires source_id, extraction_id, locator_key, raw_text, value, unit, subject, period, metric, qualifier (exact/about/more_than/less_than/range). OCR/uncertain values require human review."""
    service, rid = current(runtime)
    service.require_confirmed(rid)
    if not 1 <= len(observations) <= 200:
        raise ValueError("每次登记1—200条候选数据")
    evidence = EvidenceService(service)
    saved, errors = [], []
    for index, data in enumerate(observations):
        try:
            saved.append(evidence.add_observation(rid, data))
        except (ValueError, LookupError) as exc:
            errors.append({"index": index, "error": str(exc)})
    return {"observations": saved, "errors": errors}


@tool
def eiqas_create_dataset(title: str, observation_ids: list[str], runtime: ToolRuntime) -> dict:
    """Freeze verified observations into a computational dataset; reject conflicts, duplicates or mixed units. Keep source snapshots for replay."""
    service, rid = current(runtime)
    service.require_confirmed(rid)
    dataset = EvidenceService(service).create_dataset(rid, title, observation_ids)
    return {key: dataset[key] for key in ["id", "title", "input_hash", "rows"]}


@tool
async def eiqas_execute(dataset_id: str, method: str, parameters: dict, runtime: ToolRuntime) -> dict:
    """Run actual analysis in the thread's AIO sandbox. Methods: aggregate, growth, structure, contribution, correlation, cost_benefit, sensitivity, python.
    Growth/structure/contribution need metric; contribution also from/to periods; correlation needs x/y metrics; scenarios accept discount_rate or
    discount_rates. Never call a failed or unexecuted result verified.
    Python parameters: code, check_code, arguments(optional). Calculation CLI: python analysis.py input.json output.json;
    input contains dataset/arguments. Output: rows, provenance[list of input observation IDs per row], limitations, optional partial status.
    Independent CLI: python check.py input.json output.json checks.json. Write checks[{name,row,column,expected}]; every numeric result cell
    must be covered. The worker compares actual/expected itself. sensitivity is cost-benefit discount-rate analysis only.
    """
    from deerflow.sandbox.tools import ensure_sandbox_initialized_async

    service, rid = await asyncio.to_thread(current, runtime)
    evidence = await asyncio.to_thread(EvidenceService, service)
    analysis = AnalysisService(evidence)
    context = getattr(runtime, "context", None) or {}
    run = await asyncio.to_thread(analysis.start_run, rid, dataset_id, {"method": method, "parameters": parameters}, native_run_id=context.get("run_id"))
    job = None
    try:
        sandbox = await ensure_sandbox_initialized_async(runtime)
        plan = await asyncio.to_thread(service.require_confirmed, rid)
        if plan["hash"] != run["plan_hash"]:
            raise ValueError("研究方案已更新，请确认后重新运行")
        directory = await asyncio.to_thread(analysis.run_directory, rid, run["id"])
        data = await asyncio.to_thread((directory / "input.json").read_bytes)
        job = asyncio.create_task(asyncio.to_thread(execute_job, sandbox, "analyze", data))
        output, log = await asyncio.shield(job)
        return await asyncio.to_thread(analysis.complete_run, rid, run["id"], output, log=log)
    except asyncio.CancelledError:
        await asyncio.to_thread(analysis.stop_run, rid, run["id"], "cancelled", "原生运行已取消，迟到结果不会提升为成功")
        if job is not None:
            try:
                await asyncio.shield(job)
            except Exception:
                pass
        raise
    except Exception as exc:
        return await asyncio.to_thread(analysis.stop_run, rid, run["id"], "failed", str(exc))


@tool
def eiqas_submit_result(report: ReportDraft, runtime: ToolRuntime) -> dict:
    """Submit findings/charts bound to one checked actual run. Key numeric cells are row/column references, never invented values. Qualitative evidence uses
    exact source/extraction/locator/quote. Return the independent reader URL; conversation edits create a new result.
    """
    service, rid = current(runtime)
    result = ReportService(EvidenceService(service)).submit(rid, report.model_dump())
    research = service.get(rid)
    return {"id": result["id"], "run_id": result["run_id"], "status": result["run"]["status"], "reader_url": f"/research/{research['thread_id']}/results/{result['id']}", "scope": result["scope"], "limitations": result["limitations"]}


@tool
def eiqas_read_result(result_id: str, runtime: ToolRuntime) -> dict:
    """Read a current-thread result for conversation edits. Save revisions with submit_result; recomputation requires execute and creates a new run. Returns draft fields and checked rows."""
    service, rid = current(runtime)
    result = EvidenceService(service).get(rid, "result", result_id)
    draft = {key: result[key] for key in ReportDraft.model_fields}
    draft["findings"] = [{key: value for key, value in finding.items() if key in {"text", "kind", "observation_ids", "cells", "evidence"}} for finding in draft["findings"]]
    for finding in draft["findings"]:
        finding["cells"] = [{"row": cell["row"], "column": cell["column"]} for cell in finding["cells"]]
        finding["evidence"] = [{key: value for key, value in ref.items() if key in {"source_id", "extraction_id", "locator_key", "quote", "explanation"}} for ref in finding["evidence"]]
    draft["charts"] = [{key: value for key, value in chart.items() if key != "unit"} for chart in draft["charts"]]
    return {"draft": draft, "rows": result["run"]["result"]["rows"], "scope": result["scope"], "spec": result["run"]["spec"]}
