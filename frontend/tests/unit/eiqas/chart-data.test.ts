import { describe, expect, it } from "@rstest/core";

import { chartRows, formatNumber } from "@/core/eiqas/chart-data";
import type { ChartSpec } from "@/core/eiqas/types";

describe("result-backed chart data", () => {
  const spec: ChartSpec = {
    id: "revenue",
    title: "收入",
    type: "bar",
    x: "period",
    y: "value",
    series: "subject",
    unit: "CNY",
    explanation: "实际结果",
    filters: { metric: "收入" },
  };
  const rows = [
    { subject: "A", period: "2024", metric: "收入", value: 100 },
    { subject: "B", period: "2024", metric: "收入", value: 80 },
    { subject: "A", period: "2024", metric: "投入", value: 10 },
  ];
  it("keeps original result row indexes after linked filtering", () => {
    const frozen = JSON.stringify(rows);
    expect(chartRows(rows, spec, ["B"])).toEqual([{ row: rows[1], index: 1 }]);
    expect(JSON.stringify(rows)).toBe(frozen);
  });
  it("does not display missing or very small results as zero", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(0)).toBe("0");
    expect(formatNumber(0.1, "ratio")).toBe("10%");
    expect(formatNumber(0.000001)).toContain("e-");
  });
  it("keeps percentage levels distinct from normalized ratios", () => {
    expect(formatNumber(3.897, "%")).toBe("3.897%");
    expect(formatNumber(0.03897, "ratio")).toBe("3.9%");
    expect(formatNumber(-0.414, "百分点")).toBe("-0.414个百分点");
  });
});
