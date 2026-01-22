from typing import List, Dict, Any

class TongueHealthScorer:
    """
    將舌診特徵轉換為雷達圖數值指標的服務
    """
    
    # 定義雷達圖的維度
    DIMENSIONS = ["氣虛", "血虛", "陰虛", "陽虛", "濕熱", "血瘀"]
    
    # 定義症狀與維度的權重映射（根據實際模型標籤）
    # 標籤格式：英文標籤（如 TonguePale）或中文標籤（如 舌淡白）
    SYMPTOM_WEIGHTS = {
        # 英文標籤映射
        "TonguePale": {"氣虛": 2, "血虛": 2, "陽虛": 1},  # 舌淡白
        "TipSideRed": {"陰虛": 2, "濕熱": 1},  # 舌尖邊紅
        "Spot": {"血瘀": 2, "濕熱": 1},  # 紅點
        "Ecchymosis": {"血瘀": 4},  # 瘀斑
        "Crack": {"陰虛": 2, "氣虛": 1},  # 裂紋
        "Toothmark": {"氣虛": 3, "陽虛": 2},  # 齒痕
        "FurThick": {"濕熱": 2, "氣虛": 1},  # 苔厚
        "FurYellow": {"濕熱": 3},  # 苔黃
        
        # 中文標籤映射（備用）
        "舌淡白": {"氣虛": 2, "血虛": 2, "陽虛": 1},
        "舌尖邊紅": {"陰虛": 2, "濕熱": 1},
        "紅點": {"血瘀": 2, "濕熱": 1},
        "瘀斑": {"血瘀": 4},
        "裂紋": {"陰虛": 2, "氣虛": 1},
        "齒痕": {"氣虛": 3, "陽虛": 2},
        "苔厚": {"濕熱": 2, "氣虛": 1},
        "苔黃": {"濕熱": 3},
    }
    
    # 中英文標籤對照表（用於從中文映射到英文）
    CHINESE_TO_ENGLISH = {
        "舌淡白": "TonguePale",
        "舌尖邊紅": "TipSideRed",
        "紅點": "Spot",
        "瘀斑": "Ecchymosis",
        "裂紋": "Crack",
        "齒痕": "Toothmark",
        "苔厚": "FurThick",
        "苔黃": "FurYellow",
    }

    @classmethod
    def calculate_scores(cls, positive_symptoms: List[Any]) -> Dict[str, float]:
        """
        根據檢測到的症狀計算各維度分數 (0-10分)
        
        Args:
            positive_symptoms: 症狀列表，可能是字符串列表或字典列表
                如果是字典，應包含 'chinese' 或 'english' 字段
        """
        scores = {dim: 0.0 for dim in cls.DIMENSIONS}
        
        for symptom in positive_symptoms:
            # 處理不同格式的症狀數據
            symptom_key = None
            
            if isinstance(symptom, dict):
                # 如果是字典，優先使用 english 字段
                symptom_key = symptom.get("english", "")
                # 如果沒有 english，嘗試從 chinese 映射到英文
                if not symptom_key:
                    chinese_name = symptom.get("chinese", "")
                    if chinese_name:
                        symptom_key = cls.CHINESE_TO_ENGLISH.get(chinese_name, "")
                    if not symptom_key:
                        # 如果還是找不到，嘗試直接用中文標籤
                        symptom_key = chinese_name
            elif isinstance(symptom, str):
                symptom_key = symptom
                # 如果是中文標籤，嘗試映射到英文
                if symptom_key in cls.CHINESE_TO_ENGLISH:
                    symptom_key = cls.CHINESE_TO_ENGLISH[symptom_key]
            else:
                continue
            
            # 處理大小寫或格式差異
            symptom_key = symptom_key.strip()
            if not symptom_key:
                continue
            
            # 嘗試直接匹配
            weights = cls.SYMPTOM_WEIGHTS.get(symptom_key)
            
            # 如果沒有直接匹配，嘗試大小寫不敏感匹配
            if not weights:
                for key in cls.SYMPTOM_WEIGHTS.keys():
                    if key.lower() == symptom_key.lower():
                        weights = cls.SYMPTOM_WEIGHTS[key]
                        break
            
            if not weights:
                # 如果還是找不到，跳過
                continue
                
            # 根據權重計算分數
            for dim, weight in weights.items():
                scores[dim] += weight
        
        # 正規化或限制最高分 (例如滿分 10 分)
        for dim in scores:
            scores[dim] = min(10.0, scores[dim])
            
        return scores

    @classmethod
    def generate_weekly_report_data(cls, records: List[Any]) -> Dict[str, Any]:
        """
        將一週的 DB 紀錄轉換為前端圖表需要的格式
        """
        chart_data = []
        trend_summary = []
        
        for record in records:
            # 假設 record.prediction_raw 是一個 dict，包含 'positive' list
            prediction_raw = record.prediction_raw if hasattr(record, 'prediction_raw') else record
            positive_symptoms = prediction_raw.get("positive", []) if isinstance(prediction_raw, dict) else []
            scores = cls.calculate_scores(positive_symptoms)
            
            # 處理日期格式
            created_at = record.created_at if hasattr(record, 'created_at') else None
            if created_at is None:
                # 如果沒有 created_at，嘗試從 record 中獲取
                if isinstance(record, dict):
                    created_at_str = record.get("created_at")
                    if created_at_str:
                        from datetime import datetime
                        if isinstance(created_at_str, str):
                            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        else:
                            created_at = created_at_str
                    else:
                        continue  # 跳過沒有日期的記錄
                else:
                    continue
            
            date_str = created_at.strftime("%Y-%m-%d") if hasattr(created_at, 'strftime') else str(created_at)
            
            chart_data.append({
                "date": date_str,
                "scores": scores
            })
            
            # 簡單的文字摘要，供 LLM 參考
            high_risks = [k for k, v in scores.items() if v >= 5]
            if high_risks:
                trend_summary.append(f"{date_str}: {', '.join(high_risks)} 指數偏高")
            else:
                trend_summary.append(f"{date_str}: 狀況平穩")
                
        return {
            "chart_data": chart_data,
            "text_summary": "\n".join(trend_summary)
        }
