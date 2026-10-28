"""Provenance, data preparation and correction regressions with synthetic inputs."""

from decimal import Decimal

import pytest
from eiqas_research.evidence import EvidenceService
from eiqas_research.models import ResearchCreate
from eiqas_research.service import Conflict, NotFound, ResearchService


@pytest.fixture
def evidence(tmp_path):
    research = ResearchService(tmp_path)
    row = research.create(ResearchCreate(thread_id="data-thread", question="收入趋势"))
    return EvidenceService(research), row["id"]


def source(e, rid, text="收入 1,200 万元", ocr=False):
    s = e.register_source(rid, url="https://example.org/report.txt", title="合成报告", organization="测试机构", content=text.encode(), media_type="text/plain")
    x = e.register_extraction(rid, s["id"], {"blocks": [{"key": "p1-b1", "text": text, "page": 1, "ocr": ocr}], "page_count": 1, "engine": "synthetic-test"})
    return s, x


def observation(e, rid, s, x, **changes):
    body = dict(source_id=s["id"], extraction_id=x["id"], locator_key="p1-b1", raw_text="收入 1,200 万元", value="1200", unit="万元", subject="样例公司", period="2024", metric="收入", qualifier="exact")
    return e.add_observation(rid, {**body, **changes})


def test_source_hash_and_physical_location(evidence):
    e, rid = evidence
    s, x = source(e, rid)
    assert e.original(rid, s["id"]).read_bytes() == "收入 1,200 万元".encode()
    obs = observation(e, rid, s, x)
    assert obs["status"] == "verified"
    assert obs["locator"]["page"] == 1
    assert obs["source_hash"] == s["sha256"]
    e.original(rid, s["id"]).write_text("tampered")
    with pytest.raises(Conflict, match="完整性"):
        e.original(rid, s["id"])


def test_cross_research_and_invalid_locator_rejected(evidence):
    e, rid = evidence
    s, x = source(e, rid)
    other = e.research.create(ResearchCreate(thread_id="other", question="另一个问题"))
    with pytest.raises(NotFound):
        observation(e, other["id"], s, x)
    with pytest.raises(Conflict, match="定位"):
        observation(e, rid, s, x, locator_key="p999")
    with pytest.raises(Conflict, match="摘录"):
        observation(e, rid, s, x, raw_text="不存在的披露")


@pytest.mark.parametrize("updates,flag", [({"value": "9999"}, "number_mismatch"), ({"unit": ""}, "unit_missing"), ({"qualifier": "more_than"}, "qualified_number")])
def test_uncertain_data_goes_to_review(evidence, updates, flag):
    e, rid = evidence
    s, x = source(e, rid)
    obs = observation(e, rid, s, x, **updates)
    assert obs["status"] == "review"
    assert flag in obs["flags"]
    with pytest.raises(Conflict):
        e.create_dataset(rid, "不能使用未核实的数据", [obs["id"]])


def test_ocr_correction_requires_human_reason_and_keeps_original(evidence):
    e, rid = evidence
    s, x = source(e, rid, text="收入 l,200 万元", ocr=True)
    obs = observation(e, rid, s, x, raw_text="收入 l,200 万元")
    assert "ocr_requires_review" in obs["flags"]
    with pytest.raises(ValueError):
        e.correct_observation(rid, obs["id"], value="1200", unit="万元", reason="")
    fixed = e.correct_observation(rid, obs["id"], value="1200", unit="万元", reason="逐页核对原件，l 应为 1")
    assert fixed["status"] == "verified"
    assert fixed["raw_text"] == "收入 l,200 万元"
    assert fixed["corrections"][-1]["actor"] == "human"
    assert fixed["corrections"][-1]["before"]["status"] == "review"


def test_dataset_normalizes_units_and_freezes_input(evidence):
    e, rid = evidence
    s, x = source(e, rid)
    a = observation(e, rid, s, x)
    s2, x2 = source(e, rid, text="收入 0.15 亿元")
    b = observation(e, rid, s2, x2, raw_text="收入 0.15 亿元", value="0.15", unit="亿元", period="2025")
    dataset = e.create_dataset(rid, "收入序列", [a["id"], b["id"]])
    assert [Decimal(row["value"]) for row in dataset["rows"]] == [Decimal("12000000"), Decimal("15000000")]
    assert {row["unit"] for row in dataset["rows"]} == {"CNY"}
    e.correct_observation(rid, a["id"], value="1300", unit="万元", reason="核对原件修正")
    assert e.get(rid, "dataset", dataset["id"])["rows"][0]["value"] == "12000000"
    assert dataset["input_hash"]


def test_duplicate_and_incompatible_units_rejected(evidence):
    e, rid = evidence
    s, x = source(e, rid)
    a = observation(e, rid, s, x)
    b = observation(e, rid, s, x)
    with pytest.raises(Conflict, match="重复"):
        e.create_dataset(rid, "重复记录", [a["id"], b["id"]])
    s2, x2 = source(e, rid, text="收入 1200 USD")
    c = observation(e, rid, s2, x2, raw_text="收入 1200 USD", unit="USD", period="2025")
    with pytest.raises(Conflict, match="口径"):
        e.create_dataset(rid, "混合货币", [a["id"], c["id"]])


def test_failed_acquisition_is_a_record_not_evidence(evidence):
    e, rid = evidence
    failed = e.record_source_failure(rid, url="https://example.org/missing", title="无法取得", organization="测试", reason="HTTP 403", status="restricted")
    assert failed["status"] == "restricted"
    assert failed["sha256"] is None
    with pytest.raises(Conflict):
        e.original(rid, failed["id"])


def test_invalid_pdf_page_and_cross_source_extraction(evidence):
    e, rid = evidence
    s, x = source(e, rid)
    with pytest.raises(Conflict, match="页码"):
        e.register_extraction(rid, s["id"], {"blocks": [{"key": "bad", "text": "x", "page": 2}], "page_count": 1, "engine": "test"})
    second, _ = source(e, rid)
    with pytest.raises(Conflict, match="来源"):
        observation(e, rid, second, x)


def test_raw_modifier_and_unit_conflict_cannot_be_silently_dropped(evidence):
    e, rid = evidence
    s, x = source(e, rid, text="收入超过1200万元")
    obs = observation(e, rid, s, x, raw_text="收入超过1200万元", unit="元")
    assert obs["status"] == "review"
    assert "unit_conflict" in obs["flags"]
    assert obs["qualifier"] == "more_than"
    fixed = e.correct_observation(rid, obs["id"], value="1200", unit="万元", reason="确认原文为下限，保持下限修饰词")
    with pytest.raises(Conflict, match="下限|区间|修饰"):
        e.create_dataset(rid, "不能把下限当精确数", [fixed["id"]])


def test_explicit_human_unit_and_period_correction_remains_generic(evidence):
    e, rid = evidence
    s, x = source(e, rid, text="浓度1200 微克/升")
    obs = observation(e, rid, s, x, raw_text="浓度1200 微克/升", unit="微克/升", metric="浓度")
    assert obs["status"] == "review"
    fixed = e.correct_observation(rid, obs["id"], value="1200", unit="微克/升", period="2025-03", reason="核对来源表头，采样为2025年3月；保留原单位")
    dataset = e.create_dataset(rid, "环境主题样例", [fixed["id"]])
    assert dataset["rows"][0]["unit"] == "微克/升"
    assert dataset["rows"][0]["period"] == "2025-03"
    assert fixed["corrections"][-1]["before"]["period"] == "2024"


def test_thousands_are_registered_as_raw_values_then_normalized(evidence):
    e, rid = evidence
    s, x = source(e, rid, text="单位：千元 收入1,200")
    obs = observation(e, rid, s, x, raw_text="单位：千元 收入1,200", unit="千元")
    assert obs["status"] == "verified"
    dataset = e.create_dataset(rid, "保留原值后统一换算", [obs["id"]])
    assert dataset["rows"][0]["value"] == "1200000"
    assert dataset["observations"][0]["value"] == "1200"
    converted = observation(e, rid, s, x, raw_text="单位：千元 收入1,200", value="120", unit="万元")
    assert {"number_mismatch", "unit_conflict"} <= set(converted["flags"])


@pytest.mark.parametrize("text,value,unit", [("研发人员数量（人）23,926 23,693 0.98%", "23926", "人"), ("研发费用17,787,624 16,232,771 9.58%", "17787624", "千元")])
def test_neighboring_growth_column_does_not_override_original_amount_unit(evidence, text, value, unit):
    e, rid = evidence
    s, x = source(e, rid, text=text)
    obs = observation(e, rid, s, x, raw_text=text, value=value, unit=unit)
    assert obs["status"] == "verified"


def test_agent_can_withdraw_its_invalid_unreviewed_candidate_but_not_frozen_data(evidence):
    e, rid = evidence
    s, x = source(e, rid)
    wrong = observation(e, rid, s, x, value="120")
    with pytest.raises(ValueError):
        e.withdraw_observation(rid, wrong["id"], reason="")
    withdrawn = e.withdraw_observation(rid, wrong["id"], reason="登记时提前换算；将按原文重新登记")
    assert withdrawn["status"] == "withdrawn"
    assert withdrawn["value"] == "120" and withdrawn["raw_text"] == wrong["raw_text"]
    assert withdrawn["withdrawal"]["actor"] == "agent"
    assert e.research.events(rid)[-1]["kind"] == "observation.withdrawn"
    with pytest.raises(Conflict):
        e.create_dataset(rid, "不能使用撤回项", [wrong["id"]])
    valid = observation(e, rid, s, x)
    e.create_dataset(rid, "冻结数据", [valid["id"]])
    with pytest.raises(Conflict):
        e.withdraw_observation(rid, valid["id"], reason="不能更改已经可用的数据")
    reviewed = observation(e, rid, s, x, value="130")
    e.correct_observation(rid, reviewed["id"], value="1200", unit="万元", reason="人工确认原值")
    with pytest.raises(Conflict):
        e.withdraw_observation(rid, reviewed["id"], reason="不得撤回人工确认")
