import { ResearchWorkbench } from "@/components/eiqas/workbench";

export default async function ResearchPage({
  params,
}: {
  params: Promise<{ thread_id: string }>;
}) {
  const { thread_id } = await params;
  return <ResearchWorkbench key={thread_id} threadId={thread_id} />;
}
