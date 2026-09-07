import { env } from "cloudflare:workers";

const MAX_PAYLOAD_SIZE = 120_000;

export async function POST(request: Request) {
  let body: unknown;

  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "提交内容无法识别。" }, { status: 400 });
  }

  if (!body || typeof body !== "object") {
    return Response.json({ error: "提交内容不能为空。" }, { status: 400 });
  }

  const payload = body as { answers?: unknown; honeypot?: unknown };
  if (payload.honeypot) {
    return Response.json({ ok: true });
  }
  if (!payload.answers || typeof payload.answers !== "object") {
    return Response.json({ error: "请完成问卷后再提交。" }, { status: 400 });
  }

  const answers = payload.answers as { consent?: unknown; role?: unknown; stage?: unknown };
  if (answers.consent !== true || !answers.role || !answers.stage) {
    return Response.json({ error: "请确认知情同意并完成必答的基本信息。" }, { status: 400 });
  }

  const serialized = JSON.stringify(payload.answers);
  if (serialized.length > MAX_PAYLOAD_SIZE) {
    return Response.json({ error: "填写内容过长，请适当缩短开放题回答。" }, { status: 413 });
  }

  await env.DB.prepare(
    "INSERT INTO survey_responses (schema_version, answers_json) VALUES (?, ?)",
  )
    .bind("v0.1", serialized)
    .run();

  return Response.json({ ok: true });
}
