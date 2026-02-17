import httpx
import os
import json
import re

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

async def analyze_invoice_with_ai(raw_vendor: str, amount: float, vendors: list, raw_text: str = None):
    """
    Honest LLM integration for decision-making.
    Uses regex to extract JSON blocks from often-verbose LLM responses.
    If raw_text is provided (from email), it attempts to extract missing fields.
    """
    vendor_str = "\n".join([f"- ID {v['id']}: {v['name']}" for v in vendors])
    
    context = ""
    if raw_text:
        context = f"\nRAW EMAIL CONTENT:\n{raw_text}\n"

    prompt = f"""
    You are an autonomous procurement agent.
    Task: Match the raw vendor name '{raw_vendor}' to one of these known vendors:
    {vendor_str}
    
    Initial Invoice Amount: {amount}
    {context}
    
    If raw email content is provided, please verify or extract the CORRECT vendor name and total amount from the text.
    
    Return ONLY a JSON object in this format:
    {{
      "best_match_id": int or null,
      "extracted_vendor": "string",
      "extracted_amount": float,
      "confidence": 0-100,
      "reasoning": "string"
    }}
    """
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                timeout=30.0
            )
            result = response.json()
            raw_text = result.get("response", "")
            
            # DEBUG PRINT: So we can see exactly what the AI says in the server console
            print(f"\n--- RAW AI RESPONSE ---\n{raw_text}\n-----------------------\n")
            
            # Non-greedy extraction to find the first valid JSON block
            match = re.search(r"(\{.*?\})", raw_text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            else:
                return json.loads(raw_text)
                
    except Exception as e:
        print(f"❌ AI Extraction Failed: {str(e)}")
        return {"best_match_id": None, "confidence": 0, "reasoning": f"AI Logic Error: {str(e)}"}
