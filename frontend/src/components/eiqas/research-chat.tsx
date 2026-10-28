"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { toast } from "sonner";

import { ChatProviders } from "@/components/workspace/chats/chat-providers";
import { InputBox } from "@/components/workspace/input-box";
import { MessageList } from "@/components/workspace/messages";
import { ThreadContext } from "@/components/workspace/messages/context";
import type { Command } from "@/core/eiqas/types";
import {
  buildHumanInputResponseText,
  type HumanInputRequest,
  type HumanInputResponse,
} from "@/core/messages/human-input";
import { useThreadSettings } from "@/core/settings";
import { resolveThreadContext } from "@/core/settings/store";
import { useThreadStream } from "@/core/threads/hooks";

type Props = {
  threadId: string;
  reportId?: string;
  command?: Command | null;
  onCommandSent?: () => void;
  onBusyChange?: (busy: boolean) => void;
};

function NativeResearchChat({
  threadId,
  reportId,
  command,
  onCommandSent,
  onBusyChange,
}: Props) {
  const client = useQueryClient();
  const [settings, setSettings] = useThreadSettings(threadId);
  const {
    thread,
    sendMessage,
    isHistoryLoading,
    hasMoreHistory,
    loadMoreHistory,
  } = useThreadStream({
    threadId,
    context: settings.context,
    onFinish: () => {
      void client.invalidateQueries({ queryKey: ["eiqas"] });
    },
  });
  const delivered = useRef(new Set<string>());
  useEffect(() => {
    onBusyChange?.(thread.isLoading);
  }, [thread.isLoading, onBusyChange]);
  useEffect(() => {
    if (
      !command ||
      thread.isLoading ||
      isHistoryLoading ||
      delivered.current.has(command.id)
    )
      return;
    const storageKey = `eiqas-command:${threadId}:${command.id}`;
    try {
      if (sessionStorage.getItem(storageKey)) {
        onCommandSent?.();
        return;
      }
    } catch {
      /* private storage can be unavailable */
    }
    delivered.current.add(command.id);
    try {
      sessionStorage.setItem(storageKey, "sent");
    } catch {
      /* memory fence still applies */
    }
    void sendMessage(threadId, { text: command.text, files: [] }, undefined, {
      additionalKwargs: command.hidden ? { hide_from_ui: true } : undefined,
      onSent: onCommandSent,
    }).catch((error: unknown) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "研究请求未能启动，请在对话中重试。",
      );
    });
  }, [
    command,
    isHistoryLoading,
    onCommandSent,
    sendMessage,
    thread.isLoading,
    threadId,
  ]);

  async function respond(
    request: HumanInputRequest,
    response: HumanInputResponse,
  ) {
    let sent = false;
    await sendMessage(
      threadId,
      { text: buildHumanInputResponseText(request, response), files: [] },
      undefined,
      {
        additionalKwargs: {
          hide_from_ui: true,
          human_input_response: response,
        },
        onSent: () => {
          sent = true;
        },
      },
    );
    return sent;
  }

  return (
    <ThreadContext.Provider value={{ thread, isMock: false }}>
      <div className="eiqas-chat">
        <header>
          <span className="eiqas-live-dot" />
          研究对话{" "}
          <span>{thread.isLoading ? "正在推进" : "与 AI 一起推敲问题"}</span>
        </header>
        <div className="eiqas-chat-messages">
          <MessageList
            threadId={threadId}
            thread={thread}
            isHistoryLoading={isHistoryLoading}
            hasMoreHistory={hasMoreHistory}
            loadMoreHistory={loadMoreHistory}
            onSubmitHumanInput={respond}
            paddingBottom={12}
            enableSidecarActions={false}
          />
        </div>
        {Boolean(thread.error) && (
          <p role="alert" className="eiqas-error">
            本次模型运行未成功，请查看提示后重试。
          </p>
        )}
        <InputBox
          threadId={threadId}
          draftThreadId={threadId}
          status={
            thread.error ? "error" : thread.isLoading ? "streaming" : "ready"
          }
          context={settings.context}
          onContextChange={(context, options) => {
            if (options?.automatic) resolveThreadContext(threadId, context);
            else setSettings("context", context);
          }}
          onSubmit={(message, options) => {
            const pending = sendMessage(threadId, message, undefined, {
              ...options,
              additionalInputMessages: [
                ...(options?.additionalInputMessages ?? []),
                ...(reportId
                  ? [
                      {
                        type: "human" as const,
                        content: `当前正在阅读成果 ${reportId}。如需修改，请先用 eiqas_read_result 读取该成果，再保存修改。`,
                        additional_kwargs: { hide_from_ui: true },
                      },
                    ]
                  : []),
              ],
            });
            if (message.files.length) return pending;
            void pending;
          }}
          onStop={() => {
            void thread.stop();
          }}
          canStopStreaming
        />
      </div>
    </ThreadContext.Provider>
  );
}

export function ResearchChat(props: Props) {
  return (
    <ChatProviders key={props.threadId}>
      <NativeResearchChat {...props} />
    </ChatProviders>
  );
}
