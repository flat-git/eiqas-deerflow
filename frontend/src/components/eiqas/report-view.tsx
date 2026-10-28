"use client";

import { useState } from "react";
import { toast } from "sonner";

import { downloadExport, eiqasURL } from "@/core/eiqas/api";
import { formatNumber, methodNames, stateNames } from "@/core/eiqas/chart-data";
import type { ChartSpec, DataRow, Finding, Report } from "@/core/eiqas/types";

import {
  EvidenceTableView,
  PlanFulfillment,
  ReaderFeedback,
  reviewLabels,
} from "./delivery-context";
import { EvidencePanel, type EvidenceSelection } from "./evidence-panel";
import { ResultChart } from "./result-chart";

const findingLabels = {
  fact: "据数据与原文",
  inference: "分析推断",
  company_reported: "公司自报",
  unknown: "尚不可判断",
};

export function ReportView({
  report,
  compact = false,
  onRecompute,
  onReview,
}: {
  report: Report;
  compact?: boolean;
  onReview?: (
    status: "accepted" | "needs_revision",
    comment: string,
  ) => Promise<void>;
  onRecompute?: (parameters: Record<string, unknown>) => void;
}) {
  const [selection, setSelection] = useState<EvidenceSelection | null>(null);
  const [subjects, setSubjects] = useState<string[]>([]);
  const [findingsOpen, setFindingsOpen] = useState(false);
  const [limitationsOpen, setLimitationsOpen] = useState(false);
  const [dataOpen, setDataOpen] = useState(false);
  const [parametersOpen, setParametersOpen] = useState(false);
  const [dataTable, setDataTable] = useState("rows");
  const [exporting, setExporting] = useState("");
  const result = report.run.result;
  if (!result)
    return <p role="alert">结果材料不完整，请回到工作台核对运行状态。</p>;
  const allSubjects = [
    ...new Set(
      [result.rows, ...Object.values(result.tables ?? {})]
        .flat()
        .map((row) => row.subject)
        .filter((value): value is string => typeof value === "string"),
    ),
  ];
  const selectedSubjects = subjects.length ? subjects : allSubjects;
  function table(name = "rows"): DataRow[] {
    return name === "rows" ? result!.rows : (result!.tables?.[name] ?? []);
  }
  function inspectRows(index: number, chart: ChartSpec) {
    const ids =
      (chart.table && chart.table !== "rows"
        ? report.table_provenance?.[chart.table]
        : report.provenance)?.[index] ?? [];
    setSelection({
      title: chart.title,
      observations: report.dataset.observations.filter((observation) =>
        ids.includes(observation.id),
      ),
    });
  }
  function inspectFinding(finding: Finding) {
    const ids = [
      ...finding.observation_ids,
      ...finding.cells.flatMap((cell) => cell.observation_ids),
    ];
    setSelection({
      title: finding.text,
      observations: report.dataset.observations.filter((observation) =>
        ids.includes(observation.id),
      ),
      references: finding.evidence,
    });
  }
  async function exportReport(format: string) {
    setExporting(format);
    try {
      await downloadExport(report.research_id, report.id, format);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "导出失败");
    } finally {
      setExporting("");
    }
  }
  const visibleCharts = compact ? report.charts.slice(0, 1) : report.charts;
  const currentRows = table(dataTable);
  return (
    <article className={`eiqas-report ${compact ? "is-compact" : ""}`}>
      <div className="eiqas-report-heading">
        <div>
          <span className="eiqas-eyebrow">RESEARCH FINDINGS</span>
          <h1>{report.title}</h1>
          <p className="eiqas-muted">{report.plan.content.question}</p>
        </div>
        {!compact && (
          <div className="eiqas-export-menu">
            {["html", "md", "csv", "zip"].map((format) => (
              <button
                disabled={Boolean(exporting)}
                key={format}
                onClick={() => {
                  void exportReport(format);
                }}
              >
                {exporting === format
                  ? "生成中…"
                  : {
                      html: "交互 HTML",
                      md: "Markdown",
                      csv: "结果 CSV",
                      zip: "完整 ZIP",
                    }[format]}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="eiqas-report-meta">
        <span className="eiqas-badge">
          {report.run.status === "verified"
            ? "数值检查通过"
            : (stateNames[report.run.status] ?? report.run.status)}
        </span>
        <span
          className={
            report.review?.status === "needs_revision"
              ? "eiqas-caution"
              : "eiqas-muted"
          }
        >
          {reviewLabels[report.review?.status ?? "pending"]}
        </span>
        <span>{new Date(report.created_at).toLocaleString("zh-CN")}</span>
        <span>{methodNames[report.run.spec.method] ?? "定制分析"}</span>
        {report.scope.gaps.length > 0 && (
          <span className="eiqas-caution">
            仍有 {report.scope.gaps.length} 项判断缺口
          </span>
        )}
      </div>
      {report.review?.comment && (
        <p className="eiqas-review-note">{report.review.comment}</p>
      )}
      <PlanFulfillment
        report={report}
        inspect={(index) => {
          const finding = report.findings[index];
          if (finding) inspectFinding(finding);
        }}
      />
      <section className="eiqas-conclusion">
        <span className="eiqas-eyebrow">核心结论</span>
        <p>{report.summary}</p>
      </section>
      <section className="eiqas-findings">
        {report.findings
          .slice(0, findingsOpen && !compact ? undefined : 3)
          .map((finding, index) => (
            <div className="eiqas-finding" key={index}>
              <span className="eiqas-finding-number">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <span className={`eiqas-kind ${finding.kind}`}>
                  {findingLabels[finding.kind]}
                </span>
                <p>{finding.text}</p>
                {finding.cells.length > 0 && (
                  <div className="eiqas-number-chips">
                    {finding.cells.map((cell, position) => (
                      <span key={position}>
                        {formatNumber(cell.value, cell.unit)}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              <button
                className="eiqas-text-button"
                onClick={() => inspectFinding(finding)}
              >
                查看依据 ↗
              </button>
            </div>
          ))}
      </section>
      {!compact && report.findings.length > 3 && (
        <button
          className="eiqas-text-button"
          onClick={() => setFindingsOpen(!findingsOpen)}
        >
          {findingsOpen
            ? "收起更多发现"
            : `展开其余 ${report.findings.length - 3} 条发现`}
        </button>
      )}
      {!compact &&
        report.tables?.map((evidenceTable) => (
          <EvidenceTableView
            key={evidenceTable.id}
            table={evidenceTable}
            inspect={setSelection}
          />
        ))}
      <div className="eiqas-section-title">
        <div>
          <span className="eiqas-eyebrow">NUMBERS IN CONTEXT</span>
          <h2>用数据看清差异与变化</h2>
        </div>
        <button onClick={() => setDataOpen(!dataOpen)}>
          {dataOpen ? "收起数据" : "查看完整数据"}
        </button>
      </div>
      {allSubjects.length > 1 && (
        <div className="eiqas-filters">
          <span>图表主体</span>
          {allSubjects.map((subject) => (
            <label key={subject}>
              <input
                type="checkbox"
                checked={selectedSubjects.includes(subject)}
                disabled={
                  selectedSubjects.length === 1 &&
                  selectedSubjects.includes(subject)
                }
                onChange={(event) =>
                  setSubjects(
                    event.target.checked
                      ? [...selectedSubjects, subject]
                      : selectedSubjects.filter((value) => value !== subject),
                  )
                }
              />
              {subject}
            </label>
          ))}
          {subjects.length > 0 && (
            <button
              className="eiqas-text-button"
              onClick={() => setSubjects([])}
            >
              重置筛选
            </button>
          )}
        </div>
      )}
      {subjects.length > 0 && (
        <p className="eiqas-muted">
          筛选改变图表展示；核心结论仍基于完整研究范围。
        </p>
      )}
      {visibleCharts.map((chart) => (
        <section className="eiqas-chart-card" key={chart.id}>
          <div className="eiqas-chart-heading">
            <h3>{chart.title}</h3>
            <span>点击图形查看依据</span>
          </div>
          <ResultChart
            chart={chart}
            rows={table(chart.table)}
            subjects={subjects}
            onRowClick={(index) => inspectRows(index, chart)}
          />
          <p className="eiqas-chart-explanation">{chart.explanation}</p>
        </section>
      ))}
      {dataOpen && (
        <section className="eiqas-full-data">
          <div className="eiqas-actions">
            <h3>实际结果表</h3>
            {Object.keys(result.tables ?? {}).length > 0 && (
              <select
                aria-label="结果表"
                value={dataTable}
                onChange={(event) => setDataTable(event.target.value)}
              >
                {["rows", ...Object.keys(result.tables ?? {})].map((name) => (
                  <option key={name}>{name}</option>
                ))}
              </select>
            )}
            <a
              href={eiqasURL(
                `/research/${report.research_id}/datasets/${report.dataset.id}/csv`,
              )}
            >
              下载完整输入数据 CSV
            </a>
          </div>
          <div className="eiqas-table-scroll">
            <table>
              <thead>
                <tr>
                  {Object.keys(currentRows[0] ?? {}).map((name) => (
                    <th key={name}>{name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {currentRows.map((row, index) => (
                  <tr
                    key={index}
                    onClick={() =>
                      inspectRows(index, {
                        ...report.charts[0]!,
                        table: dataTable,
                      })
                    }
                  >
                    {Object.entries(row).map(([key, value]) => (
                      <td key={key}>{value === null ? "—" : String(value)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="eiqas-muted">
            显示实际结果，不会从图形反推数据；点击行可追溯输入。
          </p>
        </section>
      )}
      {!compact && (
        <>
          <div className="eiqas-report-bottom">
            <section>
              <span className="eiqas-eyebrow">IMPLICATIONS</span>
              <h2>对决策意味着什么</h2>
              <ul>
                {report.implications.map((text, index) => (
                  <li key={index}>{text}</li>
                ))}
              </ul>
            </section>
            <section className="eiqas-boundaries">
              <span className="eiqas-eyebrow">BOUNDARIES</span>
              <h2>哪些问题仍不能判断</h2>
              <ul>
                {(limitationsOpen
                  ? report.limitations
                  : report.limitations.slice(0, 5)
                ).map((text, index) => (
                  <li key={index}>{text}</li>
                ))}
              </ul>
              {report.limitations.length > 5 && (
                <button
                  className="eiqas-text-button"
                  onClick={() => setLimitationsOpen(!limitationsOpen)}
                  aria-expanded={limitationsOpen}
                >
                  {limitationsOpen
                    ? "收起次要限制"
                    : `展开完整限制（另 ${report.limitations.length - 5} 条）`}
                </button>
              )}
            </section>
          </div>
          {onRecompute && (
            <section className="eiqas-recompute">
              <div>
                <h2>换一个假设，再看结果</h2>
                <p>使用相同的冻结输入重新计算，保留新的运行记录。</p>
              </div>
              <button onClick={() => setParametersOpen(!parametersOpen)}>
                {parametersOpen ? "收起参数" : "调整参数并重算"}
              </button>
              {parametersOpen && (
                <Parameters report={report} onSubmit={onRecompute} />
              )}
            </section>
          )}
          <details className="eiqas-method">
            <summary>研究方法与计算检查</summary>
            <p>问题：{report.question}</p>
            {report.plan.content.methods.map((method, index) => (
              <p key={index}>
                <strong>{method.name}</strong>：{method.rationale}
              </p>
            ))}
            <h4>假设与所需资料</h4>
            <ul>
              {[
                ...report.plan.content.assumptions,
                ...report.plan.content.required_data,
              ].map((text, index) => (
                <li key={index}>{text}</li>
              ))}
            </ul>
            <h4>实际检查</h4>
            <ul>
              {result.checks.map((check, index) => (
                <li key={index}>
                  {check.passed ? "✓" : "×"} {check.name}
                </li>
              ))}
            </ul>
            <a
              href={eiqasURL(
                `/research/${report.research_id}/runs/${report.run_id}/files/input.json`,
              )}
            >
              下载冻结输入
            </a>{" "}
            ·{" "}
            <a
              href={eiqasURL(
                `/research/${report.research_id}/runs/${report.run_id}/files/script.py`,
              )}
            >
              计算脚本
            </a>{" "}
            ·{" "}
            <a
              href={eiqasURL(
                `/research/${report.research_id}/runs/${report.run_id}/files/execution.log`,
              )}
            >
              执行日志
            </a>
          </details>
        </>
      )}
      {!compact && onReview && (
        <ReaderFeedback report={report} onSubmit={onReview} />
      )}
      <EvidencePanel
        rid={report.research_id}
        sources={report.sources}
        selection={selection}
        onClose={() => setSelection(null)}
      />
    </article>
  );
}

function Parameters({
  report,
  onSubmit,
}: {
  report: Report;
  onSubmit: (parameters: Record<string, unknown>) => void;
}) {
  const [parameters, setParameters] = useState({
    ...report.run.spec.parameters,
  });
  const fields = Object.keys(parameters).filter((key) =>
    [
      "metric",
      "period",
      "from",
      "to",
      "x",
      "y",
      "discount_rate",
      "discount_rates",
    ].includes(key),
  );
  const names: Record<string, string> = {
    metric: "分析指标",
    period: "期间",
    from: "起始期间",
    to: "结束期间",
    x: "关联指标 X",
    y: "关联指标 Y",
    discount_rate: "折现率（%）",
    discount_rates: "折现率组（%，逗号分隔）",
  };
  const metrics = [
    ...new Set(report.dataset.rows.map((row) => String(row.metric))),
  ];
  const periods = [
    ...new Set(report.dataset.rows.map((row) => String(row.period))),
  ].sort();
  return (
    <form
      className="eiqas-parameters"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit(parameters);
      }}
    >
      {fields.map((key) => (
        <label key={key}>
          {names[key]}
          {["metric", "x", "y", "period", "from", "to"].includes(key) ? (
            <select
              value={String(parameters[key])}
              onChange={(event) =>
                setParameters({ ...parameters, [key]: event.target.value })
              }
            >
              {(["metric", "x", "y"].includes(key) ? metrics : periods).map(
                (value) => (
                  <option key={value}>{value}</option>
                ),
              )}
            </select>
          ) : key === "discount_rates" ? (
            <input
              defaultValue={(parameters[key] as number[])
                .map((value) => value * 100)
                .join(", ")}
              onChange={(event) =>
                setParameters({
                  ...parameters,
                  [key]: event.target.value
                    .split(",")
                    .map((value) => Number(value.trim()) / 100),
                })
              }
            />
          ) : (
            <input
              type="number"
              step="0.1"
              min="-99"
              max="1000"
              value={Number(parameters[key]) * 100}
              onChange={(event) =>
                setParameters({
                  ...parameters,
                  [key]: Number(event.target.value) / 100,
                })
              }
            />
          )}
        </label>
      ))}
      {!fields.length && (
        <p>
          当前方法没有可直接调整的参数。可以使用相同输入重跑，或通过研究对话调整方法。
        </p>
      )}
      <button className="eiqas-primary" type="submit">
        发起真实重算
      </button>
    </form>
  );
}
