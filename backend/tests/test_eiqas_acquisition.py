"""Acquisition stores originals, follows screened redirects and records failures."""

import ipaddress

import httpx
import pytest
from eiqas_research.acquisition import acquire_source
from eiqas_research.evidence import EvidenceService
from eiqas_research.models import ResearchCreate
from eiqas_research.service import ResearchService


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    from deerflow.community import url_safety

    monkeypatch.setattr(url_safety, "resolve_host_addresses", lambda hostname: [ipaddress.ip_address("8.8.8.8")])
    research = ResearchService(tmp_path)
    rid = research.create(ResearchCreate(thread_id="download-test", question="来源取得"))["id"]
    return EvidenceService(research), rid


def test_original_is_downloaded_and_retained(evidence):
    service, rid = evidence
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"a,b\n1,2\n", headers={"content-type": "text/csv"}))) as client:
        result = acquire_source(service, rid, "https://example.org/data.csv", "公开数据", "test", client=client)
    assert result["status"] == "acquired"
    assert service.original(rid, result["id"]).read_bytes() == b"a,b\n1,2\n"


def test_redirect_to_private_address_never_requested(evidence):
    service, rid = evidence
    requested = []

    def respond(request):
        requested.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = acquire_source(service, rid, "https://example.org/data", "来源", "test", client=client)
    assert len(requested) == 1
    assert result["status"] == "failed"
    assert result["sha256"] is None


def test_denied_and_empty_sources_are_not_evidence(evidence):
    service, rid = evidence
    for code in [403, 200]:
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(code, content=b""))) as client:
            result = acquire_source(service, rid, "https://example.org/data", "来源", "test", client=client)
        assert result["status"] in {"restricted", "failed"}
        assert result["sha256"] is None


def test_fake_ip_proxy_uses_public_resolution_and_pinned_tls_host(evidence, monkeypatch):
    from eiqas_research import acquisition

    from deerflow.community import url_safety

    service, rid = evidence
    monkeypatch.setattr(url_safety, "resolve_host_addresses", lambda hostname: [ipaddress.ip_address("198.18.0.226")])
    monkeypatch.setattr(acquisition, "resolve_public_doh", lambda hostname: [ipaddress.ip_address("104.18.23.19")])
    requested = []

    def respond(request):
        requested.append(request)
        return httpx.Response(200, content=b"public original", headers={"content-type": "text/plain"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = acquire_source(service, rid, "https://example.org/original", "Public source", "test", client=client)
    assert result["status"] == "acquired"
    assert requested[0].url.host == "104.18.23.19"
    assert requested[0].headers["Host"] == "example.org"
    assert requested[0].extensions["sni_hostname"] == "example.org"


def test_doh_private_answer_is_rejected_before_connection(evidence, monkeypatch):
    from eiqas_research import acquisition

    from deerflow.community import url_safety

    service, rid = evidence
    monkeypatch.setattr(url_safety, "resolve_host_addresses", lambda hostname: [ipaddress.ip_address("198.18.0.226")])
    monkeypatch.setattr(acquisition, "resolve_public_doh", lambda hostname: [ipaddress.ip_address("127.0.0.1")])

    def forbidden(request):
        raise AssertionError("private destination must never be requested")

    with httpx.Client(transport=httpx.MockTransport(forbidden)) as client:
        result = acquire_source(service, rid, "https://example.org/original", "Public source", "test", client=client)
    assert result["status"] == "failed"
