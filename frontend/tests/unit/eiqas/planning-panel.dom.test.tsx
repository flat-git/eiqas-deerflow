import { afterEach, expect, rs, test } from "@rstest/core";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { PlanningPanel } from "@/components/eiqas/planning-panel";
import type { PlanningState, Research } from "@/core/eiqas/types";

afterEach(cleanup);

function fixture(): { research: Research; planning: PlanningState } {
  const method = {
    id: "method",
    name: "同口径年度变化",
    rationale: "回答变化问题",
    selected: true,
    role: "primary" as const,
    basis: "差分",
    calculation: "当期减基期",
    applicability: "口径一致",
    expected_outputs: ["趋势图"],
  };
  const requirement = {
    id: "need",
    title: "年度良率",
    method_ids: ["method"],
    kind: "quantitative",
    required: true,
    category: "public" as const,
    fields: ["良率"],
    metrics: ["良率"],
    grain: "产线×年度",
    period: "2024—2025",
    units: "%",
    channels: ["官方报告"],
    impact_if_missing: "不能比较",
    fallback: "保留缺口",
  };
  return {
    research: {
      id: "r",
      thread_id: "thread",
      question: "良率与成本？",
      stage: "plan",
      status: "draft",
      created_at: "",
      updated_at: "",
      answerable: [],
      gaps: [],
      workflow_version: 2,
      plan: {
        hash: "hash",
        revision: 1,
        confirmed_at: null,
        content: {
          question: "良率与成本？",
          methods: [method],
          required_data: ["良率"],
          assumptions: [],
          outputs: ["趋势图"],
          limitations: [],
          decision_use: "改善决策",
          scope: "同一产线",
          research_questions: [{ id: "q", text: "成本节约多少？" }],
          question_decisions: [
            {
              question_id: "q",
              status: "unanswerable",
              explanation: "缺少成本台账",
            },
          ],
          scope_changes: ["本次保留成本问题，只执行良率分析"],
          data_requirements: [requirement],
        },
      },
    },
    planning: {
      design: {
        can_confirm: false,
        errors: ["必要数据未核实"],
        methods: [
          {
            ...method,
            readiness: "needs_data",
            missing_requirement_ids: ["need"],
          },
        ],
        requirements: [
          {
            ...requirement,
            requirement_hash: "need-hash",
            status: "located",
            issue: "",
            assessment: {
              reason: "找到链接，未取得",
              next_action: "下载核查",
              gap_types: [],
              evidence: [],
            },
          },
        ],
        question_decisions: [],
      },
      workflow: { action: "refine_design", automatic: true },
    },
  };
}

test("shows original unanswered questions, acquisition leads and method prerequisites separately", () => {
  render(<PlanningPanel {...fixture()} busy={false} onDiscuss={rs.fn()} />);
  expect(screen.getByText("当前无法判断")).toBeTruthy();
  expect(screen.getByText("缺少成本台账")).toBeTruthy();
  expect(screen.getByText("公开资料 · 已有线索")).toBeTruthy();
  expect(screen.queryByText("实际数据已取得")).toBeNull();
  expect(screen.getByText("必要数据未核实")).toBeTruthy();
});

test("a data boundary starts a visible redesign conversation without approving or erasing the original question", () => {
  const onDiscuss = rs.fn();
  render(<PlanningPanel {...fixture()} busy={false} onDiscuss={onDiscuss} />);
  fireEvent.change(
    screen.getByLabelText("当前能提供什么、哪些资料无法补充？"),
    { target: { value: "仅使用公开年报" } },
  );
  fireEvent.click(screen.getByText("据此重拟方案"));
  expect(onDiscuss).toHaveBeenCalledWith(
    expect.stringContaining("仅使用公开年报"),
  );
  expect(onDiscuss).toHaveBeenCalledWith(
    expect.stringContaining("保留原研究问题"),
  );
  expect(screen.getByText("成本节约多少？")).toBeTruthy();
});
