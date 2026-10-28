import pytest
from eiqas_research.service import Conflict
from test_eiqas_runs import prepared as prepared


def test_material_method_change_requires_plan_confirmation(prepared):
    service, rid, dataset, plan = prepared
    service.evidence.research.confirm_plan(rid, plan["hash"])
    with pytest.raises(Conflict, match="方法"):
        service.start_run(rid, dataset["id"], {"method": "growth", "parameters": {"metric": "收入"}}, native_run_id="native-change")
