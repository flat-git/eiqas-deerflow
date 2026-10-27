import type { ChartSpec, DataRow } from "./types";

export function chartRows(
  rows: DataRow[],
  chart: ChartSpec,
  subjects: string[] = [],
) {
  return rows
    .map((row, index) => ({ row, index }))
    .filter(
      ({ row }) =>
        Object.entries(chart.filters ?? {}).every(
          ([key, value]) => String(row[key]) === value,
        ) &&
        (!subjects.length ||
          !("subject" in row) ||
          subjects.includes(String(row.subject))),
    );
}

export function formatNumber(value: unknown, unit = ""): string {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  if (unit === "ratio")
    return `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(number * 100)}%`;
  if (number !== 0 && Math.abs(number) < 0.001) return number.toExponential(2);
  if (unit === "CNY" && Math.abs(number) >= 1e8)
    return `${new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(number / 1e8)}亿元`;
  return (
    new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 4 }).format(
      number,
    ) + (unit === "CNY" ? "元" : unit === "USD" ? "美元" : "")
  );
}

export const stageNames = {
  question: "明确问题",
  plan: "设计方案",
  data: "准备数据",
  analysis: "计算分析",
  review: "复核交付",
} as const;
export const methodNames: Record<string, string> = {
  aggregate: "聚合分析",
  growth: "增长分析",
  structure: "结构分析",
  contribution: "变化贡献",
  correlation: "关联分析",
  cost_benefit: "成本收益",
  sensitivity: "敏感性分析",
  python: "定制计算",
};
export const stateNames: Record<string, string> = {
  draft: "待设计方案",
  ready: "方案已确认",
  running: "正在执行",
  verified: "计算已校验",
  partial: "部分可判断",
  failed: "执行失败",
  interrupted: "执行中断",
  cancelled: "已取消",
  review: "待核对",
  acquired: "原件已取得",
  restricted: "访问受限",
};
