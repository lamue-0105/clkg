"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import "../responses.css";

export function AdminLogin() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSending(true);
    setMessage("");
    try {
      const response = await fetch("/api/admin/session", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ password }) });
      const body = await response.json() as { error?: string };
      if (!response.ok) throw new Error(body.error ?? "无法进入后台。");
      router.replace("/admin");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "无法进入后台。");
    } finally {
      setSending(false);
    }
  }

  return <main className="admin-login-shell"><form className="admin-login-card" onSubmit={submit}><span className="admin-eyebrow">CLKG · 答卷后台</span><h1>输入访问密码</h1><p>答卷以匿名方式保存。请勿将本后台入口或密码转发给受访者。</p><label>后台访问密码<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoFocus required autoComplete="current-password" /></label>{message && <p className="login-error" role="alert">{message}</p>}<button type="submit" disabled={sending}>{sending ? "正在验证…" : "进入答卷表格"}</button></form></main>;
}
