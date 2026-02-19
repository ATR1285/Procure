import asyncio
import time
import logging
import json
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from openai import AsyncOpenAI

logger = logging.getLogger("AIClient")

@dataclass
class AIResponse:
    """Response from AI model with metadata."""
    content: str
    model_used: str
    latency_ms: int
    tokens_used: int
    cost_usd: float
    fallback_used: bool
    error: Optional[str] = None

class AIClient:
    """
    Optimized AI client for Procure-IQ.
    
    Uses OpenRouter API to access cloud models:
    1. Google Gemini 2.0 Flash (Primary via OpenRouter)
    2. Rule-based (Final Fallback)
    """
    
    def __init__(self):
        self.openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        
        # Initialize OpenRouter client (OpenAI-compatible)
        self.client = None
        if self.openrouter_key:
            self.client = AsyncOpenAI(
                api_key=self.openrouter_key,
                base_url="https://openrouter.ai/api/v1"
            )
            logger.info("OpenRouter AI Client initialized (Gemini 2.0 Flash via OpenRouter)")
        else:
            logger.warning("No OPENROUTER_API_KEY found - AI features will use rule-based fallback")

        self.primary_model = "google/gemini-2.0-flash-001"
        self.fallback_model = "google/gemini-2.5-flash-preview"

    async def complete(
        self, 
        prompt: str, 
        system: str = None, 
        json_mode: bool = False,
        temperature: float = 0.1,
        max_tokens: int = 1000
    ) -> AIResponse:
        """Execute a completion with automatic fallback and retry logic."""
        start_time = time.time()
        
        if self.client:
            # Try primary model
            response = await self._retry_call(
                self._call_openrouter, prompt, system, json_mode, 
                self.primary_model, temperature, max_tokens
            )
            if response:
                return response

            # Try fallback model
            logger.warning(f"Primary model failed, trying fallback: {self.fallback_model}")
            response = await self._retry_call(
                self._call_openrouter, prompt, system, json_mode,
                self.fallback_model, temperature, max_tokens
            )
            if response:
                response.fallback_used = True
                return response

        # Final Rule-based Fallback
        return self._rule_based_fallback(prompt, start_time)

    async def complete_with_memory(
        self, 
        prompt: str, 
        history: List[Dict[str, str]], 
        system: str = None
    ) -> AIResponse:
        """Execute a completion with conversation history."""
        context = ""
        for msg in history:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            context += f"{role}: {content}\n"
        
        full_prompt = f"HISTORY:\n{context}\n\nNEW PROMPT: {prompt}"
        return await self.complete(full_prompt, system=system)

    async def _retry_call(self, func, *args):
        """Standardized retry logic: 2 retries with exponential backoff (1s, 2s)."""
        for attempt in range(3):
            try:
                return await func(*args)
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Final attempt failed for {func.__name__}: {e}")
                    return None
                delay = 1 if attempt == 0 else 2
                logger.warning(f"Attempt {attempt+1} failed for {func.__name__}. Retrying in {delay}s... Error: {e}")
                await asyncio.sleep(delay)
        return None

    async def _call_openrouter(self, prompt, system, json_mode, model, temperature, max_tokens):
        """OpenRouter API call (OpenAI-compatible)."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        start = time.time()
        
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(**kwargs)
        
        latency = int((time.time() - start) * 1000)
        tokens = response.usage.total_tokens if response.usage else 0
        cost = 0.0  # OpenRouter handles billing

        logger.info(f"OpenRouter [{model}]: {tokens} tokens, {latency}ms")

        return AIResponse(
            content=response.choices[0].message.content,
            model_used=model,
            latency_ms=latency,
            tokens_used=tokens,
            cost_usd=cost,
            fallback_used=False
        )

    def _rule_based_fallback(self, prompt: str, start_time: float) -> AIResponse:
        """Deterministic fallback when all APIs fail."""
        logger.error("All AI APIs failed - using rule-based fallback")
        
        content = "Error: System unable to process request at this time."
        if "invoice" in prompt.lower():
            content = json.dumps({"is_procurement": True, "doc_type": "invoice", "confidence": 0.5, "error": "AI failed"})
            
        return AIResponse(
            content=content,
            model_used="rule_based",
            latency_ms=int((time.time() - start_time) * 1000),
            tokens_used=0,
            cost_usd=0.0,
            fallback_used=True,
            error="API_FAILURE"
        )

    async def health_check(self) -> dict:
        """Quickly test the OpenRouter API."""
        results = {"openrouter": "not_configured"}
        
        if self.client:
            try:
                response = await self._call_openrouter(
                    "Say OK", "test", False, self.primary_model, 0.1, 10
                )
                if response:
                    results["openrouter"] = "ok"
                    results["model"] = response.model_used
                    results["latency_ms"] = response.latency_ms
                else:
                    results["openrouter"] = "fail"
            except Exception as e:
                logger.error(f"OpenRouter Health Check Failed: {e}")
                results["openrouter"] = f"fail: {str(e)}"
            
        return results

# Singleton interface
_client = None
def get_ai_client():
    global _client
    if _client is None:
        _client = AIClient()
    return _client
