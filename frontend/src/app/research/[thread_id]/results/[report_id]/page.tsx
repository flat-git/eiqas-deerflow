import { ResearchReader } from "@/components/eiqas/reader";

export default async function ResultPage({
  params,
}: {
  params: Promise<{ thread_id: string; report_id: string }>;
}) {
  const { thread_id, report_id } = await params;
  return (
    <ResearchReader key={report_id} threadId={thread_id} reportId={report_id} />
  );
}
