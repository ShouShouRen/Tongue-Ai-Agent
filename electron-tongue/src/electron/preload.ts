import { contextBridge, ipcRenderer } from "electron";

// 暴露安全的 API 給渲染進程
contextBridge.exposeInMainWorld("electronAPI", {
  sendChatMessage: (prompt: string) => ipcRenderer.invoke("rag-chat", prompt),
  sendChatMessageStream: (prompt: string, onChunk: (chunk: string) => void, onComplete: () => void, onError: (error: string) => void) => {
    // 监听流式数据
    const handleChunk = (_event: any, data: { type: 'chunk' | 'done' | 'error', content?: string, error?: string }) => {
      if (data.type === 'chunk' && data.content) {
        onChunk(data.content);
      } else if (data.type === 'done') {
        ipcRenderer.removeListener('rag-chat-stream-chunk', handleChunk);
        onComplete();
      } else if (data.type === 'error' && data.error) {
        ipcRenderer.removeListener('rag-chat-stream-chunk', handleChunk);
        onError(data.error);
      }
    };
    
    ipcRenderer.on('rag-chat-stream-chunk', handleChunk);
    
    // 发送流式请求
    ipcRenderer.send('rag-chat-stream', prompt);
    
    // 返回清理函数
    return () => {
      ipcRenderer.removeListener('rag-chat-stream-chunk', handleChunk);
    };
  },
  sendTongueAnalysis: (predictionResults: Record<string, any>, additionalInfo?: string) => 
    ipcRenderer.invoke("tongue-analyze", predictionResults, additionalInfo),
  sendTongueAnalysisStream: (
    predictionResults: Record<string, any>,
    additionalInfo: string | undefined,
    onChunk: (chunk: string) => void,
    onComplete: () => void,
    onError: (error: string) => void
  ) => {
    // 监听流式数据
    const handleChunk = (_event: any, data: { type: 'chunk' | 'done' | 'error', content?: string, error?: string }) => {
      if (data.type === 'chunk' && data.content) {
        onChunk(data.content);
      } else if (data.type === 'done') {
        ipcRenderer.removeListener('tongue-analyze-stream-chunk', handleChunk);
        onComplete();
      } else if (data.type === 'error' && data.error) {
        ipcRenderer.removeListener('tongue-analyze-stream-chunk', handleChunk);
        onError(data.error);
      }
    };
    
    ipcRenderer.on('tongue-analyze-stream-chunk', handleChunk);
    
    // 发送流式请求
    ipcRenderer.send('tongue-analyze-stream', predictionResults, additionalInfo);
    
    // 返回清理函数
    return () => {
      ipcRenderer.removeListener('tongue-analyze-stream-chunk', handleChunk);
    };
  },
});

