"""Generated methods execute two real programs with independently checked cells."""

import pytest
from eiqas_research.worker import analyze

CODE = """import json, sys
data=json.load(open(sys.argv[1]))["dataset"]["rows"]
json.dump({"rows":[{"metric":"double", "value":float(data[0]["value"])*2,"unit":"count"}],"provenance":[[data[0]["observation_id"]]],"limitations":["synthetic custom method"]},open(sys.argv[2],"w"))
"""
CHECK = """import json, sys
from decimal import Decimal
data=json.load(open(sys.argv[1]))["dataset"]["rows"]
json.dump({"checks":[{"name":"independent Decimal multiplication","row":0,"column":"value","expected":float(Decimal(data[0]["value"])+Decimal(data[0]["value"]))}]},open(sys.argv[3],"w"))
"""


def dataset():
    return {"rows": [{"subject": "sample", "period": "2025", "metric": "x", "value": "12.5", "unit": "count", "observation_id": "obs-1"}]}


def test_custom_code_and_independent_check_really_execute():
    result = analyze(dataset(), {"method": "python", "parameters": {"code": CODE, "check_code": CHECK}})
    assert result["rows"][0]["value"] == 25
    assert result["checks"][0]["actual"] == 25
    assert result["checks"][0]["expected"] == 25
    assert result["provenance"] == [["obs-1"]]
    assert result["status"] == "verified"


@pytest.mark.parametrize("bad", ["failed_check", "missing_check", "uncovered_number", "foreign_lineage", "no_lineage", "exception"])
def test_bad_custom_results_cannot_be_verified(bad):
    code, checker = CODE, CHECK
    if bad == "failed_check":
        checker = CHECK.replace('Decimal(data[0]["value"])+Decimal(data[0]["value"])', "Decimal(999)")
    if bad == "missing_check":
        checker = 'import json,sys;json.dump({"checks":[]},open(sys.argv[3],"w"))'
    if bad == "uncovered_number":
        code = CODE.replace('"value":float', '"uncovered":77,"value":float')
    if bad == "foreign_lineage":
        code = CODE.replace('[data[0]["observation_id"]]', '["foreign"]')
    if bad == "no_lineage":
        code = CODE.replace('[[data[0]["observation_id"]]]', "[]")
    if bad == "exception":
        code = 'raise RuntimeError("actual calculation failed")'
    with pytest.raises(ValueError):
        analyze(dataset(), {"method": "python", "parameters": {"code": code, "check_code": checker}})


def test_custom_scripts_need_finite_serializable_output():
    code = 'import json,sys;json.dump({"rows":[{"value":float("inf")}],"provenance":[["obs-1"]]},open(sys.argv[2],"w"))'
    with pytest.raises(ValueError):
        analyze(dataset(), {"method": "python", "parameters": {"code": code, "check_code": CHECK}})


def test_checker_format_error_explains_required_object_and_attests_failed_execution(tmp_path, monkeypatch):
    import hashlib
    import json

    from eiqas_research import worker

    checker = 'import json,sys;json.dump([{ "name":"bad root" }],open(sys.argv[3],"w"))'
    request = tmp_path / "request.json"
    output = tmp_path / "result.json"
    request.write_text(json.dumps({"dataset": dataset(), "spec": {"method": "python", "parameters": {"code": CODE, "check_code": checker}}}))
    monkeypatch.setattr(worker.sys, "argv", ["worker.py", "analyze", "--input", str(request), "--output", str(output)])
    assert worker.main() == 1
    result = json.loads(output.read_text())
    assert result["status"] == "failed"
    assert "checks.json" in result["error"] and '{"checks":' in result["error"]
    assert result["request_sha256"] == hashlib.sha256(request.read_bytes()).hexdigest()
    assert result["worker_sha256"] == hashlib.sha256(__import__("pathlib").Path(worker.__file__).read_bytes()).hexdigest()
