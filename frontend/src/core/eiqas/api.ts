import { fetch as fetchWithAuth } from "@/core/api/fetcher";
import { getBackendBaseURL } from "@/core/config";

export const eiqasURL = (path: string) =>
  `${getBackendBaseURL()}/api/eiqas${path}`;

export async function eiqasAPI<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetchWithAuth(eiqasURL(path), init);
  if (!response.ok) {
    const error = (await response.json().catch(() => null)) as {
      detail?: unknown;
    } | null;
    throw new Error(
      typeof error?.detail === "string"
        ? error.detail
        : `请求未完成（${response.status}），请重试或查看研究对话。`,
    );
  }
  return response.json() as Promise<T>;
}

export function writeJSON(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export async function downloadExport(
  rid: string,
  reportId: string,
  format: string,
): Promise<void> {
  const response = await fetchWithAuth(
    eiqasURL(`/research/${rid}/exports/${reportId}/${format}`),
  );
  if (!response.ok) {
    const error = (await response.json().catch(() => null)) as {
      detail?: unknown;
    } | null;
    throw new Error(
      typeof error?.detail === "string"
        ? error.detail
        : "导出失败，请检查来源和计算材料。",
    );
  }
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `eiqas-${reportId.slice(0, 8)}.${format}`;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
