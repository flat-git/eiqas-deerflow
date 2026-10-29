"""Actual offline cost-benefit/sensitivity acceptance with labelled synthetic data."""

import argparse
import json
import math
import uuid
from decimal import Decimal
from pathlib import Path

from eiqas_research.analysis import AnalysisService
from eiqas_research.evidence import EvidenceService
from eiqas_research.models import Plan, ResearchCreate
from eiqas_research.reports import ReportService
from eiqas_research.service import ResearchService, digest
from offline_delivery import execute


def main(output: Path):
    output.mkdir(parents=True, exist_ok=True)
    research = ResearchService(output / "state")
    rid = research.create(
        ResearchCreate(
            thread_id="synthetic-scenario-" + uuid.uuid4().hex[:10],
            question="合成验收：折现率如何影响示例项目净现值？",
        )
    )["id"]
    plan = research.save_plan(
        rid,
        Plan(
            question=research.get(rid)["question"],
            methods=[
                {
                    "name": "净现值",
                    "operation": "cost_benefit",
                    "rationale": "验证实际年度现金流折现",
                },
                {
                    "name": "折现率情景",
                    "operation": "sensitivity",
                    "rationale": "验证参数变化与新运行记录",
                },
            ],
            required_data=["自制合成现金流，非实际投资项目"],
            outputs=["净现值与情景图"],
            limitations=["合成测试，不代表任何真实项目收益或投资建议"],
        ),
    )
    # This acceptance fixture explicitly simulates confirmation; it never
    # confirms or changes an operator's research.
    # Approval follows actual data feasibility assessment below.
    evidence = EvidenceService(research)
    values = [
        ("2024", "cost", "100000"),
        ("2024", "benefit", "0"),
        ("2025", "cost", "10000"),
        ("2025", "benefit", "60000"),
        ("2026", "cost", "10000"),
        ("2026", "benefit", "70000"),
    ]
    lines = [
        "period,metric,value,unit",
        *[f"{period},{metric},{value},元" for period, metric, value in values],
    ]
    source = evidence.register_source(
        rid,
        url="https://example.org/eiqas/synthetic-cashflow.csv",
        title="自制合成现金流（非真实项目）",
        organization="EIQAS synthetic acceptance",
        content="\n".join(lines).encode(),
        media_type="text/csv",
    )
    extraction = evidence.register_extraction(
        rid,
        source["id"],
        {
            "engine": "labelled-synthetic-fixture",
            "page_count": None,
            "blocks": [
                {
                    "key": f"row:{index + 2}",
                    "text": line,
                    "row": index + 2,
                    "column": "value",
                    "sheet": "CSV",
                    "ocr": False,
                }
                for index, line in enumerate(lines[1:])
            ],
        },
    )
    observations = [
        evidence.add_observation(
            rid,
            {
                "source_id": source["id"],
                "extraction_id": extraction["id"],
                "locator_key": f"row:{index + 2}",
                "raw_text": lines[index + 1],
                "value": value,
                "unit": "元",
                "subject": "合成项目",
                "period": period,
                "metric": metric,
                "qualifier": "exact",
            },
        )
        for index, (period, metric, value) in enumerate(values)
    ]
    dataset = evidence.create_dataset(
        rid, "合成年度现金流", [row["id"] for row in observations]
    )
    from design_fixture import approve_synthetic_plan

    plan = approve_synthetic_plan(evidence, rid, plan, dataset)
    analysis = AnalysisService(evidence)

    def calculate(method: str, parameters: dict):
        run = analysis.start_run(
            rid,
            dataset["id"],
            {"method": method, "parameters": parameters},
            native_run_id=None,
        )
        result = execute(
            analysis.run_directory(rid, run["id"]), "container-result.json"
        )
        run = analysis.complete_run(
            rid,
            run["id"],
            result,
            log="Actual pinned analysis image; --network none; synthetic scenario acceptance",
        )
        assert run["status"] == "verified", run.get("errors")
        for row in run["result"]["rows"]:
            rate = Decimal(str(row["discount_rate"]))
            expected = (
                -Decimal(100000)
                + Decimal(50000) / (1 + rate)
                + Decimal(60000) / (1 + rate) ** 2
            )
            assert math.isclose(row["npv"], float(expected), abs_tol=1e-8)
        return run

    baseline = calculate("cost_benefit", {"discount_rate": 0.1})
    base_hash = digest(baseline)
    initial = calculate("sensitivity", {"discount_rates": [0, 0.05, 0.1, 0.15]})
    changed = calculate("sensitivity", {"discount_rates": [0, 0.08, 0.12, 0.2]})
    assert len({baseline["id"], initial["id"], changed["id"]}) == 3
    assert digest(evidence.get(rid, "run", baseline["id"])) == base_hash
    assert initial["result"]["rows"] != changed["result"]["rows"]
    research.update_scope(
        rid,
        answerable=["给定合成现金流下净现值随折现率的变化"],
        gaps=["数据为合成，不代表任何真实项目；未考虑税、通胀或风险调整"],
    )
    report = ReportService(evidence).submit(
        rid,
        {
            "run_id": initial["id"],
            "title": "合成成本收益情景验收",
            "summary": "折现率改变会改变示例项目的净现值。仅验证真实计算与参数记录，不代表真实项目回报。",
            "findings": [
                {
                    "text": "10%折现率情景的净现值为负，0%情景为正；结果取决于明确给定的假设。",
                    "kind": "fact",
                    "cells": [{"row": 0, "column": "npv"}, {"row": 2, "column": "npv"}],
                }
            ],
            "charts": [
                {
                    "id": "synthetic-npv",
                    "title": "合成项目：折现率与净现值",
                    "type": "line",
                    "x": "discount_rate",
                    "y": "npv",
                }
            ],
            "limitations": ["合成数据，仅验证方法与流程"],
        },
    )
    receipt = {
        "synthetic": True,
        "passed": True,
        "simulated_acceptance_confirmation": True,
        "container_network": "none",
        "run_ids": [baseline["id"], initial["id"], changed["id"]],
        "report_id": report["id"],
        "checks": {
            "actual_cost_benefit": True,
            "actual_sensitivity": True,
            "independent_decimal_recalculation": True,
            "new_run_after_parameter_change": True,
            "prior_receipt_unchanged": True,
        },
        "native_browser_recompute": "pending",
    }
    (output / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    main(parser.parse_args().output.resolve())
