import { afterEach, expect, rs, test } from "@rstest/core";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { ReportView } from "@/components/eiqas/report-view";
import type { Report } from "@/core/eiqas/types";

rs.mock("@/components/eiqas/result-chart", () => ({
  ResultChart: ({ subjects }: { subjects: string[] }) => (
    <p>图表筛选：{subjects.join(",") || "全部"}</p>
  ),
}));
rs.mock("@/components/eiqas/evidence-panel", () => ({
  EvidencePanel: ({
    selection,
  }: {
    selection: { title: string; observations: { id: string }[] } | null;
  }) =>
    selection ? (
      <div role="dialog">
        {selection.title}：
        {selection.observations.map((row) => row.id).join(",")}
      </div>
    ) : null,
}));
rs.mock("@/core/eiqas/api", () => ({
  eiqasURL: (path: string) => path,
  downloadExport: rs.fn(),
}));

afterEach(cleanup);

function report(): Report {
  return {
    id: "report-one",
    research_id: "research-one",
    run_id: "run-one",
    title: "合成趋势研究",
    question: "收入如何变化？",
    summary: "完整范围结论不随展示筛选而变化。",
    created_at: "2026-01-01T00:00:00Z",
    scope: { answerable: ["收入变化"], gaps: ["尚不能证明因果"] },
    implications: ["核查差异来源"],
    limitations: ["仅合成样例"],
    findings: ["发现一", "发现二", "发现三", "发现四"].map((text) => ({
      text,
      kind: "fact",
      cells: [
        {
          row: 0,
          column: "value",
          value: 100,
          unit: "CNY",
          observation_ids: ["obs-a"],
        },
      ],
      observation_ids: [],
      evidence: [],
    })),
    charts: [
      {
        id: "chart",
        title: "收入变化",
        type: "bar",
        x: "subject",
        y: "value",
        unit: "CNY",
        explanation: "合成数据",
      },
    ],
    dataset: {
      id: "data",
      title: "冻结输入",
      input_hash: "hash",
      rows: [],
      observations: [
        {
          id: "obs-a",
          source_id: "source-a",
          extraction_id: "extract-a",
          source_hash: "hash",
          raw_text: "收入 100 元",
          value: "100",
          unit: "元",
          subject: "甲",
          period: "2025",
          metric: "收入",
          qualifier: "exact",
          status: "verified",
          flags: [],
          locator: { key: "row-1", text: "收入 100 元" },
        },
      ],
    },
    sources: [],
    provenance: [["obs-a"], ["obs-b"]],
    plan: {
      hash: "plan-hash",
      revision: 1,
      confirmed_at: "2026-01-01",
      content: {
        question: "问题",
        methods: [{ name: "聚合", rationale: "描述", operation: "aggregate" }],
        required_data: [],
        outputs: ["图表"],
        assumptions: [],
        limitations: [],
      },
    },
    run: {
      id: "run-one",
      dataset_id: "data",
      status: "verified",
      spec: { method: "aggregate", parameters: {} },
      input_hash: "hash",
      started_at: "2026-01-01",
      completed_at: "2026-01-01",
      result: {
        rows: [
          { subject: "甲", value: 100 },
          { subject: "乙", value: 200 },
        ],
        checks: [{ name: "实际复算", passed: true }],
        limitations: [],
      },
    },
  };
}

test("reader starts with three findings and reveals further findings on demand", () => {
  render(<ReportView report={report()} />);
  expect(screen.queryByText("发现四")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "展开其余 1 条发现" }));
  expect(screen.getByText("发现四")).toBeTruthy();
});

test("subject filtering preserves the full-scope conclusion and prevents an empty selection", () => {
  render(<ReportView report={report()} />);
  fireEvent.click(screen.getByLabelText("乙"));
  expect(screen.getByText("图表筛选：甲")).toBeTruthy();
  expect(screen.getByText("完整范围结论不随展示筛选而变化。")).toBeTruthy();
  expect(screen.getByLabelText<HTMLInputElement>("甲").disabled).toBe(true);
});

test("a finding opens its frozen input evidence in one action", () => {
  render(<ReportView report={report()} />);
  fireEvent.click(screen.getAllByRole("button", { name: "查看依据 ↗" })[0]!);
  expect(screen.getByRole("dialog").textContent).toContain("obs-a");
});

test("secondary limitations expand without losing the primary judgment boundaries", () => {
  const content = report();
  content.limitations = Array.from({ length: 7 }, (_, i) => `判断边界${i + 1}`);
  render(<ReportView report={content} />);
  expect(screen.getByText("判断边界1")).toBeTruthy();
  expect(screen.getByText("判断边界5")).toBeTruthy();
  expect(screen.queryByText("判断边界6")).toBeNull();
  fireEvent.click(
    screen.getByRole("button", { name: "展开完整限制（另 2 条）" }),
  );
  expect(screen.getByText("判断边界7")).toBeTruthy();
});

test("passed numbers do not obscure a rejected reader review or unassessed plan", () => {
  const content = report();
  content.review = {
    status: "needs_revision",
    comment: "结果没有回答研究问题",
  };
  render(<ReportView report={content} />);
  expect(screen.getByText("数值检查通过")).toBeTruthy();
  expect(screen.getByText("需要修订")).toBeTruthy();
  expect(screen.getByText("未核对方案")).toBeTruthy();
  expect(screen.getByText("结果没有回答研究问题")).toBeTruthy();
});

test("generic evidence tables filter declared columns and open located evidence", () => {
  const content = report();
  content.tables = [
    {
      id: "evidence-one",
      title: "指标定义与可比性",
      columns: [
        { key: "subject", label: "主体", filterable: true },
        { key: "definition", label: "口径" },
      ],
      rows: [
        {
          values: { subject: "甲", definition: "同一统计范围" },
          kind: "company_reported",
          explanation: "机构披露",
          evidence: [],
        },
        {
          values: { subject: "乙", definition: "无法统一口径" },
          kind: "unknown",
          explanation: "缺少分母",
          evidence: [],
        },
      ],
    },
  ];
  render(<ReportView report={content} />);
  fireEvent.change(screen.getByLabelText("指标定义与可比性 · 主体"), {
    target: { value: "乙" },
  });
  expect(screen.queryByText("同一统计范围")).toBeNull();
  expect(screen.getByText("无法统一口径")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "查看表格依据" }));
  expect(screen.getByRole("dialog").textContent).toContain("指标定义与可比性");
});

test("reader feedback calls the user action without changing computational status", async () => {
  const onReview = rs.fn().mockResolvedValue(undefined);
  render(<ReportView report={report()} onReview={onReview} />);
  fireEvent.change(screen.getByLabelText("复核意见"), {
    target: { value: "需要补齐原方案的趋势分析" },
  });
  fireEvent.click(screen.getByRole("button", { name: "需要修订" }));
  expect(onReview).toHaveBeenCalledWith(
    "needs_revision",
    "需要补齐原方案的趋势分析",
  );
});
