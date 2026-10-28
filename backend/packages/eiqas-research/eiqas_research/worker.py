"""Sandbox-only parser and calculation worker; also importable for offline tests.

Run using the dedicated analysis venv. The Gateway never executes user Python.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path


def _number(value) -> Decimal:
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("输入包含无穷或缺失数值")
    return number


def _close(actual, expected) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=1e-9, abs_tol=1e-9)


def _frame(dataset):
    import pandas as pd

    rows = dataset["rows"]
    if not rows:
        raise ValueError("没有可计算数据")
    keys, units = set(), {}
    for row in rows:
        _number(row["value"])
        key = (row["subject"], row["metric"], row["period"])
        if key in keys:
            raise ValueError("输入重复或冲突")
        keys.add(key)
        if row["metric"] in units and units[row["metric"]] != row["unit"]:
            raise ValueError("指标单位口径不一致")
        units[row["metric"]] = row["unit"]
    frame = pd.DataFrame(rows)
    frame["value"] = pd.to_numeric(frame["value"], errors="raise")
    return frame


def _periods(values):
    import re

    years = all(re.fullmatch(r"\d{4}", value) for value in values)
    quarters = all(re.fullmatch(r"\d{4}-Q[1-4]", value) for value in values)
    if not years and not quarters:
        raise ValueError("期间口径必须一致，使用 YYYY 或 YYYY-Qn；不能混合年度和季度")


def _custom_analysis(dataset: dict, parameters: dict) -> dict:
    """Only the sandbox worker executes generated code; each numeric cell is checked."""
    import subprocess
    import tempfile

    if set(parameters) - {"code", "check_code", "arguments"}:
        raise ValueError("定制方法参数应为 code、check_code 和可选 arguments")
    programs = [parameters.get(key) for key in ["code", "check_code"]]
    if any(not isinstance(code, str) or not code.strip() or len(code) > 200000 for code in programs) or programs[0].strip() == programs[1].strip():
        raise ValueError("需要两个不同的、非空的计算与独立检查脚本")
    with tempfile.TemporaryDirectory(prefix="eiqas-method-") as temporary:
        directory = Path(temporary)
        request = directory / "input.json"
        request.write_text(json.dumps({"dataset": dataset, "arguments": parameters.get("arguments", {})}, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        for name, code in zip(["analysis.py", "check.py"], programs):
            path = directory / name
            path.write_text(code, encoding="utf-8")
            command = [sys.executable, str(path), str(request), str(directory / "output.json")]
            if name == "check.py":
                command.append(str(directory / "checks.json"))
            try:
                completed = subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=240, check=True)
                print(f"{name} exit 0\n{completed.stdout[-10000:]}\n{completed.stderr[-10000:]}")
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise ValueError(f"定制方法 {name} 实际执行失败：{str(getattr(exc, 'stderr', '') or exc)[-4000:]}") from exc
        try:
            result = json.loads((directory / "output.json").read_text(encoding="utf-8"))
            check_result = json.loads((directory / "checks.json").read_text(encoding="utf-8"))
            json.dumps(result, allow_nan=False)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ValueError("定制方法没有生成有效且有限的结果与检查文件") from exc
        if not isinstance(result, dict):
            raise ValueError('output.json 必须是 {"rows": [...], "provenance": [[冻结输入observation_id]], "limitations": []} 对象')
        if not isinstance(check_result, dict) or "checks" not in check_result:
            raise ValueError('checks.json 必须是 {"checks": [{"name": "复算说明", "row": 0, "column": "结果列", "expected": 复算数值}]} 对象，不能直接写数组')
        expected = check_result["checks"]
    rows, provenance = result.get("rows"), result.get("provenance")
    if not isinstance(rows, list) or not rows or len(rows) > 100000 or any(not isinstance(row, dict) or not row for row in rows):
        raise ValueError("定制方法需要非空结果行")
    if any(not isinstance(value, (str, int, float, type(None))) or isinstance(value, bool) for row in rows for value in row.values()):
        raise ValueError("结果单元格只接受文字、有限数值或空值")
    if any(type(value) in {int, float} and not math.isfinite(value) for row in rows for value in row.values()):
        raise ValueError("结果包含非有限数值")
    ids = {row["observation_id"] for row in dataset["rows"]}
    if not isinstance(provenance, list) or len(provenance) != len(rows) or any(not isinstance(refs, list) or not refs or any(ref not in ids for ref in refs) for refs in provenance):
        raise ValueError("每个结果行需要本次冻结输入的依据记录")
    if not isinstance(expected, list) or not expected:
        raise ValueError("没有独立结果检查")
    covered, checks = set(), []
    for entry in expected:
        try:
            index, column = entry["row"], entry["column"]
            if type(index) is not int or index < 0 or index >= len(rows) or not isinstance(entry["name"], str):
                raise ValueError("检查定位无效")
            actual = rows[index][column]
            if type(actual) not in {int, float} or type(entry["expected"]) not in {int, float} or not math.isfinite(entry["expected"]):
                raise ValueError("检查必须针对实际数值及独立期望数值")
            checks.append({"name": entry["name"], "row": index, "column": column, "actual": actual, "expected": entry["expected"], "passed": _close(actual, entry["expected"])})
            covered.add((index, column))
        except (KeyError, TypeError, IndexError) as exc:
            raise ValueError("独立检查缺少行列、名称或期望值") from exc
    numeric = {(index, column) for index, row in enumerate(rows) for column, value in row.items() if type(value) in {int, float}}
    if not numeric or not numeric.issubset(covered) or any(not check["passed"] for check in checks):
        raise ValueError("独立检查未覆盖全部数值或复算不一致")
    limits = result.get("limitations", [])
    if not isinstance(limits, list) or any(not isinstance(value, str) for value in limits):
        raise ValueError("判断边界必须是文字列表")
    return {
        "method": "python",
        "parameters": {"arguments": parameters.get("arguments", {})},
        "status": "partial" if result.get("status") == "partial" else "verified",
        "rows": rows,
        "checks": checks,
        "provenance": provenance,
        "limitations": limits,
    }


def validate_spec(spec: dict) -> None:
    allowed = {
        "aggregate": ({"group_by"}, set()),
        "growth": ({"metric"}, {"metric"}),
        "structure": ({"metric", "period"}, {"metric"}),
        "contribution": ({"metric", "from", "to"}, {"metric", "from", "to"}),
        "correlation": ({"x", "y"}, {"x", "y"}),
        "cost_benefit": ({"cost_metric", "benefit_metric", "discount_rate"}, set()),
        "sensitivity": ({"cost_metric", "benefit_metric", "discount_rates"}, set()),
        "python": ({"code", "check_code", "arguments"}, {"code", "check_code"}),
    }
    method, params = spec.get("method"), spec.get("parameters", {})
    if method not in allowed or not isinstance(params, dict):
        raise ValueError("未注册的方法或无效参数对象")
    keys, required = allowed[method]
    if set(params) - keys:
        raise ValueError(f"{method} 不支持参数 {', '.join(sorted(set(params) - keys))}，不会忽略后执行另一种计算")
    if required - set(params):
        raise ValueError(f"{method} 缺少参数 {', '.join(sorted(required - set(params)))}")


def analyze(dataset: dict, spec: dict) -> dict:
    """Perform actual calculations, plus independent Decimal/numpy checks."""
    import duckdb
    import pandas as pd

    validate_spec(spec)
    frame = _frame(dataset)
    method, params = spec["method"], spec.get("parameters", {})
    if method == "python":
        return _custom_analysis(dataset, params)
    checks, limitations, rows = [], [], []
    partial = False

    def check(name, actual, expected):
        checks.append({"name": name, "actual": float(actual), "expected": float(expected), "passed": _close(actual, expected)})

    if method == "aggregate":
        groups = params.get("group_by", ["metric", "unit"])
        if not isinstance(groups, list) or not {"metric", "unit"}.issubset(groups) or not set(groups).issubset({"metric", "unit", "period", "subject"}):
            raise ValueError("聚合必须保留指标和单位，分组字段无效")
        columns = ", ".join(f'"{name}"' for name in groups)
        with duckdb.connect(":memory:") as db:
            db.register("input_data", frame)
            rows = db.execute(f"SELECT {columns}, SUM(value) AS value FROM input_data GROUP BY {columns} ORDER BY {columns}").df().to_dict("records")
        for row in rows:
            subset = [r for r in dataset["rows"] if all(r[name] == row[name] for name in groups)]
            check("独立求和", row["value"], sum((_number(r["value"]) for r in subset), Decimal(0)))
    elif method in {"growth", "structure", "contribution"}:
        selected = frame[frame.metric == params["metric"]]
        if selected.empty:
            raise ValueError("指定指标没有数据")
        _periods(selected.period.tolist())
        if method == "growth":
            for subject, group in selected.groupby("subject", sort=True):
                ordered = group.sort_values("period").to_dict("records")
                if len(ordered) < 2:
                    partial = True
                    limitations.append(f"{subject} 不足两个期间，无法判断增长")
                for before, after in zip(ordered, ordered[1:]):
                    base, value = float(before["value"]), float(after["value"])
                    growth = (value - base) / base if base else None
                    rows.append({"subject": subject, "from_period": before["period"], "period": after["period"], "unit": after["unit"], "base": base, "value": value, "change": value - base, "growth": growth})
                    check("绝对变化独立复算", value - base, _number(after["value"]) - _number(before["value"]))
                    if base:
                        check("增长率独立复算", growth, (_number(after["value"]) - _number(before["value"])) / _number(before["value"]))
                    else:
                        partial = True
                        limitations.append(f"{subject} 基期为零，不计算增长率")
        elif method == "structure":
            selected = selected[selected.period == params["period"]] if params.get("period") else selected
            for period, group in selected.groupby("period", sort=True):
                if (group.value < 0).any():
                    raise ValueError("结构占比需要非负数值")
                total = float(group.value.sum())
                for item in group.to_dict("records"):
                    rows.append({**item, "share": float(item["value"]) / total if total else None})
                if total:
                    check(f"{period} 结构占比之和", sum(row["share"] for row in rows if row["period"] == period), 1)
                else:
                    partial = True
                    limitations.append(f"{period} 总量为零，无法计算结构")
        else:
            first = selected[selected.period == params["from"]].set_index("subject")
            last = selected[selected.period == params["to"]].set_index("subject")
            if first.empty or set(first.index) != set(last.index):
                raise ValueError("贡献分析两个期间必须覆盖相同主体，不能把未披露值当作零")
            total = float(last.value.sum() - first.value.sum())
            for subject in sorted(first.index):
                base, value = float(first.loc[subject, "value"]), float(last.loc[subject, "value"])
                rows.append({"subject": subject, "base": base, "value": value, "change": value - base, "contribution": (value - base) / total if total else None, "unit": first.loc[subject, "unit"]})
            check("变化贡献对账", sum(row["change"] for row in rows), total)
            if not total:
                partial = True
                limitations.append("总变化为零，仅展示绝对变化，不计算贡献占比")
    elif method == "correlation":
        import numpy as np
        from scipy.stats import pearsonr

        x = frame[frame.metric == params["x"]]
        y = frame[frame.metric == params["y"]]
        paired = x.merge(y, on=["subject", "period"], suffixes=("_x", "_y"), validate="one_to_one")
        if len(paired) < 3:
            raise ValueError("关联分析至少需要三对同主体同期间的有效值")
        if paired.value_x.nunique() < 2 or paired.value_y.nunique() < 2:
            check("配对样本数", len(paired), len(set(zip(x.subject, x.period)) & set(zip(y.subject, y.period))))
            partial = True
            rows = [{"n": len(paired), "r": None, "p_value": None}]
            limitations.append("存在常量序列，关联系数不可判断")
        else:
            r, p = pearsonr(paired.value_x.to_numpy(dtype=float), paired.value_y.to_numpy(dtype=float))
            check("相关系数独立复算", r, np.corrcoef(paired.value_x.to_numpy(dtype=float), paired.value_y.to_numpy(dtype=float))[0, 1])
            rows = [{"n": len(paired), "r": float(r), "p_value": float(p)}]
        partial = partial or len(paired) != len(x) or len(paired) != len(y)
        limitations.append("关联不代表因果；样本量、遗漏变量及共同趋势可能影响结果")
        if len(paired) != len(x) or len(paired) != len(y):
            limitations.append("未配对的数据已排除，不能视为零")
    elif method in {"cost_benefit", "sensitivity"}:
        cost_metric, benefit_metric = params.get("cost_metric", "cost"), params.get("benefit_metric", "benefit")
        costs, benefits = frame[frame.metric == cost_metric], frame[frame.metric == benefit_metric]
        if costs.empty or benefits.empty or set(costs.unit) != set(benefits.unit):
            raise ValueError("成本和收益必须具有相同的货币单位")
        paired = costs.merge(benefits, on=["subject", "period"], suffixes=("_cost", "_benefit"), validate="one_to_one")
        if len(paired) != len(costs) or len(paired) != len(benefits):
            raise ValueError("成本收益期间必须匹配；不能自动补零")
        _periods(paired.period.tolist())
        if not all(len(period) == 4 for period in paired.period):
            raise ValueError("本版成本收益使用年度折现口径")
        rates = params.get("discount_rates", [0.1]) if method == "sensitivity" else [params.get("discount_rate", 0.1)]
        if not isinstance(rates, list) or not rates or len(rates) > 100:
            raise ValueError("敏感性分析需要1—100个折现率")
        for rate in rates:
            if not -1 < float(rate) <= 10:
                raise ValueError("折现率必须大于-1且不超过10")
            for subject, group in paired.groupby("subject", sort=True):
                group = group.sort_values("period")
                first = int(group.iloc[0].period)
                value = sum((float(row.value_benefit) - float(row.value_cost)) / (1 + float(rate)) ** (int(row.period) - first) for row in group.itertuples())
                independent = sum(((_number(row.value_benefit) - _number(row.value_cost)) / (Decimal(1) + _number(rate)) ** (int(row.period) - first) for row in group.itertuples()), Decimal(0))
                check("净现值独立复算", value, independent)
                rows.append({"subject": subject, "discount_rate": float(rate), "npv": value, "unit": group.iloc[0].unit_cost})
        limitations.append("情景结果依赖已列明的成本、收益、期间和折现率假设，不是实际成效承诺")
    else:
        raise ValueError(f"未注册的方法：{method}")
    if not rows:
        raise ValueError("没有可交付结果")
    if any(not check["passed"] for check in checks):
        raise ValueError("独立复算未通过")
    # Pandas/numpy scalars must serialize to finite JSON before they leave the worker.
    rows = json.loads(pd.DataFrame(rows).to_json(orient="records", double_precision=15))
    return {"method": method, "parameters": params, "status": "partial" if partial else "verified", "rows": rows, "checks": checks, "limitations": list(dict.fromkeys(limitations))}


def parse_document(path: Path, media_type: str) -> dict:
    """Preserve original text/cells and physical PDF provenance, including OCR."""
    blocks, page_count = [], None
    data = path.read_bytes()
    engine = "python"
    if data.startswith(b"%PDF"):
        from io import BytesIO

        import pypdfium2 as pdfium
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import OcrMode, PdfPipelineOptions, TableStructureOptions, TesseractCliOcrOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling_core.types.io import DocumentStream

        native_text = {}
        with pdfium.PdfDocument(data) as pdf:
            page_count = len(pdf)
            for index in range(page_count):
                page = pdf[index]
                text = page.get_textpage()
                native_text[index + 1] = text.get_text_range().strip()
                text.close()
                page.close()
        scanned_pages = []
        for page, text in native_text.items():
            if len(text) >= 20:
                blocks.append({"key": f"native:page:{page}", "text": text, "page": page, "ocr": False})
            else:
                scanned_pages.append(page)
        if scanned_pages:
            options = PdfPipelineOptions(do_ocr=True, do_table_structure=True)
            options.ocr_options = TesseractCliOcrOptions(mode=OcrMode.FULL_PAGE, scale=4.0, lang=["chi_sim", "chi_tra", "eng"], psm=6, tesseract_cmd="/opt/eiqas/tesseract-cli")
            options.table_structure_options = TableStructureOptions(do_cell_matching=True)
            converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
            for physical_page in scanned_pages:
                converted = converter.convert(DocumentStream(name="original.pdf", stream=BytesIO(data)), page_range=(physical_page, physical_page))
                for index, (item, _level) in enumerate(converted.document.iterate_items()):
                    provs = list(getattr(item, "prov", []))
                    if not provs:
                        continue
                    prov = provs[0]
                    locator = {"page": physical_page, "bbox": list(prov.bbox.as_tuple()), "coordinate_origin": str(prov.bbox.coord_origin), "ocr": True}
                    text = getattr(item, "text", "")
                    if text:
                        blocks.append({"key": f"page:{physical_page}:item:{index}", "text": text, **locator})
                    table = getattr(item, "data", None)
                    for cell in getattr(table, "table_cells", []):
                        blocks.append(
                            {
                                "key": f"page:{physical_page}:table:{index}:row:{cell.start_row_offset_idx}:col:{cell.start_col_offset_idx}",
                                "text": cell.text,
                                "row": cell.start_row_offset_idx + 1,
                                "column": cell.start_col_offset_idx + 1,
                                "table": index,
                                **locator,
                            }
                        )
            engine = f"pypdfium2 native + docling {version('docling')} + tesseract-cli"
        else:
            engine = f"pypdfium2 {version('pypdfium2')} native text"
    elif "spreadsheet" in media_type or "excel" in media_type or data.startswith(b"PK\x03\x04"):
        import pandas as pd

        for sheet, frame in pd.read_excel(path, sheet_name=None, dtype=str, keep_default_na=False).items():
            blocks.extend(_table_blocks(frame, sheet))
        engine = "pandas/openpyxl"
    elif "csv" in media_type or path.suffix.lower() == ".csv":
        import pandas as pd

        blocks = _table_blocks(pd.read_csv(path, dtype=str, keep_default_na=False), "CSV")
        engine = "pandas/csv"
    elif "json" in media_type or data.lstrip().startswith((b"[", b"{")):

        def walk(value, locator):
            if isinstance(value, dict):
                for key, child in value.items():
                    walk(child, f"{locator}.{key}")
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, f"{locator}[{index}]")
            elif value is not None:
                blocks.append({"key": locator, "path": locator, "text": str(value), "ocr": False})

        walk(json.loads(data), "$")
        engine = "json"
    elif "html" in media_type or b"<html" in data[:2000].lower():
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(data, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        for index, tag in enumerate(soup.find_all(["p", "h1", "h2", "h3", "li", "tr"])):
            text = tag.get_text(" ", strip=True)
            if text:
                blocks.append({"key": f"web:{index}", "text": text, "element": tag.name, "ocr": False})
        if not blocks and soup.get_text(" ", strip=True):
            blocks.append({"key": "web:body", "text": soup.get_text(" ", strip=True), "ocr": False})
        for index, tag in enumerate(soup.find_all("a", href=True)):
            blocks.append({"key": f"web:link:{index}", "text": tag.get_text(" ", strip=True), "href": tag["href"], "element": "a", "ocr": False})
        engine = "beautifulsoup4"
    else:
        blocks = [{"key": f"line:{index + 1}", "text": line, "line": index + 1, "ocr": False} for index, line in enumerate(data.decode("utf-8-sig").splitlines()) if line.strip()]
    if not blocks:
        raise ValueError("没有可定位的文本或表格")
    result = {"engine": engine, "page_count": page_count, "blocks": blocks}
    if engine == "beautifulsoup4":
        result["title"] = title
    return result


def _table_blocks(frame, sheet):
    return [
        {"key": f"sheet:{sheet}:row:{row + 2}:col:{column}", "text": str(value), "sheet": sheet, "row": row + 2, "column": str(column), "ocr": False} for row, values in enumerate(frame.to_dict("records")) for column, value in values.items()
    ]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["parse", "analyze"])
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--media-type", default="application/octet-stream")
    args = parser.parse_args()
    data = None
    worker_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    try:
        data = args.input.read_bytes()
        if args.operation == "parse":
            result = parse_document(args.input, args.media_type)
        else:
            request = json.loads(data)
            result = analyze(request["dataset"], request["spec"])
        result["worker_sha256"] = worker_sha
        result["request_sha256"] = hashlib.sha256(data).hexdigest()
        args.output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except Exception as exc:
        failure = {"status": "failed", "error": f"{type(exc).__name__}: {exc}", "worker_sha256": worker_sha}
        if data is not None:
            failure["request_sha256"] = hashlib.sha256(data).hexdigest()
        args.output.write_text(json.dumps(failure, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
