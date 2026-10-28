"use client";

import { useState } from "react";

import { eiqasURL } from "@/core/eiqas/api";
import type { EvidenceTable, Report } from "@/core/eiqas/types";

import type { EvidenceSelection } from "./evidence-panel";

const statusLabels: Record<string, string> = {
  completed: "已交付",
  partial: "部分交付",
  blocked: "有缺口",
  not_applicable: "条件不适用",
  not_addressed: "未回应",
};
export const reviewLabels = {
  pending: "读者待复核",
  accepted: "读者已确认",
  needs_revision: "需要修订",
};

export function PlanFulfillment({
  report,
  inspect,
}: {
  report: Report;
  inspect: (index: number) => void;
}) {
  const coverage = report.coverage;
  const unresolved = coverage?.items.filter(
    (item) => !["completed", "not_applicable"].includes(item.status),
  );
  return (
    <details className="eiqas-fulfillment">
      <summary>
        <strong>方案履行核对</strong>
        <span>
          {!coverage || coverage.status === "not_assessed"
            ? "未核对方案"
            : coverage.status === "declared_complete"
              ? "AI已申报履行，待读者核对"
              : `方案部分履行 · ${unresolved?.length ?? 0} 项待解决`}
        </span>
      </summary>
      <p className="eiqas-muted">
        履行情况由 AI 申报，引用经过程序核对。是否回答研究问题，仍需读者判断。
      </p>
      {!coverage && <p>本成果尚未提交逐项核对，不推定方案已完成。</p>}
      {coverage?.items.map((item) => (
        <div className="eiqas-plan-item" key={`${item.kind}-${item.index}`}>
          <strong>{item.name}</strong>
          <span className="eiqas-kind">{statusLabels[item.status]}</span>
          <p>{item.explanation}</p>
          <div className="eiqas-actions">
            {item.finding_indices.map((index) => (
              <button key={index} onClick={() => inspect(index)}>
                发现 {index + 1} 的依据
              </button>
            ))}
            {item.table_ids.map((id) => (
              <a key={id} href={`#evidence-table-${id}`}>
                {report.tables?.find((table) => table.id === id)?.title ??
                  "证据表"}
              </a>
            ))}
            {item.run_ids.map((id) => (
              <a
                key={id}
                href={eiqasURL(
                  `/research/${report.research_id}/runs/${id}/files/result.json`,
                )}
              >
                计算回执 {id.slice(0, 8)}
              </a>
            ))}
            {item.plan_ref && <span>引用已确认方案本身</span>}
          </div>
        </div>
      ))}
    </details>
  );
}

export function EvidenceTableView({
  table,
  inspect,
}: {
  table: EvidenceTable;
  inspect: (selection: EvidenceSelection) => void;
}) {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [limit, setLimit] = useState(20);
  const rows = table.rows.filter((row) =>
    Object.entries(filters).every(
      ([key, value]) => !value || row.values[key] === value,
    ),
  );
  return (
    <section className="eiqas-evidence-table" id={`evidence-table-${table.id}`}>
      <h2>{table.title}</h2>
      <div className="eiqas-filters">
        {table.columns
          .filter((column) => column.filterable)
          .map((column) => (
            <label key={column.key}>
              {column.label}
              <select
                aria-label={`${table.title} · ${column.label}`}
                value={filters[column.key] ?? ""}
                onChange={(event) => {
                  setFilters({ ...filters, [column.key]: event.target.value });
                  setLimit(20);
                }}
              >
                <option value="">全部</option>
                {[
                  ...new Set(table.rows.map((row) => row.values[column.key])),
                ].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
            </label>
          ))}
      </div>
      <div className="eiqas-table-scroll">
        <table>
          <thead>
            <tr>
              {table.columns.map((column) => (
                <th key={column.key}>{column.label}</th>
              ))}
              <th>判断与依据</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, limit).map((row, index) => (
              <tr key={index}>
                {table.columns.map((column) => (
                  <td key={column.key}>{row.values[column.key]}</td>
                ))}
                <td>
                  <span className={`eiqas-kind ${row.kind}`}>
                    {
                      {
                        fact: "据数据与原文",
                        company_reported: "机构自报",
                        inference: "分析推断",
                        unknown: "尚不可判断",
                      }[row.kind]
                    }
                  </span>
                  <p>{row.explanation}</p>
                  <button
                    onClick={() =>
                      inspect({
                        title: table.title,
                        observations: [],
                        references: row.evidence,
                      })
                    }
                  >
                    查看表格依据
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="eiqas-actions">
        <span className="eiqas-muted">
          {Math.min(rows.length, limit)} / {rows.length} 行；完整表与定位随 ZIP
          导出。
        </span>
        {rows.length > limit && (
          <button onClick={() => setLimit(limit + 20)}>再显示 20 行</button>
        )}
      </div>
    </section>
  );
}

export function ReaderFeedback({
  report,
  onSubmit,
}: {
  report: Report;
  onSubmit: (
    status: "accepted" | "needs_revision",
    comment: string,
  ) => Promise<void>;
}) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(status: "accepted" | "needs_revision") {
    setBusy(true);
    setError("");
    try {
      await onSubmit(
        status,
        comment.trim() ||
          (status === "accepted"
            ? "读者确认当前成果与所列判断范围"
            : "请按原方案修订研究成果"),
      );
      setComment("");
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "复核反馈未保存，请重试。",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="eiqas-feedback">
      <h2>这份成果是否回答了研究问题</h2>
      <p>
        核对方案、主要结果和判断边界。接受当前范围会保留未完成事项；需要修订的内容可通过研究对话继续处理。
      </p>
      <label>
        复核意见
        <textarea
          value={comment}
          onChange={(event) => setComment(event.target.value)}
          placeholder="哪些问题已回答，哪些结论或依据仍需补充"
        />
      </label>
      <div className="eiqas-actions">
        <button
          disabled={busy}
          onClick={() => {
            void submit("needs_revision");
          }}
        >
          需要修订
        </button>
        <button
          disabled={busy}
          onClick={() => {
            void submit("accepted");
          }}
        >
          接受当前范围
        </button>
        <span className="eiqas-muted">
          {busy ? "保存中…" : reviewLabels[report.review?.status ?? "pending"]}
        </span>
      </div>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
