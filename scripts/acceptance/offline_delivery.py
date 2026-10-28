"""Synthetic actual-container calculation, offline export and independent ZIP replay.

Run with the backend uv environment. This does not stand in for a native model
research or a real reader trial. No provider credentials are required or mounted.
"""

import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

from eiqas_research.analysis import AnalysisService
from eiqas_research.delivery import EvidenceTableService
from eiqas_research.evidence import EvidenceService
from eiqas_research.exporter import ExportService
from eiqas_research.models import Plan, ResearchCreate
from eiqas_research.reports import ReportService
from eiqas_research.service import ResearchService


def execute(directory: Path, output: str):
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "/opt/eiqas-venv/bin/python",
            "-v",
            f"{directory.resolve()}:/job",
            "eiqas-analysis:0.1.0-dev",
            "/job/script.py",
            "analyze",
            "--input",
            "/job/input.json",
            "--output",
            f"/job/{output}",
        ],
        check=True,
    )
    return json.loads((directory / output).read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    research = ResearchService(root / "state")
    rid = research.create(
        ResearchCreate(
            thread_id="synthetic-offline-" + __import__("uuid").uuid4().hex[:10],
            question="合成流程验收：两个区域的收入如何变化？",
        )
    )["id"]
    plan = research.save_plan(
        rid,
        Plan(
            question=research.get(rid)["question"],
            methods=[
                {
                    "name": "增长分析",
                    "operation": "growth",
                    "rationale": "检验基期与当期独立复算及来源回查",
                }
            ],
            required_data=["明确标注的自制合成CSV"],
            outputs=["增长率与实际收入图表"],
            limitations=["合成测试数据，不代表企业实际表现"],
        ),
    )
    # This explicit synthetic test fixture simulates the human gate only here.
    research.confirm_plan(rid, plan["hash"])
    evidence = EvidenceService(research)
    records = [
        ("区域甲", "2024", "100"),
        ("区域甲", "2025", "125"),
        ("区域乙", "2024", "80"),
        ("区域乙", "2025", "92"),
    ]
    lines = [
        "subject,period,revenue,unit",
        *[f"{subject},{period},{value},元" for subject, period, value in records],
    ]
    source = evidence.register_source(
        rid,
        url="https://example.org/eiqas/synthetic-fixture.csv",
        title="自制合成区域收入样例（非企业披露）",
        organization="EIQAS synthetic test",
        content="\n".join(lines).encode(),
        media_type="text/csv",
    )
    extraction = evidence.register_extraction(
        rid,
        source["id"],
        {
            "engine": "synthetic-fixture",
            "page_count": None,
            "blocks": [
                {
                    "key": f"row:{i + 2}",
                    "text": records[i][2],
                    "sheet": "CSV",
                    "row": i + 2,
                    "column": "revenue",
                    "ocr": False,
                }
                for i, line in enumerate(lines[1:])
            ],
        },
    )
    observations = [
        evidence.add_observation(
            rid,
            {
                "source_id": source["id"],
                "extraction_id": extraction["id"],
                "locator_key": f"row:{i + 2}",
                "raw_text": value,
                "subject": subject,
                "period": period,
                "metric": "收入",
                "value": value,
                "unit": "元",
                "qualifier": "exact",
            },
        )
        for i, (subject, period, value) in enumerate(records)
    ]
    dataset = evidence.create_dataset(
        rid, "合成区域收入", [obs["id"] for obs in observations]
    )
    analysis = AnalysisService(evidence)
    run = analysis.start_run(
        rid,
        dataset["id"],
        {"method": "growth", "parameters": {"metric": "收入"}},
        native_run_id=None,
    )
    directory = analysis.run_directory(rid, run["id"])
    output = execute(directory, "receipt.json")
    run = analysis.complete_run(
        rid,
        run["id"],
        output,
        log="Actual pinned analysis container; --network none; exit 0",
    )
    assert run["status"] == "verified", run
    assert {row["subject"]: row["growth"] for row in run["result"]["rows"]} == {
        "区域甲": 0.25,
        "区域乙": 0.15,
    }
    indices = {row["subject"]: index for index, row in enumerate(run["result"]["rows"])}
    research.update_scope(
        rid,
        answerable=["两个合成区域的绝对变化及增长率"],
        gaps=["没有因果识别设计，不能解释差异成因"],
    )
    table = EvidenceTableService(evidence).save(
        rid,
        {
            "title": "合成输入口径与依据",
            "columns": [
                {"key": "subject", "label": "主体", "filterable": True},
                {"key": "period", "label": "期间"},
                {"key": "value", "label": "原值（元）"},
            ],
            "rows": [
                {
                    "values": {"subject": subject, "period": period, "value": value},
                    "kind": "fact",
                    "explanation": "明确标注的合成原值；不代表真实业务。",
                    "evidence": [
                        {
                            "source_id": source["id"],
                            "extraction_id": extraction["id"],
                            "locator_key": f"row:{i + 2}",
                            "quote": value,
                            "explanation": "与合成CSV中的原单元格一致",
                        }
                    ],
                }
                for i, (subject, period, value) in enumerate(records)
            ],
        },
    )
    result = ReportService(evidence).submit(
        rid,
        {
            "run_id": run["id"],
            "table_ids": [table["id"]],
            "plan_coverage": {
                "plan_hash": plan["hash"],
                "items": [
                    {
                        "kind": kind,
                        "index": 0,
                        "status": "completed",
                        "explanation": "实际增长运算及可定位合成输入已交付；尚无读者确认。",
                        "run_ids": [run["id"]],
                        "table_ids": [table["id"]],
                        "finding_indices": [0, 1],
                    }
                    for kind in ["method", "output"]
                ],
            },
            "title": "合成收入趋势：区域甲增长更快",
            "summary": "区域甲收入增长25%，区域乙增长15%；差异成因尚不能判断。",
            "findings": [
                {
                    "text": "区域甲增长25%。",
                    "kind": "fact",
                    "cells": [{"row": indices["区域甲"], "column": "growth"}],
                },
                {
                    "text": "区域乙增长15%。",
                    "kind": "fact",
                    "cells": [{"row": indices["区域乙"], "column": "growth"}],
                },
                {"text": "仅凭两期合成数据不能解释变化的原因。", "kind": "unknown"},
            ],
            "charts": [
                {
                    "id": "revenue",
                    "title": "实际收入",
                    "type": "bar",
                    "x": "subject",
                    "y": "value",
                    "explanation": "展示2025年实际计算结果，点击柱形追溯两期冻结输入。",
                },
                {
                    "id": "growth",
                    "title": "收入增长率",
                    "type": "bar",
                    "x": "subject",
                    "y": "growth",
                    "explanation": "基于2024/2025年合成输入独立复算。",
                },
            ],
            "implications": [
                "实际业务需要进一步取得价格、销量或结构数据，才能解释变化。"
            ],
            "limitations": ["本研究为工程合成样例，不能用于商业判断。"],
        },
    )
    exports = ExportService(evidence)
    paths = {
        format: exports.build(rid, result["id"], format)
        for format in ["html", "md", "csv", "zip"]
    }
    unpacked = root / "unpacked"
    with zipfile.ZipFile(paths["zip"]) as archive:
        assert all(
            not name.startswith("/") and ".." not in Path(name).parts
            for name in archive.namelist()
        )
        archive.extractall(unpacked)
    manifest = json.loads((unpacked / "manifest.json").read_text())
    for name, sha in manifest["files"].items():
        assert hashlib.sha256((unpacked / name).read_bytes()).hexdigest() == sha, name
    assert f"tables/{table['id']}.csv" in manifest["files"]
    assert "合成输入口径与依据" in paths["html"].read_text()
    assert "读者待复核" in paths["html"].read_text()
    replay = execute(unpacked / "runs" / run["id"], "replay.json")
    assert replay["rows"] == output["rows"] and replay["checks"] == output["checks"]
    receipt = {
        "synthetic": True,
        "status": "passed",
        "research_id": rid,
        "run_id": run["id"],
        "report_id": result["id"],
        "container_network": "none",
        "exports": {format: str(path) for format, path in paths.items()},
        "checks": {
            "actual_calculation": True,
            "plan_coverage_and_evidence_table": True,
            "independent_result_values": True,
            "package_checksums": True,
            "zip_replay_rows_and_checks": True,
        },
        "reader_trial": "pending",
        "browser_offline": "pending",
    }
    (root / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2)
    )
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
