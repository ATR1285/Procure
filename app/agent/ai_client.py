import asyncio
import time
import logging
import json
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

# External SDKs
import google.generativeai as genai
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
    Unified AI Client for Procure-IQ.
    
    Combines Local and Remote capabilities:
    1. OpenRouter (Gemini 2.0 Flash) - Primary [Remote]
    2. Gemini 1.5 Pro (Direct Google SDK) - Secondary [Local]
    3. GPT-4o (Direct OpenAI SDK) - Fallback [Local]
    4. Rule-based - Final Fallback
    """
    
    def __init__(self):
        self.gemini_key = os.environ.get("GEMINI_API_KEY")
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        self.openrouter_key = os.environ.get("OPENROUTER_API_KEY")
        
        # 1. Initialize OpenRouter (Primary)
        self.client = None
        if self.openrouter_key:
            self.client = AsyncOpenAI(
                api_key=self.openrouter_key,
                base_url="https://openrouter.ai/api/v1"
            )
            logger.info("OpenRouter AI Client initialized (Gemini 2.0 Flash via OpenRouter)")
            
        # 2. Initialize Gemini Direct (Secondary)
        self.gemini_model = None
        if self.gemini_key:
            genai.configure(api_key=self.gemini_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            logger.info("Gemini 1.5 Flash (Direct) initialized.")
            
        # 3. Initialize OpenAI Direct (Fallback)
        self.openai_client = None
        if self.openai_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_key)
            logger.info("GPT-4o (Direct) initialized.")

        self.primary_model = "google/gemini-2.0-flash-001"
        self.fallback_model = "google/gemini-2.5-flash-preview"

        # Cost tracking (approximate)
        self.costs = {
            "gemini-1.5-pro": {"input": 0.00035, "output": 0.00105}, # Per 1k
            "gpt-4o": {"input": 0.005, "output": 0.015} # Per 1k
        }

    async def complete(
        self, 
        prompt: str, 
        system: str = None, 
        json_mode: bool = False,
        temperature: float = 0.1,
        max_tokens: int = 1000
    ) -> AIResponse:
        """Execute a completion with robust fallback chain."""
        start_time = time.time()
        
        # 1. Try OpenRouter (Primary)
        if self.client:
            response = await self._retry_call(
                self._call_openrouter, prompt, system, json_mode, 
                self.primary_model, temperature, max_tokens
            )
            if response:
                return response
        
        # 2. Try Gemini Direct (Secondary)
        if self.gemini_model:
            logger.warning("Primary (OpenRouter) failed/missing, trying Gemini Direct")
            response = await self._retry_call(
                self._call_gemini, prompt, system, json_mode
            )
            if response:
                response.fallback_used = True
                return response

        # 3. Try GPT-4o Direct (Fallback)
        if self.openai_client:
            logger.warning("Gemini Direct failed/missing, trying GPT-4o Direct")
            response = await self._retry_call(
                self._call_gpt4o, prompt, system, json_mode
            )
            if response:
                response.fallback_used = True
                return response

        # 4. Final Rule-based Fallback
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
                # If it's the final attempt, verify if we should raise or just return None to trigger next fallback
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

    async def _call_gemini(self, prompt, system, json_mode):
        """Gemini 1.5 Pro Implementation (Direct)."""
        config = genai.types.GenerationConfig(
            temperature=0.1, # Forced to 0.1 for reliability
            response_mime_type="application/json" if json_mode else "text/plain"
        )
        
        full_prompt = f"System: {system}\n\n{prompt}" if system else prompt
        
        start = time.time()
        # Non-async SDK - wrap in thread
        response = await asyncio.to_thread(
            self.gemini_model.generate_content,
            full_prompt,
            generation_config=config
        )
        
        latency = int((time.time() - start) * 1000)
        tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0
        
        # Rough cost calculation
        cost = (tokens / 1000) * self.costs["gemini-1.5-pro"]["input"]

        logger.info(f"Gemini Direct call: {tokens} tokens, {latency}ms")
        
        return AIResponse(
            content=response.text,
            model_used="gemini-1.5-pro-direct",
            latency_ms=latency,
            tokens_used=tokens,
            cost_usd=cost,
            fallback_used=False
        )

    async def _call_gpt4o(self, prompt, system, json_mode):
        """GPT-4o Implementation (Direct)."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        start = time.time()
        response = await self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"} if json_mode else {"type": "text"}
        )
        
        latency = int((time.time() - start) * 1000)
        tokens = response.usage.total_tokens
        cost = (tokens / 1000) * self.costs["gpt-4o"]["input"]

        logger.info(f"GPT-4o Direct call: {tokens} tokens, {latency}ms")

        return AIResponse(
            content=response.choices[0].message.content,
            model_used="gpt-4o-direct",
            latency_ms=latency,
            tokens_used=tokens,
            cost_usd=cost,
            fallback_used=True
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
        """Quickly test all configured APIs."""
        results = {}
        
        # Check OpenRouter
        if self.client:
            try:
                response = await self._call_openrouter(
                    "Say OK", "test", False, self.primary_model, 0.1, 10
                )
                if response:
                    results["openrouter"] = "ok"
                else:
                    results["openrouter"] = "fail"
            except Exception as e:
                results["openrouter"] = f"fail: {str(e)}"
        else:
             results["openrouter"] = "not_configured"

        # Check Gemini Direct
        if self.gemini_model:
            try:
                await self._call_gemini("hi", "test", False)
                results["gemini_direct"] = "ok"
            except Exception as e:
                results["gemini_direct"] = f"fail: {str(e)}"
        else:
             results["gemini_direct"] = "not_configured"

        # Check OpenAI Direct
        if self.openai_client:
            try:
                await self._call_gpt4o("hi", "test", False)
                results["openai_direct"] = "ok"
            except Exception as e:
                results["openai_direct"] = f"fail: {str(e)}"
        else:
            results["openai_direct"] = "not_configured"
            
        return results

# Singleton interface
_client = None
def get_ai_client():
    global _client
    if _client is None:
        _client = AIClient()
    return _client
