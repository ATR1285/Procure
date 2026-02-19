import asyncio
import os
from dotenv import load_dotenv
import sys

sys.path.append(os.getcwd())

from app.agent.ai_client import get_ai_client

async def test_openrouter():
    load_dotenv()
    
    key = os.environ.get("OPENROUTER_API_KEY")
    print(f"OpenRouter Key: {'Found (' + key[:12] + '...)' if key else 'NOT FOUND'}")
    
    print("\nTesting OpenRouter API connection...")
    client = get_ai_client()
    
    # Run the built-in health check
    try:
        health = await client.health_check()
        print(f"Health Check: {health}")
    except Exception as e:
        print(f"Health check crashed: {e}")
        return
    
    if health.get("openrouter") == "ok":
        print(f"\n✅ SUCCESS: OpenRouter API is working!")
        print(f"   Model: {health.get('model')}")
        print(f"   Latency: {health.get('latency_ms')}ms")
        
        # Test a real completion
        print("\nSending test prompt to Gemini via OpenRouter...")
        response = await client.complete(
            prompt="Just say 'Gemini is ready for Procure-IQ!' and nothing else.",
            system="You are a helpful assistant.",
            temperature=0.1,
            max_tokens=50
        )
        print(f"Response: {response.content}")
        print(f"Model: {response.model_used}")
        print(f"Tokens: {response.tokens_used}")
    else:
        print(f"\n❌ FAILED: {health.get('openrouter')}")

if __name__ == "__main__":
    asyncio.run(test_openrouter())
