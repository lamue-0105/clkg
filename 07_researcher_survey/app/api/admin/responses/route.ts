import { env } from "cloudflare:workers";

import { cookieValue, hasValidSession, sessionCookieName } from "@/lib/admin-session";

type StoredResponse = {
  id: number;
  submitted_at: string;
  answers_json: string;
};

async function authorize(request: Request) {
  const session = cookieValue(request.headers.get("cookie"), sessionCookieName());
  if (!await hasValidSession(session)) return Response.json({ error: "请先输入后台访问密码。" }, { status: 401 });
  return null;
}

async function loadRecentResponses(): Promise<StoredResponse[]> {
  const result = await env.DB.prepare(
    "SELECT id, submitted_at, answers_json FROM survey_responses ORDER BY id DESC LIMIT 500",
  ).all<StoredResponse>();
  return result.results;
}

async function loadAllResponses(): Promise<StoredResponse[]> {
  const responses: StoredResponse[] = [];
  let lastId = 0;

  for (;;) {
    const page = await env.DB.prepare(
      "SELECT id, submitted_at, answers_json FROM survey_responses WHERE id > ? ORDER BY id ASC LIMIT 500",
    ).bind(lastId).all<StoredResponse>();
    responses.push(...page.results);
    if (page.results.length < 500) return responses;
    lastId = page.results.at(-1)?.id ?? lastId;
  }
}

function parseAnswers(value: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" ? parsed as Record<string, unknown> : {};
  } catch {
    return {};
  }
}

function csvCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const text = typeof value === "string" ? value : JSON.stringify(value);
  return `"${text.replaceAll('"', '""')}"`;
}

export async function GET(request: Request) {
  const denied = await authorize(request);
  if (denied) return denied;

  const wantsExport = new URL(request.url).searchParams.get("format") === "csv";
  const responses = wantsExport ? await loadAllResponses() : await loadRecentResponses();
  const parsed = responses.map((response) => ({
    id: response.id,
    submittedAt: response.submitted_at,
    answers: parseAnswers(response.answers_json),
  }));

  if (!wantsExport) return Response.json({ responses: parsed });

  const columns = Array.from(new Set(parsed.flatMap((response) => Object.keys(response.answers))));
  const rows = [
    ["response_id", "submitted_at", ...columns].map(csvCell).join(","),
    ...parsed.map((response) => [response.id, response.submittedAt, ...columns.map((column) => response.answers[column])].map(csvCell).join(",")),
  ];

  return new Response(`\uFEFF${rows.join("\n")}`, {
    headers: {
      "content-type": "text/csv; charset=utf-8",
      "content-disposition": "attachment; filename=clkg-survey-responses.csv",
      "cache-control": "no-store",
    },
  });
}
