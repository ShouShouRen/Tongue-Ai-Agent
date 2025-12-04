# agents/agent.py
from enum import Enum
from typing import Optional, Dict, Any, TypedDict, Annotated
import json

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

from config.settings import settings
from config.prompts import PromptTemplates
from utils.vision_loader import VisionPredictLoader
from utils.memory_manager import get_memory_manager

# 定義 Agent 狀態
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    prediction_results: Optional[Dict[str, Any]]
    additional_info: Optional[str]
    analysis_stage: str  # "initial", "analyzing", "completed"
    final_response: Optional[str]
    image_path: Optional[str]  # 用於存儲圖片路徑
    user_id: Optional[str]  # 用戶 ID（用於記憶管理）
    session_id: Optional[str]  # 會話 ID（用於短期記憶）
    memory_context: Optional[str]  # 記憶上下文（從長期記憶中檢索）


class AgentMode(str, Enum):
    CHAT = "chat"
    TONGUE_ANALYSIS = "tongue_analysis"
    TOOL_ENABLED = "tool_enabled"


# 初始化 LLM
_llm = None
_llm_with_tools = None
_vision_loader = None


def _get_llm():
    """獲取 LLM 實例（單例模式）"""
    global _llm
    if _llm is None:
        _llm = ChatOllama(
            model=settings.model_name,
            base_url=settings.ollama_base_url,
            temperature=settings.llm_temperature,
        )
    return _llm


def _get_vision_loader():
    """獲取 VisionLoader 實例（單例模式）"""
    global _vision_loader
    if _vision_loader is None:
        _vision_loader = VisionPredictLoader(settings.vision_predict_path)
    return _vision_loader


def _get_llm_with_tools():
    """獲取帶工具的 LLM 實例（單例模式）"""
    global _llm_with_tools
    if _llm_with_tools is None:
        tools = [_create_predict_tongue_image_tool()]
        _llm_with_tools = _get_llm().bind_tools(tools)
    return _llm_with_tools


def _create_predict_tongue_image_tool():
    """創建舌診圖片預測工具"""
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
        vision_loader = _get_vision_loader()
        
        if not vision_loader.status.is_available:
            return {
                "error": f"vision-predict 模組不可用: {vision_loader.status.error_message}",
                "positive": [],
                "negative": [],
                "summary": {"positive_count": 0, "negative_count": 0}
            }
        
        if vision_loader.status.analyze_function is None:
            return {
                "error": "vision-predict 分析函數不可用",
                "positive": [],
                "negative": [],
                "summary": {"positive_count": 0, "negative_count": 0}
            }
        
        try:
            import tempfile
            output_dir = tempfile.mkdtemp()
            
            # 調用 vision-predict 進行分析
            results = vision_loader.status.analyze_function(
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
    
    return predict_tongue_image_tool


# Agent 節點函數
def agent_node(state: AgentState) -> AgentState:
    """Agent 節點 - 可以調用工具"""
    messages = state["messages"]
    
    # 如果沒有系統消息，添加系統提示詞
    has_system_message = any(isinstance(msg, SystemMessage) for msg in messages)
    if not has_system_message:
        system_prompt = PromptTemplates.TOOL_AGENT_SYSTEM
        
        # 如果有記憶上下文，添加到系統提示詞中
        memory_context = state.get("memory_context")
        if memory_context:
            system_prompt += f"\n\n用戶歷史記憶和偏好：\n{memory_context}"
        
        messages = [SystemMessage(content=system_prompt)] + messages
    
    # 調用 LLM（帶工具）
    llm_with_tools = _get_llm_with_tools()
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
    predict_tool = _create_predict_tongue_image_tool()
    
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
            
            result = predict_tool.invoke({"image_path": image_path})
            
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


def analyze_tongue_node(state: AgentState) -> AgentState:
    """分析舌診預測結果的節點"""
    # 構建分析提示詞
    analysis_prompt = PromptTemplates.build_analysis_prompt(
        prediction_results=state.get('prediction_results', {}),
        additional_info=state.get('additional_info')
    )
    
    # 調用 LLM
    llm = _get_llm()
    messages = [
        SystemMessage(content=PromptTemplates.TONGUE_ANALYSIS_SYSTEM),
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
    messages = list(state["messages"])  # 創建副本以避免修改原始列表
    
    # 檢查是否已經有系統消息
    has_system_message = any(isinstance(msg, SystemMessage) for msg in messages)
    
    # 準備要返回的消息列表
    messages_to_return = []
    
    # 如果沒有系統消息，添加系統提示詞（只在第一次會話時）
    if not has_system_message:
        system_content = "你是一位友善、專業的AI助手。"
        
        # 如果有記憶上下文，添加到系統提示詞中（只在第一次會話時）
        memory_context = state.get("memory_context")
        if memory_context:
            system_content += f"\n\n用戶歷史記憶和偏好：\n{memory_context}"
        
        # 創建系統消息並添加到返回列表（這樣會被 checkpointer 保存）
        system_msg = SystemMessage(content=system_content)
        messages_to_return.append(system_msg)
        # 將系統消息添加到消息列表開頭以便 LLM 使用
        messages = [system_msg] + messages
    
    # 調用 LLM（使用完整的消息歷史，checkpointer 會自動管理）
    llm = _get_llm()
    response = llm.invoke(messages)
    
    # 將響應添加到返回列表
    messages_to_return.append(response)
    
    # 返回新消息（LangGraph 會自動通過 add_messages reducer 合併）
    return {
        "messages": messages_to_return,
        "final_response": response.content if hasattr(response, 'content') else str(response)
    }


def create_unified_agent(mode: AgentMode, use_persistent_memory: bool = False):
    """
    統一的 Agent 建構函數
    
    Args:
        mode: Agent 模式
        use_persistent_memory: 是否使用持久化記憶（SQLite），False 則使用內存記憶
    """
    workflow = StateGraph(AgentState)
    
    if mode == AgentMode.TOOL_ENABLED:
        workflow.add_node("agent", agent_node)
        workflow.add_node("tools", tool_node)
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {"tools": "tools", "end": END}
        )
        workflow.add_edge("tools", "agent")
    elif mode == AgentMode.TONGUE_ANALYSIS:
        workflow.add_node("analyze", analyze_tongue_node)
        workflow.set_entry_point("analyze")
        workflow.add_edge("analyze", END)
    else:  # CHAT
        workflow.add_node("chat", chat_node)
        workflow.set_entry_point("chat")
        workflow.add_edge("chat", END)
    
    # 使用記憶管理器獲取 checkpointer
    memory_manager = get_memory_manager()
    checkpointer = memory_manager.get_checkpointer()
    
    return workflow.compile(checkpointer=checkpointer)
