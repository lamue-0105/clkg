"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import "./responses.css";

type AnswerValue = string | string[] | boolean | Record<string, string> | undefined;
type SurveyResponse = { id: number; submittedAt: string; answers: Record<string, AnswerValue> };

const labels: Record<string, string> = {
  role: "主要角色", stage: "研究阶段", heritage: "涉及遗产类型", outputs: "预期成果", researchQuestion: "核心问题类别",
  modalities: "使用材料", sources: "材料来源", workflow: "实际工作步骤", reworkStage: "最易反复修改的环节", other: "其他补充说明",
  tools: "常用工具", priorities: "优先改善事项", problems: "资料关联或质量问题", uncertainty: "不确定性处理方式",
  approvals: "需专家确认的判断", risks: "数据使用风险或限制", capabilities: "最有价值的平台能力",
  acceptance: "数据进入正式成果的条件", owner: "质量与公开决策责任", shortcomings: "现有方式主要不足", shortcomingCase: "具体案例",
  difficulty: "困难程度评分", evidenceImportance: "证据与过程信息重要性",
};

function list(value: AnswerValue): string[] {
  return Array.isArray(value) ? value : [];
}

function distribution(responses: SurveyResponse[], key: string) {
  const counts = new Map<string, number>();
  responses.forEach((response) => {
    const value = response.answers[key];
    const values = Array.isArray(value) ? value : typeof value === "string" ? [value] : [];
    values.filter(Boolean).forEach((item) => counts.set(item, (counts.get(item) ?? 0) + 1));
  });
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

function averageDifficulty(responses: SurveyResponse[]) {
  const values: number[] = [];
  responses.forEach((response) => {
    const record = response.answers.difficulty;
    if (record && !Array.isArray(record) && typeof record === "object") {
      Object.values(record).forEach((value) => {
        const score = Number(value);
        if (score >= 1 && score <= 5) values.push(score);
      });
    }
  });
  return values.length ? (values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1) : "—";
}

function Value({ value }: { value: AnswerValue }) {
  if (Array.isArray(value)) return <span>{value.join("；") || "—"}</span>;
  if (typeof value === "object" && value) return <ul className="record-list">{Object.entries(value).map(([key, item]) => <li key={key}><span>{key}</span><strong>{item}</strong></li>)}</ul>;
  if (typeof value === "boolean") return <span>{value ? "同意" : "否"}</span>;
  return <span>{value || "—"}</span>;
}

function roleText(value: AnswerValue, fallback = "—") {
  return Array.isArray(value) ? value.join("；") || fallback : String(value || fallback);
}

export function AdminDashboard() {
  const [responses, setResponses] = useState<SurveyResponse[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState("");
  const router = useRouter();

  useEffect(() => {
    fetch("/api/admin/responses", { cache: "no-store" })
      .then(async (response) => {
        const body = await response.json() as { responses?: SurveyResponse[]; error?: string };
        if (!response.ok) throw new Error(body.error ?? "无法读取答卷。");
        setResponses(body.responses ?? []);
        setStatus("ready");
      })
      .catch((error) => { setMessage(error instanceof Error ? error.message : "无法读取答卷。"); setStatus("error"); });
  }, []);

  const topHeritage = useMemo(() => distribution(responses, "heritage").slice(0, 6), [responses]);
  const topPriorities = useMemo(() => distribution(responses, "priorities").slice(0, 6), [responses]);
  const roleDistribution = useMemo(() => distribution(responses, "role").slice(0, 6), [responses]);
  const maxCount = Math.max(1, ...[...topHeritage, ...topPriorities, ...roleDistribution].map(([, count]) => count));
  const visibleResponses = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return responses;
    return responses.filter((response) => JSON.stringify(response.answers).toLowerCase().includes(normalized));
  }, [responses, query]);

  async function signOut() {
    await fetch("/api/admin/session", { method: "DELETE" });
    router.replace("/admin/login");
    router.refresh();
  }

  return <main className="admin-shell">
    <header className="admin-hero">
      <div><span className="admin-eyebrow">CLKG · 仅限研究主持人</span><h1>匿名答卷后台</h1><p>这里显示提交后的匿名答卷及初步汇总。请只将导出数据用于本研究的需求分析与归档。</p></div>
      <div className="admin-actions"><a className="export-button" href="/api/admin/responses?format=csv">导出 CSV</a><button className="signout-button" type="button" onClick={signOut}>退出后台</button></div>
    </header>
    {status === "loading" && <p className="admin-state">正在读取答卷…</p>}
    {status === "error" && <p className="admin-state error">{message}</p>}
    {status === "ready" && <>
      <section className="metrics" aria-label="答卷概览"><article><span>有效提交</span><strong>{responses.length}</strong><small>当前显示最近 500 份</small></article><article><span>平均困难度</span><strong>{averageDifficulty(responses)}</strong><small>按已填写的 1–5 分项计算</small></article><article><span>最近提交</span><strong>{responses[0] ? new Intl.DateTimeFormat("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(responses[0].submittedAt)) : "—"}</strong><small>以服务器记录时间为准</small></article></section>
      <section className="summary-grid"><Distribution title="受访者主要角色" items={roleDistribution} max={maxCount} /><Distribution title="涉及最多的遗产类型" items={topHeritage} max={maxCount} /><Distribution title="最希望优先改善的事项" items={topPriorities} max={maxCount} /></section>
      <section className="response-section"><div className="section-heading"><div><span className="admin-eyebrow">逐份答卷</span><h2>可查看的答卷表格</h2></div><span>{visibleResponses.length} / {responses.length} 份</span></div>{responses.length === 0 ? <p className="empty-state">尚未收到答卷。公开问卷提交后会自动出现在这里。</p> : <><label className="answer-search">搜索回答内容<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="如：GIS、文献遗产、版本管理…" /></label><div className="table-wrap"><table><thead><tr><th>编号</th><th>提交时间</th><th>主要角色</th><th>研究阶段</th><th>核心研究问题</th></tr></thead><tbody>{visibleResponses.map((response) => <tr key={response.id}><td>#{response.id}</td><td>{new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(response.submittedAt))}</td><td>{roleText(response.answers.role)}</td><td>{String(response.answers.stage || "—")}</td><td>{String(response.answers.researchQuestion || "—")}</td></tr>)}</tbody></table></div><div className="response-list">{visibleResponses.map((response) => <details key={response.id} className="response-card"><summary><span>答卷 #{response.id}</span><time>{new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(response.submittedAt))}</time><strong>{roleText(response.answers.role, "未标注角色")}</strong></summary><div className="answers">{Object.entries(response.answers).filter(([key]) => !["consent", "submittedAtClient"].includes(key)).map(([key, value]) => <div className="answer" key={key}><h3>{labels[key] ?? key}</h3><Value value={value} /></div>)}</div></details>)}</div></>}</section>
    </>}
  </main>;
}

function Distribution({ title, items, max }: { title: string; items: [string, number][]; max: number }) {
  return <article className="distribution"><h2>{title}</h2>{items.length ? <ol>{items.map(([label, count]) => <li key={label}><span>{label}</span><i><b style={{ width: `${(count / max) * 100}%` }} /></i><strong>{count}</strong></li>)}</ol> : <p>尚无可汇总的回答。</p>}</article>;
}
