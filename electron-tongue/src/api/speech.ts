/**
 * Web Speech API 語音辨識（瀏覽器內建，免後端、即時、無需等待）
 * 支援 Chrome、Edge、Safari。不支援時會回傳 null，由呼叫端改走後端 Whisper。
 */

declare global {
  interface Window {
    SpeechRecognition?: new () => SpeechRecognitionInstance;
    webkitSpeechRecognition?: new () => SpeechRecognitionInstance;
  }
}

interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  onresult: ((e: SpeechRecognitionResultEvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error: string }) => void) | null;
}

interface SpeechRecognitionResultEvent {
  resultIndex: number;
  results: Array<{ isFinal: boolean; length: number; 0: { transcript: string }; [i: number]: { transcript: string } }>;
}

const SpeechRecognitionAPI =
  typeof window !== "undefined"
    ? (window.SpeechRecognition || window.webkitSpeechRecognition)
    : undefined;

export function isWebSpeechAvailable(): boolean {
  return Boolean(SpeechRecognitionAPI);
}

export type WebSpeechCallbacks = {
  onInterim?: (text: string) => void;
  onFinal?: (text: string) => void;
  onEnd?: () => void;
  onError?: (message: string) => void;
};

export function createWebSpeechRecognition(callbacks: WebSpeechCallbacks): {
  start: () => void;
  stop: () => void;
} | null {
  const API = SpeechRecognitionAPI;
  if (!API) return null;

  const recognition = new API();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "zh-TW";
  recognition.maxAlternatives = 1;

  let finalTranscript = "";

  recognition.onresult = (event: SpeechRecognitionResultEvent) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const result = event.results[i];
      const text = result[0]?.transcript ?? "";
      if (result.isFinal) {
        finalTranscript += text;
        callbacks.onFinal?.(text);
      } else {
        interim += text;
      }
    }
    if (interim) {
      callbacks.onInterim?.(finalTranscript + interim);
    }
  };

  recognition.onend = () => {
    callbacks.onEnd?.();
  };

  recognition.onerror = (event: { error: string }) => {
    const msg = event.error === "not-allowed" ? "麥克風權限被拒絕" : event.error;
    callbacks.onError?.(typeof msg === "string" ? msg : "語音辨識錯誤");
  };

  return {
    start() {
      finalTranscript = "";
      try {
        recognition.start();
      } catch (e) {
        callbacks.onError?.("無法啟動語音辨識");
      }
    },
    stop() {
      try {
        recognition.stop();
      } catch {
        // ignore
      }
    },
  };
}
