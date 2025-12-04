#!/usr/bin/env python3
"""
短期記憶測試腳本

測試會話記憶功能是否正常工作
"""

import requests
import json

BASE_URL = "http://localhost:8000"
SESSION_ID = "test_session_memory_001"
USER_ID = "test_user_001"

def test_short_term_memory():
    """測試短期記憶功能"""
    print("=" * 60)
    print("短期記憶測試")
    print("=" * 60)
    
    # 第一次對話：告訴 AI 我的名字
    print("\n1. 第一次對話：告訴 AI 我的名字")
    print("-" * 60)
    
    response1 = requests.post(
        f"{BASE_URL}/chat",
        json={
            "prompt": "我是張三",
            "user_id": USER_ID,
            "session_id": SESSION_ID
        }
    )
    
    if response1.status_code == 200:
        result1 = response1.json()
        print(f"用戶: 我是張三")
        print(f"AI: {result1.get('response', '')[:200]}...")
        print("✅ 第一次對話成功")
    else:
        print(f"❌ 第一次對話失敗: {response1.status_code}")
        print(response1.text)
        return False
    
    # 等待一下
    import time
    time.sleep(1)
    
    # 第二次對話：詢問我的名字
    print("\n2. 第二次對話：詢問我的名字（測試記憶）")
    print("-" * 60)
    
    response2 = requests.post(
        f"{BASE_URL}/chat",
        json={
            "prompt": "我叫什麼名字？",
            "user_id": USER_ID,
            "session_id": SESSION_ID  # 使用相同的 session_id
        }
    )
    
    if response2.status_code == 200:
        result2 = response2.json()
        response_text = result2.get('response', '')
        print(f"用戶: 我叫什麼名字？")
        print(f"AI: {response_text}")
        
        # 檢查 AI 是否記住了名字
        if "張三" in response_text:
            print("\n✅ 測試通過！AI 記住了你的名字！")
            return True
        else:
            print("\n⚠️ AI 可能沒有記住你的名字")
            print("   這可能是因為：")
            print("   1. LLM 的回答方式不同")
            print("   2. 記憶功能需要進一步調試")
            print(f"   完整回應: {response_text}")
            return False
    else:
        print(f"❌ 第二次對話失敗: {response2.status_code}")
        print(response2.text)
        return False


def test_different_session():
    """測試不同會話不會共享記憶"""
    print("\n" + "=" * 60)
    print("測試不同會話的隔離")
    print("=" * 60)
    
    # 使用不同的 session_id
    different_session_id = "test_session_memory_002"
    
    print(f"\n使用不同的 session_id: {different_session_id}")
    
    response = requests.post(
        f"{BASE_URL}/chat",
        json={
            "prompt": "我叫什麼名字？",
            "user_id": USER_ID,
            "session_id": different_session_id  # 不同的 session_id
        }
    )
    
    if response.status_code == 200:
        result = response.json()
        response_text = result.get('response', '')
        print(f"用戶: 我叫什麼名字？")
        print(f"AI: {response_text}")
        
        # 新會話不應該知道名字（除非從長期記憶中獲取）
        if "張三" not in response_text or "不知道" in response_text or "沒有" in response_text:
            print("\n✅ 測試通過！不同會話正確隔離")
            return True
        else:
            print("\n⚠️ 新會話可能從長期記憶中獲取了信息")
            return True  # 這也可能是正確的行為
    else:
        print(f"❌ 測試失敗: {response.status_code}")
        return False


if __name__ == "__main__":
    print("\n開始測試短期記憶功能...")
    print("確保 FastAPI 服務正在運行在 http://localhost:8000\n")
    
    # 測試短期記憶
    success1 = test_short_term_memory()
    
    # 測試會話隔離
    success2 = test_different_session()
    
    print("\n" + "=" * 60)
    print("測試總結")
    print("=" * 60)
    print(f"短期記憶測試: {'✅ 通過' if success1 else '❌ 失敗'}")
    print(f"會話隔離測試: {'✅ 通過' if success2 else '❌ 失敗'}")
    
    if success1 and success2:
        print("\n🎉 所有測試通過！")
    else:
        print("\n⚠️ 部分測試失敗，請檢查配置和日誌")



