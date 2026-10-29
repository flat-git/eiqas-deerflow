"use client";

import { useState } from "react";
import { toast } from "sonner";

import { eiqasAPI, writeJSON } from "@/core/eiqas/api";
import type { PlanningState, Research } from "@/core/eiqas/types";

export const acquisitionNames = {
  public: "公开资料",
  internal: "内部信息",
  expert: "专家访谈",
  commercial: "付费数据／研报",
  collection: "新增采集",
  unknown: "渠道待确认",
};
export const availabilityNames: Record<string, string> = {
  unknown: "未核实",
  suggested: "渠道建议",
  located: "已有线索",
  sample_checked: "公开样本已核实",
  available: "实际数据已取得",
  unavailable: "无法取得",
  restricted: "访问受限",
  quality_issue: "口径／质量待核对",
  invalid: "依据失效",
};
function textOr(value: string | undefined, fallback: string): string {
  return value?.trim() ? value : fallback;
}
const answerNames = {
  answer: "可以回答",
  partial: "只能部分回答",
  unanswerable: "当前无法判断",
};

export function PlanningPanel({
  research,
  planning,
  busy,
  onDiscuss,
  dataOnly = false,
}: {
  research: Research;
  planning?: PlanningState;
  busy: boolean;
  onDiscuss: (text: string) => void;
  dataOnly?: boolean;
}) {
  const [boundary, setBoundary] = useState("");
  const content = research.plan?.content;
  if (!content) return null;
  return (
    <div className="eiqas-design-panel">
      {!dataOnly && (
        <>
          <div className="eiqas-design-brief">
            <p>
              <strong>决策用途</strong>
              {textOr(content.decision_use, "待讨论")}
            </p>
            <p>
              <strong>研究范围</strong>
              {textOr(content.scope, "待讨论")}
            </p>
          </div>
          <h3>原问题与本次可回答范围</h3>
          <div className="eiqas-question-decisions">
            {content.research_questions?.map((q) => {
              const decision = content.question_decisions?.find(
                (d) => d.question_id === q.id,
              );
              return (
                <article key={q.id}>
                  <strong>{q.text}</strong>
                  <span className="eiqas-badge">
                    {decision ? answerNames[decision.status] : "尚未评估"}
                  </span>
                  <p>
                    {textOr(
                      decision?.explanation,
                      "需要结合方法与实际数据评估。",
                    )}
                  </p>
                </article>
              );
            })}
          </div>
          {Boolean(content.scope_changes?.length) && (
            <div className="eiqas-design-boundary">
              <strong>相对原目标的调整</strong>
              <ul>
                {content.scope_changes?.map((text, i) => (
                  <li key={i}>{text}</li>
                ))}
              </ul>
            </div>
          )}
          <h3>候选方法与选择</h3>
          <div className="eiqas-method-cards">
            {(planning?.design.methods ?? content.methods).map((method, i) => (
              <article key={method.id ?? i}>
                <span>
                  {method.selected === false
                    ? "候选 · 本次未选"
                    : method.role === "supporting"
                      ? "辅助分析"
                      : "主要量化分析"}
                </span>
                <h3>{method.name}</h3>
                <p>{method.rationale}</p>
                <details>
                  <summary>方法依据、计算与数据前提</summary>
                  <dl>
                    <dt>依据</dt>
                    <dd>{textOr(method.basis, "待补充")}</dd>
                    <dt>计算逻辑</dt>
                    <dd>{textOr(method.calculation, "待补充")}</dd>
                    <dt>适用条件</dt>
                    <dd>{textOr(method.applicability, "待补充")}</dd>
                    <dt>预期图表</dt>
                    <dd>
                      {textOr(method.expected_outputs?.join("；"), "待补充")}
                    </dd>
                  </dl>
                </details>
              </article>
            ))}
          </div>
        </>
      )}
      <h3>数据要求与补充路径</h3>
      <p className="eiqas-muted">
        渠道建议和检索线索仍需核实。公开样本可支持获取可行性判断，正式计算使用实际数据集。
      </p>
      {!planning ? (
        <p>正在核查数据可得性…</p>
      ) : (
        <div className="eiqas-requirement-list">
          {planning.design.requirements.map((need) => (
            <article key={need.id}>
              <div className="eiqas-section-title">
                <h4>{need.title}</h4>
                <span className="eiqas-badge">
                  {acquisitionNames[need.category]} ·{" "}
                  {availabilityNames[need.status] ?? need.status}
                </span>
              </div>
              <p>
                {textOr(
                  need.assessment?.reason,
                  "尚未查看实际资料，当前仅登记数据要求。",
                )}
              </p>
              <p>
                <strong>下一步：</strong>
                {textOr(
                  need.issue,
                  textOr(
                    need.assessment?.next_action,
                    need.channels.join("；"),
                  ),
                )}
              </p>
              <details>
                <summary>字段、口径及缺失影响</summary>
                <dl>
                  <dt>所需字段／指标</dt>
                  <dd>
                    {need.fields.join("、")} / {need.metrics.join("、")}
                  </dd>
                  <dt>粒度／期间／单位</dt>
                  <dd>
                    {need.grain} / {need.period} / {need.units}
                  </dd>
                  <dt>影响的方法</dt>
                  <dd>
                    {need.method_ids
                      .map(
                        (id) =>
                          content.methods.find((m) => m.id === id)?.name ?? id,
                      )
                      .join("、")}
                  </dd>
                  <dt>缺失影响</dt>
                  <dd>{need.impact_if_missing}</dd>
                  <dt>替代建议</dt>
                  <dd>{need.fallback}</dd>
                </dl>
                {need.assessment?.evidence.map((ref, i) => (
                  <blockquote key={i}>
                    {ref.quote}
                    <small>
                      定位：{ref.locator_key} · 来源 {ref.source_id.slice(0, 8)}
                    </small>
                  </blockquote>
                ))}
              </details>
            </article>
          ))}
        </div>
      )}
      {Boolean(content.data_constraints?.length) && (
        <div className="eiqas-design-boundary">
          <strong>本次数据边界</strong>
          <ul>
            {content.data_constraints?.map((text, i) => (
              <li key={i}>{text}</li>
            ))}
          </ul>
        </div>
      )}
      <details className="eiqas-boundary-input">
        <summary>说明能提供的数据，重新讨论方案</summary>
        <label htmlFor="eiqas-data-boundary">
          当前能提供什么、哪些资料无法补充？
        </label>
        <textarea
          id="eiqas-data-boundary"
          value={boundary}
          onChange={(e) => setBoundary(e.target.value)}
          rows={3}
          placeholder="例如：只能使用官方年报，没有内部台账，也不购买研报。"
        />
        <button
          disabled={busy || !boundary.trim()}
          onClick={() => {
            onDiscuss(
              `我的数据条件与边界：${boundary.trim()}。请保留原研究问题，重新评估候选量化方法、分类数据缺口和可回答范围，明确范围调整，保存修订方案供我确认。`,
            );
            setBoundary("");
          }}
        >
          据此重拟方案
        </button>
      </details>
      {!dataOnly &&
        !research.plan?.confirmed_at &&
        Boolean(planning?.design.errors.length) && (
          <details className="eiqas-design-blockers">
            <summary>
              最终确认前还需解决 {planning?.design.errors.length} 项
            </summary>
            <ul>
              {planning?.design.errors.map((text, i) => (
                <li key={i}>{text}</li>
              ))}
            </ul>
          </details>
        )}
    </div>
  );
}

export function ResearchInputRequest({
  rid,
  request,
  busy,
  onReply,
}: {
  rid: string;
  request: NonNullable<PlanningState["workflow"]["request"]>;
  busy: boolean;
  onReply: (text: string) => void;
}) {
  const [reply, setReply] = useState("");
  const [saving, setSaving] = useState(false);
  async function submit() {
    setSaving(true);
    try {
      await eiqasAPI(
        `/research/${rid}/input-requests/${request.id}/reply`,
        writeJSON("POST", {
          request_hash: request.content_hash,
          response: reply.trim(),
        }),
      );
      onReply(
        `我对研究追问的答复：${reply.trim()}。请核对这是否改变方案；按现有口径补数据可继续，实质改变目标或方法则保存修订方案等待确认。`,
      );
      setReply("");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "答复未保存");
    } finally {
      setSaving(false);
    }
  }
  return (
    <section className="eiqas-input-request">
      <strong>需要你决定后继续</strong>
      <ul>
        {request.questions.map((text, i) => (
          <li key={i}>{text}</li>
        ))}
      </ul>
      <p>影响：{request.impact}</p>
      <label htmlFor="eiqas-critical-reply">你的答复</label>
      <textarea
        id="eiqas-critical-reply"
        value={reply}
        onChange={(e) => setReply(e.target.value)}
        rows={3}
      />
      <button
        disabled={busy || saving || !reply.trim()}
        onClick={() => void submit()}
      >
        {saving ? "保存中…" : "保存答复并继续讨论"}
      </button>
    </section>
  );
}
