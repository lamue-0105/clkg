import { createSession, passwordIsValid, sessionCookie } from "@/lib/admin-session";

export async function POST(request: Request) {
  let body: { password?: unknown };
  try {
    body = await request.json() as { password?: unknown };
  } catch {
    return Response.json({ error: "请输入访问密码。" }, { status: 400 });
  }

  if (!passwordIsValid(body.password)) return Response.json({ error: "访问密码不正确。" }, { status: 401 });

  return Response.json({ ok: true }, { headers: { "set-cookie": sessionCookie(await createSession()) } });
}

export async function DELETE() {
  return Response.json({ ok: true }, { headers: { "set-cookie": sessionCookie("", 0) } });
}
