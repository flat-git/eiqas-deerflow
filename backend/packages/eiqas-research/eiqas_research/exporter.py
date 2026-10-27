"""Offline deliveries built from one checked report and an explicit file list."""

from __future__ import annotations

import hashlib
import html
import io
import json
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from .analysis import AnalysisService
from .evidence import EvidenceService
from .reports import ReportService
from .service import Conflict, canonical, digest

ASSETS = Path(__file__).with_name("assets")
EXTENSIONS = {
    "application/pdf": ".pdf",
    "text/csv": ".csv",
    "text/html": ".html",
    "text/plain": ".txt",
    "application/json": ".json",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
}
KINDS = {"fact": "计算事实", "inference": "分析推断", "company_reported": "机构自报", "unknown": "无法判断"}


def safe_url(value: str) -> str:
    return value if urlsplit(value).scheme in {"http", "https"} else "#"


def inline_json(value) -> str:
    # HTML parsers terminate even application/json script tags on </script>.
    return canonical(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def source_name(source: dict) -> str:
    return f"sources/{source['id']}/original{EXTENSIONS.get(source['media_type'].split(';')[0], '.bin')}"


def location(block: dict) -> str:
    parts = []
    for key, label in [("page", "PDF 物理页"), ("sheet", "工作表"), ("table", "表"), ("row", "行"), ("column", "列")]:
        if block.get(key) is not None:
            parts.append(f"{label} {block[key]}")
    return " · ".join(parts) or block.get("key", "已保存摘录")


def markdown(report: dict, packaged: bool) -> str:
    lines = [f"# {report['title']}", "", report["question"], "", f"运行：`{report['run_id']}`；结果：`{report['id']}`；执行状态：{report['run']['status']}", "", "## 核心结论", "", report["summary"], "", "## 主要发现", ""]
    for index, finding in enumerate(report["findings"], 1):
        lines.extend([f"{index}. **{KINDS[finding['kind']]}**：{finding['text']}", ""])
        for cell in finding["cells"]:
            lines.extend([f"   结果表第 {cell['row'] + 1} 行 `{cell['column']}`：{cell['value']} {cell['unit']}；依据：{', '.join(cell['observation_ids'])}", ""])
        for reference in finding.get("evidence", []):
            lines.extend([f"   出处 {reference['source_id']} · {location(reference['locator'])}：{reference['quote']}", f"   解释：{reference['explanation']}", ""])
    lines.extend(["## 图表与比较分析", ""])
    for chart in report["charts"]:
        lines.extend([f"### {chart['title']}", "", chart["explanation"], "", f"图表：{chart['type']}；横轴 {chart['x']}；纵轴 {chart['y']}（{chart['unit']}）。交互图见同一成果的 HTML。", ""])
    for title, values in [("管理启示", report["implications"]), ("可判断范围", report["scope"]["answerable"]), ("判断边界与缺口", report["limitations"])]:
        lines.extend([f"## {title}", "", *[f"- {value}" for value in values], ""])
    lines.extend(["## 方法与计算", "", f"方法 `{report['run']['spec']['method']}`，参数 `{canonical(report['run']['spec'].get('parameters', {}))}`。", ""])
    for check in report["run"]["result"]["checks"]:
        lines.append(f"- {canonical(check)}")
    rows = report["run"]["result"]["rows"]
    columns = list(dict.fromkeys(key for row in rows for key in row))

    def escape(value):
        return str(value).replace("|", "\\|").replace("\n", " ") if value is not None else "—"

    lines.extend(["", "### 完整计算结果", "", "| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"])
    lines.extend("| " + " | ".join(escape(row.get(key)) for key in columns) + " |" for row in rows)
    lines.extend(["", "## 来源与定位", ""])
    for source in report["sources"]:
        link = source_name(source) if packaged else safe_url(source["url"])
        lines.extend([f"- [{source['title']}]({link}) · {source['organization']} · 取得于 {source['retrieved_at']} · SHA-256 `{source['sha256']}`", f"  原始 URL：{source['url']}"])
    for obs in report["dataset"]["observations"]:
        lines.extend(["", f"### 数据 {obs['id']}", "", f"{obs['subject']} · {obs['metric']} · {obs['period']}：{obs['value']} {obs['unit']}（{obs['qualifier']}）", f"{obs['source_id']} · {location(obs['locator'])}", "", obs["raw_text"]])
    lines.extend(["", "单独 Markdown/HTML 包含出处与定位；完整原件和可重跑计算材料在同一成果的 ZIP 中。", ""])
    return "\n".join(lines)


def render_html(report: dict, packaged: bool) -> str:
    def esc(value):
        return html.escape(str(value), quote=True)

    def items(values):
        return "<ul>" + "".join(f"<li>{esc(value)}</li>" for value in values) + "</ul>" if values else "<p class=muted>未单独列出。</p>"

    findings = []
    for index, finding in enumerate(report["findings"]):
        refs = list(dict.fromkeys([*finding["observation_ids"], *[oid for cell in finding["cells"] for oid in cell["observation_ids"]]]))
        numbers = " · ".join(f"{cell['value']} {cell['unit']}（结果第 {cell['row'] + 1} 行 / {cell['column']}）" for cell in finding["cells"])
        evidence = "".join(
            f'<p>{esc(reference["quote"])}<br><a href="#source-{esc(reference["source_id"])}">{esc(location(reference["locator"]))} · 查看出处</a><br>{esc(reference["explanation"])}</p>' for reference in finding.get("evidence", [])
        )
        findings.append(
            f"<article class=finding><span class=eyebrow>{index + 1:02} / {KINDS[finding['kind']]}</span><h3>{esc(finding['text'])}</h3>"
            f"<p class=number>{esc(numbers)}</p>"
            f"{evidence}<p>{' '.join(f'<a href=#obs-{esc(oid)}>数据依据 {i + 1}</a>' for i, oid in enumerate(refs))}</p>"
            f"</article>"
        )
    sources, observations = [], []
    for source in report["sources"]:
        link = source_name(source) if packaged else safe_url(source["url"])
        sources.append(
            f'<details id="source-{esc(source["id"])}"><summary>{esc(source["title"])}</summary>'
            f"<p>{esc(source['organization'])} · {esc(source['retrieved_at'])}</p>"
            f'<p><a href="{esc(link)}" target=_blank rel=noopener>打开原件</a> · <a href="{esc(safe_url(source["url"]))}" target=_blank rel=noopener>原始网页</a></p>'
            f"<code>SHA-256 {esc(source['sha256'])}</code></details>"
        )
    for obs in report["dataset"]["observations"]:
        source = next(source for source in report["sources"] if source["id"] == obs["source_id"])
        link = source_name(source) if packaged else safe_url(source["url"])
        if obs["locator"].get("page") and source["media_type"].startswith("application/pdf"):
            link += f"#page={obs['locator']['page']}"
        observations.append(
            f'<details id="obs-{esc(obs["id"])}"><summary>{esc(obs["subject"])} / {esc(obs["metric"])} / {esc(obs["period"])}：{esc(obs["value"])} {esc(obs["unit"])}</summary>'
            f"<blockquote>{esc(obs['raw_text'])}</blockquote>"
            f"<p>{esc(location(obs['locator']))} · {'OCR，已人工核对' if obs['locator'].get('ocr') else '原生文本'} · {esc(obs['qualifier'])}</p>"
            f'<a href="{esc(link)}" target=_blank rel=noopener>{esc(source["title"])} · 打开原件</a><pre>{esc(canonical(obs.get("corrections", [])))}</pre></details>'
        )
    charts = "".join(
        f'<article class=chart-card><span class=eyebrow>图 {i + 1:02}</span><h3>{esc(chart["title"])}</h3><p>{esc(chart["explanation"])}</p><div class=chart id="chart-{i}" role=img aria-label="{esc(chart["title"])}"></div></article>'
        for i, chart in enumerate(report["charts"])
    )
    engine = (ASSETS / "echarts.min.js").read_text(encoding="utf-8").replace("</script", "<\\/script")
    template = (ASSETS / "report.html").read_text(encoding="utf-8")
    replacements = {
        "TITLE": esc(report["title"]),
        "QUESTION": esc(report["question"]),
        "SUMMARY": esc(report["summary"]),
        "IDENTITY": esc(f"{report['run']['status']} · 运行 {report['run_id']} · 成果 {report['id']}"),
        "FINDINGS": "".join(findings),
        "CHARTS": charts,
        "IMPLICATIONS": items(report["implications"]),
        "SCOPE": items(report["scope"]["answerable"]),
        "LIMITS": items(report["limitations"]),
        "SOURCES": "".join(sources),
        "OBSERVATIONS": "".join(observations),
        "PLAN": esc(canonical(report["plan"]["content"])),
        "CHECKS": esc(canonical(report["run"]["result"]["checks"])),
        "DELIVERY": "原件、提取记录和计算材料位于包内；PDF 页码跳转取决于阅读器，定位文字始终保留。" if packaged else "此 HTML 可独立离线阅读；原文按钮访问公开网址。完整离线原件、数据和计算脚本请下载同一成果的 ZIP。",
        "DATA": inline_json(report),
        "ECHARTS": engine,
    }
    # Replace in one pass so untrusted text cannot introduce template tokens.
    import re

    return re.sub(r"@@([A-Z]+)@@", lambda match: replacements[match[1]], template)


class ExportService:
    def __init__(self, evidence: EvidenceService):
        self.evidence = evidence

    def build(self, rid: str, report_id: str, format: str) -> Path:
        if format not in {"html", "md", "csv", "zip"}:
            raise ValueError("导出格式应为 html、md、csv 或 zip")
        report = self.evidence.get(rid, "result", report_id)
        run = self.evidence.get(rid, "run", report["run_id"])
        reports = ReportService(self.evidence)
        dataset = reports.verify_run(rid, run)
        if digest(report["run"]) != digest(run) or digest(report["dataset"]) != digest(dataset):
            raise Conflict("成果与其冻结运行或数据集不一致")
        manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
        for name, sha in manifest["files"].items():
            if hashlib.sha256((ASSETS / name).read_bytes()).hexdigest() != sha:
                raise Conflict(f"导出依赖 {name} 完整性检查失败")
        directory = AnalysisService(self.evidence).run_directory(rid, run["id"])
        files = {}
        for name, sha in run["artifact_hashes"].items():
            if name not in {"input.json", "script.py", "execution.log", "result.json", "result.csv", "analysis.py", "check.py"}:
                raise Conflict("运行包含未知交付材料")
            data = (directory / name).read_bytes()
            if hashlib.sha256(data).hexdigest() != sha:
                raise Conflict(f"运行材料 {name} 完整性不一致")
            files[f"runs/{run['id']}/{name}"] = data
        for source in report["sources"]:
            data = self.evidence.original(rid, source["id"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != source["sha256"]:
                raise Conflict("来源与成果快照不一致")
            files[source_name(source)] = data
        extractions = {obs["extraction_id"]: obs["extraction_hash"] for obs in dataset["observations"]}
        extractions.update({row["id"]: row["sha256"] for row in report.get("extractions", [])})
        for eid, sha in extractions.items():
            row = self.evidence.get(rid, "extraction", eid)
            if digest(row["result"]) != sha or row["sha256"] != sha:
                raise Conflict("来源提取记录完整性不一致")
            files[f"extractions/{eid}.json"] = canonical(row).encode()
        files.update({"report.json": canonical(report).encode(), "dataset.json": canonical(dataset).encode(), "report.md": markdown(report, True).encode(), "index.html": render_html(report, True).encode()})
        for name in manifest["files"]:
            files[f"dependencies/{name}"] = (ASSETS / name).read_bytes()
        files["README.txt"] = (
            "EIQAS 离线研究材料\n打开 index.html 阅读交互报告。筛选仅改变展示；参数重算请返回本地工作台，会产生新的运行记录。\n"
            "全部资料均按本成果显式引用打包；不包含其他研究、数据库、凭据或模型缓存。\n"
            "独立重算：使用 Python 3.12，在隔离环境中安装 dependencies/analysis-requirements.lock，或使用项目分析镜像。\n"
            f"cd runs/{run['id']}\npython script.py analyze --input input.json --output replay.json\n"
            "将 replay.json 的 rows、checks 与 result.json 比较；哈希记录绑定本次实际输入与脚本。\n"
            "依赖锁包含公开 PyPI 与 PyTorch CPU 索引；首次安装需要联网。离线阅读无需安装依赖。\n"
        ).encode()
        output_dir = self.evidence.directory(rid) / "exports" / report_id
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"report.{format}"
        if format == "zip":
            files["manifest.json"] = canonical(
                {"report_id": report_id, "run_id": run["id"], "input_hash": run["input_hash"], "output_hash": run["output_hash"], "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
            ).encode()
            output = io.BytesIO()
            with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, data in files.items():
                    archive.writestr(name, data)
            path.write_bytes(output.getvalue())
        elif format == "html":
            path.write_text(render_html(report, False), encoding="utf-8")
        elif format == "md":
            path.write_text(markdown(report, False), encoding="utf-8")
        else:
            path.write_bytes(files[f"runs/{run['id']}/result.csv"])
        return path
