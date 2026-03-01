# Tongue AI Agent — 中醫舌診 AI 助手

基於中醫理論的智慧舌診分析系統，結合電腦視覺模型與本地大型語言模型（LLM），提供即時舌象辨識、體質分析與健康建議，並具備長期記憶功能可追蹤用戶健康趨勢。

---

## 目錄

1. [所需環境](#所需環境)
2. [環境搭建](#環境搭建)
3. [啟動專案](#啟動專案)
4. [整體架構概覽](#整體架構概覽)
5. [前端架構詳解](#前端架構詳解)
6. [後端架構詳解](#後端架構詳解)
7. [AI 串接機制詳解](#ai-串接機制詳解)
8. [資料流程圖](#資料流程圖)
9. [API 端點一覽](#api-端點一覽)
10. [記憶系統說明](#記憶系統說明)
11. [常見問題排查](#常見問題排查)

---

### 必要軟體

| 軟體        | 最低版本                 | 用途                      |
| ----------- | ------------------------ | ------------------------- |
| **Node.js** | 20.x LTS                 | 前端執行環境              |
| **pnpm**    | 9.x                      | 前端套件管理器            |
| **Python**  | 3.12+                    | 後端執行環境              |
| **uv**      | 0.4+                     | Python 套件管理器（推薦） |
| **Ollama**  | 0.3+                     | 本地 LLM 推理引擎         |
| **Docker**  | 24+（含 Compose Plugin） | 運行 PostgreSQL 容器      |
| **Git**     | 任意版本                 | 版本控制                  |

### 硬體建議

| 規格     | 最低需求               | 建議配置           |
| -------- | ---------------------- | ------------------ |
| RAM      | 8 GB                   | 16 GB+             |
| GPU      | 無（CPU 推理，速度慢） | NVIDIA 8 GB VRAM+  |
| 儲存空間 | 20 GB                  | 40 GB+（模型權重） |
| CPU      | 4 核心                 | 8 核心+            |

> **注意**：視覺辨識模型（YOLOv8 + Swin Transformer + ConvNeXt）需要大量運算資源。若無 GPU，分析速度會明顯較慢。

---

## 環境搭建

### 步驟 1：取得程式碼

```bash
git clone https://github.com/ShouShouRen/Tongue-Ai-Agent
cd tongue-ai-agent
```

### 步驟 2：安裝 Ollama 並下載語言模型

**macOS / Linux：**

```bash
# 安裝 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 啟動 Ollama 服務
ollama serve
```

**Windows：**
前往 [https://ollama.com/download](https://ollama.com/download) 下載安裝程式。

**下載語言模型（新開一個終端機）：**

```bash
# 下載 qwen3:8b 模型（約 5 GB）
ollama pull qwen3:8b

# 驗證模型已下載
ollama list
```

> 若機器資源不足，可改用較小的模型（如 `qwen2.5:3b`），並修改 `backend/config/settings.py` 中的 `model_name`。

### 步驟 3：使用 Docker Compose 啟動 PostgreSQL

本專案已內建 `docker-compose.yml`，請先確認已安裝 [Docker Desktop](https://www.docker.com/products/docker-desktop/)（macOS / Windows）或 Docker Engine + Docker Compose Plugin（Linux）。

**在專案根目錄執行：**

```bash
docker compose up -d
```

這一行指令會自動完成：

- 拉取 `postgres:16-alpine` 映像
- 建立資料庫 `tongue_ai_memory`（帳號 `postgres` / 密碼 `postgres`）
- 綁定本機 port `5432`
- 建立 named volume `postgres_data` 持久化資料（重啟容器資料不會消失）
- 啟動 healthcheck，確認資料庫就緒後才對外服務

**驗證容器正在運行：**

```bash
docker compose ps
# 應看到 tongue-ai-postgres 狀態為 running (healthy)
```

**停止資料庫（資料保留）：**

```bash
docker compose stop
```

**重新啟動：**

```bash
docker compose start
```

> **資料表會在第一次啟動後端時自動建立**，不需要手動執行任何 SQL。

### 步驟 4：安裝後端依賴

```bash
cd backend

# 方式 A：使用 uv（推薦，速度快）
pip install uv
uv sync

# 方式 B：使用 pip
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .
```

### 步驟 5：安裝前端依賴

```bash
cd frontend

# 安裝 pnpm（若尚未安裝）
npm install -g pnpm

# 安裝前端套件
pnpm install
```

### 步驟 6：下載並放置視覺辨識模型權重

視覺模型需要三個預訓練權重檔案，**請先從 Google Drive 下載**：

> **模型下載連結（Google Drive）**：[Toung-Ai-Agent - Google 雲端硬碟](https://drive.google.com/drive/folders/1bIMiFUssL13KKdULAbF83bLgieuv6QLq?usp=sharing)

下載後，將三個檔案放置到以下**精確路徑**：

```
tongue-ai-agent/
└── backend/
    └── vision_predict/            ← 模型權重放這裡
        ├── swim_trasnformer_384.pth       # 舌體分割模型（Swin Transformer）
        ├── Simple_convnext_base_fold3.pth # 舌象特徵分類模型（ConvNeXt）
        └── best.pt                        # 舌頭偵測模型（YOLOv8）
```

**放置完成後，目錄結構確認方式：**

```bash
# 在專案根目錄執行，應看到三個檔案
ls backend/vision_predict/*.pth backend/vision_predict/*.pt
# 預期輸出：
# backend/vision_predict/Simple_convnext_base_fold3.pth
# backend/vision_predict/swim_trasnformer_384.pth
# backend/vision_predict/best.pt
```

> **注意事項：**
>
> - 三個檔案缺一不可，否則後端啟動時會顯示 `vision_predict 模組不可用`
> - 檔名必須完全一致（含大小寫），不可重新命名
> - 檔案應放在 `backend/vision_predict/` 目錄**下一層**，不需要建立子資料夾

### 步驟 7：（可選）調整設定

後端設定位於 `backend/config/settings.py`，可依需求修改：

```python
# LLM 設定
model_name: str = "qwen3:8b"             # 使用的 Ollama 模型
ollama_base_url: str = "http://localhost:11434"
llm_temperature: float = 0.7             # 生成溫度（0=確定性，1=創意性）

# 資料庫設定
memory_db_host: str = "localhost"
memory_db_port: int = 5432
memory_db_name: str = "tongue_ai_memory"
memory_db_user: str = "postgres"
memory_db_password: str = "postgres"
```

---

## 啟動專案

每次使用都需要依序啟動三個服務：

### 終端機 1：啟動 Ollama

```bash
ollama serve
# 服務將在 http://localhost:11434 執行
```

### 終端機 2：啟動後端（FastAPI）

```bash
cd backend

# 使用 uv
uv run python main.py

# 或使用 uvicorn
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

看到以下輸出表示後端啟動成功：

```
INFO: Started server process
INFO: Waiting for application startup.
INFO: 初始化 Vision Predict Loader...
INFO: Vision Predict 模組載入成功
INFO: 初始化 LangGraph Agents...
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8000
```

### 終端機 3：啟動前端（Electron）

```bash
cd frontend
pnpm run dev
# Vite 開發伺服器：http://localhost:5173
# Electron 視窗將自動開啟
```

---

## 整體架構概覽

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Electron 桌面應用                             │
│  ┌────────────────┐    IPC Bridge    ┌──────────────────────────┐   │
│  │  React UI      │ ◄──────────────► │  Electron Main Process   │   │
│  │  (Renderer)    │                  │  (Node.js / IPC Handlers)│   │
│  └────────────────┘                  └──────────────────────────┘   │
│          │                                        │                  │
│          │ HTTP (瀏覽器模式) / IPC (Electron 模式) │                  │
└──────────┼────────────────────────────────────────┼──────────────────┘
           │                                        │
           ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    FastAPI 後端 (port 8000)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │  /chat   │  │ /tongue  │  │  /agent  │  │    /memory       │   │
│  │  routes  │  │  routes  │  │  routes  │  │    routes        │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
│       │              │              │                  │             │
│       └──────────────┴──────────────┘                  │             │
│                       │                                │             │
│              ┌─────────▼─────────────┐                 │             │
│              │   LangGraph Agents     │                 │             │
│              │  ┌───────┐ ┌────────┐ │                 │             │
│              │  │ Chat  │ │Tongue  │ │                 │             │
│              │  │ Agent │ │Analysis│ │                 │             │
│              │  └───────┘ └────────┘ │                 │             │
│              │  ┌──────────────────┐ │                 │             │
│              │  │  Tool-Enabled    │ │                 │             │
│              │  │     Agent        │ │                 │             │
│              │  └──────────────────┘ │                 │             │
│              └──────────┬────────────┘                 │             │
│                         │                              │             │
│              ┌──────────▼─────────┐    ┌──────────────▼──────────┐  │
│              │  Ollama (LLM)      │    │  PostgreSQL              │  │
│              │  qwen3:8b          │    │  (長期記憶資料庫)         │  │
│              │  port 11434        │    │  port 5432               │  │
│              └────────────────────┘    └─────────────────────────┘  │
│                                                                      │
│              ┌────────────────────────────────────────────────────┐  │
│              │  Vision-Predict 模組                                │  │
│              │  YOLOv8 + Swin Transformer + ConvNeXt              │  │
│              └────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 前端架構詳解

### 技術棧

| 技術                 | 版本  | 用途                   |
| -------------------- | ----- | ---------------------- |
| Electron             | 39.x  | 桌面應用容器、相機存取 |
| React                | 19.x  | UI 元件框架            |
| TypeScript           | 5.9.x | 靜態型別               |
| Vite (rolldown-vite) | 7.x   | 建置工具               |
| Tailwind CSS         | 4.x   | 樣式框架               |
| Recharts             | 3.x   | 健康週報雷達圖         |
| react-markdown       | 10.x  | Markdown 渲染 AI 回覆  |

### 目錄結構

```
frontend/src/
├── electron/
│   ├── main.ts          # Electron 主程序（IPC 處理、視窗管理）
│   └── preload.ts       # 預載腳本（安全橋接主程序與渲染程序）
├── ui/
│   ├── App.tsx          # 根元件（~99 行，純組合器）
│   ├── main.tsx         # React 進入點
│   └── components/
│       ├── ChatInput.tsx           # 輸入框 + 相機按鈕 + 發送按鈕
│       ├── ImagePreview.tsx        # 圖片預覽 + 移除按鈕
│       ├── chat-message/           # 聊天訊息氣泡元件
│       ├── camera-modal/           # 相機即時偵測 Modal
│       └── weekly-report-modal.tsx # 健康週報圖表 Modal
├── hooks/
│   └── useChatSession.ts  # 會話狀態 Hook（聊天紀錄、isLoading、handleSubmit）
├── api/
│   ├── api.ts             # 所有 HTTP API 函式
│   └── stream-utils.ts    # SSE 串流解析工具
├── config/
│   └── api-config.ts      # API Base URL + 端點常數
└── types/
    └── electron.d.ts      # Electron API TypeScript 型別定義
```

### Electron 雙程序架構

Electron 分為兩個程序，透過 IPC（程序間通訊）溝通：

```
Renderer Process (React)          Main Process (Node.js)
─────────────────────────         ────────────────────────────────
App.tsx                           main.ts
  └─ useChatSession               ipcMain.handle("rag-chat-stream")
       └─ makeStreamRequest   ───►   └─ fetch("http://localhost:8000/chat/stream")
            └─ onChunk        ◄───       └─ 逐塊讀取 SSE 回傳
```

**Preload 腳本的角色**：

為了安全性，Electron 開啟了 `contextIsolation` 並關閉 `nodeIntegration`。Preload 腳本（`preload.ts`）是唯一可以同時存取 Node.js API 與 DOM 的橋樑，它透過 `contextBridge.exposeInMainWorld` 將受控 API 暴露給 React：

```typescript
// preload.ts
contextBridge.exposeInMainWorld("electronAPI", {
  sendChatMessageStream: (
    prompt,
    userId,
    sessionId,
    onChunk,
    onComplete,
    onError,
  ) =>
    ipcRenderer.invoke(
      "rag-chat-stream",
      { prompt, user_id: userId, session_id: sessionId },
      onChunk,
      onComplete,
      onError,
    ),
  // ...其他方法
});
```

### 狀態管理（useChatSession Hook）

所有聊天狀態集中在 `useChatSession.ts`：

```
useChatSession
├── userId      ← 從 localStorage 讀取或生成，跨 session 持久化
├── sessionId   ← 每次啟動應用程式生成新的 ID
├── chatLog     ← ChatEntry[] 陣列（含 user/message/imageUrl/toolStatus）
├── isLoading   ← 是否正在等待 AI 回覆
└── handleSubmit(userMessage, imageUrl)
      ├── 有圖片 → predictAndAnalyzeTongueImage()（視覺分析 + LLM 分析）
      └── 純文字 → makeStreamRequest()（一般聊天）
```

### SSE 串流處理（stream-utils.ts）

所有與後端的串流通訊都透過統一的 `parseSSEStream` 函式處理：

```typescript
// 後端傳送的 SSE 格式
data: {"type": "status", "message": "正在進行圖片分析..."}\n\n
data: {"type": "content", "content": "根據您的舌象..."}\n\n
data: [DONE]\n\n

// parseSSEStream 的 callback 對應
onStatus(message)   ← type === "status"（顯示工具狀態提示）
onChunk(content)    ← type === "content"（累加顯示 AI 文字）
onComplete()        ← 收到 [DONE]
onError(error)      ← json.error 或連線失敗
```

---

## 後端架構詳解

### 技術棧

| 技術             | 版本   | 用途                        |
| ---------------- | ------ | --------------------------- |
| FastAPI          | 0.121+ | API 框架                    |
| LangGraph        | 1.0+   | Agent 工作流程圖            |
| LangChain        | 1.0+   | LLM 工具鏈                  |
| langchain-ollama | 1.0+   | Ollama 整合                 |
| SQLAlchemy       | 2.0+   | ORM（PostgreSQL）           |
| psycopg2         | 2.9+   | PostgreSQL 驅動             |
| PyTorch          | 2.0+   | 視覺模型推理                |
| Ultralytics      | 8.4+   | YOLOv8 舌頭偵測             |
| timm             | 0.9+   | Swin Transformer / ConvNeXt |

### 目錄結構

```
backend/
├── main.py                    # FastAPI 應用進入點（lifespan、路由掛載）
├── routes.py                  # 所有 API 路由處理器
├── realtime_router.py         # 即時幀分析路由
├── tools.py                   # LangGraph 工具定義
├── database.py                # SQLAlchemy 資料庫連線設定
├── agents/
│   ├── agent.py               # LangGraph Agent 定義（3 種模式）
│   └── message_helpers.py     # 系統訊息建構（含記憶上下文）
├── config/
│   ├── settings.py            # 全域設定（Ollama URL、DB、模型路徑）
│   ├── prompts.py             # 各 Agent 模式的系統提示詞
│   ├── models.py              # SQLAlchemy ORM 資料模型
│   └── scoring.py             # 舌象症狀 → 體質向度評分表
└── utils/
    ├── memory_manager.py      # 長短期記憶管理
    ├── agent_helpers.py       # Agent 狀態建構工具函式
    ├── vision_loader.py       # 視覺模型載入器（包裝器）
    ├── streaming.py           # SSE 串流工具
    ├── file_handler.py        # 檔案上傳處理
    └── error_handler.py       # 錯誤處理
```

### FastAPI 應用初始化（main.py）

應用程式使用 `lifespan` 上下文管理器在啟動時初始化所有資源：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. 載入視覺模型
    vision_loader = VisionPredictLoader(settings.vision_predict_path)

    # 2. 建立三個 LangGraph Agent
    agents = {
        "chat":   create_unified_agent(AgentMode.CHAT),
        "tongue": create_unified_agent(AgentMode.TONGUE_ANALYSIS),
        "tool":   create_unified_agent(AgentMode.TOOL_ENABLED),
    }

    # 3. 注入到路由
    set_agents(agents)
    set_vision_loader(vision_loader)

    yield  # 應用程式運行中
    # 關閉時的清理工作

# 路由掛載
app.include_router(chat_router,   prefix="/chat")
app.include_router(tongue_router, prefix="/tongue")
app.include_router(agent_router,  prefix="/agent")
app.include_router(memory_router, prefix="/memory")
app.include_router(realtime_router)
```

### 視覺辨識模型流程

舌診圖片分析使用三階段的電腦視覺管道：

```
原始圖片
    │
    ▼
YOLOv8 (best.pt)           ← 偵測並裁切舌體區域
    │
    ▼
Swin Transformer (384.pth)  ← 舌體分割（去除背景）
    │
    ▼
ConvNeXt (fold3.pth)        ← 多標籤分類 → 輸出舌象特徵

輸出格式：
{
  "positive": [
    {"english": "TonguePale", "chinese": "舌淡白"},
    {"english": "FurThick",   "chinese": "苔厚"}
  ],
  "negative": [...],
  "summary": {"positive_count": 2, "negative_count": 18}
}
```

---

## AI 串接機制詳解

### LangGraph Agent 架構

系統定義了三種 Agent 模式，各自有不同的計算圖（StateGraph）：

#### 模式一：CHAT（一般對話）

```
Entry ──► chat_node ──► END

chat_node 執行流程：
1. 檢查是否已有 SystemMessage（避免重複注入）
2. 若無，呼叫 build_system_message(base_prompt, memory_context)
3. LLM 推理（Ollama / qwen3:8b）
4. 回傳 AIMessage，LangGraph 自動透過 MemorySaver 記住對話
```

#### 模式二：TONGUE_ANALYSIS（舌診分析）

```
Entry ──► analyze_tongue_node ──► END

analyze_tongue_node 執行流程：
1. 從 state 讀取 prediction_results（視覺模型輸出）
2. 呼叫 PromptTemplates.build_analysis_prompt() 組合分析提示
3. LLM 推理，生成中醫體質分析與建議
4. 儲存 final_response 並回傳
```

#### 模式三：TOOL_ENABLED（帶工具的 Agent）

```
Entry ──► agent_node ──► should_continue?
                              │
                    ┌─────────┴─────────┐
                  "tools"             "end"
                    │                   │
              tool_node              END
                    │
                    └──► agent_node（再次推理）
```

`predict_tongue_image_tool` 工具讓 LLM 能主動呼叫視覺模型分析圖片，實現「LLM 決策 → 工具執行 → LLM 整合結果」的閉環。

### Ollama 本地 LLM 串接

```python
# agents/agent.py
from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="qwen3:8b",                    # 模型名稱
    base_url="http://localhost:11434",   # Ollama 服務位址
    temperature=0.7                      # 回覆多樣性
)

# 串流推理（routes.py）
async for event in agent.astream_events(state, config, version="v2"):
    if event["event"] == "on_chat_model_stream":
        chunk = event["data"]["chunk"]
        if chunk.content:
            yield f"data: {json.dumps({'type': 'content', 'content': chunk.content})}\n\n"
```

LangGraph 的 `astream_events` 讓每個 token 生成後立即透過 SSE 傳送給前端，實現打字機效果。

### 記憶上下文注入

每次對話開始時，系統會從 PostgreSQL 讀取用戶歷史記憶並注入到系統提示詞：

```python
# routes.py（以 chat_stream 為例）
memory_context = memory_manager.get_user_context(user_id)  # 查詢歷史

initial_state = build_initial_state(
    messages=[HumanMessage(content=prompt)],
    memory_context=memory_context,  # 帶入狀態
)

# agents/message_helpers.py
def build_system_message(base_prompt, memory_context=None) -> SystemMessage:
    content = base_prompt
    if memory_context:
        content += (
            "\n\n===== 以下是關於用戶的歷史資料 =====\n"
            f"{memory_context}\n"
            "===== 用戶資料結束 ====="
        )
    return SystemMessage(content=content)
```

### LangGraph Checkpointer（短期記憶）

LangGraph 使用 `MemorySaver` 作為 checkpointer，以 `thread_id`（= session_id）為鍵儲存完整的對話狀態。這使得 LLM 在同一個 session 中能記住之前的對話內容，而不需要前端每次都重傳歷史訊息：

```python
# agents/agent.py
memory_manager = get_memory_manager()
checkpointer = memory_manager.get_checkpointer()  # MemorySaver()
return workflow.compile(checkpointer=checkpointer)

# 使用時：每個 session 有獨立的 thread
config = {"configurable": {"thread_id": session_id}}
result = await agent.ainvoke(state, config)
```

### 系統提示詞設計

三種 Agent 各有獨立的系統提示詞（定義在 `config/prompts.py`）：

| Agent                  | 提示詞重點                                                  |
| ---------------------- | ----------------------------------------------------------- |
| CHAT_SYSTEM            | 中醫健康助手角色、只回答中醫相關問題、專業友善語氣          |
| TONGUE_ANALYSIS_SYSTEM | 舌診專家角色、分析流程（推理過程 + 健康建議）、使用中醫術語 |
| TOOL_AGENT_SYSTEM      | 可使用工具的助手、說明 predict_tongue_image_tool 的用途     |

---

## 資料流程圖

### 流程一：純文字聊天

```
用戶輸入文字
     │
     ▼ (useChatSession.handleSubmit)
makeStreamRequest() ──HTTP POST──► /chat/stream
                                       │
                               routes.py 讀取 session 狀態
                               若是新 session，查詢長期記憶
                                       │
                               build_initial_state()
                                       │
                               LangGraph chat_node
                                 ├─ 注入系統提示 + 記憶上下文
                                 └─ ChatOllama 推理（streaming）
                                       │
                               SSE: data: {"type":"content","content":"..."}
                                       │
     ◄─────────────────── parseSSEStream → onChunk → updateLastMessage

用戶看到 AI 即時打字回覆
```

### 流程二：舌頭圖片分析

```
用戶上傳/拍攝舌頭照片
     │
     ▼
predictAndAnalyzeTongueImage()
     │ HTTP POST multipart/form-data
     ▼
/tongue/predict-and-analyze/stream
     │
     ├─► SSE: {"type":"status","message":"正在進行圖片分析..."}
     │        → 前端顯示「分析中」狀態
     │
     ├─► Vision Pipeline:
     │     YOLOv8 偵測舌體
     │       └─ Swin Transformer 分割
     │              └─ ConvNeXt 多標籤分類
     │
     ├─► SSE: {"type":"status","message":"預測完成，正在進行 AI 分析..."}
     │
     ├─► LangGraph TONGUE_ANALYSIS Agent:
     │     analyze_tongue_node
     │       ├─ 組合舌象特徵 → 中醫分析提示
     │       └─ ChatOllama 推理（streaming）
     │
     ├─► SSE: {"type":"content","content":"根據您的舌象分析..."} × N
     │        → 前端逐字顯示 AI 分析
     │
     ├─► 儲存分析記錄到 PostgreSQL
     │
     └─► SSE: [DONE] → onComplete() → isLoading = false
```

### 流程三：即時相機偵測

```
CameraModal 開啟相機
     │
     ▼ (每隔數幀)
analyzeRealtimeFrame(imageBlob)
     │ HTTP POST multipart/form-data
     ▼
/realtime/analyze-frame
     │
     └─► YOLOv8 快速推理（不呼叫 LLM）
           └─ 回傳偵測框座標 + 舌體狀態

前端在 Canvas 上繪製偵測框
```

---

## API 端點一覽

### Chat 路由（`/chat`）

| 方法 | 路徑           | 說明               | 請求格式 | 回應格式 |
| ---- | -------------- | ------------------ | -------- | -------- |
| POST | `/chat`        | 一般聊天（非串流） | JSON     | JSON     |
| POST | `/chat/stream` | 串流聊天           | JSON     | SSE      |

```json
// 請求體
{
  "prompt": "我的舌苔偏黃，是什麼體質？",
  "user_id": "user_xxx",
  "session_id": "session_yyy"
}
```

### Tongue 路由（`/tongue`）

| 方法 | 路徑                                 | 說明                    | 請求格式  | 回應格式 |
| ---- | ------------------------------------ | ----------------------- | --------- | -------- |
| POST | `/tongue/analyze`                    | 分析預測結果（非串流）  | JSON      | JSON     |
| POST | `/tongue/analyze/stream`             | 串流舌診分析            | JSON      | SSE      |
| POST | `/tongue/predict`                    | 圖片視覺預測（僅辨識）  | multipart | JSON     |
| POST | `/tongue/predict-and-analyze/stream` | 完整流程（辨識 + 分析） | multipart | SSE      |

### Agent 路由（`/agent`）

| 方法 | 路徑                 | 說明                             | 請求格式  | 回應格式 |
| ---- | -------------------- | -------------------------------- | --------- | -------- |
| POST | `/agent/chat/stream` | 帶工具的 Agent（可主動分析圖片） | multipart | SSE      |

### Memory 路由（`/memory`）

| 方法 | 路徑                               | 說明                       |
| ---- | ---------------------------------- | -------------------------- |
| POST | `/memory/save`                     | 儲存長期記憶               |
| POST | `/memory/preference`               | 儲存用戶偏好               |
| GET  | `/memory/preference/{user_id}`     | 取得用戶偏好               |
| POST | `/memory/search`                   | 搜尋記憶                   |
| GET  | `/memory/context/{user_id}`        | 取得記憶上下文             |
| GET  | `/memory/tongue/history/{user_id}` | 取得舌診歷史（含日期篩選） |
| GET  | `/memory/tongue/stats/{user_id}`   | 取得舌診統計（用於雷達圖） |

### Realtime 路由

| 方法 | 路徑                      | 說明       | 請求格式  | 回應格式 |
| ---- | ------------------------- | ---------- | --------- | -------- |
| POST | `/realtime/analyze-frame` | 即時幀分析 | multipart | JSON     |

---

## 記憶系統說明

### 短期記憶（Session 內）

由 LangGraph `MemorySaver` 管理，以 `session_id` 作為 `thread_id`。在同一個 session 中，Agent 能記住完整的對話歷史，不需要前端重傳。應用程式重啟後，短期記憶會消失。

### 長期記憶（跨 Session）

儲存在 PostgreSQL 中，分為四張資料表：

| 資料表                    | 說明                              |
| ------------------------- | --------------------------------- |
| `user_memory`             | 用戶基本資料與偏好設定            |
| `tongue_analysis_records` | 每次舌診的預測結果 + LLM 分析全文 |
| `memory_records`          | 一般記憶條目（帶重要性分數）      |
| `session_summaries`       | 每個 session 的摘要               |

每次開始新對話時，後端會從資料庫查詢用戶的歷史記憶摘要，並附加到系統提示詞中，讓 LLM 能「記得」用戶的健康狀況歷史。

### 體質評分系統（健康週報）

系統將舌象辨識結果對應到 6 個中醫體質向度，生成雷達圖：

| 向度 | 範例觸發症狀                              |
| ---- | ----------------------------------------- |
| 氣虛 | TonguePale（舌淡白）、FurWhite（苔白）    |
| 血虛 | TonguePale、TongueSmall（舌小）           |
| 陰虛 | TonguePeeled（剝苔）、TongueRed（舌紅）   |
| 陽虛 | TongueSwollen（舌胖大）、FurMoist（苔潤） |
| 濕熱 | FurYellow（苔黃）、FurGreasy（苔膩）      |
| 血瘀 | Ecchymosis（瘀斑）、TonguePurple（舌紫）  |

---

## 常見問題排查

### Q: Electron 視窗開啟但顯示空白

確認 Vite 開發伺服器已在 `http://localhost:5173` 啟動，並且 Electron 可以連線到該位址。

### Q: 發送訊息後沒有回應

1. 確認 FastAPI 後端正在 `http://localhost:8000` 運行
2. 確認 Ollama 服務正在運行（`ollama serve`）
3. 確認已下載 `qwen3:8b` 模型（`ollama list`）
4. 查看後端終端機是否有錯誤訊息

### Q: 資料庫連線失敗

確認 PostgreSQL 正在運行，且資料庫 `tongue_ai_memory` 已建立。後端 console 會顯示具體的連線錯誤訊息。

### Q: 記憶功能沒有作用

若 PostgreSQL 無法連線，系統會降級為無記憶模式繼續運作，但不會儲存歷史資料。查看後端 logs 中是否有 `WARNING: 記憶資料庫連線失敗` 的訊息。

---

## 建置與打包

前端支援打包為各平台桌面應用：

```bash
cd frontend

# macOS（ARM64 / Apple Silicon）
pnpm run dist:mac

# Windows（x64）
pnpm run dist:win

# Linux（ARMv7l）
pnpm run dist:linux
```

打包完成的安裝程式會輸出到 `frontend/dist/` 目錄。

> **注意**：打包後的應用程式仍需要在同一台機器上運行 FastAPI 後端與 Ollama 服務。
