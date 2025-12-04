# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings
from config.prompts import PromptTemplates
from utils.vision_loader import VisionPredictLoader
from agents import create_unified_agent, AgentMode
from routes import chat_router, tongue_router, agent_router, memory_router
import logging

# 設定日誌
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# 初始化 FastAPI
app = FastAPI(title="舌診 AI Agent API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化 Vision-Predict
vision_loader = VisionPredictLoader(settings.vision_predict_path, verbose=True)
if not vision_loader.status.is_available:
    logger.warning(f"Vision-Predict unavailable: {vision_loader.status.error_message}")
    print("\n" + "="*60)
    print("警告: vision-predict 模組不可用")
    print("="*60)
    if vision_loader.status.error_message:
        print(f"錯誤詳情: {vision_loader.status.error_message}")
    print(f"\n請確保:")
    print(f"1. vision-predict 目錄存在於: {settings.vision_predict_path}")
    print(f"2. 已安裝所有必要的依賴項 (torch, torchvision, timm, Pillow, numpy)")
    print(f"3. 模型文件存在於 vision-predict 目錄中")
    print("="*60 + "\n")

# 初始化 Agents
agents = {
    "chat": create_unified_agent(AgentMode.CHAT),
    "tongue": create_unified_agent(AgentMode.TONGUE_ANALYSIS),
    "tool": create_unified_agent(AgentMode.TOOL_ENABLED),
}

# 設置路由依賴
from routes import set_agents, set_vision_loader
set_agents(agents)
set_vision_loader(vision_loader)

# 註冊路由
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(tongue_router, prefix="/tongue", tags=["tongue"])
app.include_router(agent_router, prefix="/agent", tags=["agent"])
app.include_router(memory_router, prefix="/memory", tags=["memory"])

@app.get("/")
async def root():
    return {
        "message": "舌診 AI Agent API 運行中",
        "model": settings.model_name,
        "framework": "LangGraph",
        "vision_predict_available": vision_loader.status.is_available
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "vision_predict": vision_loader.status.is_available
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port
    )
