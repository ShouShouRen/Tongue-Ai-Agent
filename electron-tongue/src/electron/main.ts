import { app, BrowserWindow, ipcMain, IpcMainEvent } from "electron";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const FASTAPI_URL = "http://localhost:8000";

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
    }
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
    }
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
    }
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
      path.join(app.getAppPath(), "dist-react", "index.html")
    );
  }
});

ipcMain.handle("rag-chat", async (_event, prompt: string) => {
  try {
    if (!prompt || prompt.trim().length === 0) {
      throw new Error("提示內容不能為空");
    }

    const response = await fetch(`${FASTAPI_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        prompt: prompt,
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
      success: true,
      data: data.response || data.answer || "沒有收到回應",
    };
  } catch (error: any) {
    console.error("FastAPI 服務錯誤:", {
      message: error.message,
      url: FASTAPI_URL,
    });

    let errorMessage = "發生未知錯誤";

    if (error.message) {
      if (
        error.message.includes("fetch failed") ||
        error.message.includes("ECONNREFUSED")
      ) {
        errorMessage = `無法連接到 FastAPI 服務 (${FASTAPI_URL})，請確保服務正在運行`;
      } else {
        errorMessage = error.message;
      }
    }

    return {
      success: false,
      error: errorMessage,
    };
  }
});

ipcMain.on("rag-chat-stream", async (event: IpcMainEvent, prompt: string) => {
  try {
    if (!prompt || prompt.trim().length === 0) {
      event.sender.send("rag-chat-stream-chunk", {
        type: "error",
        error: "提示內容不能為空",
      });
      return;
    }

    const response = await fetch(`${FASTAPI_URL}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        prompt: prompt,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMessage =
        errorData.detail || `API 請求失敗 (狀態碼: ${response.status})`;
      event.sender.send("rag-chat-stream-chunk", {
        type: "error",
        error: errorMessage,
      });
      return;
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      event.sender.send("rag-chat-stream-chunk", {
        type: "error",
        error: "無法讀取響應流",
      });
      return;
    }

    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        event.sender.send("rag-chat-stream-chunk", {
          type: "done",
        });
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data === "[DONE]") {
            event.sender.send("rag-chat-stream-chunk", {
              type: "done",
            });
            return;
          }

          try {
            const json = JSON.parse(data);
            const content = json.content || json.chunk || json.response || "";
            if (content) {
              event.sender.send("rag-chat-stream-chunk", {
                type: "chunk",
                content: content,
              });
            }
          } catch (e) {
            if (data.trim()) {
              event.sender.send("rag-chat-stream-chunk", {
                type: "chunk",
                content: data,
              });
            }
          }
        } else if (line.trim()) {
          try {
            const json = JSON.parse(line);
            const content = json.content || json.chunk || json.response || "";
            if (content) {
              event.sender.send("rag-chat-stream-chunk", {
                type: "chunk",
                content: content,
              });
            }
          } catch (e) {
            if (line.trim()) {
              event.sender.send("rag-chat-stream-chunk", {
                type: "chunk",
                content: line,
              });
            }
          }
        }
      }
    }
  } catch (error: any) {
    console.error("FastAPI 流式服務錯誤:", error);

    let errorMessage = "發生未知錯誤";

    if (error.message) {
      if (
        error.message.includes("fetch failed") ||
        error.message.includes("ECONNREFUSED")
      ) {
        errorMessage = `無法連接到 FastAPI 服務 (${FASTAPI_URL})，請確保服務正在運行`;
      } else {
        errorMessage = error.message;
      }
    }

    event.sender.send("rag-chat-stream-chunk", {
      type: "error",
      error: errorMessage,
    });
  }
});

ipcMain.handle(
  "tongue-analyze",
  async (
    _event,
    predictionResults: Record<string, any>,
    additionalInfo?: string
  ) => {
    try {
      if (!predictionResults || Object.keys(predictionResults).length === 0) {
        throw new Error("預測結果不能為空");
      }

      const response = await fetch(`${FASTAPI_URL}/tongue/analyze`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prediction_results: predictionResults,
          additional_info: additionalInfo || null,
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
        success: true,
        data: data.response || "沒有收到回應",
      };
    } catch (error: any) {
      console.error("舌診分析服務錯誤:", {
        message: error.message,
        url: FASTAPI_URL,
      });

      let errorMessage = "發生未知錯誤";

      if (error.message) {
        if (
          error.message.includes("fetch failed") ||
          error.message.includes("ECONNREFUSED")
        ) {
          errorMessage = `無法連接到 FastAPI 服務 (${FASTAPI_URL})，請確保服務正在運行`;
        } else {
          errorMessage = error.message;
        }
      }

      return {
        success: false,
        error: errorMessage,
      };
    }
  }
);

ipcMain.on(
  "tongue-analyze-stream",
  async (
    event: IpcMainEvent,
    predictionResults: Record<string, any>,
    additionalInfo?: string
  ) => {
    try {
      if (!predictionResults || Object.keys(predictionResults).length === 0) {
        event.sender.send("tongue-analyze-stream-chunk", {
          type: "error",
          error: "預測結果不能為空",
        });
        return;
      }

      const response = await fetch(`${FASTAPI_URL}/tongue/analyze/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          prediction_results: predictionResults,
          additional_info: additionalInfo || null,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage =
          errorData.detail || `API 請求失敗 (狀態碼: ${response.status})`;
        event.sender.send("tongue-analyze-stream-chunk", {
          type: "error",
          error: errorMessage,
        });
        return;
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        event.sender.send("tongue-analyze-stream-chunk", {
          type: "error",
          error: "無法讀取響應流",
        });
        return;
      }

      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          event.sender.send("tongue-analyze-stream-chunk", {
            type: "done",
          });
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "[DONE]") {
              event.sender.send("tongue-analyze-stream-chunk", {
                type: "done",
              });
              return;
            }

            try {
              const json = JSON.parse(data);
              const content = json.content || json.chunk || json.response || "";
              if (content) {
                event.sender.send("tongue-analyze-stream-chunk", {
                  type: "chunk",
                  content: content,
                });
              }
            } catch (e) {
              if (data.trim()) {
                event.sender.send("tongue-analyze-stream-chunk", {
                  type: "chunk",
                  content: data,
                });
              }
            }
          } else if (line.trim()) {
            try {
              const json = JSON.parse(line);
              const content = json.content || json.chunk || json.response || "";
              if (content) {
                event.sender.send("tongue-analyze-stream-chunk", {
                  type: "chunk",
                  content: content,
                });
              }
            } catch (e) {
              if (line.trim()) {
                event.sender.send("tongue-analyze-stream-chunk", {
                  type: "chunk",
                  content: line,
                });
              }
            }
          }
        }
      }
    } catch (error: any) {
      console.error("舌診分析流式服務錯誤:", error);

      let errorMessage = "發生未知錯誤";

      if (error.message) {
        if (
          error.message.includes("fetch failed") ||
          error.message.includes("ECONNREFUSED")
        ) {
          errorMessage = `無法連接到 FastAPI 服務 (${FASTAPI_URL})，請確保服務正在運行`;
        } else {
          errorMessage = error.message;
        }
      }

      event.sender.send("tongue-analyze-stream-chunk", {
        type: "error",
        error: errorMessage,
      });
    }
  }
);
