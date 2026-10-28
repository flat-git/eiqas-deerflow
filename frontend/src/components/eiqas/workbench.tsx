"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowUpRight,
  PanelRightClose,
  PanelRightOpen,
  Plus,
  Search,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { eiqasAPI, eiqasURL, writeJSON } from "@/core/eiqas/api";
import { methodNames, stageNames, stateNames } from "@/core/eiqas/chart-data";
import type {
  Command,
  Dataset,
  Observation,
  Report,
  Research,
  Run,
  Source,
  Stage,
} from "@/core/eiqas/types";
import { createThread } from "@/core/threads/api";

import { EvidencePanel, type EvidenceSelection } from "./evidence-panel";
import { ReportView } from "./report-view";
import { ResearchChat } from "./research-chat";

function useRecords<T>(rid: string | undefined, name: string) {
  return useQuery({
    queryKey: ["eiqas", rid, name],
    queryFn: ({ signal }) =>
      eiqasAPI<T[]>(`/research/${rid}/records/${name}`, { signal }),
    enabled: Boolean(rid),
    refetchInterval: 2500,
  });
}

export function ResearchWorkbench({ threadId }: { threadId?: string }) {
  const router = useRouter();
  const search = useSearchParams();
  const client = useQueryClient();
  const alive = useRef(true);
  const [stage, setStage] = useState<Stage>("question");
  const [follow, setFollow] = useState(true);
  const [newQuestion, setNewQuestion] = useState("");
  const [question, setQuestion] = useState("");
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [chatOpen, setChatOpen] = useState(true);
  const [busy, setBusy] = useState(false);
  const [command, setCommand] = useState<Command | null>(null);
  const [selection, setSelection] = useState<EvidenceSelection | null>(null);
  const studies = useQuery({
    queryKey: ["eiqas", "research"],
    queryFn: ({ signal }) => eiqasAPI<Research[]>("/research", { signal }),
    refetchInterval: 2500,
  });
  const research = studies.data?.find((item) => item.thread_id === threadId);
  const rid = research?.id;
  const canonicalQuestion = research?.question;
  const sourceQuery = useRecords<Source>(rid, "sources");
  const observationQuery = useRecords<Observation>(rid, "observations");
  const datasetQuery = useRecords<Dataset>(rid, "datasets");
  const runQuery = useRecords<Run>(rid, "runs");
  const reportQuery = useRecords<Report>(rid, "results");
  const sources = sourceQuery.data ?? [];
  const observations = observationQuery.data ?? [];
  const datasets = datasetQuery.data ?? [];
  const runs = runQuery.data ?? [];
  const reports = reportQuery.data ?? [];
  const latest = reports.at(-1);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  useEffect(() => {
    if (research && follow) setStage(research.stage);
  }, [research?.stage, follow, research]);
  useEffect(() => {
    if (canonicalQuestion !== undefined) setQuestion(canonicalQuestion);
  }, [canonicalQuestion]);
  useEffect(() => {
    if (research && search.get("start") === "1")
      setCommand({
        id: `start-${research.id}`,
        text: `研究问题：${research.question}。请先讨论必要范围，并保存问题导向的研究方案。给出方法及依据、数据要求、假设、产出和限制。等待我在工作台确认方案后再执行。`,
      });
  }, [research?.id, research, search]);
  const commandSent = useCallback(() => {
    setCommand(null);
    if (threadId && search.get("start"))
      history.replaceState(null, "", `/research/${threadId}`);
  }, [search, threadId]);
  function ask(text: string) {
    setChatOpen(true);
    setCommand({ id: crypto.randomUUID(), text, hidden: true });
  }
  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (!newQuestion.trim() || creating) return;
    setCreating(true);
    const id = crypto.randomUUID();
    try {
      await createThread(id);
      await eiqasAPI<Research>(
        "/research",
        writeJSON("POST", { thread_id: id, question: newQuestion.trim() }),
      );
      await client.invalidateQueries({ queryKey: ["eiqas", "research"] });
      if (alive.current) router.push(`/research/${id}?start=1`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "未能创建研究");
    } finally {
      if (alive.current) setCreating(false);
    }
  }
  async function saveQuestion() {
    if (!research || question.trim() === research.question || !question.trim())
      return;
    setSaving(true);
    try {
      await eiqasAPI(
        `/research/${rid}/question`,
        writeJSON("PATCH", { question: question.trim() }),
      );
      await client.invalidateQueries({ queryKey: ["eiqas"] });
      toast.success("问题已更新，原方案需要重新核对确认。");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }
  async function confirm() {
    if (!research?.plan) return;
    setSaving(true);
    try {
      await eiqasAPI(
        `/research/${rid}/confirm`,
        writeJSON("POST", { plan_hash: research.plan.hash }),
      );
      await client.invalidateQueries({ queryKey: ["eiqas"] });
      setStage("data");
      setFollow(true);
      ask(
        "我已在工作台确认当前方案。请按已确认方案自主取得公开原件、准备可追溯的数据、执行真实计算并生成含图表的成果。关键缺失、冲突、OCR存疑或实质改变目标和方法时再询问。不得把业务背景指标或披露数量自动当作 AI 能力评分。完成计算检查后使用 eiqas_submit_result 保存成果。",
      );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "确认失败");
    } finally {
      setSaving(false);
    }
  }
  function recompute(parameters: Record<string, unknown>) {
    if (!latest) return;
    ask(
      `请使用冻结数据集 ${latest.dataset.id} 进行新的实际计算，方法 ${latest.run.spec.method}，参数严格使用 ${JSON.stringify(parameters)}。保存新的运行和更新后的结构化成果，说明变化与限制。`,
    );
  }
  const error =
    studies.error ??
    sourceQuery.error ??
    observationQuery.error ??
    datasetQuery.error ??
    runQuery.error ??
    reportQuery.error;
  return (
    <div className="eiqas-layout">
      <aside className="eiqas-sidebar">
        <Link className="eiqas-brand" href="/research">
          <span>e.</span>
          <strong>
            EIQAS<small>定量研究工作台</small>
          </strong>
        </Link>
        <Link className="eiqas-new-study" href="/research">
          <Plus size={15} />
          新建研究
        </Link>
        <div className="eiqas-sidebar-label">
          研究记录 <span>{studies.data?.length ?? 0}</span>
        </div>
        <nav>
          {studies.data?.map((item) => (
            <Link
              key={item.id}
              className={item.thread_id === threadId ? "is-selected" : ""}
              href={`/research/${item.thread_id}`}
            >
              <span>{item.question}</span>
              <small>
                {new Date(item.created_at).toLocaleDateString("zh-CN")} ·{" "}
                {stageNames[item.stage]}
              </small>
            </Link>
          ))}
        </nav>
        <footer>
          <span className="eiqas-live-dot" />
          本机 · 单用户<Link href="/workspace/capabilities">模型与工具 ↗</Link>
          <a
            href="https://github.com/flat-git/eiqas-deerflow"
            target="_blank"
            rel="noreferrer"
          >
            v0.1 开发版
          </a>
        </footer>
      </aside>
      <div className="eiqas-workspace">
        <header className="eiqas-topbar">
          <div>
            研究工作台 <span>/</span> {research ? "研究推进" : "开始一项研究"}
          </div>
          <div>
            {research && (
              <span className="eiqas-badge">
                {busy
                  ? "AI 正在推进"
                  : (stateNames[research.status] ?? research.status)}
              </span>
            )}
            {threadId && (
              <button
                aria-label={chatOpen ? "收起研究对话" : "展开研究对话"}
                onClick={() => setChatOpen(!chatOpen)}
              >
                {chatOpen ? (
                  <PanelRightClose size={18} />
                ) : (
                  <PanelRightOpen size={18} />
                )}
              </button>
            )}
          </div>
        </header>
        <div
          className={`eiqas-work-area ${chatOpen && research ? "with-chat" : ""}`}
        >
          <main className="eiqas-main">
            {error && (
              <p role="alert" className="eiqas-error">
                {error.message}
              </p>
            )}
            {!threadId ? (
              <section className="eiqas-start">
                <span className="eiqas-eyebrow">START WITH A QUESTION</span>
                <h1>
                  把一个问题，
                  <br />
                  变成有依据的判断。
                </h1>
                <p>
                  描述你需要理解的变化、差异、关系或情景。研究方法由问题决定，数据与计算贯穿全过程。
                </p>
                <form
                  onSubmit={(event) => {
                    void create(event);
                  }}
                >
                  <label htmlFor="new-research-question">你想研究什么？</label>
                  <textarea
                    id="new-research-question"
                    placeholder="例如：近五年某项指标如何变化，哪些因素值得进一步解释？"
                    value={newQuestion}
                    onChange={(event) => setNewQuestion(event.target.value)}
                    rows={4}
                  />
                  <button
                    className="eiqas-primary"
                    disabled={creating || !newQuestion.trim()}
                  >
                    {creating ? "创建中…" : "创建研究，与 AI 讨论"}
                    <ArrowUpRight size={16} />
                  </button>
                </form>
                <div className="eiqas-start-note">
                  <Search size={17} />
                  <p>
                    从公开资料出发，保留原件、数据口径与实际计算。没有足够依据的部分，会作为判断边界明确列出。
                  </p>
                </div>
              </section>
            ) : !research ? (
              <p>
                {studies.isLoading
                  ? "正在载入研究…"
                  : "未找到这项研究，请从左侧选择或新建。"}
              </p>
            ) : (
              <>
                <div className="eiqas-study-heading">
                  <span className="eiqas-eyebrow">QUESTION-LED RESEARCH</span>
                  <h1 title={research.question}>
                    {research.question.split(/[。！？\n]/u)[0]?.slice(0, 100) ??
                      research.question.slice(0, 100)}
                  </h1>
                  <p>
                    {research.plan?.confirmed_at
                      ? "方案已确认，按问题推进；可以随时回看资料、方法和计算。"
                      : "先把问题与方案说清楚，再开始数据准备和真实计算。"}
                  </p>
                </div>
                <nav className="eiqas-stage-nav" aria-label="研究阶段">
                  {(Object.keys(stageNames) as Stage[]).map((key, index) => (
                    <button
                      aria-current={stage === key ? "step" : undefined}
                      className={stage === key ? "active" : ""}
                      key={key}
                      onClick={() => {
                        setStage(key);
                        setFollow(false);
                      }}
                    >
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      {stageNames[key]}
                    </button>
                  ))}
                </nav>
                {!follow && stage !== research.stage && (
                  <button
                    className="eiqas-follow"
                    onClick={() => {
                      setFollow(true);
                      setStage(research.stage);
                    }}
                  >
                    回到当前推进阶段：{stageNames[research.stage]} →
                  </button>
                )}
                {stage === "question" && (
                  <section className="eiqas-section">
                    <div className="eiqas-section-title">
                      <h2>这次研究要回答什么</h2>
                      <button
                        disabled={
                          saving ||
                          busy ||
                          question.trim() === research.question
                        }
                        onClick={() => {
                          void saveQuestion();
                        }}
                      >
                        保存问题
                      </button>
                    </div>
                    <textarea
                      aria-label="研究问题"
                      value={question}
                      onChange={(event) => setQuestion(event.target.value)}
                      rows={4}
                    />
                    <p className="eiqas-muted">
                      目标变化会使原方案确认失效。补充范围、口径和限制，可以直接通过右侧对话讨论。
                    </p>
                    <div className="eiqas-actions">
                      <button
                        className="eiqas-primary"
                        disabled={busy}
                        onClick={() => {
                          setFollow(false);
                          setStage("plan");
                          ask(
                            "请根据当前研究问题设计方案并保存到工作台，说明每种方法的依据、所需数据、假设、预期产出及限制。等待人工确认后再执行。",
                          );
                        }}
                      >
                        {research.plan ? "与 AI 完善方案" : "请 AI 拟定方案"}
                      </button>
                      {research.plan && (
                        <button
                          onClick={() => {
                            setStage("plan");
                            setFollow(false);
                          }}
                        >
                          查看当前方案 →
                        </button>
                      )}
                    </div>
                    <Scope research={research} />
                  </section>
                )}
                {stage === "plan" && (
                  <section className="eiqas-section">
                    <div className="eiqas-section-title">
                      <div>
                        <h2>研究方案</h2>
                        <p>方法按问题组合，不预设固定数量。</p>
                      </div>
                      {research.plan && (
                        <span className="eiqas-badge">
                          {research.plan.confirmed_at ? "已确认" : "待核对确认"}
                        </span>
                      )}
                    </div>
                    {!research.plan ? (
                      <div className="eiqas-empty">
                        <p>方案尚未保存。先与 AI 明确范围和适合的分析方法。</p>
                        <button
                          disabled={busy}
                          onClick={() =>
                            ask(
                              "请设计并用 eiqas_save_plan 保存当前研究方案，等待工作台确认。",
                            )
                          }
                        >
                          开始讨论方案
                        </button>
                      </div>
                    ) : (
                      <>
                        <div className="eiqas-method-cards">
                          {research.plan.content.methods.map(
                            (method, index) => (
                              <article key={index}>
                                <span>
                                  {String(index + 1).padStart(2, "0")}
                                </span>
                                <h3>{method.name}</h3>
                                <p>{method.rationale}</p>
                              </article>
                            ),
                          )}
                        </div>
                        <div className="eiqas-plan-details">
                          <List
                            title="需要哪些数据"
                            values={research.plan.content.required_data}
                          />
                          <List
                            title="预期交付"
                            values={research.plan.content.outputs}
                          />
                          <List
                            title="使用的假设"
                            values={research.plan.content.assumptions}
                          />
                          <List
                            title="当前限制"
                            values={research.plan.content.limitations}
                          />
                        </div>
                        <div className="eiqas-approval">
                          <p>
                            {research.plan.confirmed_at
                              ? "本方案已经确认。关键数据问题会再向你核对，其他步骤自动推进。"
                              : "核对问题、方法、数据范围与假设。确认绑定当前方案，目标或方法发生实质变化后需要再次确认。"}
                          </p>
                          <button
                            className="eiqas-primary"
                            disabled={saving || busy}
                            onClick={() => {
                              if (research.plan?.confirmed_at)
                                ask(
                                  "请继续已确认研究，检查实际资料与运行状态，推进到可交付成果；关键问题才询问。",
                                );
                              else void confirm();
                            }}
                          >
                            {saving
                              ? "确认中…"
                              : research.plan.confirmed_at
                                ? "继续已确认研究"
                                : "确认方案并开始"}
                          </button>
                        </div>
                      </>
                    )}
                  </section>
                )}
                {stage === "data" && (
                  <section className="eiqas-section">
                    <div className="eiqas-section-title">
                      <div>
                        <h2>把资料变成可计算的数据</h2>
                        <p>先看口径与核对项，再使用实际留存的原件计算。</p>
                      </div>
                      <button
                        disabled={busy}
                        onClick={() =>
                          ask(
                            "请继续资料准备，保留下载失败和访问限制；关键数值关联原件与具体定位，存疑项留在核对队列。",
                          )
                        }
                      >
                        继续准备资料
                      </button>
                    </div>
                    <div className="eiqas-data-summary">
                      <div>
                        <strong>
                          {
                            sources.filter(
                              (source) => source.status === "acquired",
                            ).length
                          }
                        </strong>
                        <span>已取得原件</span>
                      </div>
                      <div>
                        <strong>{observations.length}</strong>
                        <span>候选数据</span>
                      </div>
                      <div className="needs-review">
                        <strong>
                          {
                            observations.filter(
                              (observation) => observation.status === "review",
                            ).length
                          }
                        </strong>
                        <span>需要核对</span>
                      </div>
                      <div>
                        <strong>{datasets.length}</strong>
                        <span>可计算数据集</span>
                      </div>
                    </div>
                    <Scope research={research} />
                    <h3>数据与口径核对</h3>
                    {!observations.length ? (
                      <div className="eiqas-empty">
                        尚未形成候选数据。AI
                        取得与解析资料后，这里会显示每个关键值及其出处。
                      </div>
                    ) : (
                      <div className="eiqas-table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>主体／指标</th>
                              <th>期间</th>
                              <th>原始值</th>
                              <th>核对状态</th>
                              <th>依据与纠正</th>
                            </tr>
                          </thead>
                          <tbody>
                            {observations.map((observation) => (
                              <ObservationRow
                                key={observation.id}
                                observation={observation}
                                rid={research.id}
                                onEvidence={() =>
                                  setSelection({
                                    title: observation.metric,
                                    observations: [observation],
                                  })
                                }
                                onSaved={() => {
                                  void client.invalidateQueries({
                                    queryKey: ["eiqas", rid],
                                  });
                                }}
                              />
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                    <h3 className="eiqas-spaced">资料留存</h3>
                    <div className="eiqas-source-list">
                      {sources.map((source) => (
                        <article key={source.id}>
                          <div>
                            <strong>{source.title}</strong>
                            <small>
                              {source.organization} ·{" "}
                              {stateNames[source.status] ?? source.status}
                            </small>
                            {source.reason && <p>{source.reason}</p>}
                          </div>
                          {source.status === "acquired" && (
                            <a
                              href={eiqasURL(
                                `/research/${rid}/sources/${source.id}/original`,
                              )}
                            >
                              下载原件 ↗
                            </a>
                          )}
                        </article>
                      ))}
                    </div>
                    {datasets.length > 0 && (
                      <>
                        <h3 className="eiqas-spaced">冻结的数据集</h3>
                        {datasets.map((dataset) => (
                          <div className="eiqas-dataset-row" key={dataset.id}>
                            <span>
                              {dataset.title} · {dataset.rows.length} 行
                            </span>
                            <a
                              href={eiqasURL(
                                `/research/${rid}/datasets/${dataset.id}/csv`,
                              )}
                            >
                              完整 CSV ↗
                            </a>
                          </div>
                        ))}
                      </>
                    )}
                  </section>
                )}
                {stage === "analysis" && (
                  <section className="eiqas-section">
                    <div className="eiqas-section-title">
                      <div>
                        <h2>实际运行，逐项核对结果</h2>
                        <p>
                          未运行、失败或未通过检查的内容，不会显示为已校验。
                        </p>
                      </div>
                      <button
                        disabled={busy || !research.plan?.confirmed_at}
                        onClick={() =>
                          ask(
                            "请根据已确认方案与可用数据集执行真实计算，保存输入、脚本、日志、结果和独立检查。不要以推测替代未运行结果。",
                          )
                        }
                      >
                        继续计算分析
                      </button>
                    </div>
                    {!runs.length && (
                      <div className="eiqas-empty">
                        尚无实际计算记录。方案确认、数据核对完成后，运行会保存在这里。
                      </div>
                    )}
                    {runs.map((run) => (
                      <article className="eiqas-run" key={run.id}>
                        <div>
                          <h3>{methodNames[run.spec.method] ?? "定制计算"}</h3>
                          <span className={`eiqas-status ${run.status}`}>
                            {stateNames[run.status] ?? run.status}
                          </span>
                        </div>
                        <p>
                          {new Date(run.started_at).toLocaleString("zh-CN")}
                        </p>
                        {run.errors?.map((error, index) => (
                          <p className="eiqas-error" key={index}>
                            {error}
                          </p>
                        ))}
                        {run.result && (
                          <p>
                            {run.result.rows.length} 行结果 ·{" "}
                            {
                              run.result.checks.filter((check) => check.passed)
                                .length
                            }{" "}
                            项检查通过
                          </p>
                        )}
                        <details>
                          <summary>计算材料与检查</summary>
                          <div className="eiqas-actions">
                            {[
                              "input.json",
                              "script.py",
                              "execution.log",
                              "result.json",
                              "result.csv",
                            ].map((name) => (
                              <a
                                key={name}
                                href={eiqasURL(
                                  `/research/${rid}/runs/${run.id}/files/${name}`,
                                )}
                              >
                                {name}
                              </a>
                            ))}
                          </div>
                          {run.result?.checks.map((check, index) => (
                            <p key={index}>
                              {check.passed ? "✓" : "×"} {check.name}
                            </p>
                          ))}
                        </details>
                      </article>
                    ))}
                  </section>
                )}
                {stage === "review" && (
                  <section className="eiqas-section">
                    {!latest ? (
                      <div className="eiqas-empty">
                        <h2>成果尚未形成</h2>
                        <p>
                          AI
                          需基于已校验的实际运行，保存结论、图表、依据和判断边界。
                        </p>
                        <button
                          disabled={busy}
                          onClick={() =>
                            ask(
                              "请复核实际运行与证据，把支持性发现和关键数字关联数据，使用 eiqas_submit_result 保存至少一张有意义的图表、管理启示及限制。无法判断的部分明确标识。",
                            )
                          }
                        >
                          请 AI 复核并交付
                        </button>
                      </div>
                    ) : (
                      <>
                        <div className="eiqas-review-toolbar">
                          <span>
                            最新成果 ·{" "}
                            {new Date(latest.created_at).toLocaleDateString(
                              "zh-CN",
                            )}
                          </span>
                          <Link
                            className="eiqas-primary"
                            href={`/research/${threadId}/results/${latest.id}`}
                          >
                            打开独立成果页 <ArrowUpRight size={15} />
                          </Link>
                        </div>
                        <ReportView
                          report={latest}
                          compact
                          onRecompute={recompute}
                        />
                      </>
                    )}
                  </section>
                )}
              </>
            )}
          </main>
          {research && chatOpen && (
            <aside className="eiqas-chat-pane">
              <ResearchChat
                threadId={research.thread_id}
                command={command}
                onCommandSent={commandSent}
                onBusyChange={setBusy}
              />
            </aside>
          )}
        </div>
      </div>
      {research && (
        <EvidencePanel
          rid={research.id}
          sources={sources}
          selection={selection}
          onClose={() => setSelection(null)}
        />
      )}
    </div>
  );
}

function List({ title, values }: { title: string; values: string[] }) {
  return values.length ? (
    <section>
      <h3>{title}</h3>
      <ul>
        {values.map((value, index) => (
          <li key={index}>{value}</li>
        ))}
      </ul>
    </section>
  ) : null;
}
function Scope({ research }: { research: Research }) {
  return research.answerable.length || research.gaps.length ? (
    <div className="eiqas-scope">
      <List title="当前可以回答" values={research.answerable} />
      <List title="仍需保留的判断边界" values={research.gaps} />
    </div>
  ) : null;
}

function ObservationRow({
  observation,
  rid,
  onEvidence,
  onSaved,
}: {
  observation: Observation;
  rid: string;
  onEvidence: () => void;
  onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(observation.value);
  const [unit, setUnit] = useState(observation.unit);
  const [reason, setReason] = useState("");
  const [dimensions, setDimensions] = useState({
    subject: observation.subject,
    metric: observation.metric,
    period: observation.period,
    qualifier: observation.qualifier,
  });
  const [saving, setSaving] = useState(false);
  async function save() {
    setSaving(true);
    try {
      await eiqasAPI(
        `/research/${rid}/observations/${observation.id}`,
        writeJSON("PATCH", { value, unit, reason, ...dimensions }),
      );
      onSaved();
      setEditing(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "核对保存失败");
    } finally {
      setSaving(false);
    }
  }
  return (
    <tr>
      <td>
        <strong>{observation.subject}</strong>
        <small>{observation.metric}</small>
      </td>
      <td>{observation.period}</td>
      <td>
        {observation.value} {observation.unit}
      </td>
      <td>
        <span
          className={
            observation.status === "review" ? "eiqas-caution" : "eiqas-muted"
          }
        >
          {observation.status === "review"
            ? "需要核对"
            : observation.status === "verified"
              ? "已通过校验"
              : observation.status === "withdrawn"
                ? "登记已撤回"
                : observation.status}
        </span>
        {observation.locator.ocr && <small>扫描识别</small>}
      </td>
      <td>
        <button className="eiqas-text-button" onClick={onEvidence}>
          查依据
        </button>
        <button
          className="eiqas-text-button"
          onClick={() => setEditing(!editing)}
        >
          核对纠正
        </button>
        {editing && (
          <form
            className="eiqas-correction"
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          >
            <label>
              核对后的值
              <input
                value={value}
                onChange={(event) => setValue(event.target.value)}
                required
              />
            </label>
            <label>
              单位
              <input
                value={unit}
                onChange={(event) => setUnit(event.target.value)}
                required
              />
            </label>
            {(["subject", "metric", "period"] as const).map((key) => (
              <label key={key}>
                {{ subject: "主体", metric: "指标", period: "期间" }[key]}
                <input
                  required
                  value={dimensions[key]}
                  onChange={(event) =>
                    setDimensions({ ...dimensions, [key]: event.target.value })
                  }
                />
              </label>
            ))}
            <label>
              数值修饰词
              <select
                value={dimensions.qualifier}
                onChange={(event) =>
                  setDimensions({
                    ...dimensions,
                    qualifier: event.target.value,
                  })
                }
              >
                {Object.entries({
                  exact: "精确值",
                  about: "约数",
                  more_than: "超过 / 下限",
                  less_than: "不足 / 上限",
                  range: "区间",
                }).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <p className="eiqas-muted">
              下限、上限和区间会保留，不会当作精确数值进入计算。自定义单位按原文保留。
            </p>
            <label>
              核对依据
              <textarea
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                placeholder="按原件核对的页码、单位或更正原因"
                required
              />
            </label>
            <button
              disabled={saving || !reason.trim()}
              className="eiqas-primary"
            >
              {saving ? "保存中…" : "保存核对记录"}
            </button>
          </form>
        )}
      </td>
    </tr>
  );
}
