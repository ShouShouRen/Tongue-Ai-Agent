export interface TongueFeatureResult {
  chinese: string;
  english: string;
  probability: number;
  threshold: number;
}

export interface TonguePredictionResults {
  positive?: TongueFeatureResult[];
  negative?: TongueFeatureResult[];
  summary?: {
    positive_count?: number;
    negative_count?: number;
  };
  [key: string]: unknown;
}

export interface ElectronAPI {
  sendChatMessage: (prompt: string, userId?: string, sessionId?: string) => Promise<{
    success: boolean;
    data?: string;
    error?: string;
  }>;
  sendChatMessageStream: (
    prompt: string,
    userId?: string,
    sessionId?: string,
    onChunk?: (chunk: string) => void,
    onComplete?: () => void,
    onError?: (error: string) => void
  ) => () => void;
  sendTongueAnalysis: (
    predictionResults: TonguePredictionResults | Record<string, unknown>,
    additionalInfo?: string
  ) => Promise<{
    success: boolean;
    data?: string;
    error?: string;
  }>;
  sendTongueAnalysisStream: (
    predictionResults: TonguePredictionResults | Record<string, unknown>,
    additionalInfo: string | undefined,
    onChunk: (chunk: string) => void,
    onComplete: () => void,
    onError: (error: string) => void
  ) => () => void;
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}

