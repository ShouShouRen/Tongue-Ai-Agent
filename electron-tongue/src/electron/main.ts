import { app, BrowserWindow, ipcMain, IpcMainEvent } from "electron";
import http from "http";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const FASTAPI_URL = "http://localhost:8000";
const FASTAPI_BASE = new URL(FASTAPI_URL);

/** 使用 Node http 發送 POST JSON，避免主進程 fetch 造成 405 */
function fastApiPostJson(
  path: string,
  body: Record<string, unknown>,
): Promise<{ statusCode: number; raw: string }> {
  const bodyStr = JSON.stringify(body);
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        hostname: FASTAPI_BASE.hostname,
        port: FASTAPI_BASE.port || 80,
        path,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(bodyStr, "utf8"),
        },
      },
      (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (chunk: Buffer) => chunks.push(chunk));
        res.on("end", () =>
          resolve({
            statusCode: res.statusCode || 0,
            raw: Buffer.concat(chunks).toString("utf8"),
          }),
        );
      },
    );
    req.on("error", reject);
    req.write(bodyStr, "utf8");
    req.end();
  });
}

/** 使用 Node http 發送 POST JSON 並處理 SSE 串流，透過 onChunk 回傳 */
function fastApiPostStream(
  path: string,
  body: Record<string, unknown>,
  onChunk: (data: {
    type: "chunk" | "done" | "error";
    content?: string;
    error?: string;
  }) => void,
): Promise<void> {
  const bodyStr = JSON.stringify(body);
  return new Promise((resolve, reject) => {
    const req = http.request(
      {
        hostname: FASTAPI_BASE.hostname,
        port: FASTAPI_BASE.port || 80,
        path,
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(bodyStr, "utf8"),
        },
      },
      (res) => {
        if (res.statusCode && (res.statusCode < 200 || res.statusCode >= 300)) {
          let raw = "";
          res.on("data", (chunk: Buffer) => (raw += chunk.toString("utf8")));
          res.on("end", () => {
            try {
              const data = JSON.parse(raw) as { detail?: string };
              onChunk({
                type: "error",
                error:
                  data.detail || `API 請求失敗 (狀態碼: ${res.statusCode})`,
              });
            } catch {
              onChunk({
                type: "error",
                error: raw || `API 請求失敗 (狀態碼: ${res.statusCode})`,
              });
            }
            resolve();
          });
          return;
        }
        let buffer = "";
        let done = false;
        const processLine = (line: string): boolean => {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") {
              onChunk({ type: "done" });
              done = true;
              return true;
            }
            try {
              const json = JSON.parse(data) as {
                content?: string;
                chunk?: string;
                response?: string;
              };
              const content = json.content ?? json.chunk ?? json.response ?? "";
              if (content) onChunk({ type: "chunk", content });
            } catch {
              if (data.trim()) onChunk({ type: "chunk", content: data });
            }
          } else if (line.trim()) {
            try {
              const json = JSON.parse(line) as {
                content?: string;
                chunk?: string;
                response?: string;
              };
              const content = json.content ?? json.chunk ?? json.response ?? "";
              if (content) onChunk({ type: "chunk", content });
            } catch {
              if (line.trim()) onChunk({ type: "chunk", content: line });
            }
          }
          return false;
        };
        res.on("data", (chunk: Buffer) => {
          if (done) return;
          buffer += chunk.toString("utf8");
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";
          for (const line of lines) {
            if (processLine(line)) return;
          }
        });
        res.on("end", () => {
          if (done) {
            resolve();
            return;
          }
          if (buffer.trim()) processLine(buffer);
          onChunk({ type: "done" });
          resolve();
        });
      },
    );
    req.on("error", (err) => {
      onChunk({ type: "error", error: err.message });
      resolve();
    });
    req.write(bodyStr, "utf8");
    req.end();
  });
}

function toIpcErrorMessage(error: unknown, baseUrl: string): string {
  if (!(error instanceof Error)) return "發生未知錯誤";
  if (
    error.message.includes("fetch failed") ||
    error.message.includes("ECONNREFUSED")
  ) {
    return `無法連接到 FastAPI 服務 (${baseUrl})，請確保服務正在運行`;
  }
  return error.message;
}

app.on("ready", () => {
  const mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
      plugins: false,
      enableBlinkFeatures: "",
      disableBlinkFeatures: "AutomationControlled",
      sandbox: false,
      webSecurity: true,
    },
  });

  mainWindow.setMenuBarVisibility(false);

  mainWindow.webContents.session.setPermissionRequestHandler(
    (webContents, permission, callback) => {
      if (permission === "media") {
        console.log("允許媒體權限請求（攝像頭/麥克風）");
        callback(true);
        return;
      }
      console.log(`拒絕權限請求: ${permission}`);
      callback(false);
    },
  );

  mainWindow.webContents.session.webRequest.onBeforeRequest(
    (details, callback) => {
      if (
        details.url.includes("chrome-extension://") ||
        details.url.includes("moz-extension://") ||
        details.url.includes("safari-extension://")
      ) {
        callback({ cancel: true });
        return;
      }
      callback({});
    },
  );

  mainWindow.webContents.session.webRequest.onHeadersReceived(
    (details, callback) => {
      callback({
        responseHeaders: {
          ...details.responseHeaders,
          "Content-Security-Policy": [
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: file: http: https:; script-src 'self' 'unsafe-inline' 'unsafe-eval' http: https:; style-src 'self' 'unsafe-inline' http: https:;",
          ],
        },
      });
    },
  );

  const isDev = !app.isPackaged;

  if (isDev) {
    const VITE_DEV_SERVER_URL = "http://localhost:5173";
    mainWindow.loadURL(VITE_DEV_SERVER_URL);

    mainWindow.webContents.openDevTools();

    mainWindow.webContents.on("did-fail-load", () => {
      console.log("等待 Vite 開發伺服器啟動...");
      setTimeout(() => {
        mainWindow.loadURL(VITE_DEV_SERVER_URL);
      }, 1000);
    });
  } else {
    mainWindow.loadFile(
      path.join(app.getAppPath(), "dist-react", "index.html"),
    );
  }
});

ipcMain.handle(
  "rag-chat",
  async (_event, prompt: string, userId?: string, sessionId?: string) => {
    try {
      if (!prompt || prompt.trim().length === 0) {
        throw new Error("提示內容不能為空");
      }

      const { statusCode, raw } = await fastApiPostJson("/chat", {
        prompt: prompt.trim(),
        user_id: userId,
        session_id: sessionId,
      });

      if (statusCode < 200 || statusCode >= 300) {
        const errorData = (() => {
          try {
            return JSON.parse(raw) as { detail?: string };
          } catch {
            return {};
          }
        })();
        throw new Error(
          errorData.detail || `API 請求失敗 (狀態碼: ${statusCode})`,
        );
      }

      const data = (() => {
        try {
          return JSON.parse(raw) as { response?: string; answer?: string };
        } catch {
          return {};
        }
      })();
      return {
        success: true,
        data: data.response || data.answer || "沒有收到回應",
      };
    } catch (error: unknown) {
      const errorMessage = toIpcErrorMessage(error, FASTAPI_URL);
      console.error("FastAPI 服務錯誤:", {
        message: errorMessage,
        url: FASTAPI_URL,
      });
      return {
        success: false,
        error: errorMessage,
      };
    }
  },
);

ipcMain.on(
  "rag-chat-stream",
  async (
    event: IpcMainEvent,
    prompt: string,
    userId?: string,
    sessionId?: string,
  ) => {
    try {
      if (!prompt || prompt.trim().length === 0) {
        event.sender.send("rag-chat-stream-chunk", {
          type: "error",
          error: "提示內容不能為空",
        });
        return;
      }

      const send = (payload: {
        type: "chunk" | "done" | "error";
        content?: string;
        error?: string;
      }) => event.sender.send("rag-chat-stream-chunk", payload);

      await fastApiPostStream(
        "/chat/stream",
        { prompt, user_id: userId, session_id: sessionId },
        (data) => {
          if (data.type === "chunk" && data.content)
            send({ type: "chunk", content: data.content });
          else if (data.type === "done") send({ type: "done" });
          else if (data.type === "error" && data.error)
            send({ type: "error", error: data.error });
        },
      );
    } catch (error: unknown) {
      const errorMessage = toIpcErrorMessage(error, FASTAPI_URL);
      console.error("FastAPI 流式服務錯誤:", errorMessage);
      event.sender.send("rag-chat-stream-chunk", {
        type: "error",
        error: errorMessage,
      });
    }
  },
);

ipcMain.handle("transcribe-audio", async (_event, audioData: Uint8Array) => {
  try {
    const buffer = Buffer.from(audioData);
    const boundary = `----ElectronFormBoundary${Date.now().toString(36)}`;
    const preamble = Buffer.from(
      `--${boundary}\r\n` +
        `Content-Disposition: form-data; name="file"; filename="audio.webm"\r\n` +
        `Content-Type: audio/webm\r\n\r\n`,
      "utf8",
    );
    const epilogue = Buffer.from(`\r\n--${boundary}--\r\n`, "utf8");
    const body = Buffer.concat([preamble, buffer, epilogue]);

    const result = await new Promise<{
      success: boolean;
      text?: string;
      error?: string;
    }>((resolve) => {
      const req = http.request(
        {
          hostname: FASTAPI_BASE.hostname,
          port: FASTAPI_BASE.port || 80,
          path: "/transcribe",
          method: "POST",
          headers: {
            "Content-Type": `multipart/form-data; boundary=${boundary}`,
            "Content-Length": body.length,
          },
        },
        (res) => {
          const chunks: Buffer[] = [];
          res.on("data", (chunk: Buffer) => chunks.push(chunk));
          res.on("end", () => {
            const raw = Buffer.concat(chunks).toString("utf8");
            try {
              const data = JSON.parse(raw) as {
                text?: string;
                detail?: string;
              };
              if (
                res.statusCode &&
                res.statusCode >= 200 &&
                res.statusCode < 300
              ) {
                resolve({ success: true, text: data.text ?? "" });
              } else {
                resolve({
                  success: false,
                  error: data.detail || `語音轉文字失敗 (${res.statusCode})`,
                });
              }
            } catch {
              resolve({
                success: false,
                error: raw || `語音轉文字失敗 (${res.statusCode})`,
              });
            }
          });
        },
      );
      req.on("error", (err) => {
        resolve({ success: false, error: err.message });
      });
      req.write(body);
      req.end();
    });

    if (!result.success) {
      throw new Error(result.error);
    }
    return { success: true, text: result.text ?? "" };
  } catch (error: unknown) {
    const msg = error instanceof Error ? error.message : "發生未知錯誤";
    console.error("語音辨識 IPC 錯誤:", msg);
    return { success: false, error: msg };
  }
});

ipcMain.handle(
  "tongue-analyze",
  async (
    _event,
    predictionResults: Record<string, any>,
    additionalInfo?: string,
  ) => {
    try {
      if (!predictionResults || Object.keys(predictionResults).length === 0) {
        throw new Error("預測結果不能為空");
      }

      const { statusCode, raw } = await fastApiPostJson("/tongue/analyze", {
        prediction_results: predictionResults,
        additional_info: additionalInfo ?? null,
      });

      if (statusCode < 200 || statusCode >= 300) {
        const errorData = (() => {
          try {
            return JSON.parse(raw) as { detail?: string };
          } catch {
            return {};
          }
        })();
        throw new Error(
          errorData.detail || `API 請求失敗 (狀態碼: ${statusCode})`,
        );
      }

      const data = (() => {
        try {
          return JSON.parse(raw) as { response?: string };
        } catch {
          return {};
        }
      })();
      return {
        success: true,
        data: data.response || "沒有收到回應",
      };
    } catch (error: unknown) {
      const errorMessage = toIpcErrorMessage(error, FASTAPI_URL);
      console.error("舌診分析服務錯誤:", {
        message: errorMessage,
        url: FASTAPI_URL,
      });
      return {
        success: false,
        error: errorMessage,
      };
    }
  },
);

ipcMain.on(
  "tongue-analyze-stream",
  async (
    event: IpcMainEvent,
    predictionResults: Record<string, any>,
    additionalInfo?: string,
  ) => {
    try {
      if (!predictionResults || Object.keys(predictionResults).length === 0) {
        event.sender.send("tongue-analyze-stream-chunk", {
          type: "error",
          error: "預測結果不能為空",
        });
        return;
      }

      const send = (payload: {
        type: "chunk" | "done" | "error";
        content?: string;
        error?: string;
      }) => event.sender.send("tongue-analyze-stream-chunk", payload);

      await fastApiPostStream(
        "/tongue/analyze/stream",
        {
          prediction_results: predictionResults,
          additional_info: additionalInfo ?? null,
        },
        (data) => {
          if (data.type === "chunk" && data.content)
            send({ type: "chunk", content: data.content });
          else if (data.type === "done") send({ type: "done" });
          else if (data.type === "error" && data.error)
            send({ type: "error", error: data.error });
        },
      );
    } catch (error: unknown) {
      const errorMessage = toIpcErrorMessage(error, FASTAPI_URL);
      console.error("舌診分析流式服務錯誤:", errorMessage);
      event.sender.send("tongue-analyze-stream-chunk", {
        type: "error",
        error: errorMessage,
      });
    }
  },
);
