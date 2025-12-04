# utils/memory_manager.py
"""
記憶管理模組
- 短期記憶：會話級別的上下文記憶（使用 LangGraph MemorySaver）
- 長期記憶：跨會話的持久化記憶（使用 PostgreSQL）
"""
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
from contextlib import contextmanager
from langgraph.checkpoint.memory import MemorySaver

from config.settings import settings


class ShortTermMemory:
    """短期記憶管理器 - 會話級別的上下文記憶"""
    
    def __init__(self):
        # 使用 MemorySaver 作為短期記憶（內存中）
        # 如果需要持久化短期記憶，可以改用 SqliteSaver
        self.checkpointer = MemorySaver()
    
    def get_checkpointer(self):
        """獲取 LangGraph checkpointer"""
        return self.checkpointer


class LongTermMemory:
    """長期記憶管理器 - 跨會話的持久化記憶（使用 PostgreSQL）"""
    
    def __init__(self, db_url: Optional[str] = None):
        """
        初始化長期記憶數據庫
        
        Args:
            db_url: PostgreSQL 連接字符串，如果為 None 則從 settings 構建
        """
        # 構建數據庫連接字符串
        if db_url:
            self.db_url = db_url
        elif settings.memory_db_url:
            self.db_url = settings.memory_db_url
        else:
            # 從單獨的配置項構建連接字符串
            self.db_url = (
                f"postgresql://{settings.memory_db_user}:{settings.memory_db_password}"
                f"@{settings.memory_db_host}:{settings.memory_db_port}/{settings.memory_db_name}"
            )
        
        # 初始化數據庫
        self._init_database()
    
    @contextmanager
    def _get_connection(self):
        """獲取數據庫連接的上下文管理器"""
        conn = psycopg2.connect(self.db_url)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_database(self):
        """初始化數據庫表結構"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 用戶記憶表：存儲用戶的基本信息和偏好
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_memory (
                    user_id VARCHAR(255) PRIMARY KEY,
                    preferences TEXT,  -- JSON 格式的用戶偏好
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 會話記憶表：存儲每個會話的摘要和關鍵信息
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_memory (
                    session_id VARCHAR(255) PRIMARY KEY,
                    user_id VARCHAR(255),
                    summary TEXT,  -- 會話摘要
                    key_points TEXT,  -- JSON 格式的關鍵點
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user_memory(user_id) ON DELETE CASCADE
                )
            """)
            
            # 長期記憶表：存儲重要的記憶片段（事實、偏好、歷史等）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS long_term_memories (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    memory_type VARCHAR(50),  -- 'fact', 'preference', 'history', 'medical_record'
                    content TEXT,  -- 記憶內容
                    metadata TEXT,  -- JSON 格式的元數據
                    importance_score REAL DEFAULT 1.0,  -- 重要性評分（1-10）
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user_memory(user_id) ON DELETE CASCADE
                )
            """)
            
            # 創建索引以提高查詢效率
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_id ON long_term_memories(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_type ON long_term_memories(memory_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_user ON session_memory(user_id)
            """)
            
            # 創建重要性評分索引以優化查詢
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_importance_score ON long_term_memories(importance_score DESC)
            """)
            
            # 舌診分析記錄表：存儲每次舌診分析的完整結果（用於製作圖表）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tongue_analysis_records (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255),
                    session_id VARCHAR(255),
                    prediction_results TEXT,  -- JSON 格式的預測結果
                    analysis_response TEXT,  -- LLM 分析的回應
                    additional_info TEXT,  -- 額外信息
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES user_memory(user_id) ON DELETE CASCADE
                )
            """)
            
            # 創建索引以提高查詢效率
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tongue_user_date ON tongue_analysis_records(user_id, created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tongue_session ON tongue_analysis_records(session_id)
            """)
    
    def save_user_preference(self, user_id: str, preferences: Dict[str, Any]):
        """保存用戶偏好"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            preferences_json = json.dumps(preferences, ensure_ascii=False)
            
            cursor.execute("""
                INSERT INTO user_memory (user_id, preferences, updated_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id) 
                DO UPDATE SET preferences = EXCLUDED.preferences, updated_at = EXCLUDED.updated_at
            """, (user_id, preferences_json, datetime.now()))
    
    def get_user_preference(self, user_id: str) -> Optional[Dict[str, Any]]:
        """獲取用戶偏好"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT preferences FROM user_memory WHERE user_id = %s", (user_id,))
            row = cursor.fetchone()
            
            if row and row[0]:
                return json.loads(row[0])
            return None
    
    def save_session_summary(self, session_id: str, user_id: str, summary: str, key_points: List[str] = None):
        """保存會話摘要"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            key_points_json = json.dumps(key_points or [], ensure_ascii=False)
            
            # 確保用戶存在（如果不存在則創建）
            cursor.execute("""
                INSERT INTO user_memory (user_id, updated_at)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id, datetime.now()))
            
            cursor.execute("""
                INSERT INTO session_memory (session_id, user_id, summary, key_points, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (session_id) 
                DO UPDATE SET 
                    summary = EXCLUDED.summary, 
                    key_points = EXCLUDED.key_points, 
                    updated_at = EXCLUDED.updated_at
            """, (session_id, user_id, summary, key_points_json, datetime.now()))
    
    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """獲取會話摘要"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT user_id, summary, key_points, created_at, updated_at
                FROM session_memory WHERE session_id = %s
            """, (session_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    "user_id": row[0],
                    "summary": row[1],
                    "key_points": json.loads(row[2]) if row[2] else [],
                    "created_at": row[3].isoformat() if row[3] else None,
                    "updated_at": row[4].isoformat() if row[4] else None
                }
            return None
    
    def save_memory(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        importance_score: float = 1.0
    ):
        """
        保存長期記憶
        
        Args:
            user_id: 用戶 ID
            memory_type: 記憶類型（'fact', 'preference', 'history', 'medical_record'）
            content: 記憶內容
            metadata: 元數據（可選）
            importance_score: 重要性評分（1-10）
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
            
            # 確保用戶存在（如果不存在則創建）
            cursor.execute("""
                INSERT INTO user_memory (user_id, updated_at)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id, datetime.now()))
            
            cursor.execute("""
                INSERT INTO long_term_memories 
                (user_id, memory_type, content, metadata, importance_score, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_id, memory_type, content, metadata_json, importance_score, datetime.now()))
    
    def search_memories(
        self,
        user_id: str,
        query: Optional[str] = None,
        memory_type: Optional[str] = None,
        limit: int = 10,
        min_importance: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        搜索長期記憶
        
        Args:
            user_id: 用戶 ID
            query: 搜索關鍵詞（簡單的文本匹配）
            memory_type: 記憶類型過濾
            limit: 返回結果數量限制
            min_importance: 最小重要性評分
        
        Returns:
            記憶列表，按重要性評分和時間排序
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 構建查詢
            conditions = ["user_id = %s", "importance_score >= %s"]
            params = [user_id, min_importance]
            
            if memory_type:
                conditions.append("memory_type = %s")
                params.append(memory_type)
            
            if query:
                conditions.append("(content LIKE %s OR metadata LIKE %s)")
                query_pattern = f"%{query}%"
                params.extend([query_pattern, query_pattern])
            
            where_clause = " AND ".join(conditions)
            
            cursor.execute(f"""
                SELECT id, memory_type, content, metadata, importance_score, created_at, updated_at
                FROM long_term_memories
                WHERE {where_clause}
                ORDER BY importance_score DESC, updated_at DESC
                LIMIT %s
            """, params + [limit])
            
            rows = cursor.fetchall()
            
            memories = []
            for row in rows:
                memories.append({
                    "id": row[0],
                    "memory_type": row[1],
                    "content": row[2],
                    "metadata": json.loads(row[3]) if row[3] else {},
                    "importance_score": float(row[4]) if row[4] else 0.0,
                    "created_at": row[5].isoformat() if row[5] else None,
                    "updated_at": row[6].isoformat() if row[6] else None
                })
            
            return memories
    
    def get_user_memories_summary(self, user_id: str) -> Dict[str, Any]:
        """獲取用戶記憶摘要（用於構建上下文）"""
        # 獲取用戶偏好
        preferences = self.get_user_preference(user_id)
        
        # 獲取重要的長期記憶
        important_memories = self.search_memories(
            user_id=user_id,
            limit=5,
            min_importance=5.0
        )
        
        # 獲取最近的會話摘要
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_id, summary, key_points, updated_at
                FROM session_memory
                WHERE user_id = %s
                ORDER BY updated_at DESC
                LIMIT 3
            """, (user_id,))
            recent_sessions = cursor.fetchall()
        
        sessions = []
        for row in recent_sessions:
            sessions.append({
                "session_id": row[0],
                "summary": row[1],
                "key_points": json.loads(row[2]) if row[2] else [],
                "updated_at": row[3].isoformat() if row[3] else None
            })
        
        return {
            "preferences": preferences,
            "important_memories": important_memories,
            "recent_sessions": sessions
        }
    
    def save_tongue_analysis(
        self,
        user_id: str,
        session_id: Optional[str],
        prediction_results: Dict[str, Any],
        analysis_response: str,
        additional_info: Optional[str] = None
    ):
        """
        保存舌診分析記錄
        
        Args:
            user_id: 用戶 ID
            session_id: 會話 ID（可選）
            prediction_results: 預測結果（字典）
            analysis_response: LLM 分析的回應
            additional_info: 額外信息（可選）
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 確保用戶存在
            cursor.execute("""
                INSERT INTO user_memory (user_id, updated_at)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO NOTHING
            """, (user_id, datetime.now()))
            
            # 保存分析記錄
            prediction_json = json.dumps(prediction_results, ensure_ascii=False)
            cursor.execute("""
                INSERT INTO tongue_analysis_records 
                (user_id, session_id, prediction_results, analysis_response, additional_info)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, session_id, prediction_json, analysis_response, additional_info))
    
    def get_tongue_analysis_history(
        self,
        user_id: str,
        limit: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        獲取用戶的舌診分析歷史記錄（用於製作圖表）
        
        Args:
            user_id: 用戶 ID
            limit: 返回記錄數量限制
            start_date: 開始日期（可選）
            end_date: 結束日期（可選）
        
        Returns:
            分析記錄列表，按時間倒序排列
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            conditions = ["user_id = %s"]
            params = [user_id]
            
            if start_date:
                conditions.append("created_at >= %s")
                params.append(start_date)
            
            if end_date:
                conditions.append("created_at <= %s")
                params.append(end_date)
            
            where_clause = " AND ".join(conditions)
            
            cursor.execute(f"""
                SELECT id, session_id, prediction_results, analysis_response, 
                       additional_info, created_at
                FROM tongue_analysis_records
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT %s
            """, params + [limit])
            
            rows = cursor.fetchall()
            
            records = []
            for row in rows:
                records.append({
                    "id": row[0],
                    "session_id": row[1],
                    "prediction_results": json.loads(row[2]) if row[2] else {},
                    "analysis_response": row[3],
                    "additional_info": row[4],
                    "created_at": row[5].isoformat() if row[5] else None
                })
            
            return records
    
    def get_tongue_analysis_stats(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        獲取用戶的舌診分析統計信息（用於圖表）
        
        Args:
            user_id: 用戶 ID
            days: 統計天數
        
        Returns:
            統計信息字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 獲取指定天數內的記錄
            cursor.execute("""
                SELECT prediction_results, created_at
                FROM tongue_analysis_records
                WHERE user_id = %s 
                AND created_at >= CURRENT_TIMESTAMP - INTERVAL '%s days'
                ORDER BY created_at ASC
            """, (user_id, days))
            
            rows = cursor.fetchall()
            
            # 統計各項特徵的出現頻率
            feature_counts = {}
            dates = []
            
            for row in rows:
                prediction_results = json.loads(row[0]) if row[0] else {}
                created_at = row[1]
                dates.append(created_at.isoformat() if created_at else None)
                
                # 統計陽性症狀
                positive = prediction_results.get("positive", [])
                for feature in positive:
                    feature_name = feature.get("chinese", feature.get("english", ""))
                    if feature_name:
                        if feature_name not in feature_counts:
                            feature_counts[feature_name] = []
                        feature_counts[feature_name].append({
                            "date": created_at.isoformat() if created_at else None,
                            "probability": feature.get("probability", 0)
                        })
            
            return {
                "total_records": len(rows),
                "date_range": {
                    "start": dates[0] if dates else None,
                    "end": dates[-1] if dates else None
                },
                "feature_trends": feature_counts,
                "records": [
                    {
                        "date": row[1].isoformat() if row[1] else None,
                        "prediction_results": json.loads(row[0]) if row[0] else {}
                    }
                    for row in rows
                ]
            }


class MemoryManager:
    """統一的記憶管理器"""
    
    def __init__(self, db_url: Optional[str] = None):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(db_url)
    
    def get_checkpointer(self):
        """獲取短期記憶的 checkpointer（用於 LangGraph）"""
        return self.short_term.get_checkpointer()
    
    def get_user_context(self, user_id: str) -> str:
        """
        獲取用戶上下文信息（用於構建系統提示詞）
        
        Returns:
            格式化的上下文字符串
        """
        summary = self.long_term.get_user_memories_summary(user_id)
        
        context_parts = []
        
        # 用戶偏好
        if summary["preferences"]:
            prefs = json.dumps(summary["preferences"], ensure_ascii=False, indent=2)
            context_parts.append(f"用戶偏好：\n{prefs}")
        
        # 重要記憶
        if summary["important_memories"]:
            memories_text = "\n".join([
                f"- [{m['memory_type']}] {m['content']}" 
                for m in summary["important_memories"]
            ])
            context_parts.append(f"重要記憶：\n{memories_text}")
        
        # 最近的會話摘要
        if summary["recent_sessions"]:
            sessions_text = "\n".join([
                f"- {s['summary']}" 
                for s in summary["recent_sessions"]
            ])
            context_parts.append(f"最近的會話摘要：\n{sessions_text}")
        
        if context_parts:
            return "\n\n".join(context_parts)
        return ""


# 全局記憶管理器實例
_memory_manager = None


def get_memory_manager(db_url: Optional[str] = None) -> MemoryManager:
    """獲取全局記憶管理器實例（單例模式）"""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager(db_url)
    return _memory_manager
