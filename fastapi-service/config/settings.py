# config/settings.py
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional

class Settings(BaseSettings):
    # LLM 設定
    model_name: str = "qwen3:8b"
    ollama_base_url: str = "http://localhost:11434"
    llm_temperature: float = 0.7
    
    # Vision-Predict 設定
    # vision-predict 目錄位於專案根目錄（fastapi-service 的上一層）
    vision_predict_path: Path = Path(__file__).parent.parent.parent / "vision-predict"
    segmentation_model_name: str = "swim_trasnformer_384.pth"
    classification_model_name: str = "Simple_convnext_base_fold3.pth"
    
    # API 設定
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["*"]
    
    # 日誌設定
    log_level: str = "INFO"
    
    # 記憶設定（PostgreSQL）
    memory_db_host: str = "localhost"
    memory_db_port: int = 5432
    memory_db_name: str = "tongue_ai_memory"
    memory_db_user: str = "postgres"
    memory_db_password: str = "postgres"
    # 或者直接使用連接字符串（優先級更高）
    memory_db_url: Optional[str] = None  # 例如: postgresql://user:password@host:port/dbname

settings = Settings()
