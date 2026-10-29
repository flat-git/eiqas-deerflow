"""Direct page reading retains evidence and uses the same native sandbox parser."""

from types import SimpleNamespace

import pytest
from eiqas_research import tools
from eiqas_research.evidence import EvidenceService
from eiqas_research.models import Plan, ResearchCreate
from eiqas_research.service import ResearchService


@pytest.fixture
def context(tmp_path, monkeypatch):
    service = ResearchService(tmp_path)
    research = service.create(ResearchCreate(thread_id="web-thread", question="公开网页研究"))
    rid = research["id"]
    service._mutate(rid, "fixture.pre_design", {}, lambda body: body.update(workflow_version=1))
    plan = service.save_plan(rid, Plan(question="公开网页研究", methods=[{"name": "阅读原件", "operation": "evidence_review", "rationale": "取得可回查的证据"}], required_data=["公开原件"], assumptions=[], outputs=["依据"], limitations=[]))
    service.confirm_plan(rid, plan["hash"])
    monkeypatch.setattr(tools, "current", lambda runtime: (service, rid))
    return service, rid, SimpleNamespace()


@pytest.mark.asyncio
async def test_fetch_downloads_and_parses_before_returning_located_text(context, monkeypatch):
    from eiqas_research import acquisition

    service, rid, runtime = context
    evidence = EvidenceService(service)
    calls = []

    def acquire(evidence, rid, url, title, organization):
        calls.append(url)
        return evidence.register_source(rid, url=url, title=title, organization=organization, content=b"<p>1200</p>", media_type="text/html", retrieved_url="https://example.org/reports/index.html")

    async def parse(source_id, runtime):
        assert evidence.original(rid, source_id).read_bytes() == b"<p>1200</p>"
        return evidence.register_extraction(
            rid,
            source_id,
            {
                "blocks": [{"key": "web:0", "text": "1200", "ocr": False}, {"key": "web:link:0", "text": "年报", "href": "files/report.pdf"}, {"key": "web:link:1", "text": "坏链接", "href": "javascript:alert(1)"}],
                "page_count": None,
                "engine": "synthetic-native-parser",
            },
        )

    monkeypatch.setattr(acquisition, "acquire_source", acquire)
    monkeypatch.setattr(tools, "_parse_source", parse)
    result = await tools.web_fetch_public.coroutine("https://example.org/start", runtime)
    assert result["status"] == "acquired"
    assert result["source_id"] and result["extraction_id"]
    assert result["blocks"][0] == {"key": "web:0", "text": "1200"}
    assert result["links"] == [{"locator_key": "web:link:0", "text": "年报", "url": "https://example.org/reports/files/report.pdf"}]
    assert calls == ["https://example.org/start"]


@pytest.mark.asyncio
async def test_fetch_retains_failures_and_allows_new_scope_discovery_before_approval(context, monkeypatch):
    from eiqas_research import acquisition

    service, rid, runtime = context
    monkeypatch.setattr(acquisition, "acquire_source", lambda evidence, rid, url, title, organization: evidence.record_source_failure(rid, url=url, title=title, organization=organization, reason="HTTP 403", status="restricted"))
    failed = await tools.web_fetch_public.coroutine("https://example.org/denied", runtime)
    assert failed["status"] == "restricted" and failed["reason"] == "HTTP 403"
    service.update_question(rid, "目标改变")
    result = await tools.web_fetch_public.coroutine("https://example.org/denied", runtime)
    assert result["status"] == "restricted"
    assert service.get(rid)["plan"]["confirmed_at"] is None


def test_web_fetch_native_schema_hides_runtime():
    assert tools.web_fetch_public.name == "web_fetch"
    assert "runtime" not in tools.web_fetch_public.tool_call_schema.model_json_schema()["properties"]
