"""
OpenAI-compatible LLM Client Module.

This module provides a modular, reusable client for interacting with 
OpenAI-compatible LLM APIs (OpenAI, Azure OpenAI, Local LLMs like Ollama, etc.)
"""

from typing import List, Optional, Dict, Any, TypeVar, Type
from pydantic import BaseModel
import httpx
import json
from .config import get_settings

T = TypeVar("T", bound=BaseModel)

class LLMMessage(BaseModel):
    """A single message in the conversation context."""
    role: str  # "system", "user", or "assistant"
    content: str

class LLMClient:
    """
    A modular client for OpenAI-compatible LLM APIs.
    
    Supports:
    - OpenAI API
    - Azure OpenAI
    - Local LLMs (Ollama, LM Studio, etc.)
    - Any OpenAI-compatible endpoint
    
    Usage:
        client = LLMClient()
        response = await client.chat_completion([
            LLMMessage(role="user", content="Hello!")
        ])
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        """
        Initialize the LLM client.
        
        All parameters are optional and will fall back to settings from config.
        """
        settings = get_settings()
        self.base_url = (base_url or settings.llm_api_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        self.temperature = temperature if temperature is not None else settings.llm_temperature
        self.max_tokens = max_tokens or settings.llm_max_tokens
    
    def _get_headers(self) -> Dict[str, str]:
        """Build request headers with optional API key."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
    
    async def chat_completion(
        self,
        messages: List[LLMMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs: Any,
    ) -> str:
        """
        Send a chat completion request to the LLM.
        
        Args:
            messages: List of conversation messages
            model: Override the default model
            temperature: Override the default temperature
            max_tokens: Override the default max tokens
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            The assistant's response content as a string
        """
        payload = {
            "model": model or self.model,
            "messages": [msg.model_dump() for msg in messages],
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            **kwargs,
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    async def structured_output(
        self,
        messages: List[LLMMessage],
        output_schema: Type[T],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        **kwargs: Any,
    ) -> T:
        """
        Request structured JSON output from the LLM.
        
        Uses response_format for models that support it, otherwise
        parses JSON from the response.
        
        Args:
            messages: List of conversation messages
            output_schema: Pydantic model class for the expected output
            model: Override the default model
            temperature: Override the default temperature
            **kwargs: Additional parameters
            
        Returns:
            Parsed Pydantic model instance
        """
        # Add schema information to the system message
        schema_json = json.dumps(output_schema.model_json_schema(), indent=2)
        schema_instruction = LLMMessage(
            role="system",
            content=f"""You must respond with valid JSON that matches this schema:
{schema_json}

Respond ONLY with the JSON object, no additional text or markdown."""
        )
        
        full_messages = [schema_instruction] + messages
        
        # Request JSON mode if supported
        response_format = kwargs.pop("response_format", None)
        if response_format is None:
            response_format = {"type": "json_object"}
        
        response_text = await self.chat_completion(
            messages=full_messages,
            model=model,
            temperature=temperature or 0.3,  # Lower temp for structured output
            response_format=response_format,
            **kwargs,
        )
        
        # Parse and validate against the schema
        response_data = json.loads(response_text)
        return output_schema.model_validate(response_data)

# Singleton instance for convenience
_default_client: Optional[LLMClient] = None

def get_llm_client() -> LLMClient:
    """Get or create the default LLM client instance."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
