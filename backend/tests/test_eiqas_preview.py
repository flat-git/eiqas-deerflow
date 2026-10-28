"""Physical-page preflight returns actionable errors before embedding a PDF."""

from eiqas_research.api import build_router
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_eiqas_evidence import evidence as evidence


def test_preview_validates_original_and_physical_page(evidence):
    e, rid = evidence
    s = e.register_source(rid, url="https://example.org/test.pdf", title="Synthetic PDF metadata test", organization="test", content=b"%PDF-synthetic fixture", media_type="application/pdf")
    e.register_extraction(rid, s["id"], {"blocks": [{"key": "p1", "text": "Synthetic test", "page": 1}], "page_count": 1, "engine": "test"})
    app = FastAPI()
    app.include_router(build_router(e.research))
    with TestClient(app) as client:
        route = f"/api/eiqas/research/{rid}/sources/{s['id']}/preview-info"
        assert client.get(route + "?page=1").json()["page_count"] == 1
        assert client.get(route + "?page=2").status_code == 422
        e.original(rid, s["id"]).unlink()
        response = client.get(route)
        assert response.status_code == 409
        assert "缺失" in response.json()["detail"]
