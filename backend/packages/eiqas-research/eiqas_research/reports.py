"""One report manifest drives the workbench, reader and all exported formats."""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import Field

from .analysis import AnalysisService
from .delivery import EvidenceTableService, LocatedEvidence, PlanCoverage, resolve_coverage, resolve_reference
from .evidence import EvidenceService
from .models import Contract, Identifier, Text
from .service import Conflict, digest


class Cell(Contract):
    row: int = Field(ge=0)
    column: Text


class Finding(Contract):
    text: Text
    kind: Literal["fact", "inference", "company_reported", "unknown"]
    cells: list[Cell] = Field(default_factory=list, max_length=30)
    observation_ids: list[Identifier] = Field(default_factory=list, max_length=100)
    evidence: list[LocatedEvidence] = Field(default_factory=list, max_length=30)


class Chart(Contract):
    id: Identifier
    title: Text
    type: Literal["bar", "line", "scatter"]
    x: Text
    y: Text
    series: Text | None = None
    filters: dict[str, str] = Field(default_factory=dict, max_length=20)
    explanation: Text = "依据已校验的实际计算；点击图表查看数据与来源。"


class ReportDraft(Contract):
    run_id: Identifier
    title: Text
    summary: Text
    findings: list[Finding] = Field(min_length=1, max_length=12)
    charts: list[Chart] = Field(min_length=1, max_length=12)
    implications: list[Text] = Field(default_factory=list, max_length=20)
    limitations: list[Text] = Field(default_factory=list, max_length=30)
    table_ids: list[Identifier] = Field(default_factory=list, max_length=20)
    plan_coverage: PlanCoverage | None = None


def field_unit(column: str, row: dict) -> str:
    if column in {"growth", "share", "contribution"}:
        return "ratio"
    if column in {"r", "p_value", "discount_rate"}:
        return "dimensionless"
    if column == "n":
        return "count"
    return row.get("unit", "")


def lineage(dataset: dict, run: dict) -> list[list[str]]:
    method, params = run["spec"]["method"], run["spec"].get("parameters", {})
    if method == "python":
        return run["result"]["provenance"]
    inputs = dataset["rows"]
    result = []
    for row in run["result"]["rows"]:
        selected = inputs
        if method == "aggregate":
            selected = [value for value in selected if all(value.get(key) == row.get(key) for key in params.get("group_by", ["metric", "unit"]))]
        elif method in {"growth", "structure", "contribution"}:
            selected = [value for value in selected if value["metric"] == params["metric"] and value["subject"] == row["subject"]]
            periods = {row.get("from_period"), row.get("period")} if method == "growth" else {params["from"], params["to"]} if method == "contribution" else {row["period"]}
            selected = [value for value in selected if value["period"] in periods]
        elif method == "correlation":
            paired = set((value["subject"], value["period"]) for value in inputs if value["metric"] == params["x"]) & set((value["subject"], value["period"]) for value in inputs if value["metric"] == params["y"])
            selected = [value for value in inputs if value["metric"] in {params["x"], params["y"]} and (value["subject"], value["period"]) in paired]
        elif method in {"cost_benefit", "sensitivity"}:
            selected = [value for value in inputs if value["subject"] == row["subject"] and value["metric"] in {params.get("cost_metric", "cost"), params.get("benefit_metric", "benefit")}]
        result.append([value["observation_id"] for value in selected])
    return result


class ReportService:
    def __init__(self, evidence: EvidenceService):
        self.evidence = evidence

    def verify_run(self, rid: str, run: dict) -> dict:
        from .worker import validate_spec

        validate_spec(run["spec"])
        if run["status"] not in {"verified", "partial"} or not run.get("verified_at"):
            raise Conflict("只有实际运行并通过检查的结果可以交付")
        if digest(run["result"]) != run["output_hash"]:
            raise Conflict("运行结果完整性不一致")
        directory = AnalysisService(self.evidence).run_directory(rid, run["id"])
        expected = {"input.json": run["request_sha256"], "script.py": run["worker_sha256"], "result.json": run["output_hash"], **run.get("artifact_hashes", {})}
        for name, sha in expected.items():
            path = directory / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                raise Conflict(f"运行材料 {name} 缺失或完整性不一致")
        dataset = self.evidence.get(rid, "dataset", run["dataset_id"])
        if dataset["input_hash"] != run["input_hash"] or digest({key: dataset[key] for key in ["title", "rows", "observations"]}) != run["input_hash"]:
            raise Conflict("运行输入与数据集不一致")
        for observation in dataset["observations"]:
            self.evidence.original(rid, observation["source_id"])
        return dataset

    def submit(self, rid: str, draft: dict) -> dict:
        content = ReportDraft.model_validate(draft)
        run = self.evidence.get(rid, "run", content.run_id)
        dataset = self.verify_run(rid, run)
        research = self.evidence.research.get(rid)
        if not research["plan"] or run["plan_hash"] != research["plan"]["hash"]:
            raise Conflict("研究方案已改变，请先确认并完成新方案计算")
        observations = {row["id"]: row for row in dataset["observations"]}
        provenance = lineage(dataset, run)
        findings, rows = [], run["result"]["rows"]
        additional_sources, located_extractions = {}, {}
        for finding in content.findings:
            if finding.kind != "unknown" and not finding.cells and not finding.observation_ids and not finding.evidence:
                raise Conflict("支持性结论需要运行数值或具体数据依据")
            if any(oid not in observations for oid in finding.observation_ids):
                raise Conflict("结论引用的数据不属于本次冻结输入")
            cells = []
            for cell in finding.cells:
                if cell.row >= len(rows) or cell.column not in rows[cell.row]:
                    raise Conflict("数值引用没有定位到实际结果单元格")
                value = rows[cell.row][cell.column]
                if type(value) not in {int, float}:
                    raise Conflict("关键数字引用必须指向实际数值")
                cells.append({**cell.model_dump(), "value": value, "unit": field_unit(cell.column, rows[cell.row]), "observation_ids": provenance[cell.row]})
            evidence = []
            for reference in finding.evidence:
                source = self.evidence.get(rid, "source", reference.source_id)
                self.evidence.original(rid, source["id"])
                extraction = self.evidence.get(rid, "extraction", reference.extraction_id)
                if extraction["source_id"] != source["id"] or extraction["source_hash"] != source["sha256"] or digest(extraction["result"]) != extraction["sha256"]:
                    raise Conflict("定性依据的来源或提取完整性不一致")
                block = next((block for block in extraction["result"]["blocks"] if block["key"] == reference.locator_key), None)
                if block is None or reference.quote not in block["text"]:
                    raise Conflict("结论摘录不在指定的来源定位中")
                evidence.append({**reference.model_dump(), "locator": block, "source_hash": source["sha256"]})
                additional_sources[source["id"]] = source
                located_extractions[extraction["id"]] = extraction
            findings.append({**finding.model_dump(), "cells": cells, "evidence": evidence})
        ids = set()
        charts = []
        for chart in content.charts:
            if chart.id in ids:
                raise Conflict("图表标识重复")
            ids.add(chart.id)
            chart_rows = [row for row in rows if all(key in row and str(row[key]) == value for key, value in chart.filters.items())]
            if not chart_rows:
                raise Conflict("图表筛选后没有实际结果")
            if any(chart.x not in row or chart.y not in row or (chart.series and chart.series not in row) for row in chart_rows):
                raise Conflict("图表字段不属于实际结果")
            numeric = [row[chart.y] for row in chart_rows if row[chart.y] is not None]
            if not numeric or any(type(value) not in {int, float} for value in numeric):
                raise Conflict("图表没有可绘制的实际数值")
            units = {field_unit(chart.y, row) for row in chart_rows}
            if len(units) != 1:
                raise Conflict("同一图表的纵轴单位不同，请拆图或筛选同口径指标")
            coordinates = [(str(row[chart.x]), str(row.get(chart.series)) if chart.series else "") for row in chart_rows]
            if chart.type != "scatter" and len(set(coordinates)) != len(coordinates):
                raise Conflict("图表存在重复横轴与系列组合，请增加系列字段或筛选条件")
            if chart.type == "scatter" and any(type(row[chart.x]) not in {int, float} for row in chart_rows):
                raise Conflict("散点图横轴必须是实际数值")
            charts.append({**chart.model_dump(), "unit": next(iter(units))})
        source_ids = list(dict.fromkeys(obs["source_id"] for obs in observations.values()))
        if len(set(content.table_ids)) != len(content.table_ids):
            raise Conflict("交付证据表引用重复")
        tables = [EvidenceTableService(self.evidence).verify(rid, table_id, research["plan"]["hash"]) for table_id in content.table_ids]
        for table in tables:
            for row in table["rows"]:
                for reference in row["evidence"]:
                    _resolved, source, extraction = resolve_reference(self.evidence, rid, reference)
                    additional_sources[source["id"]] = source
                    located_extractions[extraction["id"]] = extraction
        verified_runs = {run["id"]: run}
        datasets = {dataset["id"]: dataset}

        def verify_auxiliary(run_id):
            if run_id not in verified_runs:
                auxiliary = self.evidence.get(rid, "run", run_id)
                if auxiliary["plan_hash"] != research["plan"]["hash"]:
                    raise Conflict("履行核对引用了其他方案的运行")
                auxiliary_dataset = self.verify_run(rid, auxiliary)
                verified_runs[run_id] = auxiliary
                datasets[auxiliary_dataset["id"]] = auxiliary_dataset
            return verified_runs[run_id]

        coverage, _declared_runs = resolve_coverage(research, content, tables, verify_auxiliary)
        for auxiliary_dataset in datasets.values():
            for observation in auxiliary_dataset["observations"]:
                if observation["source_id"] not in source_ids:
                    additional_sources[observation["source_id"]] = self.evidence.get(rid, "source", observation["source_id"])
        sources = [self.evidence.get(rid, "source", sid) for sid in source_ids]
        sources.extend(source for sid, source in additional_sources.items() if sid not in source_ids)
        result = self.evidence.put(
            rid,
            "result",
            {
                **content.model_dump(),
                "findings": findings,
                "charts": charts,
                "tables": tables,
                "coverage": coverage,
                "auxiliary_runs": [value for key, value in verified_runs.items() if key != run["id"]],
                "auxiliary_datasets": [value for key, value in datasets.items() if key != dataset["id"]],
                "run": run,
                "dataset": dataset,
                "sources": sources,
                "provenance": provenance,
                "extractions": list(located_extractions.values()),
                "question": research["question"],
                "plan": research["plan"],
                "scope": {"answerable": research["answerable"], "gaps": research["gaps"]},
                "limitations": list(dict.fromkeys([*content.limitations, *run["result"]["limitations"], *research["plan"]["content"]["limitations"], *research["gaps"]])),
            },
        )
        self.evidence.research.set_stage(rid, "review")
        return result
