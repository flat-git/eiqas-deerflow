"""Actual numerical work: no fabricated execution receipts or mocked math."""

import pytest
from eiqas_research.worker import analyze, parse_document


def data(rows):
    return {"rows": [{"subject": subject, "period": period, "metric": metric, "value": str(value), "unit": unit, "observation_id": str(i)} for i, (subject, period, metric, value, unit) in enumerate(rows)]}


@pytest.fixture
def revenue():
    return data([("A", "2024", "收入", 100, "CNY"), ("B", "2024", "收入", 50, "CNY"), ("A", "2025", "收入", 110, "CNY"), ("B", "2025", "收入", 40, "CNY")])


def test_actual_aggregate_and_independent_check(revenue):
    result = analyze(revenue, {"method": "aggregate", "parameters": {}})
    assert result["rows"][0]["value"] == 300
    assert all(check["passed"] for check in result["checks"])
    assert result["status"] == "verified"


def test_growth_and_zero_denominator(revenue):
    result = analyze(revenue, {"method": "growth", "parameters": {"metric": "收入"}})
    assert [row["growth"] for row in result["rows"]] == pytest.approx([0.1, -0.2])
    revenue["rows"][0]["value"] = "0"
    result = analyze(revenue, {"method": "growth", "parameters": {"metric": "收入"}})
    assert result["status"] == "partial"
    assert result["rows"][0]["growth"] is None
    assert result["limitations"]


def test_contribution_preserves_zero_total_change(revenue):
    result = analyze(revenue, {"method": "contribution", "parameters": {"metric": "收入", "from": "2024", "to": "2025"}})
    assert [row["change"] for row in result["rows"]] == [10, -10]
    assert all(row["contribution"] is None for row in result["rows"])
    assert result["status"] == "partial"


def test_structure_sum_and_correlation(revenue):
    result = analyze(revenue, {"method": "structure", "parameters": {"metric": "收入", "period": "2024"}})
    assert sum(row["share"] for row in result["rows"]) == pytest.approx(1)
    values = data([(subject, "2024", metric, value, "count") for subject, x in [("A", 1), ("B", 2), ("C", 3)] for metric, value in [("x", x), ("y", 2 * x)]])
    result = analyze(values, {"method": "correlation", "parameters": {"x": "x", "y": "y"}})
    assert result["rows"][0]["r"] == pytest.approx(1)
    assert "因果" in " ".join(result["limitations"])


def test_cost_benefit_and_sensitivity():
    values = data([("方案", "2024", "cost", 100, "CNY"), ("方案", "2024", "benefit", 0, "CNY"), ("方案", "2025", "cost", 0, "CNY"), ("方案", "2025", "benefit", 150, "CNY")])
    result = analyze(values, {"method": "cost_benefit", "parameters": {"discount_rate": 0.1}})
    assert result["rows"][0]["npv"] == pytest.approx(150 / 1.1 - 100)
    result = analyze(values, {"method": "sensitivity", "parameters": {"discount_rates": [0.1, 0.2]}})
    assert [row["npv"] for row in result["rows"]] == pytest.approx([150 / 1.1 - 100, 25])


@pytest.mark.parametrize("change", ["duplicate", "unit", "period", "infinite"])
def test_invalid_comparability_is_rejected(revenue, change):
    if change == "duplicate":
        revenue["rows"].append(revenue["rows"][0])
    if change == "unit":
        revenue["rows"][0]["unit"] = "USD"
    if change == "period":
        revenue["rows"][0]["period"] = "2024-Q1"
    if change == "infinite":
        revenue["rows"][0]["value"] = "Infinity"
    with pytest.raises(ValueError):
        analyze(revenue, {"method": "growth", "parameters": {"metric": "收入"}})


def test_csv_and_web_json_have_cell_locators(tmp_path):
    source = tmp_path / "source.csv"
    source.write_text("主体,收入\n示例,1200\n", encoding="utf-8")
    parsed = parse_document(source, "text/csv")
    cell = next(block for block in parsed["blocks"] if block["text"] == "1200")
    assert cell["row"] == 2 and cell["column"] == "收入"
    source = tmp_path / "world-bank.json"
    source.write_text('[{"page":1},[{"date":"2024","value":12.5}]]')
    parsed = parse_document(source, "application/json")
    assert any(block["text"] == "12.5" and block["path"] == "$[1][0].value" for block in parsed["blocks"])


def test_web_text_and_links_have_saved_original_locators(tmp_path):
    source = tmp_path / "page.html"
    source.write_text('<html><title>公开报告</title><script>secret()</script><h1>年度研究</h1><p>收入1200元</p><a href="files/report.pdf">下载年报</a></html>', encoding="utf-8")
    parsed = parse_document(source, "text/html")
    assert parsed["title"] == "公开报告"
    assert any(block["text"] == "收入1200元" for block in parsed["blocks"])
    link = next(block for block in parsed["blocks"] if block.get("href"))
    assert link["href"] == "files/report.pdf"
    assert link["text"] == "下载年报" and link["key"].startswith("web:link:")
    assert not any("secret()" in block["text"] for block in parsed["blocks"])
