# utils/streaming.py
import json
from typing import AsyncGenerator, Dict, Any

class StreamingResponseBuilder:
    """流式回應建構器"""
    
    @staticmethod
    async def build_sse_stream(
        generator: AsyncGenerator[Dict[str, Any], None]
    ) -> AsyncGenerator[str, None]:
        """建構 SSE 格式的流式回應"""
        try:
            async for event in generator:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            error_event = {
                "type": "error",
                "error": str(e)
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    @staticmethod
    async def from_langgraph_agent(
        agent,
        initial_state: Dict[str, Any],
        config: Dict[str, Any]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """從 LangGraph agent 產生事件流"""
        async for event in agent.astream_events(initial_state, config, version="v2"):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, 'content') and chunk.content:
                    yield {
                        "type": "content",
                        "content": chunk.content
                    }
            elif event["event"] == "on_tool_start":
                yield {
                    "type": "status",
                    "message": f"正在調用工具: {event.get('name', '')}..."
                }
            elif event["event"] == "on_tool_end":
                yield {
                    "type": "status",
                    "message": "工具執行完成"
                }

# 使用方式
@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    async def generate():
        initial_state = {...}
        config = {...}
        
        event_stream = StreamingResponseBuilder.from_langgraph_agent(
            chat_agent, initial_state, config
        )
        sse_stream = StreamingResponseBuilder.build_sse_stream(event_stream)
        
        async for data in sse_stream:
            yield data
    
    return StreamingResponse(generate(), media_type="text/event-stream")
