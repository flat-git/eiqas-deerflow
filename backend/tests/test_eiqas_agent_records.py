"""Native tools can resume from persisted records without exposing other threads."""

from types import SimpleNamespace

import pytest
from eiqas_research import tools
from eiqas_research.evidence import EvidenceService
from eiqas_research.models import ResearchCreate
from eiqas_research.service import NotFound, ResearchService


def test_records_are_scoped_paginated_and_extractions_are_bounded(tmp_path, monkeypatch):
    service = ResearchService(tmp_path)
    rid = service.create(ResearchCreate(thread_id="resumable", question="数据恢复"))["id"]
    other = service.create(ResearchCreate(thread_id="other", question="其他研究"))["id"]
    evidence = EvidenceService(service)
    first = evidence.register_source(rid, url="https://example.org/one", title="One", organization="test", content=b"1200", media_type="text/plain")
    evidence.register_source(rid, url="https://example.org/two", title="Two", organization="test", content=b"1500", media_type="text/plain")
    foreign = evidence.register_source(other, url="https://example.org/foreign", title="Foreign", organization="test", content=b"999", media_type="text/plain")
    extraction = evidence.register_extraction(rid, first["id"], {"blocks": [{"key": "line:1", "text": "1200" * 20000}], "page_count": None, "engine": "synthetic"})
    monkeypatch.setattr(tools, "current", lambda runtime: (service, rid))
    runtime = SimpleNamespace()
    page = tools.eiqas_read_records.func("source", runtime, limit=1)
    assert page["records"][0]["id"] == first["id"] and page["next_offset"] == 1
    assert page["total"] == 2
    assert tools.eiqas_read_records.func("source", runtime, offset=1)["records"][0]["title"] == "Two"
    with pytest.raises(NotFound):
        tools.eiqas_read_records.func("source", runtime, record_id=foreign["id"])
    parsed = tools.eiqas_read_records.func("extraction", runtime, record_id=extraction["id"])
    assert parsed["block_count"] == 1 and "blocks" not in parsed
    assert "runtime" not in tools.eiqas_read_records.tool_call_schema.model_json_schema()["properties"]
