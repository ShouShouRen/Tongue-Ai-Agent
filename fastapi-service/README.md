## 安裝

本專案使用 [uv](https://github.com/astral-sh/uv) 來管理 Python 依賴。

```bash
# 安裝所有依賴（uv 會自動讀取 pyproject.toml）
uv sync

# 或者使用 uv 運行
uv run python main.py
```

## 啟動服務

確保 Ollama 服務正在運行，並且已經下載了 qwen3:8b 模型：

```bash
ollama pull qwen3:8b
```

然後啟動 FastAPI 服務：

```bash
# 使用 uv 運行
uv run python main.py

# 或使用 uvicorn
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

```

## API 端點

### 1. 一般聊天

- **POST** `/chat` - 一般聊天接口
- **POST** `/chat/stream` - 流式聊天接口

### 2. 舌診分析

- **POST** `/tongue/analyze` - 舌診分析接口（接收預測結果）
- **POST** `/tongue/analyze/stream` - 流式舌診分析接口

### 舌診分析請求格式

```json
{
  "prediction_results": {
    "tongue_color": "淡紅",
    "coating_color": "白",
    "coating_thickness": "薄",
    "moisture": "潤",
    "shape": "正常"
  },
  "additional_info": "患者最近感到疲勞，食慾不振"
}
```

## 注意事項

- 確保 Ollama 服務運行在 `http://localhost:11434`
- 如果使用不同的模型名稱，請修改 `main.py` 中的 `model` 參數
