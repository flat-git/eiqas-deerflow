"""Offline delivery uses one checked report and explicit, hash-checked materials."""

import json
import zipfile

import pytest
from eiqas_research.exporter import ExportService
from eiqas_research.service import Conflict
from test_eiqas_reports import draft, finished
from test_eiqas_runs import prepared as prepared


def test_offline_html_markdown_csv_and_zip_share_results(prepared):
    reports, rid, run = finished(prepared)
    result = reports.submit(rid, draft(run))
    exports = ExportService(reports.evidence)
    html = exports.build(rid, result["id"], "html").read_text()
    assert "echarts" in html and "合成研究结果" in html
    assert "<script src=" not in html
    assert "100" in exports.build(rid, result["id"], "csv").read_text(encoding="utf-8-sig")
    assert "合成研究结果" in exports.build(rid, result["id"], "md").read_text()
    package = exports.build(rid, result["id"], "zip")
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        assert "index.html" in names and "report.md" in names
        assert {"dependencies/ZRENDER-LICENSE", "dependencies/D3-LICENSE", "dependencies/TSLIB-LICENSE"}.issubset(names)
        assert any(name.endswith("/script.py") for name in names)
        assert any(name.startswith("sources/") and "original" in name for name in names)
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["report_id"] == result["id"]
        assert manifest["run_id"] == run["id"]
        assert not any(".env" in name or ".sqlite" in name or ".." in name for name in names)
        assert all(f"sources/{source['id']}/" in archive.read("index.html").decode() for source in result["sources"])


def test_export_rejects_modified_materials(prepared):
    reports, rid, run = finished(prepared)
    result = reports.submit(rid, draft(run))
    directory = reports.evidence.directory(rid) / "runs" / run["id"]
    (directory / "result.csv").write_text("forged")
    with pytest.raises(Conflict):
        ExportService(reports.evidence).build(rid, result["id"], "zip")


def test_untrusted_report_text_cannot_escape_html_script(prepared):
    reports, rid, run = finished(prepared)
    body = draft(run)
    body["summary"] = "</script><script>window.fakeAttack=true</script>"
    result = reports.submit(rid, body)
    html = ExportService(reports.evidence).build(rid, result["id"], "html").read_text()
    assert "</script><script>window.fakeAttack=true</script>" not in html
    assert "\\u003c/script" in html
