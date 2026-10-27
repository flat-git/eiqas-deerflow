"use client";

import { useEffect, useState } from "react";

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { eiqasAPI, eiqasURL } from "@/core/eiqas/api";
import { formatNumber } from "@/core/eiqas/chart-data";
import type {
  EvidenceReference,
  Observation,
  Source,
} from "@/core/eiqas/types";

export type EvidenceSelection = {
  title: string;
  observations: Observation[];
  references?: EvidenceReference[];
};

export function EvidencePanel({
  rid,
  sources,
  selection,
  onClose,
}: {
  rid: string;
  sources: Source[];
  selection: EvidenceSelection | null;
  onClose: () => void;
}) {
  const [index, setIndex] = useState(0);
  const [preview, setPreview] = useState(false);
  const [previewState, setPreviewState] = useState<{
    key: string;
    error?: string;
  }>({ key: "" });
  useEffect(() => {
    setIndex(0);
    setPreview(false);
  }, [selection]);
  const items = [
    ...(selection?.observations.map((observation) => ({
      source_id: observation.source_id,
      locator: observation.locator,
      quote: observation.raw_text,
      label: `${observation.subject} · ${observation.metric} · ${observation.period}`,
      value: `${observation.value} ${observation.unit}`,
      explanation: "该原始值属于本次计算保留的输入。",
    })) ?? []),
    ...(selection?.references?.map((reference) => ({
      ...reference,
      label: "原文依据",
      value: "",
    })) ?? []),
  ];
  const item = items[index];
  const source = sources.find((source) => source.id === item?.source_id);
  const page = item?.locator.page;
  const previewKey = source && page ? `${rid}/${source.id}/${page}` : "";
  useEffect(() => {
    if (!preview || !source || !page) return;
    const controller = new AbortController();
    eiqasAPI(
      `/research/${rid}/sources/${source.id}/preview-info?page=${page}`,
      { signal: controller.signal },
    )
      .then(() => {
        if (!controller.signal.aborted) setPreviewState({ key: previewKey });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setPreviewState({
            key: previewKey,
            error: error instanceof Error ? error.message : "原件预览检查失败",
          });
      });
    return () => controller.abort();
  }, [preview, source, page, rid, previewKey]);
  return (
    <Sheet
      open={Boolean(selection)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <SheetContent className="eiqas eiqas-evidence">
        <SheetHeader>
          <SheetTitle>依据与原始数据</SheetTitle>
          <SheetDescription>{selection?.title}</SheetDescription>
        </SheetHeader>
        <div className="eiqas-evidence-body">
          {items.length > 1 && (
            <label>
              用于该判断的依据
              <select
                value={index}
                onChange={(event) => {
                  setIndex(Number(event.target.value));
                  setPreview(false);
                }}
              >
                {items.map((value, position) => (
                  <option key={position} value={position}>
                    {position + 1}. {value.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          {item && source ? (
            <>
              <span className="eiqas-eyebrow">{item.label}</span>
              {item.value && (
                <div className="eiqas-evidence-value">{item.value}</div>
              )}
              <h3>{source.title}</h3>
              <p className="eiqas-muted">
                {source.organization} ·{" "}
                {new Date(source.retrieved_at).toLocaleDateString("zh-CN")}
              </p>
              <div className="eiqas-locator">
                {page
                  ? `PDF 物理第 ${page} 页`
                  : item.locator.row
                    ? `${item.locator.sheet ?? "表格"} · 第 ${item.locator.row} 行 · ${item.locator.column ?? ""} 列`
                    : `原文定位：${item.locator.key}`}
                {item.locator.ocr && <span>扫描识别内容</span>}
              </div>
              <blockquote>{item.quote}</blockquote>
              <p>{item.explanation}</p>
              <div className="eiqas-actions">
                {page && (
                  <button onClick={() => setPreview(!preview)}>
                    {preview ? "收起原件" : "预览物理页"}
                  </button>
                )}
                <a
                  href={eiqasURL(
                    `/research/${rid}/sources/${source.id}/original`,
                  )}
                  target="_blank"
                  rel="noreferrer"
                >
                  下载留存原件
                </a>
                <a href={source.url} target="_blank" rel="noreferrer">
                  原文入口 ↗
                </a>
              </div>
              {preview && page && (
                <>
                  {previewState.key !== previewKey ? (
                    <p role="status">正在检查原件和物理页…</p>
                  ) : previewState.error ? (
                    <p role="alert" className="eiqas-error">
                      {previewState.error}
                    </p>
                  ) : (
                    <iframe
                      title={`原件物理第${page}页`}
                      src={`${eiqasURL(`/research/${rid}/sources/${source.id}/preview`)}?page=${page}#page=${page}`}
                    />
                  )}
                  <p className="eiqas-muted">
                    若浏览器无法嵌入
                    PDF，可下载原件并按上述物理页定位。原件缺失或完整性不符时，服务会明确拒绝预览。
                  </p>
                </>
              )}
              <details>
                <summary>来源与校验信息</summary>
                <p>SHA-256：{source.sha256}</p>
                <p>
                  摘录及数值均保留在本研究的证据记录中。
                  {formatNumber(items.length)}条依据可以逐项查看。
                </p>
              </details>
            </>
          ) : (
            <p>该判断尚无可定位依据，请查看研究限制或在对话中补充。</p>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
