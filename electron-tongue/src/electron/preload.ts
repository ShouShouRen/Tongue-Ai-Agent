import { contextBridge, ipcRenderer, type IpcRendererEvent } from "electron";

type StreamChunkPayload =
  | { type: "chunk"; content?: string }
  | { type: "done" }
  | { type: "error"; error?: string };

contextBridge.exposeInMainWorld("electronAPI", {
  sendChatMessage: (prompt: string, userId?: string, sessionId?: string) =>
    ipcRenderer.invoke("rag-chat", prompt, userId, sessionId),
  sendChatMessageStream: (
    prompt: string,
    userId?: string,
    sessionId?: string,
    onChunk?: (chunk: string) => void,
    onComplete?: () => void,
    onError?: (error: string) => void,
  ) => {
    const handleChunk = (
      _event: IpcRendererEvent,
      data: StreamChunkPayload,
    ) => {
      if (data.type === "chunk" && data.content && onChunk) {
        onChunk(data.content);
      } else if (data.type === "done" && onComplete) {
        ipcRenderer.removeListener("rag-chat-stream-chunk", handleChunk);
        onComplete();
      } else if (data.type === "error" && data.error && onError) {
        ipcRenderer.removeListener("rag-chat-stream-chunk", handleChunk);
        onError(data.error);
      }
    };

    ipcRenderer.on("rag-chat-stream-chunk", handleChunk);

    // 发送流式请求
    ipcRenderer.send("rag-chat-stream", prompt, userId, sessionId);

    // 返回清理函数
    return () => {
      ipcRenderer.removeListener("rag-chat-stream-chunk", handleChunk);
    };
  },
  sendTongueAnalysis: (
    predictionResults: Record<string, unknown>,
    additionalInfo?: string,
  ) => ipcRenderer.invoke("tongue-analyze", predictionResults, additionalInfo),
  transcribeAudio: (audioData: Uint8Array) =>
    ipcRenderer.invoke("transcribe-audio", audioData),
  sendTongueAnalysisStream: (
    predictionResults: Record<string, unknown>,
    additionalInfo: string | undefined,
    onChunk: (chunk: string) => void,
    onComplete: () => void,
    onError: (error: string) => void,
  ) => {
    const handleChunk = (
      _event: IpcRendererEvent,
      data: StreamChunkPayload,
    ) => {
      if (data.type === "chunk" && data.content) {
        onChunk(data.content);
      } else if (data.type === "done") {
        ipcRenderer.removeListener("tongue-analyze-stream-chunk", handleChunk);
        onComplete();
      } else if (data.type === "error" && data.error) {
        ipcRenderer.removeListener("tongue-analyze-stream-chunk", handleChunk);
        onError(data.error);
      }
    };

    ipcRenderer.on("tongue-analyze-stream-chunk", handleChunk);

    // 发送流式请求
    ipcRenderer.send(
      "tongue-analyze-stream",
      predictionResults,
      additionalInfo,
    );

    // 返回清理函数
    return () => {
      ipcRenderer.removeListener("tongue-analyze-stream-chunk", handleChunk);
    };
  },
});
