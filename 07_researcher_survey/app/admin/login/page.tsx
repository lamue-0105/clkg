import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { hasValidSession, sessionCookieName } from "@/lib/admin-session";

import { AdminLogin } from "./password-form";

export const dynamic = "force-dynamic";

export default async function AdminLoginPage() {
  const cookieStore = await cookies();
  if (await hasValidSession(cookieStore.get(sessionCookieName())?.value)) redirect("/admin");

  return <AdminLogin />;
}
