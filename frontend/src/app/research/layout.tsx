import "katex/dist/katex.min.css";
import "streamdown/styles.css";
import "@/styles/eiqas.css";

import Link from "next/link";
import { redirect } from "next/navigation";
import { Toaster } from "sonner";

import { QueryClientProvider } from "@/components/query-client-provider";
import { SidebarProvider } from "@/components/ui/sidebar";
import { AuthProvider } from "@/core/auth/AuthProvider";
import { getServerSideUser } from "@/core/auth/server";
import { buildLoginUrl } from "@/core/auth/types";
import { I18nProvider } from "@/core/i18n/context";
import { UserPreferencesBoundary } from "@/core/settings/user-preferences-boundary";

export const dynamic = "force-dynamic";

export default async function ResearchLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const result = await getServerSideUser();
  if (result.tag === "needs_setup" || result.tag === "system_setup_required")
    redirect("/setup");
  if (result.tag === "unauthenticated") redirect(buildLoginUrl("/research"));
  if (result.tag !== "authenticated")
    return (
      <main className="eiqas-offline">
        <h1>工作台暂时无法连接</h1>
        <p>请确认本地 Gateway 已启动，再刷新页面。</p>
        <Link href="/research">重新连接</Link>
      </main>
    );
  return (
    <I18nProvider initialLocale="zh-CN">
      <AuthProvider initialUser={result.user}>
        <QueryClientProvider>
          <UserPreferencesBoundary>
            <SidebarProvider defaultOpen={false} className="h-screen">
              <div className="eiqas" lang="zh-CN">
                {children}
              </div>
            </SidebarProvider>
            <Toaster position="top-center" />
          </UserPreferencesBoundary>
        </QueryClientProvider>
      </AuthProvider>
    </I18nProvider>
  );
}
