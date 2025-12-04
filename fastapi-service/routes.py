# routes.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import json
import os
import tempfile
import shutil

from langchain_core.messages import HumanMessage

from agents import create_unified_agent, AgentMode
from utils.vision_loader import VisionPredictLoader
from utils.memory_manager import get_memory_manager
from config.settings import settings

# 創建路由器
chat_router = APIRouter()
tongue_router = APIRouter()
agent_router = APIRouter()
memory_router = APIRouter()

# 初始化 Agents（這些會在 main.py 中初始化，但這裡需要訪問）
# 我們將通過依賴注入的方式傳遞
_agents = None
_vision_loader = None


def set_agents(agents_dict: dict):
    """設置 agents 實例"""
    global _agents
    _agents = agents_dict


def set_vision_loader(loader: VisionPredictLoader):
    """設置 vision_loader 實例"""
    global _vision_loader
    _vision_loader = loader


# Pydantic 模型
class ChatRequest(BaseModel):
    prompt: str
    user_id: Optional[str] = "default"  # 用戶 ID，默認為 "default"
    session_id: Optional[str] = None  # 會話 ID，如果不提供則自動生成


class TongueAnalysisRequest(BaseModel):
    prediction_results: Dict[str, Any]  # 預測模型的結果
    additional_info: Optional[str] = None  # 額外的患者信息或症狀描述
    user_id: Optional[str] = "default"  # 用戶 ID（用於記錄）
    session_id: Optional[str] = None  # 會話 ID（可選）


class ChatResponse(BaseModel):
    response: str


# ==================== Chat 路由 ====================

@chat_router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """一般聊天接口 - 使用 LangGraph Agent（支持記憶功能）"""
    try:
        chat_agent = _agents["chat"]
        memory_manager = get_memory_manager()
        
        # 生成會話 ID（如果未提供）
        session_id = request.session_id or f"chat-{id(request)}"
        user_id = request.user_id or "default"
        
        # 獲取用戶的長期記憶上下文（只在第一次會話時需要）
        config = {"configurable": {"thread_id": session_id}}
        
        # 檢查是否已有會話狀態
        try:
            current_state = await chat_agent.aget_state(config)
            is_new_session = current_state.values == {} or not current_state.values.get("messages")
        except:
            is_new_session = True
        
        # 只在新會話時獲取長期記憶上下文（避免每次都查詢數據庫）
        memory_context = None
        if is_new_session:
            memory_context = memory_manager.get_user_context(user_id)
        
        # 構建初始狀態（只包含新消息，LangGraph 會自動合併歷史消息）
        initial_state = {
            "messages": [HumanMessage(content=request.prompt)],
            "prediction_results": None,
            "additional_info": None,
            "analysis_stage": "initial",
            "final_response": None,
            "user_id": user_id,
            "session_id": session_id,
            "memory_context": memory_context
        }
        
        # 運行 Agent（使用 session_id 作為 thread_id 以保持會話記憶）
        result = await chat_agent.ainvoke(initial_state, config)
        
        # 獲取最終回應
        response_text = result.get("final_response", "")
        if not response_text:
            # 如果沒有 final_response，從 messages 中獲取
            messages = result.get("messages", [])
            if messages:
                last_message = messages[-1]
                response_text = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        return ChatResponse(response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 處理錯誤: {str(e)}")


@chat_router.post("/stream")
async def chat_stream(request: ChatRequest):
    """流式聊天接口 - 使用 LangGraph Agent（支持記憶功能）"""
    async def generate():
        try:
            chat_agent = _agents["chat"]
            memory_manager = get_memory_manager()
            
            # 生成會話 ID（如果未提供）
            session_id = request.session_id or f"chat-stream-{id(request)}"
            user_id = request.user_id or "default"
            
            # 獲取用戶的長期記憶上下文（只在第一次會話時需要）
            config = {"configurable": {"thread_id": session_id}}
            
            # 檢查是否已有會話狀態
            try:
                current_state = await chat_agent.aget_state(config)
                is_new_session = current_state.values == {} or not current_state.values.get("messages")
            except:
                is_new_session = True
            
            # 只在新會話時獲取長期記憶上下文（避免每次都查詢數據庫）
            memory_context = None
            if is_new_session:
                memory_context = memory_manager.get_user_context(user_id)
            
            # 構建初始狀態（只包含新消息，LangGraph 會自動合併歷史消息）
            initial_state = {
                "messages": [HumanMessage(content=request.prompt)],
                "prediction_results": None,
                "additional_info": None,
                "analysis_stage": "initial",
                "final_response": None,
                "user_id": user_id,
                "session_id": session_id,
                "memory_context": memory_context
            }
            
            # 運行 Agent（流式，使用 session_id 作為 thread_id）
            # 使用 astream_events 來獲取真正的流式輸出
            async for event in chat_agent.astream_events(
                initial_state, 
                config,
                version="v2"
            ):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, 'content') and chunk.content:
                        yield f"data: {json.dumps({'content': chunk.content}, ensure_ascii=False)}\n\n"
                elif event["event"] == "on_chain_end" and event.get("name") == "chat":
                    # Agent 完成
                    break
            
            yield "data: [DONE]\n\n"
        except Exception as e:
            error_msg = json.dumps({"error": f"LLM 處理錯誤: {str(e)}"}, ensure_ascii=False)
            yield f"data: {error_msg}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


# ==================== Tongue 路由 ====================

@tongue_router.post("/analyze", response_model=ChatResponse)
async def analyze_tongue(request: TongueAnalysisRequest):
    """舌診分析接口 - 使用 LangGraph Agent（自動保存分析記錄）"""
    try:
        tongue_agent = _agents["tongue"]
        memory_manager = get_memory_manager()
        
        user_id = request.user_id or "default"
        session_id = request.session_id or f"tongue-{id(request)}"
        
        # 構建初始狀態
        initial_state = {
            "messages": [],
            "prediction_results": request.prediction_results,
            "additional_info": request.additional_info,
            "analysis_stage": "initial",
            "final_response": None
        }
        
        # 運行 Agent
        config = {"configurable": {"thread_id": session_id}}
        result = await tongue_agent.ainvoke(initial_state, config)
        
        # 獲取最終回應
        response_text = result.get("final_response", "")
        if not response_text:
            # 如果沒有 final_response，從 messages 中獲取
            messages = result.get("messages", [])
            if messages:
                last_message = messages[-1]
                response_text = last_message.content if hasattr(last_message, 'content') else str(last_message)
        
        # 自動保存分析記錄到數據庫
        try:
            memory_manager.long_term.save_tongue_analysis(
                user_id=user_id,
                session_id=session_id,
                prediction_results=request.prediction_results,
                analysis_response=response_text,
                additional_info=request.additional_info
            )
        except Exception as e:
            # 記錄錯誤但不影響響應
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"保存舌診分析記錄失敗: {str(e)}")
        
        return ChatResponse(response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"舌診分析錯誤: {str(e)}")


@tongue_router.post("/analyze/stream")
async def analyze_tongue_stream(request: TongueAnalysisRequest):
    """流式舌診分析接口 - 使用 LangGraph Agent"""
    async def generate():
        try:
            tongue_agent = _agents["tongue"]
            
            # 構建初始狀態
            initial_state = {
                "messages": [],
                "prediction_results": request.prediction_results,
                "additional_info": request.additional_info,
                "analysis_stage": "initial",
                "final_response": None
            }
            
            # 運行 Agent（流式）
            config = {"configurable": {"thread_id": f"tongue-stream-{id(request)}"}}
            
            # 使用 astream_events 來獲取真正的流式輸出
            async for event in tongue_agent.astream_events(
                initial_state, 
                config,
                version="v2"
            ):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, 'content') and chunk.content:
                        yield f"data: {json.dumps({'content': chunk.content}, ensure_ascii=False)}\n\n"
                elif event["event"] == "on_chain_end" and event.get("name") == "analyze":
                    # Agent 完成
                    break
            
            yield "data: [DONE]\n\n"
        except Exception as e:
            error_msg = json.dumps({"error": f"舌診分析錯誤: {str(e)}"}, ensure_ascii=False)
            yield f"data: {error_msg}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@tongue_router.post("/predict")
async def predict_tongue_image(
    file: UploadFile = File(...),
    additional_info: Optional[str] = Form(None)
):
    """舌診圖片預測接口 - 調用 vision-predict 進行預測，返回 JSON 結果"""
    if _vision_loader is None or not _vision_loader.status.is_available:
        error_detail = _vision_loader.status.error_message if _vision_loader else "vision-predict 模組未初始化"
        raise HTTPException(
            status_code=503, 
            detail=f"vision-predict 模組不可用: {error_detail}. 請確保 vision-predict 目錄存在於 {settings.vision_predict_path} 且已安裝所有依賴項。"
        )
    
    try:
        # 創建臨時文件保存上傳的圖片
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            tmp_path = tmp_file.name
        
        try:
            # 創建臨時輸出目錄
            with tempfile.TemporaryDirectory() as tmp_output_dir:
                # 調用 vision-predict 進行分析
                if _vision_loader.status.analyze_function is None:
                    raise HTTPException(status_code=503, detail="vision-predict 分析函數不可用")
                
                results = _vision_loader.status.analyze_function(
                    image_path=tmp_path,
                    output_format="structured",
                    output_dir=tmp_output_dir
                )
                
                if results is None:
                    raise HTTPException(status_code=500, detail="圖片預測失敗，請檢查圖片格式和內容")
                
                return {
                    "success": True,
                    "prediction_results": results,
                    "additional_info": additional_info
                }
        finally:
            # 清理臨時文件
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"預測過程發生錯誤: {str(e)}")


@tongue_router.post("/predict-and-analyze/stream")
async def predict_and_analyze_tongue_stream(
    file: UploadFile = File(...),
    additional_info: Optional[str] = Form(None),
    user_id: Optional[str] = Form("default"),
    session_id: Optional[str] = Form(None)
):
    """完整的舌診分析流程：預測 + LLM 分析（流式）"""
    async def generate():
        try:
            # 步驟 1: 進行圖片預測
            yield f"data: {json.dumps({'type': 'status', 'message': '正在進行圖片分析...'}, ensure_ascii=False)}\n\n"
            
            if _vision_loader is None or not _vision_loader.status.is_available:
                error_detail = _vision_loader.status.error_message if _vision_loader else "vision-predict 模組未初始化"
                error_msg = json.dumps({
                    "error": f"vision-predict 模組不可用: {error_detail}",
                    "details": {
                        "vision_predict_path": str(settings.vision_predict_path),
                        "path_exists": settings.vision_predict_path.exists(),
                    }
                }, ensure_ascii=False)
                yield f"data: {error_msg}\n\n"
                return
            
            # 創建臨時文件保存上傳的圖片
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
                shutil.copyfileobj(file.file, tmp_file)
                tmp_path = tmp_file.name
            
            try:
                # 創建臨時輸出目錄
                with tempfile.TemporaryDirectory() as tmp_output_dir:
                    # 調用 vision-predict 進行分析
                    if _vision_loader.status.analyze_function is None:
                        error_msg = json.dumps({
                            "error": "vision-predict 分析函數不可用"
                        }, ensure_ascii=False)
                        yield f"data: {error_msg}\n\n"
                        return
                    
                    prediction_results = _vision_loader.status.analyze_function(
                        image_path=tmp_path,
                        output_format="structured",
                        output_dir=tmp_output_dir
                    )
                    
                    if prediction_results is None:
                        error_msg = json.dumps({
                            "error": "圖片預測失敗，請檢查圖片格式和內容"
                        }, ensure_ascii=False)
                        yield f"data: {error_msg}\n\n"
                        return
                    
                    yield f"data: {json.dumps({'type': 'status', 'message': '預測完成，正在進行 AI 分析...'}, ensure_ascii=False)}\n\n"
                    
                    # 步驟 2: 將預測結果傳給 LLM 分析
                    tongue_agent = _agents["tongue"]
                    memory_manager = get_memory_manager()
                    
                    session_id_value = session_id or f"tongue-predict-stream-{id(file)}"
                    user_id_value = user_id or "default"
                    
                    initial_state = {
                        "messages": [],
                        "prediction_results": prediction_results,
                        "additional_info": additional_info,
                        "analysis_stage": "initial",
                        "final_response": None
                    }
                    
                    # 運行 Agent（流式）
                    config = {"configurable": {"thread_id": session_id_value}}
                    
                    # 收集完整的分析回應
                    full_response = ""
                    
                    # 使用 astream_events 來獲取真正的流式輸出
                    async for event in tongue_agent.astream_events(
                        initial_state, 
                        config,
                        version="v2"
                    ):
                        if event["event"] == "on_chat_model_stream":
                            chunk = event["data"]["chunk"]
                            if hasattr(chunk, 'content') and chunk.content:
                                full_response += chunk.content
                                yield f"data: {json.dumps({'type': 'content', 'content': chunk.content}, ensure_ascii=False)}\n\n"
                        elif event["event"] == "on_chain_end" and event.get("name") == "analyze":
                            # Agent 完成，保存分析記錄
                            try:
                                memory_manager.long_term.save_tongue_analysis(
                                    user_id=user_id_value,
                                    session_id=session_id_value,
                                    prediction_results=prediction_results,
                                    analysis_response=full_response,
                                    additional_info=additional_info
                                )
                            except Exception as e:
                                import logging
                                logger = logging.getLogger(__name__)
                                logger.warning(f"保存舌診分析記錄失敗: {str(e)}")
                            break
                    
                    yield "data: [DONE]\n\n"
            finally:
                # 清理臨時文件
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except Exception as e:
            error_msg = json.dumps({
                "error": f"處理過程發生錯誤: {str(e)}"
            }, ensure_ascii=False)
            yield f"data: {error_msg}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


# ==================== Agent 路由 ====================

@agent_router.post("/chat/stream")
async def agent_chat_stream(
    file: Optional[UploadFile] = File(None),
    prompt: Optional[str] = Form(None),
    user_id: Optional[str] = Form("default"),
    session_id: Optional[str] = Form(None)
):
    """帶工具的 Agent 聊天接口（流式）- Agent 可以自動調用 vision-predict 工具（支持記憶功能）"""
    async def generate():
        image_path = None
        try:
            tool_agent = _agents["tool"]
            memory_manager = get_memory_manager()
            
            # 生成會話 ID（如果未提供）
            session_id_value = session_id or f"agent-chat-stream-{id(file) if file else id(prompt)}"
            user_id_value = user_id or "default"
            
            # 獲取用戶的長期記憶上下文
            memory_context = memory_manager.get_user_context(user_id_value)
            
            # 保存圖片到臨時文件（如果有的話）
            if file:
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
                    shutil.copyfileobj(file.file, tmp_file)
                    image_path = tmp_file.name
            
            # 構建初始消息
            messages = []
            
            if image_path:
                # 如果有圖片，告訴 agent 圖片路徑
                user_message = f"{prompt or '請幫我分析這張舌診圖片'}\n\n圖片已上傳，路徑為: {image_path}"
                messages.append(HumanMessage(content=user_message))
            elif prompt:
                messages.append(HumanMessage(content=prompt))
            else:
                error_msg = json.dumps({"error": "請提供圖片或文字提示"}, ensure_ascii=False)
                yield f"data: {error_msg}\n\n"
                return
            
            # 構建初始狀態
            initial_state = {
                "messages": messages,
                "prediction_results": None,
                "additional_info": None,
                "analysis_stage": "initial",
                "final_response": None,
                "image_path": image_path,
                "user_id": user_id_value,
                "session_id": session_id_value,
                "memory_context": memory_context
            }
            
            # 運行 Agent（流式，使用 session_id 作為 thread_id）
            config = {"configurable": {"thread_id": session_id_value}}
            
            # 使用 astream_events 來獲取真正的流式輸出
            async for event in tool_agent.astream_events(
                initial_state, 
                config,
                version="v2"
            ):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, 'content') and chunk.content:
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk.content}, ensure_ascii=False)}\n\n"
                elif event["event"] == "on_tool_start":
                    # 工具開始執行
                    tool_name = event.get("name", "")
                    yield f"data: {json.dumps({'type': 'status', 'message': f'正在調用工具: {tool_name}...'}, ensure_ascii=False)}\n\n"
                elif event["event"] == "on_tool_end":
                    # 工具執行完成
                    yield f"data: {json.dumps({'type': 'status', 'message': '工具執行完成，正在分析結果...'}, ensure_ascii=False)}\n\n"
                elif event["event"] == "on_chain_end" and event.get("name") == "agent":
                    # Agent 完成
                    break
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            error_msg = json.dumps({
                "error": f"處理過程發生錯誤: {str(e)}"
            }, ensure_ascii=False)
            yield f"data: {error_msg}\n\n"
        finally:
            # 清理臨時文件
            if image_path and os.path.exists(image_path):
                try:
                    os.unlink(image_path)
                except:
                    pass
    
    return StreamingResponse(generate(), media_type="text/event-stream")


# ==================== Memory 路由 ====================

class SaveMemoryRequest(BaseModel):
    user_id: str
    memory_type: str  # 'fact', 'preference', 'history', 'medical_record'
    content: str
    metadata: Optional[Dict[str, Any]] = None
    importance_score: float = 1.0


class SavePreferenceRequest(BaseModel):
    user_id: str
    preferences: Dict[str, Any]


class SearchMemoryRequest(BaseModel):
    user_id: str
    query: Optional[str] = None
    memory_type: Optional[str] = None
    limit: int = 10
    min_importance: float = 0.0


@memory_router.post("/save")
async def save_memory(request: SaveMemoryRequest):
    """保存長期記憶"""
    try:
        memory_manager = get_memory_manager()
        memory_manager.long_term.save_memory(
            user_id=request.user_id,
            memory_type=request.memory_type,
            content=request.content,
            metadata=request.metadata,
            importance_score=request.importance_score
        )
        return {"success": True, "message": "記憶已保存"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存記憶錯誤: {str(e)}")


@memory_router.post("/preference")
async def save_preference(request: SavePreferenceRequest):
    """保存用戶偏好"""
    try:
        memory_manager = get_memory_manager()
        memory_manager.long_term.save_user_preference(
            user_id=request.user_id,
            preferences=request.preferences
        )
        return {"success": True, "message": "偏好已保存"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存偏好錯誤: {str(e)}")


@memory_router.get("/preference/{user_id}")
async def get_preference(user_id: str):
    """獲取用戶偏好"""
    try:
        memory_manager = get_memory_manager()
        preferences = memory_manager.long_term.get_user_preference(user_id)
        return {"success": True, "preferences": preferences}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取偏好錯誤: {str(e)}")


@memory_router.post("/search")
async def search_memories(request: SearchMemoryRequest):
    """搜索長期記憶"""
    try:
        memory_manager = get_memory_manager()
        memories = memory_manager.long_term.search_memories(
            user_id=request.user_id,
            query=request.query,
            memory_type=request.memory_type,
            limit=request.limit,
            min_importance=request.min_importance
        )
        return {"success": True, "memories": memories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"搜索記憶錯誤: {str(e)}")


@memory_router.get("/context/{user_id}")
async def get_user_context(user_id: str):
    """獲取用戶記憶上下文（用於構建系統提示詞）"""
    try:
        memory_manager = get_memory_manager()
        context = memory_manager.get_user_context(user_id)
        summary = memory_manager.long_term.get_user_memories_summary(user_id)
        return {
            "success": True,
            "context": context,
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取上下文錯誤: {str(e)}")


@memory_router.post("/session/summary")
async def save_session_summary(
    session_id: str,
    user_id: str,
    summary: str,
    key_points: Optional[List[str]] = None
):
    """保存會話摘要"""
    try:
        memory_manager = get_memory_manager()
        memory_manager.long_term.save_session_summary(
            session_id=session_id,
            user_id=user_id,
            summary=summary,
            key_points=key_points
        )
        return {"success": True, "message": "會話摘要已保存"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存會話摘要錯誤: {str(e)}")


@memory_router.get("/session/{session_id}")
async def get_session_summary(session_id: str):
    """獲取會話摘要"""
    try:
        memory_manager = get_memory_manager()
        summary = memory_manager.long_term.get_session_summary(session_id)
        return {"success": True, "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取會話摘要錯誤: {str(e)}")


# ==================== 舌診分析記錄路由 ====================

@memory_router.get("/tongue/history/{user_id}")
async def get_tongue_history(
    user_id: str,
    limit: int = 30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """獲取用戶的舌診分析歷史記錄（用於製作圖表）"""
    try:
        memory_manager = get_memory_manager()
        
        from datetime import datetime
        start_dt = datetime.fromisoformat(start_date) if start_date else None
        end_dt = datetime.fromisoformat(end_date) if end_date else None
        
        records = memory_manager.long_term.get_tongue_analysis_history(
            user_id=user_id,
            limit=limit,
            start_date=start_dt,
            end_date=end_dt
        )
        return {"success": True, "records": records, "count": len(records)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取歷史記錄錯誤: {str(e)}")


@memory_router.get("/tongue/stats/{user_id}")
async def get_tongue_stats(user_id: str, days: int = 30):
    """獲取用戶的舌診分析統計信息（用於圖表）"""
    try:
        memory_manager = get_memory_manager()
        stats = memory_manager.long_term.get_tongue_analysis_stats(
            user_id=user_id,
            days=days
        )
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"獲取統計信息錯誤: {str(e)}")

