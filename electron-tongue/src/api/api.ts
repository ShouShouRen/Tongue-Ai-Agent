import type { TonguePredictionResults } from "../types/electron";

interface PromptRequest {
  prompt: string;
}

interface PromptResponse {
  data: string;
}

interface TongueAnalysisRequest {
  prediction_results: TonguePredictionResults | Record<string, unknown>;
  additional_info?: string;
}

const isElectron = () => {
  return typeof window !== "undefined" && window.electronAPI !== undefined;
};

const FASTAPI_URL = "http://localhost:8000";

const makeBrowserRequest = async (
  message: PromptRequest
): Promise<PromptResponse> => {
  const response = await fetch(`${FASTAPI_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      prompt: message.prompt,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `API 請求失敗 (狀態碼: ${response.status})`
    );
  }

  const data = await response.json();
  return {
    data: data.response || data.answer || "沒有收到回應",
  };
};

const makeElectronRequest = async (
  message: PromptRequest
): Promise<PromptResponse> => {
  if (!window.electronAPI) {
    throw new Error("Electron API 不可用");
  }

  const response = await window.electronAPI.sendChatMessage(message.prompt);

  if (!response.success) {
    throw new Error(response.error || "API 請求失敗");
  }

  return {
    data: response.data || "沒有收到回應",
  };
};

export const makeRequest = async (
  message: PromptRequest
): Promise<PromptResponse> => {
  if (isElectron()) {
    return makeElectronRequest(message);
  } else {
    return makeBrowserRequest(message);
  }
};

export const makeStreamRequest = async (
  message: PromptRequest,
  onChunk: (chunk: string) => void,
  onComplete: () => void,
  onError: (error: string) => void
): Promise<() => void> => {
  if (isElectron() && window.electronAPI?.sendChatMessageStream) {
    const electronAPI = window.electronAPI;
    return electronAPI.sendChatMessageStream(
      message.prompt,
      onChunk,
      onComplete,
      onError
    );
  } else {
    try {
      const response = await fetch(`${FASTAPI_URL}/chat/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prompt: message.prompt,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        onError(
          errorData.detail || `API 請求失敗 (狀態碼: ${response.status})`
        );
        return () => {};
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        onError("無法讀取響應流");
        return () => {};
      }

      let buffer = "";

      const readStream = async () => {
        try {
          while (true) {
            const { done, value } = await reader.read();

            if (done) {
              onComplete();
              break;
            }

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
              if (line.startsWith("data: ")) {
                const data = line.slice(6);
                if (data === "[DONE]") {
                  onComplete();
                  return;
                }

                try {
                  const json = JSON.parse(data);
                  const content =
                    json.content || json.chunk || json.response || "";
                  if (content) {
                    onChunk(content);
                  }
                } catch (e) {
                  if (data.trim()) {
                    onChunk(data);
                  }
                }
              } else if (line.trim()) {
                try {
                  const json = JSON.parse(line);
                  const content =
                    json.content || json.chunk || json.response || "";
                  if (content) {
                    onChunk(content);
                  }
                } catch (e) {
                  if (line.trim()) {
                    onChunk(line);
                  }
                }
              }
            }
          }
        } catch (error: unknown) {
          const errorMessage =
            error instanceof Error ? error.message : "讀取流時發生錯誤";
          onError(errorMessage);
        }
      };

      readStream();

      return () => {
        reader.cancel();
      };
    } catch (error: unknown) {
      if (error instanceof Error) {
        if (
          error.message?.includes("fetch failed") ||
          error.message?.includes("ECONNREFUSED")
        ) {
          onError(
            `無法連接到 FastAPI 服務 (${FASTAPI_URL})，請確保服務正在運行`
          );
        } else {
          onError(error.message || "發生未知錯誤");
        }
      } else {
        onError("發生未知錯誤");
      }
      return () => {};
    }
  }
};

const makeBrowserTongueAnalysis = async (
  request: TongueAnalysisRequest
): Promise<PromptResponse> => {
  const response = await fetch(`${FASTAPI_URL}/tongue/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `API 請求失敗 (狀態碼: ${response.status})`
    );
  }

  const data = await response.json();
  return {
    data: data.response || "沒有收到回應",
  };
};

const makeElectronTongueAnalysis = async (
  request: TongueAnalysisRequest
): Promise<PromptResponse> => {
  if (!window.electronAPI) {
    throw new Error("Electron API 不可用");
  }

  const response = await window.electronAPI.sendTongueAnalysis(
    request.prediction_results,
    request.additional_info
  );

  if (!response.success) {
    throw new Error(response.error || "API 請求失敗");
  }

  return {
    data: response.data || "沒有收到回應",
  };
};

export const analyzeTongue = async (
  request: TongueAnalysisRequest
): Promise<PromptResponse> => {
  if (isElectron()) {
    return makeElectronTongueAnalysis(request);
  } else {
    return makeBrowserTongueAnalysis(request);
  }
};

interface ImagePredictRequest {
  imageFile: File | string;
  additional_info?: string;
}

const makeBrowserImagePredictAndAnalyze = async (
  request: ImagePredictRequest,
  onChunk: (chunk: string) => void,
  onStatus?: (status: string) => void,
  onComplete: () => void = () => {},
  onError: (error: string) => void = () => {}
): Promise<() => void> => {
  try {
    const formData = new FormData();

    if (request.imageFile instanceof File) {
      formData.append("file", request.imageFile);
    } else {
      const base64Data = request.imageFile;
      let mimeType = "image/jpeg";
      let base64String = base64Data;

      if (base64Data.startsWith("data:")) {
        const matches = base64Data.match(/data:([^;]+);base64,(.+)/);
        if (matches) {
          mimeType = matches[1];
          base64String = matches[2];
        }
      }

      const byteCharacters = atob(base64String);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: mimeType });

      formData.append("file", blob, "tongue_image.jpg");
    }

    if (request.additional_info) {
      formData.append("additional_info", request.additional_info);
    }

    const response = await fetch(
      `${FASTAPI_URL}/tongue/predict-and-analyze/stream`,
      {
        method: "POST",
        body: formData,
      }
    );

    if (!response.ok) {
      let errorMessage = `API 請求失敗 (狀態碼: ${response.status})`;

      const errorText = await response.text();
      if (errorText) {
        try {
          const errorData = JSON.parse(errorText);
          errorMessage = errorData.detail || errorData.error || errorMessage;
        } catch {
          errorMessage = errorText || errorMessage;
        }
      }

      if (response.status === 404) {
        errorMessage = `API 端點未找到。請確保 FastAPI 服務正在運行，並且端點路徑正確。`;
      }

      onError(errorMessage);
      return () => {};
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      onError("無法讀取響應流");
      return () => {};
    }

    let buffer = "";

    const readStream = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            onComplete();
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6);
              if (data === "[DONE]") {
                onComplete();
                return;
              }

              try {
                const json = JSON.parse(data);

                if (json.type === "status" && json.message && onStatus) {
                  onStatus(json.message);
                }

                if (json.type === "content" && json.content) {
                  onChunk(json.content);
                }

                if (json.error) {
                  onError(json.error);
                  return;
                }

                const content =
                  json.content || json.chunk || json.response || "";
                if (content && !json.type) {
                  onChunk(content);
                }
              } catch (e: unknown) {
                if (data.trim()) {
                  onChunk(data);
                }
              }
            } else if (line.trim()) {
              try {
                const json = JSON.parse(line);
                const content =
                  json.content || json.chunk || json.response || "";
                if (content) {
                  onChunk(content);
                }
              } catch (e: unknown) {
                if (line.trim()) {
                  onChunk(line);
                }
              }
            }
          }
        }
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : "讀取流時發生錯誤";
        onError(errorMessage);
      }
    };

    readStream();

    return () => {
      reader.cancel();
    };
  } catch (error: unknown) {
    if (error instanceof Error) {
      if (
        error.message?.includes("fetch failed") ||
        error.message?.includes("ECONNREFUSED")
      ) {
        onError(`無法連接到 FastAPI 服務 (${FASTAPI_URL})，請確保服務正在運行`);
      } else {
        onError(error.message || "發生未知錯誤");
      }
    } else {
      onError("發生未知錯誤");
    }
    return () => {};
  }
};

export const predictAndAnalyzeTongueImage = async (
  request: ImagePredictRequest,
  onChunk: (chunk: string) => void,
  onStatus?: (status: string) => void,
  onComplete?: () => void,
  onError?: (error: string) => void
): Promise<() => void> => {
  return makeBrowserImagePredictAndAnalyze(
    request,
    onChunk,
    onStatus,
    onComplete || (() => {}),
    onError || (() => {})
  );
};

const makeBrowserAgentChat = async (
  request: ImagePredictRequest & { prompt?: string },
  onChunk: (chunk: string) => void,
  onStatus?: (status: string) => void,
  onComplete: () => void = () => {},
  onError: (error: string) => void = () => {}
): Promise<() => void> => {
  try {
    const formData = new FormData();

    if (request.imageFile instanceof File) {
      formData.append("file", request.imageFile);
    } else if (request.imageFile) {
      const base64Data = request.imageFile;
      let mimeType = "image/jpeg";
      let base64String = base64Data;

      if (base64Data.startsWith("data:")) {
        const matches = base64Data.match(/data:([^;]+);base64,(.+)/);
        if (matches) {
          mimeType = matches[1];
          base64String = matches[2];
        }
      }

      const byteCharacters = atob(base64String);
      const byteNumbers = new Array(byteCharacters.length);
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
      }
      const byteArray = new Uint8Array(byteNumbers);
      const blob = new Blob([byteArray], { type: mimeType });

      formData.append("file", blob, "tongue_image.jpg");
    }

    if (request.prompt || request.additional_info) {
      formData.append(
        "prompt",
        request.prompt || request.additional_info || ""
      );
    }

    const response = await fetch(`${FASTAPI_URL}/agent/chat/stream`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      let errorMessage = `API 請求失敗 (狀態碼: ${response.status})`;

      const errorText = await response.text();
      if (errorText) {
        try {
          const errorData = JSON.parse(errorText);
          errorMessage = errorData.detail || errorData.error || errorMessage;
        } catch {
          errorMessage = errorText || errorMessage;
        }
      }

      if (response.status === 404) {
        errorMessage = `API 端點未找到。請確保 FastAPI 服務正在運行，並且端點路徑正確。`;
      }

      onError(errorMessage);
      return () => {};
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      onError("無法讀取響應流");
      return () => {};
    }

    let buffer = "";

    const readStream = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            onComplete();
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6);
              if (data === "[DONE]") {
                onComplete();
                return;
              }

              try {
                const json = JSON.parse(data);

                if (json.type === "status" && json.message && onStatus) {
                  onStatus(json.message);
                }

                if (json.type === "content" && json.content) {
                  onChunk(json.content);
                }

                if (json.error) {
                  onError(json.error);
                  return;
                }

                const content =
                  json.content || json.chunk || json.response || "";
                if (content && !json.type) {
                  onChunk(content);
                }
              } catch (e) {
                if (data.trim()) {
                  onChunk(data);
                }
              }
            } else if (line.trim()) {
              try {
                const json = JSON.parse(line);
                const content =
                  json.content || json.chunk || json.response || "";
                if (content) {
                  onChunk(content);
                }
              } catch (e) {
                if (line.trim()) {
                  onChunk(line);
                }
              }
            }
          }
        }
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : "讀取流時發生錯誤";
        onError(errorMessage);
      }
    };

    readStream();

    return () => {
      reader.cancel();
    };
  } catch (error: unknown) {
    if (error instanceof Error) {
      if (
        error.message?.includes("fetch failed") ||
        error.message?.includes("ECONNREFUSED")
      ) {
        onError(`無法連接到 FastAPI 服務 (${FASTAPI_URL})，請確保服務正在運行`);
      } else {
        onError(error.message || "發生未知錯誤");
      }
    } else {
      onError("發生未知錯誤");
    }
    return () => {};
  }
};

export const agentChat = async (
  request: ImagePredictRequest & { prompt?: string },
  onChunk: (chunk: string) => void,
  onStatus?: (status: string) => void,
  onComplete?: () => void,
  onError?: (error: string) => void
): Promise<() => void> => {
  return makeBrowserAgentChat(
    request,
    onChunk,
    onStatus,
    onComplete || (() => {}),
    onError || (() => {})
  );
};

export const analyzeTongueStream = async (
  request: TongueAnalysisRequest,
  onChunk: (chunk: string) => void,
  onComplete: () => void,
  onError: (error: string) => void
): Promise<() => void> => {
  if (isElectron() && window.electronAPI?.sendTongueAnalysisStream) {
    const electronAPI = window.electronAPI;
    return electronAPI.sendTongueAnalysisStream(
      request.prediction_results,
      request.additional_info,
      onChunk,
      onComplete,
      onError
    );
  } else {
    try {
      const response = await fetch(`${FASTAPI_URL}/tongue/analyze/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        onError(
          errorData.detail || `API 請求失敗 (狀態碼: ${response.status})`
        );
        return () => {};
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        onError("無法讀取響應流");
        return () => {};
      }

      let buffer = "";

      const readStream = async () => {
        try {
          while (true) {
            const { done, value } = await reader.read();

            if (done) {
              onComplete();
              break;
            }

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
              if (line.startsWith("data: ")) {
                const data = line.slice(6);
                if (data === "[DONE]") {
                  onComplete();
                  return;
                }

                try {
                  const json = JSON.parse(data);
                  const content =
                    json.content || json.chunk || json.response || "";
                  if (content) {
                    onChunk(content);
                  }
                } catch (e) {
                  if (data.trim()) {
                    onChunk(data);
                  }
                }
              } else if (line.trim()) {
                try {
                  const json = JSON.parse(line);
                  const content =
                    json.content || json.chunk || json.response || "";
                  if (content) {
                    onChunk(content);
                  }
                } catch (e) {
                  if (line.trim()) {
                    onChunk(line);
                  }
                }
              }
            }
          }
        } catch (error: unknown) {
          const errorMessage =
            error instanceof Error ? error.message : "讀取流時發生錯誤";
          onError(errorMessage);
        }
      };

      readStream();

      return () => {
        reader.cancel();
      };
    } catch (error: unknown) {
      if (error instanceof Error) {
        if (
          error.message?.includes("fetch failed") ||
          error.message?.includes("ECONNREFUSED")
        ) {
          onError(
            `無法連接到 FastAPI 服務 (${FASTAPI_URL})，請確保服務正在運行`
          );
        } else {
          onError(error.message || "發生未知錯誤");
        }
      } else {
        onError("發生未知錯誤");
      }
      return () => {};
    }
  }
};
