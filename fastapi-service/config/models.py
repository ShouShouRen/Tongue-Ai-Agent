from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class DiagnosisRecord(Base):
    """
    舌診診斷記錄表
    用於長期記憶功能，儲存每次的視覺模型預測結果
    """
    __tablename__ = "diagnosis_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True, nullable=False)  # 綁定用戶
    image_path = Column(String, nullable=True)
    
    # 儲存視覺模型的原始輸出 (JSON 格式)
    # 例如: {"positive": ["Yellow_Coating", "Teeth_Marks"], "negative": [...]}
    prediction_raw = Column(JSON, nullable=False)
    
    # 也可以選擇儲存計算後的雷達圖分數，方便快速查詢
    # 例如: {"qi_deficiency": 5, "damp_heat": 2, ...}
    health_scores = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<DiagnosisRecord(id={self.id}, user={self.user_id}, date={self.created_at})>"
