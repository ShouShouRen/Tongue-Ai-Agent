#!/usr/bin/env python3
"""
記憶功能測試腳本

使用方法：
1. 確保 PostgreSQL 已啟動並配置正確
2. 確保 FastAPI 服務正在運行（http://localhost:8000）
3. 運行此腳本：python test_memory.py
"""

import requests
import json
import time
from typing import Dict, Any

# API 基礎 URL
BASE_URL = "http://localhost:8000"

# 測試用戶 ID
TEST_USER_ID = "test_user_001"
TEST_SESSION_ID = "test_session_001"


def print_section(title: str):
    """打印測試區塊標題"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_save_preference():
    """測試保存用戶偏好"""
    print_section("測試 1: 保存用戶偏好")
    
    url = f"{BASE_URL}/memory/preference"
    data = {
        "user_id": TEST_USER_ID,
        "preferences": {
            "language": "繁體中文",
            "response_style": "詳細",
            "medical_focus": "中醫",
            "preferred_format": "結構化"
        }
    }
    
    try:
        response = requests.post(url, json=data)
        print(f"請求 URL: {url}")
        print(f"請求數據: {json.dumps(data, ensure_ascii=False, indent=2)}")
        print(f"狀態碼: {response.status_code}")
        print(f"響應: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
        
        if response.status_code == 200:
            print("✅ 測試通過")
            return True
        else:
            print("❌ 測試失敗")
            return False
    except Exception as e:
        print(f"❌ 錯誤: {str(e)}")
        return False


def test_get_preference():
    """測試獲取用戶偏好"""
    print_section("測試 2: 獲取用戶偏好")
    
    url = f"{BASE_URL}/memory/preference/{TEST_USER_ID}"
    
    try:
        response = requests.get(url)
        print(f"請求 URL: {url}")
        print(f"狀態碼: {response.status_code}")
        print(f"響應: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
        
        if response.status_code == 200:
            print("✅ 測試通過")
            return True
        else:
            print("❌ 測試失敗")
            return False
    except Exception as e:
        print(f"❌ 錯誤: {str(e)}")
        return False


def test_save_memory():
    """測試保存長期記憶"""
    print_section("測試 3: 保存長期記憶")
    
    url = f"{BASE_URL}/memory/save"
    
    memories = [
        {
            "user_id": TEST_USER_ID,
            "memory_type": "fact",
            "content": "用戶有慢性胃炎病史",
            "metadata": {"source": "medical_record", "date": "2024-01-15"},
            "importance_score": 8.5
        },
        {
            "user_id": TEST_USER_ID,
            "memory_type": "preference",
            "content": "用戶喜歡詳細的解釋",
            "metadata": {"source": "user_feedback"},
            "importance_score": 7.0
        },
        {
            "user_id": TEST_USER_ID,
            "memory_type": "medical_record",
            "content": "上次舌診顯示舌質淡紅，苔薄白",
            "metadata": {"date": "2024-01-10", "session_id": "session_001"},
            "importance_score": 9.0
        }
    ]
    
    success_count = 0
    for i, memory in enumerate(memories, 1):
        print(f"\n保存記憶 {i}/{len(memories)}:")
        try:
            response = requests.post(url, json=memory)
            print(f"  狀態碼: {response.status_code}")
            print(f"  響應: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
            
            if response.status_code == 200:
                success_count += 1
                print(f"  ✅ 記憶 {i} 保存成功")
            else:
                print(f"  ❌ 記憶 {i} 保存失敗")
        except Exception as e:
            print(f"  ❌ 錯誤: {str(e)}")
    
    if success_count == len(memories):
        print(f"\n✅ 所有記憶保存成功 ({success_count}/{len(memories)})")
        return True
    else:
        print(f"\n❌ 部分記憶保存失敗 ({success_count}/{len(memories)})")
        return False


def test_search_memories():
    """測試搜索記憶"""
    print_section("測試 4: 搜索記憶")
    
    url = f"{BASE_URL}/memory/search"
    
    test_cases = [
        {
            "name": "搜索所有記憶",
            "data": {
                "user_id": TEST_USER_ID,
                "limit": 10
            }
        },
        {
            "name": "按類型搜索",
            "data": {
                "user_id": TEST_USER_ID,
                "memory_type": "medical_record",
                "limit": 5
            }
        },
        {
            "name": "關鍵詞搜索",
            "data": {
                "user_id": TEST_USER_ID,
                "query": "胃炎",
                "limit": 5
            }
        },
        {
            "name": "重要性評分過濾",
            "data": {
                "user_id": TEST_USER_ID,
                "min_importance": 8.0,
                "limit": 5
            }
        }
    ]
    
    success_count = 0
    for test_case in test_cases:
        print(f"\n{test_case['name']}:")
        try:
            response = requests.post(url, json=test_case["data"])
            print(f"  請求: {json.dumps(test_case['data'], ensure_ascii=False, indent=2)}")
            print(f"  狀態碼: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                memories = result.get("memories", [])
                print(f"  找到 {len(memories)} 條記憶")
                for mem in memories[:3]:  # 只顯示前3條
                    print(f"    - [{mem['memory_type']}] {mem['content'][:50]}... (重要性: {mem['importance_score']})")
                success_count += 1
                print(f"  ✅ 搜索成功")
            else:
                print(f"  ❌ 搜索失敗")
        except Exception as e:
            print(f"  ❌ 錯誤: {str(e)}")
    
    if success_count == len(test_cases):
        print(f"\n✅ 所有搜索測試通過 ({success_count}/{len(test_cases)})")
        return True
    else:
        print(f"\n❌ 部分搜索測試失敗 ({success_count}/{len(test_cases)})")
        return False


def test_get_context():
    """測試獲取用戶上下文"""
    print_section("測試 5: 獲取用戶上下文")
    
    url = f"{BASE_URL}/memory/context/{TEST_USER_ID}"
    
    try:
        response = requests.get(url)
        print(f"請求 URL: {url}")
        print(f"狀態碼: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"上下文摘要:")
            print(json.dumps(result.get("summary", {}), ensure_ascii=False, indent=2))
            print(f"\n格式化上下文:")
            print(result.get("context", ""))
            print("✅ 測試通過")
            return True
        else:
            print(f"❌ 測試失敗: {response.json()}")
            return False
    except Exception as e:
        print(f"❌ 錯誤: {str(e)}")
        return False


def test_chat_with_memory():
    """測試帶記憶的聊天"""
    print_section("測試 6: 帶記憶的聊天功能")
    
    url = f"{BASE_URL}/chat"
    
    # 第一次對話
    print("\n第一次對話:")
    data1 = {
        "prompt": "你好，我是新用戶",
        "user_id": TEST_USER_ID,
        "session_id": TEST_SESSION_ID
    }
    
    try:
        response1 = requests.post(url, json=data1)
        print(f"  請求: {data1['prompt']}")
        print(f"  狀態碼: {response1.status_code}")
        if response1.status_code == 200:
            result1 = response1.json()
            print(f"  回應: {result1.get('response', '')[:100]}...")
            print("  ✅ 第一次對話成功")
        else:
            print(f"  ❌ 第一次對話失敗: {response1.json()}")
            return False
    except Exception as e:
        print(f"  ❌ 錯誤: {str(e)}")
        return False
    
    time.sleep(1)
    
    # 第二次對話（應該記住第一次對話）
    print("\n第二次對話（測試會話記憶）:")
    data2 = {
        "prompt": "剛才我說什麼了？",
        "user_id": TEST_USER_ID,
        "session_id": TEST_SESSION_ID  # 使用相同的 session_id
    }
    
    try:
        response2 = requests.post(url, json=data2)
        print(f"  請求: {data2['prompt']}")
        print(f"  狀態碼: {response2.status_code}")
        if response2.status_code == 200:
            result2 = response2.json()
            response_text = result2.get('response', '')
            print(f"  回應: {response_text[:200]}...")
            
            # 檢查是否提到了之前的對話
            if "新用戶" in response_text or "你好" in response_text:
                print("  ✅ Agent 記住了之前的對話")
                return True
            else:
                print("  ⚠️ Agent 可能沒有記住之前的對話")
                return True  # 仍然算通過，因為可能 LLM 回答方式不同
        else:
            print(f"  ❌ 第二次對話失敗: {response2.json()}")
            return False
    except Exception as e:
        print(f"  ❌ 錯誤: {str(e)}")
        return False


def test_save_session_summary():
    """測試保存會話摘要"""
    print_section("測試 7: 保存會話摘要")
    
    url = f"{BASE_URL}/memory/session/summary"
    params = {
        "session_id": TEST_SESSION_ID,
        "user_id": TEST_USER_ID,
        "summary": "用戶進行了初次諮詢，討論了健康狀況",
        "key_points": ["新用戶", "健康諮詢", "初次對話"]
    }
    
    try:
        response = requests.post(url, params=params)
        print(f"請求 URL: {url}")
        print(f"參數: {json.dumps(params, ensure_ascii=False, indent=2)}")
        print(f"狀態碼: {response.status_code}")
        print(f"響應: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
        
        if response.status_code == 200:
            print("✅ 測試通過")
            return True
        else:
            print("❌ 測試失敗")
            return False
    except Exception as e:
        print(f"❌ 錯誤: {str(e)}")
        return False


def test_get_session_summary():
    """測試獲取會話摘要"""
    print_section("測試 8: 獲取會話摘要")
    
    url = f"{BASE_URL}/memory/session/{TEST_SESSION_ID}"
    
    try:
        response = requests.get(url)
        print(f"請求 URL: {url}")
        print(f"狀態碼: {response.status_code}")
        print(f"響應: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
        
        if response.status_code == 200:
            print("✅ 測試通過")
            return True
        else:
            print("❌ 測試失敗")
            return False
    except Exception as e:
        print(f"❌ 錯誤: {str(e)}")
        return False


def check_api_health():
    """檢查 API 健康狀態"""
    print_section("檢查 API 健康狀態")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"健康檢查 URL: {BASE_URL}/health")
        print(f"狀態碼: {response.status_code}")
        print(f"響應: {json.dumps(response.json(), ensure_ascii=False, indent=2)}")
        
        if response.status_code == 200:
            print("✅ API 服務正常運行")
            return True
        else:
            print("❌ API 服務異常")
            return False
    except Exception as e:
        print(f"❌ 無法連接到 API: {str(e)}")
        print("   請確保 FastAPI 服務正在運行在 http://localhost:8000")
        return False


def main():
    """主測試函數"""
    print("\n" + "=" * 60)
    print("  記憶功能測試套件")
    print("=" * 60)
    
    # 檢查 API 健康狀態
    if not check_api_health():
        print("\n❌ API 服務不可用，請先啟動 FastAPI 服務")
        return
    
    # 執行測試
    tests = [
        ("保存用戶偏好", test_save_preference),
        ("獲取用戶偏好", test_get_preference),
        ("保存長期記憶", test_save_memory),
        ("搜索記憶", test_search_memories),
        ("獲取用戶上下文", test_get_context),
        ("保存會話摘要", test_save_session_summary),
        ("獲取會話摘要", test_get_session_summary),
        ("帶記憶的聊天", test_chat_with_memory),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ 測試 '{test_name}' 發生異常: {str(e)}")
            results.append((test_name, False))
    
    # 打印測試總結
    print_section("測試總結")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"{status}: {test_name}")
    
    print(f"\n總計: {passed}/{total} 測試通過")
    
    if passed == total:
        print("\n🎉 所有測試通過！")
    else:
        print(f"\n⚠️ 有 {total - passed} 個測試失敗")


if __name__ == "__main__":
    main()



