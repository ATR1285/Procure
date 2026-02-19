"""
Tool Registry System for Procure-IQ

Manages registration, discovery, and execution of tools for AI agent.
Provides a centralized registry for all available tools with schema validation.
"""

from typing import Dict, List, Callable, Optional, Any
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Central registry for AI agent tools.
    
    Manages tool registration, discovery, and execution with schema validation.
    """
    
    _instance = None
    _tools: Dict[str, Dict[str, Any]] = {}
    
    def __new__(cls):
        """Singleton pattern to ensure single registry instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register(
        self,
        name: str,
        function: Callable,
        description: str,
        parameters: Dict[str, Any]
    ):
        """
        Register a tool in the registry.
        
        Args:
            name: Tool name (unique identifier)
            function: Python function to execute
            description: Human-readable description
            parameters: JSON schema for parameters
        """
        self._tools[name] = {
            "function": function,
            "description": description,
            "parameters": parameters
        }
        logger.info(f"Registered tool: {name}")
    
    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get tool by name.
        
        Args:
            name: Tool name
        
        Returns:
            Tool dict or None if not found
        """
        return self._tools.get(name)
    
    def list_tools(self) -> List[str]:
        """
        List all registered tool names.
        
        Returns:
            List of tool names
        """
        return list(self._tools.keys())
    
    def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all registered tools.
        
        Returns:
            Dict of all tools
        """
        return self._tools.copy()
    
    def execute(self, name: str, params: Dict[str, Any]) -> Any:
        """
        Execute a tool with given parameters.
        
        Args:
            name: Tool name
            params: Tool parameters
        
        Returns:
            Tool execution result
        
        Raises:
            ValueError: If tool not found
            Exception: If tool execution fails
        """
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found in registry")
        
        try:
            logger.info(f"Executing tool: {name} with params: {params}")
            result = tool["function"](**params)
            logger.info(f"Tool {name} executed successfully")
            return result
        except Exception as e:
            logger.error(f"Tool {name} execution failed: {e}")
            raise
    
    def get_gemini_schemas(self) -> List[Dict[str, Any]]:
        """
        Get tool schemas in Gemini function calling format.
        
        Returns:
            List of Gemini-compatible tool schemas
        """
        schemas = []
        for name, tool in self._tools.items():
            schemas.append({
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"]
            })
        return schemas
    
    def get_openai_schemas(self) -> List[Dict[str, Any]]:
        """
        Get tool schemas in OpenAI function calling format.
        
        Returns:
            List of OpenAI-compatible tool schemas
        """
        schemas = []
        for name, tool in self._tools.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool["description"],
                    "parameters": tool["parameters"]
                }
            })
        return schemas


# Global registry instance
_registry = ToolRegistry()


def register_tool(
    name: str,
    description: str,
    parameters: Dict[str, Any]
):
    """
    Decorator for registering tools.
    
    Usage:
        @register_tool(
            name="my_tool",
            description="Does something useful",
            parameters={...}
        )
        def my_tool(arg1: str, arg2: int):
            return {"result": "success"}
    """
    def decorator(func: Callable):
        _registry.register(name, func, description, parameters)
        return func
    return decorator


def get_registry() -> ToolRegistry:
    """Get the global tool registry instance."""
    return _registry
