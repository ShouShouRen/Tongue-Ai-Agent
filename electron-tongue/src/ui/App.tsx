import "./reset.css";
import {
  useState,
  type FormEvent,
  type ChangeEvent,
  useRef,
  useEffect,
} from "react";
import { makeStreamRequest, predictAndAnalyzeTongueImage } from "../api/api";
import ChatMessage from "./components/chat-message/chat-message";
import CameraModal from "./components/camera-modal/camera-modal";
import mitLogo from "/logo.png";

interface ChatEntry {
  user: "assistant" | "user";
  message: string;
  imageUrl?: string;
  toolStatus?: string;
}

const App = () => {
  const [input, setInput] = useState<string>("");
  const [chatLog, setChatLog] = useState<ChatEntry[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [isCameraOpen, setIsCameraOpen] = useState<boolean>(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
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
            setChatLog((prev) => {
              const newLog = [...prev];
              const lastIndex = newLog.length - 1;
              if (lastIndex >= 0 && newLog[lastIndex].user === "assistant") {
                newLog[lastIndex] = {
                  ...newLog[lastIndex],
                  message: accumulatedText,
                };
              }
              return newLog;
            });
          },
          (status: string) => {
            setChatLog((prev) => {
              const newLog = [...prev];
              const lastIndex = newLog.length - 1;
              if (lastIndex >= 0 && newLog[lastIndex].user === "assistant") {
                newLog[lastIndex] = {
                  ...newLog[lastIndex],
                  toolStatus: status,
                };
              }
              return newLog;
            });
          },
          () => {
            setIsLoading(false);
            setChatLog((prev) => {
              const newLog = [...prev];
              const lastIndex = newLog.length - 1;
              if (lastIndex >= 0 && newLog[lastIndex].user === "assistant") {
                newLog[lastIndex] = {
                  ...newLog[lastIndex],
                  toolStatus: undefined,
                };
              }
              return newLog;
            });
          },
          (error: string) => {
            setChatLog((prev) => {
              const newLog = [...prev];
              const lastIndex = newLog.length - 1;
              if (lastIndex >= 0 && newLog[lastIndex].user === "assistant") {
                newLog[lastIndex] = {
                  ...newLog[lastIndex],
                  message: `錯誤：${error}`,
                  toolStatus: undefined,
                };
              }
              return newLog;
            });
            setIsLoading(false);
          }
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
            setChatLog((prev) => {
              const newLog = [...prev];
              const lastIndex = newLog.length - 1;
              if (lastIndex >= 0 && newLog[lastIndex].user === "assistant") {
                newLog[lastIndex] = {
                  ...newLog[lastIndex],
                  message: accumulatedText,
                };
              }
              return newLog;
            });
          },
          () => {
            setIsLoading(false);
            setChatLog((prev) => {
              const newLog = [...prev];
              const lastIndex = newLog.length - 1;
              if (lastIndex >= 0 && newLog[lastIndex].user === "assistant") {
                newLog[lastIndex] = {
                  ...newLog[lastIndex],
                  toolStatus: undefined,
                };
              }
              return newLog;
            });
          },
          (error: string) => {
            setChatLog((prev) => {
              const newLog = [...prev];
              const lastIndex = newLog.length - 1;
              if (lastIndex >= 0 && newLog[lastIndex].user === "assistant") {
                newLog[lastIndex] = {
                  ...newLog[lastIndex],
                  message: `錯誤：${error}`,
                  toolStatus: undefined,
                };
              }
              return newLog;
            });
            setIsLoading(false);
          }
        );

        return cleanup;
      }
    } catch (error: any) {
      setChatLog((prev) => {
        const newLog = [...prev];
        const lastIndex = newLog.length - 1;
        if (lastIndex >= 0 && newLog[lastIndex].user === "assistant") {
          newLog[lastIndex] = {
            ...newLog[lastIndex],
            message: `錯誤：${error.message || "發生未知錯誤"}`,
            toolStatus: undefined,
          };
        }
        return newLog;
      });
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-white text-gray-800 overflow-hidden font-sans">
      <header className="h-[70px] bg-white border-b border-gray-200 flex items-center px-6 md:px-6 shrink-0 shadow-sm">
        <div className="w-full max-w-[1200px] mx-auto flex items-center">
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
        </div>
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
            <input
              type="text"
              className="flex-1 py-3 px-4 border border-gray-200 rounded-xl text-sm text-gray-800 bg-white outline-none transition-all shadow-sm placeholder:text-gray-400 focus:border-mit-red focus:shadow-[0_0_0_3px_rgba(214,69,69,0.1)] disabled:bg-gray-50 disabled:cursor-not-allowed"
              value={input}
              onChange={(e: ChangeEvent<HTMLInputElement>) =>
                setInput(e.target.value)
              }
              disabled={isLoading}
              placeholder={isLoading ? "正在處理..." : "輸入訊息..."}
            />
            <button
              type="submit"
              className="flex items-center justify-center w-11 h-11 border-none rounded-xl cursor-pointer transition-all shrink-0 bg-mit-red text-white shadow-[0_2px_4px_rgba(214,69,69,0.2)] hover:bg-mit-red-dark hover:-translate-y-0.5 hover:shadow-[0_4px_8px_rgba(214,69,69,0.3)] active:translate-y-0 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
              disabled={isLoading || (!input.trim() && !selectedImage)}
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
    </div>
  );
};

export default App;
