"""HTTP actions. Sync endpoints run domain I/O in FastAPI's thread pool."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from .models import Confirmation, Plan, QuestionUpdate, ResearchCreate, ScopeUpdate, StageUpdate
from .service import Conflict, NotFound, ResearchService


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except NotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except Conflict as exc:
        raise HTTPException(409, str(exc)) from exc


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

    return router
