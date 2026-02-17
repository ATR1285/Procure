import os
import logging
from typing import List, Dict, Optional, Any
from langchain.memory import ConversationSummaryBufferMemory
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger("AgentMemory")

class AgentMemory:
    """
    Manages agent memory using LangChain's ConversationSummaryBufferMemory.
    
    Provides efficient context management by automatically summarizing older
    parts of the conversation while keeping recent messages in full.
    """
    
    def __init__(self, supplier_id: Optional[str] = None):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found in environment.")

        # Summary model: gemini-1.5-flash for speed and cost efficiency
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=self.api_key
        )
        
        # Core LangChain memory
        self.memory = ConversationSummaryBufferMemory(
            llm=self.llm,
            max_token_limit=2000,
            return_messages=True
        )
        
        # Per-supplier memory dict
        self.supplier_memories = {}
        
        # Generic decision storage
        self.decision_dict = {}

    def add_agent_action(self, action: str, result: str):
        """Save an agent action and its result to memory."""
        self.memory.save_context(
            {"input": f"ACTION: {action}"},
            {"output": f"RESULT: {result}"}
        )
        logger.debug(f"Memorized action: {action[:50]}...")

    def get_context_for_decision(self, context_type: str) -> str:
        """Return the current history as a string."""
        history = self.memory.load_memory_variables({})
        messages = history.get("history", [])
        
        context_str = f"CONTEXT TYPE: {context_type}\n"
        for msg in messages:
            role = "User" if isinstance(msg, HumanMessage) else "AI"
            context_str += f"{role}: {msg.content}\n"
            
        return context_str

    def get_context_with_summary(self, messages: list) -> str:
        """
        Custom summarization logic for long sessions.
        
        Reduces token usage by summarizing history older than 15 messages.
        """
        if len(messages) <= 15:
            return "\n".join([f"{m.get('role')}: {m.get('content')}" for m in messages])

        # Separate early messages and last 5
        early_messages = messages[:-5]
        recent_messages = messages[-5:]

        # Call Gemini to summarize early history
        summary_prompt = "Summarize the following conversation history in exactly 3 sentences:\n\n"
        for m in early_messages:
            summary_prompt += f"{m.get('role')}: {m.get('content')}\n"

        try:
            summary_response = self.llm.invoke([HumanMessage(content=summary_prompt)])
            summary = summary_response.content
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            summary = "Error generating summary of early context."

        # Format final output
        recent_str = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in recent_messages])
        
        return f"SUMMARY OF EARLIER CONTEXT: {summary}\n\nRECENT:\n{recent_str}"

    def get_supplier_context(self, supplier_email: str) -> str:
        """Retrieve recent interactions for a specific supplier."""
        interactions = self.supplier_memories.get(supplier_email, [])
        if not interactions:
            return "No previous interactions with this supplier."
        
        return "\n".join(interactions[-5:])

    def add_supplier_interaction(self, supplier_email: str, interaction: str):
        """Store interaction in the per-supplier memory dict."""
        if supplier_email not in self.supplier_memories:
            self.supplier_memories[supplier_email] = []
        
        self.supplier_memories[supplier_email].append(
            f"[{datetime.now().strftime('%Y-%m-%d')}] {interaction}"
        )

    def remember_owner_decision(self, item_id, amount, decision, threshold):
        """Store a specific owner decision in the local dict."""
        key = f"{item_id}_{datetime.now().timestamp()}"
        self.decision_dict[key] = {
            "item_id": item_id,
            "amount": amount,
            "decision": decision,
            "threshold": threshold,
            "timestamp": datetime.now().isoformat()
        }
        logger.info(f"Remembered decision for item {item_id}: {decision}")

# Global instance
_memory = None

def get_memory() -> AgentMemory:
    global _memory
    if _memory is None:
        _memory = AgentMemory()
    return _memory
from datetime import datetime
