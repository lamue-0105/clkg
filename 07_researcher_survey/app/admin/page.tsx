import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { hasValidSession, sessionCookieName } from "@/lib/admin-session";

import { AdminDashboard } from "./responses-dashboard";

export const dynamic = "force-dynamic";

export default async function AdminPage() {
  const cookieStore = await cookies();
  if (!await hasValidSession(cookieStore.get(sessionCookieName())?.value)) redirect("/admin/login");

  return <AdminDashboard />;
}
