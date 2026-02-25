import type { TonguePredictionResults } from "../types/electron";

interface PromptRequest {
  prompt: string;
  user_id?: string;
  session_id?: string;
}

interface PromptResponse {
  data: string;
}

interface TongueAnalysisRequest {
  prediction_results: TonguePredictionResults | Record<string, unknown>;
  additional_info?: string;
  user_id?: string;
  session_id?: string;
}

/** 是否在 Electron 環境 */
const isElectron = (): boolean =>
  typeof window !== "undefined" && window.electronAPI !== undefined;

const FASTAPI_URL = "http://localhost:8000";

/** 從 JSON 取出內容欄位 */
function getContentFromJson(json: Record<string, unknown>): string {
  return (json.content ?? json.chunk ?? json.response ?? "") as string;
}

/** 解析單行 SSE data，回傳是否應結束串流 */
function processSSEDataLine(
  data: string,
  callbacks: {
    onChunk: (chunk: string) => void;
    onComplete?: () => void;
    onError: (error: string) => void;
    onStatus?: (status: string) => void;
  },
): boolean {
  if (data === "[DONE]") {
    callbacks.onComplete?.();
    return true;
  }
  try {
    const json = JSON.parse(data) as Record<string, unknown>;
    if (json.type === "status" && json.message && callbacks.onStatus) {
      callbacks.onStatus(String(json.message));
    }
    if (json.type === "content" && json.content) {
      callbacks.onChunk(String(json.content));
    }
    if (json.error) {
      callbacks.onError(String(json.error));
      return true;
    }
    const content = getContentFromJson(json);
    if (content && !json.type) {
      callbacks.onChunk(content);
    }
  } catch {
    if (data.trim()) {
      callbacks.onChunk(data);
    }
  }
  return false;
}

/** 解析一般 JSON 行（無 "data: " 前綴）的內容 */
function processJsonLine(line: string, onChunk: (chunk: string) => void): void {
  try {
    const json = JSON.parse(line) as Record<string, unknown>;
    const content = getContentFromJson(json);
    if (content) {
      onChunk(content);
    }
  } catch {
    if (line.trim()) {
      onChunk(line);
    }
  }
}

/** 讀取 fetch Response 的 SSE 串流，依行呼叫 callbacks */
async function readSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  decoder: TextDecoder,
  callbacks: {
    onChunk: (chunk: string) => void;
    onComplete: () => void;
    onError: (error: string) => void;
    onStatus?: (status: string) => void;
  },
): Promise<void> {
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        callbacks.onComplete();
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (processSSEDataLine(data, callbacks)) return;
        } else if (line.trim()) {
          processJsonLine(line, callbacks.onChunk);
        }
      }
    }
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : "讀取流時發生錯誤";
    callbacks.onError(msg);
  }
}

/** 將 File 或 base64 字串轉成 Blob 並 append 到 FormData */
function appendImageToFormData(
  formData: FormData,
  imageFile: File | string,
  fieldName = "file",
): void {
  if (imageFile instanceof File) {
    formData.append(fieldName, imageFile);
    return;
  }
  let mimeType = "image/jpeg";
  let base64String = imageFile;
  if (imageFile.startsWith("data:")) {
    const matches = imageFile.match(/data:([^;]+);base64,(.+)/);
    if (matches) {
      mimeType = matches[1];
      base64String = matches[2];
    }
  }
  const byteCharacters = atob(base64String);
  const byteArray = new Uint8Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteArray[i] = byteCharacters.charCodeAt(i);
  }
  formData.append(
    fieldName,
    new Blob([byteArray], { type: mimeType }),
    "tongue_image.jpg",
  );
}

/** 將 fetch 錯誤轉成使用者可讀訊息 */
function toFetchErrorMessage(error: unknown, baseUrl: string): string {
  if (!(error instanceof Error)) return "發生未知錯誤";
  if (
    error.message?.includes("fetch failed") ||
    error.message?.includes("ECONNREFUSED")
  ) {
    return `無法連接到 FastAPI 服務 (${baseUrl})，請確保服務正在運行`;
  }
  return error.message || "發生未知錯誤";
}

const makeBrowserRequest = async (
  message: PromptRequest,
): Promise<PromptResponse> => {
  const response = await fetch(`${FASTAPI_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      prompt: message.prompt,
      user_id: message.user_id,
      session_id: message.session_id,
    }),
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    throw new Error(
      errorData.detail || `API 請求失敗 (狀態碼: ${response.status})`,
    );
  }

  const data = (await response.json()) as {
    response?: string;
    answer?: string;
  };
  return {
    data: data.response || data.answer || "沒有收到回應",
  };
};

const makeElectronRequest = async (
  message: PromptRequest,
): Promise<PromptResponse> => {
  if (!window.electronAPI) {
    throw new Error("Electron API 不可用");
  }

  const response = await window.electronAPI.sendChatMessage(
    message.prompt,
    message.user_id,
    message.session_id,
  );

  if (!response.success) {
    throw new Error(response.error || "API 請求失敗");
  }

  return {
    data: response.data || "沒有收到回應",
  };
};

export const makeRequest = async (
  message: PromptRequest,
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
  onError: (error: string) => void,
): Promise<() => void> => {
  if (isElectron() && window.electronAPI?.sendChatMessageStream) {
    const electronAPI = window.electronAPI;
    return electronAPI.sendChatMessageStream(
      message.prompt,
      message.user_id,
      message.session_id,
      onChunk,
      onComplete,
      onError,
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
          user_id: message.user_id,
          session_id: message.session_id,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        onError(
          (errorData as { detail?: string }).detail ||
            `API 請求失敗 (狀態碼: ${response.status})`,
        );
        return () => {};
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) {
        onError("無法讀取響應流");
        return () => {};
      }
      readSSEStream(reader, decoder, { onChunk, onComplete, onError });
      return () => reader.cancel();
    } catch (error: unknown) {
      onError(toFetchErrorMessage(error, FASTAPI_URL));
      return () => {};
    }
  }
};

const makeBrowserTongueAnalysis = async (
  request: TongueAnalysisRequest,
): Promise<PromptResponse> => {
  const response = await fetch(`${FASTAPI_URL}/tongue/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      prediction_results: request.prediction_results,
      additional_info: request.additional_info,
      user_id: request.user_id,
      session_id: request.session_id,
    }),
  });

  if (!response.ok) {
    const errorData = (await response.json().catch(() => ({}))) as {
      detail?: string;
    };
    throw new Error(
      errorData.detail || `API 請求失敗 (狀態碼: ${response.status})`,
    );
  }

  const data = (await response.json()) as { response?: string };
  return {
    data: data.response || "沒有收到回應",
  };
};

const makeElectronTongueAnalysis = async (
  request: TongueAnalysisRequest,
): Promise<PromptResponse> => {
  if (!window.electronAPI) {
    throw new Error("Electron API 不可用");
  }

  const response = await window.electronAPI.sendTongueAnalysis(
    request.prediction_results,
    request.additional_info,
  );

  if (!response.success) {
    throw new Error(response.error || "API 請求失敗");
  }

  return {
    data: response.data || "沒有收到回應",
  };
};

export const analyzeTongue = async (
  request: TongueAnalysisRequest,
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
  user_id?: string;
  session_id?: string;
}

const makeBrowserImagePredictAndAnalyze = async (
  request: ImagePredictRequest,
  onChunk: (chunk: string) => void,
  onStatus?: (status: string) => void,
  onComplete: () => void = () => {},
  onError: (error: string) => void = () => {},
): Promise<() => void> => {
  try {
    const formData = new FormData();
    appendImageToFormData(formData, request.imageFile);
    if (request.additional_info) {
      formData.append("additional_info", request.additional_info);
    }
    if (request.user_id) formData.append("user_id", request.user_id);
    if (request.session_id) formData.append("session_id", request.session_id);

    const response = await fetch(
      `${FASTAPI_URL}/tongue/predict-and-analyze/stream`,
      {
        method: "POST",
        body: formData,
      },
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
    readSSEStream(reader, decoder, {
      onChunk,
      onComplete,
      onError,
      onStatus,
    });
    return () => reader.cancel();
  } catch (error: unknown) {
    onError(toFetchErrorMessage(error, FASTAPI_URL));
    return () => {};
  }
};

export const predictAndAnalyzeTongueImage = async (
  request: ImagePredictRequest,
  onChunk: (chunk: string) => void,
  onStatus?: (status: string) => void,
  onComplete?: () => void,
  onError?: (error: string) => void,
): Promise<() => void> => {
  return makeBrowserImagePredictAndAnalyze(
    request,
    onChunk,
    onStatus,
    onComplete || (() => {}),
    onError || (() => {}),
  );
};

const makeBrowserAgentChat = async (
  request: ImagePredictRequest & { prompt?: string },
  onChunk: (chunk: string) => void,
  onStatus?: (status: string) => void,
  onComplete: () => void = () => {},
  onError: (error: string) => void = () => {},
): Promise<() => void> => {
  try {
    const formData = new FormData();
    if (request.imageFile) {
      appendImageToFormData(formData, request.imageFile);
    }
    formData.append("prompt", request.prompt ?? request.additional_info ?? "");
    if (request.user_id) formData.append("user_id", request.user_id);
    if (request.session_id) formData.append("session_id", request.session_id);

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
    readSSEStream(reader, decoder, {
      onChunk,
      onComplete,
      onError,
      onStatus,
    });
    return () => reader.cancel();
  } catch (error: unknown) {
    onError(toFetchErrorMessage(error, FASTAPI_URL));
    return () => {};
  }
};

export const agentChat = async (
  request: ImagePredictRequest & { prompt?: string },
  onChunk: (chunk: string) => void,
  onStatus?: (status: string) => void,
  onComplete?: () => void,
  onError?: (error: string) => void,
): Promise<() => void> => {
  return makeBrowserAgentChat(
    request,
    onChunk,
    onStatus,
    onComplete || (() => {}),
    onError || (() => {}),
  );
};

export const analyzeTongueStream = async (
  request: TongueAnalysisRequest,
  onChunk: (chunk: string) => void,
  onComplete: () => void,
  onError: (error: string) => void,
): Promise<() => void> => {
  if (isElectron() && window.electronAPI?.sendTongueAnalysisStream) {
    const electronAPI = window.electronAPI;
    return electronAPI.sendTongueAnalysisStream(
      request.prediction_results,
      request.additional_info,
      onChunk,
      onComplete,
      onError,
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
          (errorData as { detail?: string }).detail ||
            `API 請求失敗 (狀態碼: ${response.status})`,
        );
        return () => {};
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) {
        onError("無法讀取響應流");
        return () => {};
      }
      readSSEStream(reader, decoder, { onChunk, onComplete, onError });
      return () => reader.cancel();
    } catch (error: unknown) {
      onError(toFetchErrorMessage(error, FASTAPI_URL));
      return () => {};
    }
  }
};

/** 從 FastAPI /transcribe 取得音訊轉文字（Google Speech-to-Text） */
export const transcribeAudio = async (audioBlob: Blob): Promise<string> => {
  if (isElectron() && window.electronAPI?.transcribeAudio) {
    // Electron：由 main process 代為請求 /transcribe
    const arrayBuffer = await audioBlob.arrayBuffer();
    const uint8Array = new Uint8Array(arrayBuffer);
    const result = await window.electronAPI.transcribeAudio(uint8Array);
    if (!result.success) {
      throw new Error(result.error || "語音轉文字失敗");
    }
    return result.text ?? "";
  }

  // 瀏覽器模式：直接 fetch
  const formData = new FormData();
  formData.append("file", audioBlob, "audio.webm");

  const response = await fetch(`${FASTAPI_URL}/transcribe`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(
      (err as { detail?: string }).detail ||
        `語音轉文字失敗 (${response.status})`,
    );
  }

  const data = (await response.json()) as { text?: string };
  return data.text ?? "";
};
