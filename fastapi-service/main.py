import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Body, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging
import os
import shutil
import tempfile

# 靜音不明 WebSocket 連線的 403 log（來自外部工具/擴充套件，如 Open WebUI）
class _SuppressWSFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not ("/ws" in msg and ("403" in msg or "connection rejected" in msg or "connection closed" in msg))

logging.getLogger("uvicorn.access").addFilter(_SuppressWSFilter())
logging.getLogger("uvicorn.error").addFilter(_SuppressWSFilter())

from database import get_db, engine
from config.models import Base, DiagnosisRecord
from config.scoring import TongueHealthScorer
from config.settings import settings
from tools import predict_tongue_image_tool, get_weekly_report_tool

# New imports for Agents and Routing
from agents import create_unified_agent, AgentMode
from utils.memory_manager import get_memory_manager
from utils.vision_loader import VisionPredictLoader
from routes import (
    chat_router,
    tongue_router,
    agent_router,
    memory_router,
    set_agents,
    set_vision_loader,
    transcribe_audio_file,
)

# 初始化資料庫 (建立 Table)
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Agents and Vision Loader
    print("Initializing components...")
    
    try:
        # 1. Vision Loader
        vision_loader = VisionPredictLoader(settings.vision_predict_path)
        set_vision_loader(vision_loader)
        
        # 2. Agents
        # Initialize agents for different modes
        agents = {
            "chat": create_unified_agent(AgentMode.CHAT),
            "tongue": create_unified_agent(AgentMode.TONGUE_ANALYSIS),
            "tool": create_unified_agent(AgentMode.TOOL_ENABLED)
        }
        set_agents(agents)
        
        print("Components initialized successfully.")
        if getattr(settings, "use_google_speech", False) and (
            getattr(settings, "google_speech_api_key", None) or os.environ.get("GOOGLE_SPEECH_API_KEY")
        ):
            print("語音辨識：Google Speech-to-Text")
        else:
            print("語音辨識：請在 .env 設定 USE_GOOGLE_SPEECH=true 與 GOOGLE_SPEECH_API_KEY")
    except Exception as e:
        print(f"Error initializing components: {e}")
        # We don't raise here to allow the server to start even if some components fail,
        # but in production, you might want to fail hard.
    
    yield
    
    # Shutdown logic
    print("Shutting down...")

app = FastAPI(title="Tongue AI Agent API", lifespan=lifespan, redirect_slashes=False)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers from routes.py
app.include_router(chat_router, prefix="/chat", tags=["Chat"])
app.include_router(tongue_router, prefix="/tongue", tags=["Tongue Analysis"])
app.include_router(agent_router, prefix="/agent", tags=["Agent"])
app.include_router(memory_router, prefix="/memory", tags=["Memory"])

@app.post("/transcribe", tags=["Transcribe"])
async def transcribe_audio_endpoint(file: UploadFile = File(...)):
    """語音轉文字（Google Speech-to-Text）"""
    try:
        suffix = os.path.splitext(file.filename or "audio.webm")[1] or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        try:
            text = await transcribe_audio_file(tmp_path)
            return {"text": text}
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"語音轉文字失敗: {str(e)}")

# ==================== Existing Simple Endpoints ====================

class ChatRequest(BaseModel):
    user_id: str
    message: str
    image_path: Optional[str] = None

class AdviceRequest(BaseModel):
    user_id: str

@app.post("/api/chat")
def chat_endpoint(req: ChatRequest, db: Session = Depends(get_db)):
    """
    Agent 對話接口 (Simple Version)
    這裡簡化了 ReAct 迴圈，直接根據輸入判斷調用哪個工具
    """
    # 情況 A: 用戶上傳圖片 -> 強制診斷
    if req.image_path:
        tool_result = predict_tongue_image_tool(db, req.user_id, req.image_path)
        # TODO: 將 tool_result 餵給 LLM 生成完整建議
        return {
            "reply": f"收到您的圖片。分析結果顯示有：{', '.join(tool_result['symptoms'])}。\n這筆紀錄已保存。",
            "action_taken": "predict_tongue_image"
        }
    
    # 情況 B: 用戶詢問週報 -> 調用週報工具
    if "週報" in req.message or "趨勢" in req.message:
        summary = get_weekly_report_tool(db, req.user_id)
        # TODO: 將 summary 餵給 LLM 生成詳細週報 (使用 build_weekly_report_prompt)
        return {
            "reply": f"以下是您的健康週報摘要：\n{summary}\n\n(詳細雷達圖請參考下方圖表)",
            "action_taken": "get_weekly_report"
        }
        
    # 情況 C: 一般閒聊
    return {"reply": "我是您的中醫助手，請問今天想了解什麼？"}

@app.get("/api/reports/weekly")
def get_weekly_chart_data(user_id: str):
    """
    [前端專用] 獲取雷達圖所需的 JSON 數據
    前端會呼叫這個 API 來繪製圖表 (使用 Agent 的長期記憶)
    """
    try:
        memory_manager = get_memory_manager()
        
        # 獲取過去 30 天的數據 (給予前端更多彈性)
        records = memory_manager.long_term.get_tongue_analysis_history(
            user_id=user_id,
            limit=50,
            start_date=datetime.now() - timedelta(days=30)
        )
        
        if not records:
            return []
            
        # 轉換格式以適配 scoring.py
        class RecordWrapper:
            def __init__(self, data):
                self.prediction_raw = data.get("prediction_results", {})
                self.created_at = datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data["created_at"]
        
        wrapped_records = [RecordWrapper(r) for r in records]
        
        # 生成報表數據 (Scorer 會自動計算分數)
        report_data = TongueHealthScorer.generate_weekly_report_data(wrapped_records)
        return report_data["chart_data"]
        
    except Exception as e:
        print(f"Error generating weekly report: {e}")
        return []

# 修正為 Async 函數以便調用 LLM
@app.post("/api/tongue/advice")
async def get_ai_health_advice(req: AdviceRequest):
    try:
        memory_manager = get_memory_manager()
        records = memory_manager.long_term.get_tongue_analysis_history(
            user_id=req.user_id,
            limit=10,
            start_date=datetime.now() - timedelta(days=7)
        )
        
        if not records:
            return {"advice": "目前沒有足夠的舌診紀錄來生成建議，請先上傳舌頭照片進行分析。"}
            
        symptom_counts = {}
        for r in records:
            results = r.get("prediction_results", {})
            positive = results.get("positive", [])
            for p in positive:
                name = p.get("chinese", p.get("english", ""))
                if name:
                    symptom_counts[name] = symptom_counts.get(name, 0) + 1
        
        top_symptoms = sorted(symptom_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        symptom_str = ", ".join([f"{name}(出現{count}次)" for name, count in top_symptoms])
        
        prompt = f"""
        你是一位專業的中醫健康顧問。以下是用戶過去一週的舌診分析摘要：
        最常出現的症狀：{symptom_str}
        請根據這些症狀，給出 3 點具體、實用的生活與飲食調理建議。
        請用條列式回答，語氣親切專業，不要過於冗長 (約 150-200 字)。
        """
        
        from agents.agent import _get_llm
        llm = _get_llm()
        from langchain_core.messages import HumanMessage, SystemMessage
        
        messages = [
            SystemMessage(content="你是一位專業的中醫健康顧問。"),
            HumanMessage(content=prompt)
        ]
        
        response = await llm.ainvoke(messages)
        return {"advice": response.content}
        
    except Exception as e:
        print(f"Error generating advice: {e}")
        return {"advice": "抱歉，生成建議時發生錯誤。"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
