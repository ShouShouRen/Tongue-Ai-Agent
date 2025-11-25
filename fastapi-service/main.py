from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, TypedDict, Annotated
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
import operator
import base64

# 添加 vision-predict 目錄到路徑
vision_predict_path = Path(__file__).parent.parent / "vision-predict"
vision_predict_path_abs = vision_predict_path.resolve()

print(f"嘗試載入 vision-predict 模組...")
print(f"vision-predict 路徑: {vision_predict_path_abs}")
print(f"路徑存在: {vision_predict_path_abs.exists()}")

if str(vision_predict_path_abs) not in sys.path:
    sys.path.insert(0, str(vision_predict_path_abs))
    print(f"已添加路徑到 sys.path: {vision_predict_path_abs}")

analyze_tongue_image = None
import_error_details = None

try:
    try:
        import torch
        import torchvision
        import timm
        from PIL import Image
        import numpy as np
        print("✓ 所有必要的依賴項已安裝")
    except ImportError as deps_error:
        import_error_details = f"缺少必要的依賴項: {deps_error}"
        print(f"✗ {import_error_details}")
        raise ImportError(import_error_details)
    
    try:
        from tongue_analysis_pipeline import analyze_tongue_image as _analyze_tongue_image
        print("✓ 成功導入 tongue_analysis_pipeline")
        
        segmentation_model_path = vision_predict_path_abs / "swim_trasnformer_384.pth"
        classification_model_path = vision_predict_path_abs / "Simple_convnext_base_fold3.pth"
        
        if not segmentation_model_path.exists():
            print(f"⚠ 警告: 分割模型文件不存在: {segmentation_model_path}")
        else:
            print(f"✓ 分割模型文件存在: {segmentation_model_path}")
            
        if not classification_model_path.exists():
            print(f"⚠ 警告: 分類模型文件不存在: {classification_model_path}")
        else:
            print(f"✓ 分類模型文件存在: {classification_model_path}")
        
        def analyze_tongue_image_wrapper(image_path, output_format="structured", output_dir=None):
            """包裝 analyze_tongue_image 函數，使用正確的模型路徑"""
            import tempfile
            if output_dir is None:
                output_dir = tempfile.mkdtemp()
            
            segmentation_model = str(segmentation_model_path)
            classification_model = str(classification_model_path)
            
            return _analyze_tongue_image(
                image_path=image_path,
                segmentation_model_path=segmentation_model,
                classification_model_path=classification_model,
                output_format=output_format,
                output_dir=output_dir
            )
        
        analyze_tongue_image = analyze_tongue_image_wrapper
        print("✓ vision-predict 模組已成功載入並配置")
        
    except ImportError as module_error:
        import_error_details = f"無法導入 tongue_analysis_pipeline 模組: {module_error}"
        print(f"✗ {import_error_details}")
        import traceback
        traceback.print_exc()
        raise ImportError(import_error_details)
        
except Exception as e:
    import_error_details = f"載入 vision-predict 時發生錯誤: {str(e)}"
    print(f"✗ {import_error_details}")
    import traceback
    traceback.print_exc()
    analyze_tongue_image = None

if analyze_tongue_image is None:
    print("\n" + "="*60)
    print("警告: vision-predict 模組不可用")
    print("="*60)
    if import_error_details:
        print(f"錯誤詳情: {import_error_details}")
    print(f"\n請確保:")
    print(f"1. vision-predict 目錄存在於: {vision_predict_path_abs}")
    print(f"2. 已安裝所有必要的依賴項 (torch, torchvision, timm, Pillow, numpy)")
    print(f"3. 模型文件存在於 vision-predict 目錄中")
    print("="*60 + "\n")

app = FastAPI(title="舌診 AI Agent API")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化 Ollama LLM
MODEL_NAME = "qwen3:8b"  # 使用 qwen3:8b 模型

llm = ChatOllama(
    model=MODEL_NAME,
    base_url="http://localhost:11434",
    temperature=0.7,
)

# ==================== LangGraph Agent 定義 ====================

# 定義 Agent 狀態
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    prediction_results: Optional[Dict[str, Any]]
    additional_info: Optional[str]
    analysis_stage: str  # "initial", "analyzing", "completed"
    final_response: Optional[str]
    image_path: Optional[str]  # 用於存儲圖片路徑


# ==================== 創建 Vision-Predict 工具 ====================

@tool
def predict_tongue_image_tool(image_path: str) -> Dict[str, Any]:
    """
    使用 vision-predict 模型分析舌診圖片
    
    Args:
        image_path: 圖片文件的路徑
        
    Returns:
        包含預測結果的字典，格式為：
        {
            "positive": [...],  # 檢測到的陽性症狀
            "negative": [...],  # 未檢測到的症狀
            "summary": {...}    # 統計摘要
        }
    """
    if analyze_tongue_image is None:
        return {
            "error": "vision-predict 模組不可用",
            "positive": [],
            "negative": [],
            "summary": {"positive_count": 0, "negative_count": 0}
        }
    
    try:
        import tempfile
        output_dir = tempfile.mkdtemp()
        
        # 調用 vision-predict 進行分析
        results = analyze_tongue_image(
            image_path=image_path,
            output_format="structured",
            output_dir=output_dir
        )
        
        if results is None:
            return {
                "error": "圖片預測失敗",
                "positive": [],
                "negative": [],
                "summary": {"positive_count": 0, "negative_count": 0}
            }
        
        return results
    except Exception as e:
        return {
            "error": f"預測過程發生錯誤: {str(e)}",
            "positive": [],
            "negative": [],
            "summary": {"positive_count": 0, "negative_count": 0}
        }


# 創建工具列表
tools = [predict_tongue_image_tool]

# 將工具綁定到 LLM
llm_with_tools = llm.bind_tools(tools)


# 舌診分析系統提示詞
TONGUE_ANALYSIS_SYSTEM_PROMPT = """你是一位專業的中醫舌診分析專家。你的任務是根據提供的舌診預測模型結果，進行深入的中醫理論分析和健康建議。

請根據以下原則進行分析：
1. 結合中醫理論，解釋提取到的舌象特徵的意義，並且解釋推理過程，且不要輸出任何概率數值
2. 分析可能的體質問題和健康狀況
3. 提供專業的健康建議和調理方向
4. 使用專業但易懂的語言
5. 如果預測結果不明確，請說明需要更多信息
6. 以上內容請分兩點，推理過程與健康建議調理方向

請以專業、友善的語氣回答。"""

# 帶工具的 Agent 系統提示詞
TOOL_AGENT_SYSTEM_PROMPT = """你是一位專業的中醫舌診分析 AI 助手。你可以幫助用戶分析舌診圖片。

當用戶上傳舌診圖片或要求分析舌頭時，你應該：
1. 檢查用戶消息中是否包含圖片路徑（格式：路徑為: /path/to/image.jpg）
2. 如果包含圖片路徑，使用 predict_tongue_image_tool 工具來分析圖片
3. 工具會返回預測結果，包含檢測到的症狀（positive）和未檢測到的症狀（negative）
4. 根據工具返回的預測結果，進行專業的中醫理論分析
5. 解釋每個檢測到的症狀的中醫意義
6. 提供健康建議和調理方向

工具使用方法：
- 工具名稱：predict_tongue_image_tool
- 參數：image_path（圖片文件的完整路徑）

如果用戶只是聊天或詢問一般問題，直接回答即可，不需要調用工具。

請以專業、友善的語氣與用戶交流。"""


# ==================== 帶工具的 Agent 節點 ====================

def agent_node(state: AgentState) -> AgentState:
    """Agent 節點 - 可以調用工具"""
    messages = state["messages"]
    
    # 如果沒有系統消息，添加系統提示詞
    has_system_message = any(isinstance(msg, SystemMessage) for msg in messages)
    if not has_system_message:
        messages = [SystemMessage(content=TOOL_AGENT_SYSTEM_PROMPT)] + messages
    
    # 調用 LLM（帶工具）
    response = llm_with_tools.invoke(messages)
    
    return {"messages": [response]}


def tool_node(state: AgentState) -> AgentState:
    """工具節點 - 執行工具調用"""
    messages = state["messages"]
    last_message = messages[-1]
    
    # 檢查是否有工具調用
    tool_calls = []
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        tool_calls = last_message.tool_calls
    
    tool_messages = []
    for tool_call in tool_calls:
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})
        tool_call_id = tool_call.get("id", "")
        
        if tool_name == "predict_tongue_image_tool":
            # 調用 vision-predict 工具
            image_path = tool_args.get("image_path", "")
            
            # 如果沒有提供路徑，嘗試從 state 中獲取
            if not image_path:
                image_path = state.get("image_path", "")
            
            if not image_path:
                tool_messages.append(
                    ToolMessage(
                        content="錯誤：未提供圖片路徑",
                        tool_call_id=tool_call_id
                    )
                )
                continue
            
            result = predict_tongue_image_tool.invoke({"image_path": image_path})
            
            # 將結果轉換為 JSON 字符串以便 LLM 理解
            result_str = json.dumps(result, ensure_ascii=False, indent=2)
            
            tool_messages.append(
                ToolMessage(
                    content=f"預測結果：\n{result_str}",
                    tool_call_id=tool_call_id
                )
            )
        else:
            tool_messages.append(
                ToolMessage(
                    content=f"未知工具: {tool_name}",
                    tool_call_id=tool_call_id
                )
            )
    
    return {"messages": tool_messages}


def should_continue(state: AgentState) -> str:
    """決定下一步：調用工具還是結束"""
    messages = state["messages"]
    last_message = messages[-1]
    
    # 檢查最後一條消息是否有工具調用
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    
    return "end"


# Agent 節點函數（保留原有功能）
def analyze_tongue_node(state: AgentState) -> AgentState:
    """分析舌診預測結果的節點"""
    # 構建分析提示詞
    analysis_prompt = f"""請根據以下舌診預測模型的結果進行專業分析：

預測結果：
{json.dumps(state.get('prediction_results', {}), ensure_ascii=False, indent=2)}
"""
    
    if state.get('additional_info'):
        analysis_prompt += f"\n\n額外信息：\n{state['additional_info']}"
    
    analysis_prompt += "\n\n請提供詳細的中醫理論分析和健康建議。"
    
    # 調用 LLM
    messages = [
        SystemMessage(content=TONGUE_ANALYSIS_SYSTEM_PROMPT),
        HumanMessage(content=analysis_prompt)
    ]
    
    response = llm.invoke(messages)
    
    return {
        "messages": [response],
        "analysis_stage": "completed",
        "final_response": response.content if hasattr(response, 'content') else str(response)
    }


def chat_node(state: AgentState) -> AgentState:
    """一般聊天的節點"""
    # 獲取最後一條用戶消息
    user_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    if not user_messages:
        return state
    
    last_user_message = user_messages[-1]
    
    # 調用 LLM
    messages = [
        SystemMessage(content="你是一位友善、專業的AI助手。"),
        last_user_message
    ]
    
    response = llm.invoke(messages)
    
    return {
        "messages": [response],
        "final_response": response.content if hasattr(response, 'content') else str(response)
    }


# 構建 LangGraph
def create_tongue_analysis_agent():
    """創建舌診分析的 LangGraph Agent"""
    workflow = StateGraph(AgentState)
    
    # 添加節點
    workflow.add_node("analyze", analyze_tongue_node)
    
    # 設置入口點和邊
    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", END)
    
    # 編譯圖
    memory = MemorySaver()
    app_agent = workflow.compile(checkpointer=memory)
    
    return app_agent


def create_chat_agent():
    """創建一般聊天的 LangGraph Agent"""
    workflow = StateGraph(AgentState)
    
    # 添加節點
    workflow.add_node("chat", chat_node)
    
    # 設置入口點和邊
    workflow.set_entry_point("chat")
    workflow.add_edge("chat", END)
    
    # 編譯圖
    memory = MemorySaver()
    app_agent = workflow.compile(checkpointer=memory)
    
    return app_agent


# 創建帶工具的 Agent
def create_tool_agent():
    """創建帶有 vision-predict 工具的 Agent"""
    workflow = StateGraph(AgentState)
    
    # 添加節點
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    # 設置入口點
    workflow.set_entry_point("agent")
    
    # 添加條件邊
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    
    # 工具執行後返回 agent
    workflow.add_edge("tools", "agent")
    
    # 編譯圖
    memory = MemorySaver()
    agent = workflow.compile(checkpointer=memory)
    
    return agent


# 創建 Agent 實例
tongue_analysis_agent = create_tongue_analysis_agent()
chat_agent = create_chat_agent()
tool_agent = create_tool_agent()


# ==================== FastAPI 端點 ====================

class ChatRequest(BaseModel):
    prompt: str


class TongueAnalysisRequest(BaseModel):
    prediction_results: Dict[str, Any]  # 預測模型的結果
    additional_info: Optional[str] = None  # 額外的患者信息或症狀描述


class TonguePredictAndAnalyzeRequest(BaseModel):
    additional_info: Optional[str] = None  # 額外的患者信息或症狀描述


class ChatResponse(BaseModel):
    response: str


@app.get("/")
async def root():
    return {
        "message": "舌診 AI Agent API 運行中",
        "model": MODEL_NAME,
        "framework": "LangGraph"
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """一般聊天接口 - 使用 LangGraph Agent"""
    try:
        # 構建初始狀態
        initial_state = {
            "messages": [HumanMessage(content=request.prompt)],
            "prediction_results": None,
            "additional_info": None,
            "analysis_stage": "initial",
            "final_response": None
        }
        
        # 運行 Agent
        config = {"configurable": {"thread_id": "chat-1"}}
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


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """流式聊天接口 - 使用 LangGraph Agent"""
    async def generate():
        try:
            # 構建初始狀態
            initial_state = {
                "messages": [HumanMessage(content=request.prompt)],
                "prediction_results": None,
                "additional_info": None,
                "analysis_stage": "initial",
                "final_response": None
            }
            
            # 運行 Agent（流式）
            config = {"configurable": {"thread_id": f"chat-stream-{id(request)}"}}
            
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


@app.post("/tongue/analyze", response_model=ChatResponse)
async def analyze_tongue(request: TongueAnalysisRequest):
    """舌診分析接口 - 使用 LangGraph Agent"""
    try:
        # 構建初始狀態
        initial_state = {
            "messages": [],
            "prediction_results": request.prediction_results,
            "additional_info": request.additional_info,
            "analysis_stage": "initial",
            "final_response": None
        }
        
        # 運行 Agent
        config = {"configurable": {"thread_id": f"tongue-{id(request)}"}}
        result = await tongue_analysis_agent.ainvoke(initial_state, config)
        
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
        raise HTTPException(status_code=500, detail=f"舌診分析錯誤: {str(e)}")


@app.post("/tongue/analyze/stream")
async def analyze_tongue_stream(request: TongueAnalysisRequest):
    """流式舌診分析接口 - 使用 LangGraph Agent"""
    async def generate():
        try:
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
            async for event in tongue_analysis_agent.astream_events(
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


@app.post("/tongue/predict")
async def predict_tongue_image(
    file: UploadFile = File(...),
    additional_info: Optional[str] = Form(None)
):
    """舌診圖片預測接口 - 調用 vision-predict 進行預測，返回 JSON 結果"""
    if analyze_tongue_image is None:
        error_detail = import_error_details or "vision-predict 模組不可用"
        raise HTTPException(
            status_code=503, 
            detail=f"vision-predict 模組不可用: {error_detail}. 請確保 vision-predict 目錄存在於 {vision_predict_path_abs} 且已安裝所有依賴項。"
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
                results = analyze_tongue_image(
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
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"預測過程發生錯誤: {str(e)}")


@app.post("/tongue/predict-and-analyze/stream")
async def predict_and_analyze_tongue_stream(
    file: UploadFile = File(...),
    additional_info: Optional[str] = Form(None)
):
    """完整的舌診分析流程：預測 + LLM 分析（流式）"""
    async def generate():
        try:
            # 步驟 1: 進行圖片預測
            yield f"data: {json.dumps({'type': 'status', 'message': '正在進行圖片分析...'}, ensure_ascii=False)}\n\n"
            
            if analyze_tongue_image is None:
                error_detail = import_error_details or "vision-predict 模組不可用"
                error_msg = json.dumps({
                    "error": f"vision-predict 模組不可用: {error_detail}",
                    "details": {
                        "vision_predict_path": str(vision_predict_path_abs),
                        "path_exists": vision_predict_path_abs.exists(),
                        "import_error": import_error_details
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
                    prediction_results = analyze_tongue_image(
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
                    initial_state = {
                        "messages": [],
                        "prediction_results": prediction_results,
                        "additional_info": additional_info,
                        "analysis_stage": "initial",
                        "final_response": None
                    }
                    
                    # 運行 Agent（流式）
                    config = {"configurable": {"thread_id": f"tongue-predict-stream-{id(file)}"}}
                    
                    # 使用 astream_events 來獲取真正的流式輸出
                    async for event in tongue_analysis_agent.astream_events(
                        initial_state, 
                        config,
                        version="v2"
                    ):
                        if event["event"] == "on_chat_model_stream":
                            chunk = event["data"]["chunk"]
                            if hasattr(chunk, 'content') and chunk.content:
                                yield f"data: {json.dumps({'type': 'content', 'content': chunk.content}, ensure_ascii=False)}\n\n"
                        elif event["event"] == "on_chain_end" and event.get("name") == "analyze":
                            # Agent 完成
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


@app.post("/agent/chat/stream")
async def agent_chat_stream(
    file: Optional[UploadFile] = File(None),
    prompt: Optional[str] = Form(None)
):
    """帶工具的 Agent 聊天接口（流式）- Agent 可以自動調用 vision-predict 工具"""
    async def generate():
        try:
            # 保存圖片到臨時文件（如果有的話）
            image_path = None
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
                "image_path": image_path
            }
            
            # 運行 Agent（流式）
            config = {"configurable": {"thread_id": f"agent-chat-stream-{id(file) if file else id(prompt)}"}}
            
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
            
            # 清理臨時文件
            if image_path and os.path.exists(image_path):
                try:
                    os.unlink(image_path)
                except:
                    pass
                    
        except Exception as e:
            error_msg = json.dumps({
                "error": f"處理過程發生錯誤: {str(e)}"
            }, ensure_ascii=False)
            yield f"data: {error_msg}\n\n"
            
            # 清理臨時文件
            if image_path and os.path.exists(image_path):
                try:
                    os.unlink(image_path)
                except:
                    pass
    
    return StreamingResponse(generate(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
