"""
AI-powered invoice analysis using the unified AIClient.

This module replaces the old Ollama integration with the new AIClient
that supports Gemini 1.5 Pro (primary), GPT-4o (fallback), and rule-based fallback.

The analyze_invoice_with_ai function maintains the same interface for backward
compatibility but now uses the more robust AIClient underneath.
"""

import json
import re
from ..agent.ai_client import get_ai_client


async def analyze_invoice_with_ai(raw_vendor: str, amount: float, vendors: list, raw_text: str = None):
    """
    AI-powered invoice analysis with vendor matching and data extraction.
    
    Uses the unified AIClient which provides:
    - Primary: Google Gemini 1.5 Pro
    - Fallback: OpenAI GPT-4o
    - Final fallback: Rule-based logic
    
    Args:
        raw_vendor: Raw vendor name from invoice
        amount: Invoice amount
        vendors: List of known vendors from database
        raw_text: Optional raw email content for extraction
    
    Returns:
        Dict with:
            - best_match_id: Matched vendor ID or None
            - extracted_vendor: Cleaned vendor name
            - extracted_amount: Verified/extracted amount
            - confidence: Match confidence (0-100)
            - reasoning: Explanation of decision
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
    
    system_instruction = """You are a procurement AI assistant specializing in invoice analysis and vendor matching. 
    Always return valid JSON with no markdown fences or explanations."""
    
    try:
        # Use the unified AI client
        client = get_ai_client()
        response = await client.complete(
            prompt=prompt,
            system=system_instruction,
            json_mode=True,
            temperature=0.3,  # Lower temperature for more deterministic matching
            max_tokens=500
        )
        
        # Log the response for debugging
        print(f"\n--- AI RESPONSE ({response.model_used}) ---")
        print(f"Content: {response.content}")
        print(f"Tokens: {response.tokens_used}, Cost: ${response.cost_usd:.4f}")
        print(f"Latency: {response.latency_ms}ms")
        if response.fallback_used:
            print(f"[FALLBACK USED]")
        print(f"-----------------------------------\n")
        
        # Parse the JSON response
        # Try direct JSON parse first
        try:
            return json.loads(response.content)
        except json.JSONDecodeError:
            # Fallback: extract JSON from markdown fences or text
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response.content, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            
            # Try to find any JSON object in the response
            match = re.search(r"(\{.*?\})", response.content, re.DOTALL)
            if match:
                return json.loads(match.group(1))
            
            # If all parsing fails, return error
            raise ValueError("Could not extract valid JSON from AI response")
                
    except Exception as e:
        print(f"[ERROR] AI Extraction Failed: {str(e)}")
        
        # Return rule-based fallback result
        # Simple heuristic: check for exact or partial name match
        best_match = None
        best_score = 0
        
        raw_lower = raw_vendor.lower().strip()
        for vendor in vendors:
            vendor_lower = vendor['name'].lower().strip()
            
            if raw_lower == vendor_lower:
                best_match = vendor['id']
                best_score = 100
                break
            elif raw_lower in vendor_lower or vendor_lower in raw_lower:
                if len(raw_lower) > best_score:  # Longer match = better
                    best_match = vendor['id']
                    best_score = 85
        
        return {
            "best_match_id": best_match,
            "extracted_vendor": raw_vendor,
            "extracted_amount": amount,
            "confidence": best_score,
            "reasoning": f"Rule-based fallback: {str(e)}"
        }
