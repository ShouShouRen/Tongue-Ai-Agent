import type { TonguePredictionResults } from "../types/electron";
import { API_BASE_URL, ENDPOINTS } from "../config/api-config";
import {
  parseSSEStream,
  convertBase64ToBlob,
  parseJsonErrorResponse,
  parseTextErrorResponse,
  handleConnectionError,
} from "./stream-utils";

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

const isElectron = () => {
  return typeof window !== "undefined" && window.electronAPI !== undefined;
};

// ========= Realtime Frame 分析 =========

export interface RealtimeBoxResult {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  status: string;
  ratio: number;
  aspect_ratio: number;
  touching_edge: boolean;
}

export interface RealtimeFrameResult {
  ok: boolean;
  reason: string;
  boxes: RealtimeBoxResult[];
}

export const analyzeRealtimeFrame = async (
  imageBlob: Blob
): Promise<RealtimeFrameResult> => {
  const formData = new FormData();
  formData.append("file", imageBlob, "frame.jpg");

  const response = await fetch(
    `${API_BASE_URL}${ENDPOINTS.REALTIME_ANALYZE_FRAME}`,
    { method: "POST", body: formData }
  );

  if (!response.ok) {
    const errorMessage = await parseTextErrorResponse(
      response,
      `即時偵測 API 失敗 (狀態碼: ${response.status})`
    );
    throw new Error(errorMessage);
  }

  return (await response.json()) as RealtimeFrameResult;
};

const makeBrowserRequest = async (
  message: PromptRequest
): Promise<PromptResponse> => {
  const response = await fetch(`${API_BASE_URL}${ENDPOINTS.CHAT}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: message.prompt,
      user_id: message.user_id,
      session_id: message.session_id,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      (errorData as { detail?: string }).detail ||
        `API 請求失敗 (狀態碼: ${response.status})`
    );
  }

  const data = await response.json();
  return { data: data.response || data.answer || "沒有收到回應" };
};

const makeElectronRequest = async (
  message: PromptRequest
): Promise<PromptResponse> => {
  if (!window.electronAPI) throw new Error("Electron API 不可用");

  const response = await window.electronAPI.sendChatMessage(
    message.prompt,
    message.user_id,
    message.session_id
  );

  if (!response.success) throw new Error(response.error || "API 請求失敗");
  return { data: response.data || "沒有收到回應" };
};

export const makeRequest = async (
  message: PromptRequest
): Promise<PromptResponse> => {
  return isElectron()
    ? makeElectronRequest(message)
    : makeBrowserRequest(message);
};

export const makeStreamRequest = async (
  message: PromptRequest,
  onChunk: (chunk: string) => void,
  onComplete: () => void,
  onError: (error: string) => void
): Promise<() => void> => {
  if (isElectron() && window.electronAPI?.sendChatMessageStream) {
    return window.electronAPI.sendChatMessageStream(
      message.prompt,
      message.user_id,
      message.session_id,
      onChunk,
      onComplete,
      onError
    );
  }

  try {
    const response = await fetch(`${API_BASE_URL}${ENDPOINTS.CHAT_STREAM}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: message.prompt,
        user_id: message.user_id,
        session_id: message.session_id,
      }),
    });

    if (!response.ok) {
      onError(
        await parseJsonErrorResponse(
          response,
          `API 請求失敗 (狀態碼: ${response.status})`
        )
      );
      return () => {};
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError("無法讀取響應流");
      return () => {};
    }

    return parseSSEStream(reader, { onChunk, onComplete, onError });
  } catch (error: unknown) {
    handleConnectionError(error, API_BASE_URL, onError);
    return () => {};
  }
};

const makeBrowserTongueAnalysis = async (
  request: TongueAnalysisRequest
): Promise<PromptResponse> => {
  const response = await fetch(`${API_BASE_URL}${ENDPOINTS.TONGUE_ANALYZE}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prediction_results: request.prediction_results,
      additional_info: request.additional_info,
      user_id: request.user_id,
      session_id: request.session_id,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      (errorData as { detail?: string }).detail ||
        `API 請求失敗 (狀態碼: ${response.status})`
    );
  }

  const data = await response.json();
  return { data: data.response || "沒有收到回應" };
};

const makeElectronTongueAnalysis = async (
  request: TongueAnalysisRequest
): Promise<PromptResponse> => {
  if (!window.electronAPI) throw new Error("Electron API 不可用");

  const response = await window.electronAPI.sendTongueAnalysis(
    request.prediction_results,
    request.additional_info
  );

  if (!response.success) throw new Error(response.error || "API 請求失敗");
  return { data: response.data || "沒有收到回應" };
};

export const analyzeTongue = async (
  request: TongueAnalysisRequest
): Promise<PromptResponse> => {
  return isElectron()
    ? makeElectronTongueAnalysis(request)
    : makeBrowserTongueAnalysis(request);
};

interface ImagePredictRequest {
  imageFile: File | string;
  additional_info?: string;
  user_id?: string;
  session_id?: string;
}

const appendImageToFormData = (
  formData: FormData,
  imageFile: File | string
): void => {
  if (imageFile instanceof File) {
    formData.append("file", imageFile);
  } else if (imageFile) {
    const blob = convertBase64ToBlob(imageFile);
    formData.append("file", blob, "tongue_image.jpg");
  }
};

const makeBrowserImagePredictAndAnalyze = async (
  request: ImagePredictRequest,
  onChunk: (chunk: string) => void,
  onStatus?: (status: string) => void,
  onComplete: () => void = () => {},
  onError: (error: string) => void = () => {}
): Promise<() => void> => {
  try {
    const formData = new FormData();
    appendImageToFormData(formData, request.imageFile);
    if (request.additional_info)
      formData.append("additional_info", request.additional_info);
    if (request.user_id) formData.append("user_id", request.user_id);
    if (request.session_id) formData.append("session_id", request.session_id);

    const response = await fetch(
      `${API_BASE_URL}${ENDPOINTS.TONGUE_PREDICT_AND_ANALYZE_STREAM}`,
      { method: "POST", body: formData }
    );

    if (!response.ok) {
      onError(
        await parseTextErrorResponse(
          response,
          `API 請求失敗 (狀態碼: ${response.status})`
        )
      );
      return () => {};
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError("無法讀取響應流");
      return () => {};
    }

    return parseSSEStream(reader, { onChunk, onComplete, onError, onStatus });
  } catch (error: unknown) {
    handleConnectionError(error, API_BASE_URL, onError);
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
    appendImageToFormData(formData, request.imageFile);

    if (request.prompt || request.additional_info) {
      formData.append(
        "prompt",
        request.prompt || request.additional_info || ""
      );
    }
    if (request.user_id) formData.append("user_id", request.user_id);
    if (request.session_id) formData.append("session_id", request.session_id);

    const response = await fetch(
      `${API_BASE_URL}${ENDPOINTS.AGENT_CHAT_STREAM}`,
      { method: "POST", body: formData }
    );

    if (!response.ok) {
      onError(
        await parseTextErrorResponse(
          response,
          `API 請求失敗 (狀態碼: ${response.status})`
        )
      );
      return () => {};
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError("無法讀取響應流");
      return () => {};
    }

    return parseSSEStream(reader, { onChunk, onComplete, onError, onStatus });
  } catch (error: unknown) {
    handleConnectionError(error, API_BASE_URL, onError);
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

export const fetchAdviceStream = async (
  userId: string,
  onChunk: (chunk: string) => void,
  onComplete: () => void,
  onError: (error: string) => void
): Promise<() => void> => {
  try {
    const response = await fetch(`${API_BASE_URL}${ENDPOINTS.TONGUE_ADVICE_STREAM}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId }),
    });

    if (!response.ok) {
      onError(await parseJsonErrorResponse(response, `API 請求失敗 (狀態碼: ${response.status})`));
      return () => {};
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError("無法讀取響應流");
      return () => {};
    }

    return parseSSEStream(reader, { onChunk, onComplete, onError });
  } catch (error: unknown) {
    handleConnectionError(error, API_BASE_URL, onError);
    return () => {};
  }
};

export const analyzeTongueStream = async (
  request: TongueAnalysisRequest,
  onChunk: (chunk: string) => void,
  onComplete: () => void,
  onError: (error: string) => void
): Promise<() => void> => {
  if (isElectron() && window.electronAPI?.sendTongueAnalysisStream) {
    return window.electronAPI.sendTongueAnalysisStream(
      request.prediction_results,
      request.additional_info,
      onChunk,
      onComplete,
      onError
    );
  }

  try {
    const response = await fetch(
      `${API_BASE_URL}${ENDPOINTS.TONGUE_ANALYZE_STREAM}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      }
    );

    if (!response.ok) {
      onError(
        await parseJsonErrorResponse(
          response,
          `API 請求失敗 (狀態碼: ${response.status})`
        )
      );
      return () => {};
    }

    const reader = response.body?.getReader();
    if (!reader) {
      onError("無法讀取響應流");
      return () => {};
    }

    return parseSSEStream(reader, { onChunk, onComplete, onError });
  } catch (error: unknown) {
    handleConnectionError(error, API_BASE_URL, onError);
    return () => {};
  }
};
