import "./reset.css";
import {
  useState,
  type FormEvent,
  type ChangeEvent,
  type Dispatch,
  type SetStateAction,
  useRef,
  useEffect,
  useCallback,
} from "react";
import {
  makeStreamRequest,
  predictAndAnalyzeTongueImage,
  transcribeAudio,
} from "../api/api";
import ChatMessage from "./components/chat-message/chat-message";
import CameraModal from "./components/camera-modal/camera-modal";
import WeeklyReportModal from "./components/weekly-report-modal";
import mitLogo from "/logo.png";
import { BarChart3 } from "lucide-react";

interface ChatEntry {
  user: "assistant" | "user";
  message: string;
  imageUrl?: string;
  toolStatus?: string;
}

/** 移除重複的句子（多段辨識常會回傳相同內容，可能交錯出現） */
function dedupeRepeatedSentences(text: string): string {
  const parts = text
    .split(/[。.]+/)
    .map((p) => p.trim())
    .filter(Boolean);
  const seen = new Set<string>();
  const result: string[] = [];
  for (const p of parts) {
    if (!seen.has(p)) {
      seen.add(p);
      result.push(p);
    }
  }
  return result.length ? result.join("。") + "。" : "";
}

/** 更新聊天記錄中最後一則助理訊息的欄位 */
function updateLastAssistantMessage(
  setChatLog: Dispatch<SetStateAction<ChatEntry[]>>,
  update: Partial<Pick<ChatEntry, "message" | "toolStatus">>,
): void {
  setChatLog((prev) => {
    const newLog = [...prev];
    const lastIndex = newLog.length - 1;
    if (lastIndex >= 0 && newLog[lastIndex].user === "assistant") {
      newLog[lastIndex] = { ...newLog[lastIndex], ...update };
    }
    return newLog;
  });
}

const App = () => {
  const [input, setInput] = useState<string>("");
  const [chatLog, setChatLog] = useState<ChatEntry[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [isCameraOpen, setIsCameraOpen] = useState<boolean>(false);
  const [isWeeklyReportOpen, setIsWeeklyReportOpen] = useState<boolean>(false);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [isTranscribing, setIsTranscribing] = useState<boolean>(false);
  const [liveTranscript, setLiveTranscript] = useState<string>("");
  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunkQueueRef = useRef<Blob[]>([]);
  const isProcessingChunkRef = useRef<boolean>(false);
  const mimeTypeRef = useRef<string>("");
  const shouldContinueRecordingRef = useRef<boolean>(false);
  const recordingTimerRef = useRef<number | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  // 記憶管理：生成並保存 user_id 和 session_id
  const [userId] = useState<string>(() => {
    // 從 localStorage 獲取或生成新的 user_id
    let storedUserId = localStorage.getItem("tongue_ai_user_id");
    if (!storedUserId) {
      storedUserId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      localStorage.setItem("tongue_ai_user_id", storedUserId);
    }
    return storedUserId;
  });

  const [sessionId] = useState<string>(() => {
    // 每次應用啟動時生成新的 session_id（會話記憶）
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  });

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatLog]);

  // 逐一處理 chunk 佇列，避免同時送出多個請求
  const processChunkQueue = useCallback(async () => {
    if (isProcessingChunkRef.current) return;
    isProcessingChunkRef.current = true;
    while (chunkQueueRef.current.length > 0) {
      const chunk = chunkQueueRef.current.shift()!;
      try {
        const text = await transcribeAudio(chunk);
        if (text) {
          setLiveTranscript((prev) => dedupeRepeatedSentences(prev + text));
        }
      } catch {
        // chunk 辨識失敗靜默忽略，繼續下一個
      }
    }
    isProcessingChunkRef.current = false;
  }, []);

  const toggleRecording = useCallback(async () => {
    if (isRecording) {
      // 停止錄音
      setIsRecording(false);
      shouldContinueRecordingRef.current = false;
      if (recordingTimerRef.current) {
        clearTimeout(recordingTimerRef.current);
        recordingTimerRef.current = null;
      }
      mediaRecorderRef.current?.stop();
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "";
      mimeTypeRef.current = mimeType;
      chunkQueueRef.current = [];
      isProcessingChunkRef.current = false;
      setLiveTranscript("");
      shouldContinueRecordingRef.current = true;

      // 停止-重啟模式：每2.5秒重啟錄音，確保每個chunk都有完整的WebM頭
      const startRecorder = () => {
        if (!shouldContinueRecordingRef.current || !streamRef.current) return;

        const recorder = new MediaRecorder(
          streamRef.current,
          mimeType ? { mimeType } : undefined,
        );
        mediaRecorderRef.current = recorder;

        recorder.ondataavailable = (e) => {
          if (e.data.size > 0) {
            const chunkBlob = new Blob([e.data], {
              type: mimeType || "audio/webm",
            });
            chunkQueueRef.current.push(chunkBlob);
            processChunkQueue();
          }
        };

        recorder.onstop = async () => {
          // 如果應該繼續錄音，立即重啟
          if (shouldContinueRecordingRef.current) {
            setTimeout(startRecorder, 0);
          } else {
            // 真正停止錄音
            streamRef.current?.getTracks().forEach((t) => t.stop());
            streamRef.current = null;
            setIsTranscribing(true);
            const maxWaitMs = 45000; // 最多等 45 秒，避免後端載入 Whisper 時卡住
            const start = Date.now();
            while (
              (isProcessingChunkRef.current ||
                chunkQueueRef.current.length > 0) &&
              Date.now() - start < maxWaitMs
            ) {
              await new Promise((r) => setTimeout(r, 100));
            }
            setIsTranscribing(false);
            setLiveTranscript((live) => {
              if (live) {
                const deduped = dedupeRepeatedSentences(live);
                setInput((prev) => (prev ? prev + deduped : deduped));
              }
              return "";
            });
          }
        };

        recorder.start();
        // 2.5秒後停止，觸發onstop自動重啟
        recordingTimerRef.current = setTimeout(() => {
          if (recorder.state === "recording") {
            recorder.stop();
          }
        }, 2500);
      };

      startRecorder();
      setIsRecording(true);
    } catch {
      alert("無法存取麥克風，請允許麥克風權限。");
    }
  }, [isRecording, processChunkQueue]);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.type.startsWith("image/")) {
        alert("請只上傳圖片檔案");
        return;
      }

      const reader = new FileReader();
      reader.onloadend = () => {
        setSelectedImage(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleRemoveImage = () => {
    setSelectedImage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleCameraCapture = (imageDataUrl: string) => {
    setSelectedImage(imageDataUrl);
  };

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if ((!input.trim() && !selectedImage) || isLoading) {
      return;
    }

    const userMessage = input.trim();
    const imageUrl = selectedImage;

    setInput("");
    setSelectedImage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    setIsLoading(true);

    setChatLog((prev) => {
      const newLog = [
        ...prev,
        {
          user: "user" as const,
          message: userMessage || "[圖片]",
          imageUrl: imageUrl || undefined,
        },
        {
          user: "assistant" as const,
          message: "",
          toolStatus: undefined,
        },
      ];
      return newLog;
    });

    try {
      let accumulatedText = "";

      if (imageUrl) {
        const cleanup = await predictAndAnalyzeTongueImage(
          {
            imageFile: imageUrl,
            additional_info: userMessage || undefined,
            user_id: userId,
            session_id: sessionId,
          },
          (chunk: string) => {
            accumulatedText += chunk;
            updateLastAssistantMessage(setChatLog, {
              message: accumulatedText,
            });
          },
          (status: string) => {
            updateLastAssistantMessage(setChatLog, { toolStatus: status });
          },
          () => {
            setIsLoading(false);
            updateLastAssistantMessage(setChatLog, { toolStatus: undefined });
          },
          (error: string) => {
            updateLastAssistantMessage(setChatLog, {
              message: `錯誤：${error}`,
              toolStatus: undefined,
            });
            setIsLoading(false);
          },
        );

        return cleanup;
      } else {
        const prompt = userMessage;

        const cleanup = await makeStreamRequest(
          {
            prompt,
            user_id: userId,
            session_id: sessionId,
          },
          (chunk: string) => {
            accumulatedText += chunk;
            updateLastAssistantMessage(setChatLog, {
              message: accumulatedText,
            });
          },
          () => {
            setIsLoading(false);
            updateLastAssistantMessage(setChatLog, { toolStatus: undefined });
          },
          (error: string) => {
            updateLastAssistantMessage(setChatLog, {
              message: `錯誤：${error}`,
              toolStatus: undefined,
            });
            setIsLoading(false);
          },
        );

        return cleanup;
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "發生未知錯誤";
      updateLastAssistantMessage(setChatLog, {
        message: `錯誤：${message}`,
        toolStatus: undefined,
      });
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-white text-gray-800 overflow-hidden font-sans">
      <header className="h-[70px] bg-white border-b border-gray-200 flex items-center px-6 md:px-6 shrink-0 shadow-sm justify-between">
        <div className="flex items-center">
          <div className="flex items-baseline gap-1 font-semibold tracking-tight">
            <img
              src={mitLogo}
              alt="MIT Logo"
              width={200}
              className="h-[70px]"
            />
          </div>
        </div>
        <button
          onClick={() => setIsWeeklyReportOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 text-gray-600 rounded-lg hover:bg-gray-50 hover:text-mit-red transition-all shadow-sm group"
          title="查看健康週報"
        >
          <BarChart3
            size={18}
            className="group-hover:scale-110 transition-transform"
          />
          <span className="text-sm font-medium">健康週報</span>
        </button>
      </header>

      <main className="flex-1 flex flex-col overflow-hidden bg-gray-50">
        <div className="flex-1 overflow-y-auto p-4 md:p-6 flex flex-col gap-4 scroll-smooth [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:bg-gray-100 [&::-webkit-scrollbar-thumb]:bg-gray-300 [&::-webkit-scrollbar-thumb]:rounded [&::-webkit-scrollbar-thumb:hover]:bg-gray-400">
          {chatLog.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 text-center py-10">
              <div className="text-6xl mb-4 opacity-50">💬</div>
              <h2 className="text-xl font-semibold text-gray-600 mb-2">
                開始對話
              </h2>
              <p className="text-sm text-gray-400">
                輸入訊息或拍攝照片來開始分析
              </p>
            </div>
          )}
          {chatLog.map((message, index) => (
            <ChatMessage key={index} message={message} />
          ))}
          <div ref={chatEndRef} />
        </div>

        <div className="bg-white border-t border-gray-200 py-3 px-4 md:py-4 md:px-6 shrink-0 shadow-[0_-1px_3px_rgba(0,0,0,0.05)]">
          {selectedImage && (
            <div className="mb-3 flex max-w-[200px]">
              <div className="rounded-lg overflow-hidden border border-gray-200">
                <img
                  src={selectedImage}
                  alt="預覽"
                  className="max-w-full max-h-[200px] block object-contain"
                />
              </div>
              <div className="flex-1">
                <button
                  type="button"
                  className="mx-auto block bg-mit-red text-white border-none rounded-full w-6 h-6 cursor-pointer text-lg leading-none flex items-center justify-center transition-all shadow-md hover:bg-[#c0392b] hover:scale-110"
                  onClick={handleRemoveImage}
                  aria-label="移除圖片"
                >
                  ×
                </button>
              </div>
            </div>
          )}
          <form
            onSubmit={handleSubmit}
            className="flex items-center gap-2 md:gap-3 max-w-[1200px] mx-auto"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleFileChange}
              className="hidden"
            />
            <button
              type="button"
              className="flex items-center justify-center w-11 h-11 border-none rounded-xl cursor-pointer transition-all shrink-0 bg-gray-50 text-gray-600 border border-gray-200 hover:bg-gray-100 hover:text-gray-700 hover:border-gray-300 active:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
              onClick={() => setIsCameraOpen(true)}
              disabled={isLoading}
              title="拍攝照片"
              aria-label="拍攝照片"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
                <circle cx="12" cy="13" r="4" />
              </svg>
            </button>
            <button
              type="button"
              className={`flex items-center justify-center w-11 h-11 border-none rounded-xl cursor-pointer transition-all shrink-0 ${
                isRecording
                  ? "bg-red-100 text-red-600 border border-red-300 animate-pulse shadow-[0_0_0_3px_rgba(220,38,38,0.2)]"
                  : isTranscribing
                    ? "bg-yellow-50 text-yellow-500 border border-yellow-200"
                    : "bg-gray-50 text-gray-600 border border-gray-200 hover:bg-gray-100 hover:text-gray-700 hover:border-gray-300 active:bg-gray-200"
              } disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none`}
              onClick={toggleRecording}
              disabled={isLoading || isTranscribing}
              title={
                isRecording
                  ? "停止錄音"
                  : isTranscribing
                    ? "辨識中..."
                    : "語音輸入"
              }
              aria-label={isRecording ? "停止錄音" : "語音輸入"}
            >
              {isTranscribing ? (
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="animate-spin"
                >
                  <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
                  <path d="M12 2a10 10 0 0 1 10 10" />
                </svg>
              ) : isRecording ? (
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
              ) : (
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                  <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                  <line x1="12" y1="19" x2="12" y2="23" />
                  <line x1="8" y1="23" x2="16" y2="23" />
                </svg>
              )}
            </button>
            <input
              type="text"
              className="flex-1 py-3 px-4 border border-gray-200 rounded-xl text-sm text-gray-800 bg-white outline-none transition-all shadow-sm placeholder:text-gray-400 focus:border-mit-red focus:shadow-[0_0_0_3px_rgba(214,69,69,0.1)] disabled:bg-gray-50 disabled:cursor-not-allowed"
              value={isRecording ? input + liveTranscript : input}
              onChange={(e: ChangeEvent<HTMLInputElement>) => {
                if (!isRecording) setInput(e.target.value);
              }}
              disabled={isLoading || isTranscribing}
              placeholder={
                isTranscribing
                  ? "辨識中..."
                  : isRecording
                    ? "正在聆聽..."
                    : isLoading
                      ? "正在處理..."
                      : "輸入訊息..."
              }
            />
            <button
              type="submit"
              className="flex items-center justify-center w-11 h-11 border-none rounded-xl cursor-pointer transition-all shrink-0 bg-mit-red text-white shadow-[0_2px_4px_rgba(214,69,69,0.2)] hover:bg-mit-red-dark hover:-translate-y-0.5 hover:shadow-[0_4px_8px_rgba(214,69,69,0.3)] active:translate-y-0 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
              disabled={
                isLoading ||
                (!(input.trim() || liveTranscript) && !selectedImage)
              }
              title="發送"
              aria-label="發送訊息"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </form>
        </div>
      </main>

      <CameraModal
        isOpen={isCameraOpen}
        onClose={() => setIsCameraOpen(false)}
        onCapture={handleCameraCapture}
      />

      <WeeklyReportModal
        isOpen={isWeeklyReportOpen}
        onClose={() => setIsWeeklyReportOpen(false)}
        userId={userId}
      />
    </div>
  );
};

export default App;
