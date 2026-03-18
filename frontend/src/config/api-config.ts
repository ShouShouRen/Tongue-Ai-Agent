export const API_BASE_URL = "http://localhost:8000";

export const ENDPOINTS = {
  CHAT: "/chat",
  CHAT_STREAM: "/chat/stream",
  TONGUE_ANALYZE: "/tongue/analyze",
  TONGUE_ANALYZE_STREAM: "/tongue/analyze/stream",
  TONGUE_PREDICT: "/tongue/predict",
  TONGUE_PREDICT_AND_ANALYZE_STREAM: "/tongue/predict-and-analyze/stream",
  AGENT_CHAT_STREAM: "/agent/chat/stream",
  REALTIME_ANALYZE_FRAME: "/realtime/analyze-frame",
  TONGUE_ADVICE_STREAM: "/api/tongue/advice/stream",
} as const;
