from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from config.models import DiagnosisRecord
from config.scoring import TongueHealthScorer

# 模擬視覺模型預測 (未來請替換為真實模型的 import 與呼叫)
def _mock_vision_model_predict(image_path: str):
    # 這裡應該調用你的 PyTorch 模型
    # 暫時回傳假資料以供測試
    return ["Yellow_Coating", "Red_Tongue", "Teeth_Marks"]

def predict_tongue_image_tool(db: Session, user_id: str, image_path: str):
    """
    工具：分析圖片並將結果存入資料庫 (長期記憶)
    """
    # 1. 呼叫視覺模型
    symptoms = _mock_vision_model_predict(image_path)
    
    # 2. 存入資料庫 (這就是長期記憶的關鍵步驟)
    record = DiagnosisRecord(
        user_id=user_id,
        image_path=image_path,
        prediction_raw={"positive": symptoms}
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    
    # 3. 回傳結果給 Agent
    return {
        "symptoms": symptoms,
        "message": "診斷已完成，結果已存入健康檔案。"
    }

def get_weekly_report_tool(db: Session, user_id: str):
    """
    工具：獲取週報文字摘要 (供 Agent 閱讀並回答用戶)
    """
    one_week_ago = datetime.now() - timedelta(days=7)
    
    # 從 DB 撈取過去 7 天紀錄
    records = db.query(DiagnosisRecord).filter(
        DiagnosisRecord.user_id == user_id,
        DiagnosisRecord.created_at >= one_week_ago
    ).order_by(DiagnosisRecord.created_at.asc()).all()
    
    if not records:
        return "系統顯示過去一週沒有足夠的診斷數據，無法生成週報。"
        
    # 利用 Scorer 生成摘要
    report_data = TongueHealthScorer.generate_weekly_report_data(records)
    return report_data["text_summary"]
