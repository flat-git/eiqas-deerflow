"use client";

import type { EChartsOption } from "echarts";
import { useEffect, useRef } from "react";

import { chartRows, formatNumber } from "@/core/eiqas/chart-data";
import type { ChartSpec, DataRow } from "@/core/eiqas/types";

export function ResultChart({
  rows,
  chart,
  subjects = [],
  onRowClick,
}: {
  rows: DataRow[];
  chart: ChartSpec;
  subjects?: string[];
  onRowClick: (index: number) => void;
}) {
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let disposed = false;
    let cleanup = () => {
      /* initialized after the chart module loads */
    };
    void import("echarts").then((echarts) => {
      if (disposed || !element.current) return;
      const graph = echarts.init(element.current, undefined, {
        renderer: "canvas",
      });
      const values = chartRows(rows, chart, subjects);
      const categories = [
        ...new Set(values.map(({ row }) => String(row[chart.x]))),
      ];
      const groups = chart.series
        ? [...new Set(values.map(({ row }) => String(row[chart.series!])))]
        : [chart.title];
      const series = groups.map((group) => ({
        name: group,
        type: chart.type,
        smooth: false,
        connectNulls: false,
        barMaxWidth: 42,
        data:
          chart.type === "scatter"
            ? values
                .filter(
                  ({ row }) =>
                    !chart.series || String(row[chart.series]) === group,
                )
                .map(({ row, index }) => ({
                  value: [Number(row[chart.x]), Number(row[chart.y])],
                  originalRow: index,
                }))
            : categories.map((category) => {
                const item = values.find(
                  ({ row }) =>
                    String(row[chart.x]) === category &&
                    (!chart.series || String(row[chart.series]) === group),
                );
                return {
                  value: item?.row[chart.y] ?? null,
                  originalRow: item?.index,
                };
              }),
      }));
      graph.setOption({
        color: ["#315d47", "#b39462", "#718d8a", "#8b7367"],
        textStyle: { fontFamily: '"Noto Sans SC", "PingFang SC", sans-serif' },
        grid: { left: 70, right: 24, top: 48, bottom: 64 },
        tooltip: {
          trigger: chart.type === "scatter" ? "item" : "axis",
          renderMode: "richText",
          valueFormatter: (value: unknown) => formatNumber(value, chart.unit),
        },
        legend: { top: 0, textStyle: { color: "#686a5f" } },
        toolbox: {
          right: 10,
          feature: {
            saveAsImage: {
              title: "下载图形",
              name: chart.title,
              pixelRatio: 2,
            },
          },
        },
        xAxis: {
          type: chart.type === "scatter" ? "value" : "category",
          data: chart.type === "scatter" ? undefined : categories,
          axisLine: { lineStyle: { color: "#cecfc3" } },
          axisLabel: { color: "#6c7064", hideOverlap: true },
        },
        yAxis: {
          type: "value",
          name:
            chart.unit === "ratio"
              ? "%"
              : chart.unit === "CNY"
                ? "元"
                : chart.unit,
          axisLabel: {
            color: "#6c7064",
            formatter: (value: number) => formatNumber(value, chart.unit),
          },
          splitLine: { lineStyle: { color: "#e8e9df" } },
        },
        dataZoom:
          categories.length > 10
            ? [{ type: "inside" }, { type: "slider", height: 14, bottom: 0 }]
            : [],
        series,
      } as EChartsOption);
      graph.on("click", (event) => {
        const data = event.data as { originalRow?: number } | undefined;
        if (typeof data?.originalRow === "number") onRowClick(data.originalRow);
      });
      const observer = new ResizeObserver(() => graph.resize());
      observer.observe(element.current);
      cleanup = () => {
        observer.disconnect();
        graph.dispose();
      };
    });
    return () => {
      disposed = true;
      cleanup();
    };
  }, [chart, rows, subjects, onRowClick]);
  return (
    <div
      className="eiqas-chart"
      ref={element}
      role="img"
      aria-label={`${chart.title}，点击图形可查看数据依据`}
    />
  );
}
