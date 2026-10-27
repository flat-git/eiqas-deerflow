"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { eiqasAPI } from "@/core/eiqas/api";
import type { Command, Report, Research } from "@/core/eiqas/types";

import { ReportView } from "./report-view";
import { ResearchChat } from "./research-chat";

const parametersKey = (value: Record<string, unknown>) =>
  JSON.stringify(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)));

export function ResearchReader({
  threadId,
  reportId,
}: {
  threadId: string;
  reportId: string;
}) {
  const [chat, setChat] = useState(false);
  const [busy, setBusy] = useState(false);
  const [command, setCommand] = useState<Command | null>(null);
  const [request, setRequest] = useState<{
    parameters: Record<string, unknown>;
    at: number;
  } | null>(null);
  const studies = useQuery({
    queryKey: ["eiqas", "research"],
    queryFn: ({ signal }) => eiqasAPI<Research[]>("/research", { signal }),
  });
  const rid = studies.data?.find(
    (research) => research.thread_id === threadId,
  )?.id;
  const record = useQuery({
    queryKey: ["eiqas", rid, "result", reportId],
    queryFn: ({ signal }) =>
      eiqasAPI<Report>(`/research/${rid}/records/results/${reportId}`, {
        signal,
      }),
    enabled: Boolean(rid),
  });
  const latest = useQuery({
    queryKey: ["eiqas", rid, "results"],
    queryFn: ({ signal }) =>
      eiqasAPI<Report[]>(`/research/${rid}/records/results`, { signal }),
    enabled: Boolean(rid),
    refetchInterval: request ? 2500 : false,
  });
  const report = record.data;
  const updated =
    request &&
    latest.data
      ?.slice()
      .reverse()
      .find(
        (candidate) =>
          candidate.run_id !== report?.run_id &&
          Date.parse(candidate.run.started_at) >= request.at &&
          parametersKey(candidate.run.spec.parameters) ===
            parametersKey(request.parameters) &&
          ["verified", "partial"].includes(candidate.run.status),
      );
  function recompute(parameters: Record<string, unknown>) {
    if (!report) return;
    setRequest({ parameters, at: Date.now() });
    setChat(true);
    setCommand({
      id: crypto.randomUUID(),
      hidden: true,
      text: `我正在阅读成果 ${report.id}。请使用相同冻结输入数据集 ${report.dataset.id}，执行方法 ${report.run.spec.method}，严格使用新参数 ${JSON.stringify(parameters)}。必须产生新的真实运行记录，并保存基于新运行的结构化成果，解释结果变化和判断限制。`,
    });
  }
  return (
    <div className={`eiqas-reader ${chat ? "with-chat" : ""}`}>
      <header className="eiqas-reader-bar">
        <Link href={`/research/${threadId}`}>← 返回研究工作台</Link>
        <strong>
          EIQAS<span>研究成果</span>
        </strong>
        <button onClick={() => setChat(!chat)}>
          {chat ? "收起研究对话" : "通过对话修改"}
        </button>
      </header>
      <div className="eiqas-reader-body">
        <main>
          {(record.error ?? studies.error) && (
            <p role="alert" className="eiqas-error">
              {(record.error ?? studies.error)?.message}
            </p>
          )}
          {request && (
            <div className="eiqas-recompute-banner">
              {updated ? (
                <>
                  <span>新参数的实际计算与成果已形成。</span>
                  <Link href={`/research/${threadId}/results/${updated.id}`}>
                    查看新结果 →
                  </Link>
                </>
              ) : (
                <span>
                  {busy
                    ? "正在执行参数重算，当前页面仍展示原结果。"
                    : "已请求重算，等待补充或新成果。可在研究对话中查看实际进展。"}
                </span>
              )}
            </div>
          )}
          {report ? (
            <ReportView report={report} onRecompute={recompute} />
          ) : (
            !record.error && <p>正在载入研究成果…</p>
          )}
        </main>
        {chat && (
          <aside className="eiqas-chat-pane">
            <ResearchChat
              threadId={threadId}
              reportId={reportId}
              command={command}
              onCommandSent={() => setCommand(null)}
              onBusyChange={setBusy}
            />
          </aside>
        )}
      </div>
    </div>
  );
}
