"""HTTP actions. Sync endpoints run domain I/O in FastAPI's thread pool."""

import csv
import io
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

from .delivery import ReviewRequest, ReviewService
from .evidence import EvidenceService
from .models import Confirmation, ObservationCorrection, Plan, QuestionUpdate, ResearchCreate, ScopeUpdate, StageUpdate
from .planning import DataAssessment, InputReply, PlanningService
from .service import Conflict, NotFound, ResearchService


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def build_router(service: ResearchService) -> APIRouter:
    router = APIRouter(prefix="/api/eiqas", tags=["eiqas"])

    @router.get("/research")
    def list_research():
        return service.list()

    @router.post("/research", status_code=201)
    def create_research(body: ResearchCreate):
        return _call(service.create, body)

    @router.get("/research/{rid}")
    def get_research(rid: str):
        return _call(service.get, rid)

    @router.patch("/research/{rid}/question")
    def update_question(rid: str, body: QuestionUpdate):
        return _call(service.update_question, rid, body.question)

    @router.put("/research/{rid}/plan")
    def save_plan(rid: str, body: Plan):
        return _call(service.save_plan, rid, body)

    @router.post("/research/{rid}/confirm")
    def confirm_plan(rid: str, body: Confirmation):
        return _call(service.confirm_plan, rid, body.plan_hash)

    @router.patch("/research/{rid}/stage")
    def set_stage(rid: str, body: StageUpdate):
        return _call(service.set_stage, rid, body.stage)

    @router.patch("/research/{rid}/scope")
    def update_scope(rid: str, body: ScopeUpdate):
        return _call(service.update_scope, rid, **body.model_dump())

    @router.get("/research/{rid}/events")
    def events(rid: str, after: Annotated[int, Query(ge=0)] = 0):
        return _call(service.events, rid, after)

    def evidence():
        return EvidenceService(service)

    @router.get("/research/{rid}/planning")
    def planning_status(rid: str):
        planning = PlanningService(evidence())
        return _call(lambda: {"design": planning.inspect(rid), "workflow": planning.workflow(rid)})

    @router.post("/research/{rid}/data-assessments")
    def assess_data(rid: str, body: DataAssessment):
        return _call(PlanningService(evidence()).assess, rid, body)

    @router.post("/research/{rid}/input-requests/{request_id}/reply")
    def reply_input(rid: str, request_id: str, body: InputReply):
        return _call(PlanningService(evidence()).reply, rid, request_id, **body.model_dump())

    @router.post("/research/{rid}/results/{result_id}/review")
    def review_result(rid: str, result_id: str, body: ReviewRequest):
        return _call(ReviewService(evidence()).record, rid, result_id, **body.model_dump())

    @router.get("/research/{rid}/results/{result_id}/review")
    def get_review(rid: str, result_id: str):
        return _call(ReviewService(evidence()).latest, rid, result_id)

    @router.patch("/research/{rid}/observations/{oid}")
    def correct_observation(rid: str, oid: str, body: ObservationCorrection):
        return _call(evidence().correct_observation, rid, oid, **body.model_dump())

    @router.get("/research/{rid}/sources/{sid}/original")
    def original(rid: str, sid: str):
        path = _call(evidence().original, rid, sid)
        return FileResponse(path, media_type="application/octet-stream", filename=f"source-{sid}.bin", headers={"X-Content-Type-Options": "nosniff"})

    def preview_record(rid: str, sid: str, page: int):
        e = evidence()
        path = _call(e.original, rid, sid)
        with path.open("rb") as handle:
            if handle.read(5) != b"%PDF-":
                raise HTTPException(409, "该来源不是 PDF，请查看摘录或下载原件")
        extractions = [x for x in _call(e.list, rid, "extraction") if x["source_id"] == sid and x.get("sha256")]
        count = extractions[-1]["result"].get("page_count") if extractions else None
        if not count:
            raise HTTPException(409, "该来源尚无 PDF 物理页预览，请查看摘录或下载原件")
        if page > count:
            raise HTTPException(422, "物理页码超出原件范围")
        return path, count

    @router.get("/research/{rid}/sources/{sid}/preview-info")
    def preview_info(rid: str, sid: str, page: Annotated[int, Query(ge=1)] = 1):
        _path, count = preview_record(rid, sid, page)
        return {"page": page, "page_count": count}

    @router.get("/research/{rid}/sources/{sid}/preview")
    def preview(rid: str, sid: str, page: Annotated[int, Query(ge=1)] = 1):
        path, _count = preview_record(rid, sid, page)
        return FileResponse(path, media_type="application/pdf", filename="source.pdf", content_disposition_type="inline", headers={"X-Content-Type-Options": "nosniff"})

    @router.get("/research/{rid}/datasets/{did}/csv")
    def dataset_csv(rid: str, did: str):
        dataset = _call(evidence().get, rid, "dataset", did)
        output = io.StringIO()
        rows = dataset["rows"]
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        return Response("\ufeff" + output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="dataset-{did}.csv"'})

    @router.get("/research/{rid}/runs/{run_id}/files/{filename}")
    def run_file(rid: str, run_id: str, filename: Literal["input.json", "script.py", "execution.log", "result.json", "result.csv", "analysis.py", "check.py"]):
        from .analysis import AnalysisService

        path = _call(AnalysisService(evidence()).run_directory, rid, run_id) / filename
        if not path.is_file():
            raise HTTPException(404, "该运行尚未产生此文件")
        return FileResponse(path, media_type="application/octet-stream", filename=filename)

    @router.get("/research/{rid}/exports/{report_id}/{format}")
    def export_result(rid: str, report_id: str, format: Literal["html", "md", "csv", "zip"]):
        from .exporter import ExportService

        path = _call(ExportService(evidence()).build, rid, report_id, format)
        media = {"html": "text/html", "md": "text/markdown", "csv": "text/csv", "zip": "application/zip"}
        return FileResponse(path, media_type=media[format], filename=f"eiqas-{report_id}.{format}", headers={"X-Content-Type-Options": "nosniff"})

    collections = {"sources": "source", "extractions": "extraction", "observations": "observation", "datasets": "dataset", "runs": "run", "results": "result", "evidence-tables": "evidence_table"}

    @router.get("/research/{rid}/records/{collection}")
    def list_records(rid: str, collection: Literal["sources", "extractions", "observations", "datasets", "runs", "results", "evidence-tables"]):
        e = evidence()
        records = _call(e.list, rid, collections[collection])
        return [{**record, "review": ReviewService(e).latest(rid, record["id"])} for record in records] if collection == "results" else records

    @router.get("/research/{rid}/records/{collection}/{record_id}")
    def get_record(rid: str, collection: Literal["sources", "extractions", "observations", "datasets", "runs", "results", "evidence-tables"], record_id: str):
        e = evidence()
        record = _call(e.get, rid, collections[collection], record_id)
        return {**record, "review": ReviewService(e).latest(rid, record_id)} if collection == "results" else record

    return router
