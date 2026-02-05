
import os
import base64
from dotenv import load_dotenv
from openai import OpenAI

def test_openai():
    # 1. 加载环境变量
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    print(f"Loaded API Key: {api_key[:5]}...{api_key[-5:] if api_key else 'None'}")
    print(f"Base URL: {base_url}")
    print(f"Model: {model_name}")

    if not api_key or "xxxx" in api_key:
        print("[ERROR] Please set a valid OPENAI_API_KEY in .env")
        return

    # 2. 配置 Client
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    # 3. 发送测试请求 (Text only)
    print(f"Sending test prompt to {model_name}...")
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "user", "content": "Hello, are you working?"}
            ],
            max_tokens=50
        )
        msg = response.choices[0].message.content
        # 过滤非 ASCII 字符以兼容 Windows 终端
        safe_msg = msg.encode('ascii', errors='ignore').decode('ascii')
        print(f"[OK] Response received: {safe_msg}")
    except Exception as e:
        print(f"[ERROR] Generation Error: {e}")

if __name__ == "__main__":
    test_openai()
