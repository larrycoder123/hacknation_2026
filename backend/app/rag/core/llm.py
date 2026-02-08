"""LLM provider for RAG component."""

from dataclasses import dataclass
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from .config import settings

T = TypeVar("T", bound=BaseModel)


@dataclass
class TokenUsage:
    """Minimal token usage tracking (replaces agentic_backend.logging.TokenUsage)."""

    input: int = 0
    output: int = 0
    model: str = ""

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input=self.input + other.input,
            output=self.output + other.output,
            model=other.model or self.model,
        )


class LLM:
    """OpenAI chat wrapper with structured output support and token tracking."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_chat_model
        self._client: OpenAI | None = None
        self._last_usage: TokenUsage | None = None
        self._total_usage: TokenUsage = TokenUsage()

    @property
    def client(self) -> OpenAI:
        """Lazy-load OpenAI client."""
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    @property
    def last_usage(self) -> TokenUsage | None:
        """Token usage from the most recent API call."""
        return self._last_usage

    @property
    def total_usage(self) -> TokenUsage:
        """Cumulative token usage across all API calls."""
        return self._total_usage

    def reset_usage(self) -> None:
        """Reset token usage counters."""
        self._last_usage = None
        self._total_usage = TokenUsage()

    def _track_usage(self, response) -> None:
        """Extract and track token usage from API response."""
        if hasattr(response, "usage") and response.usage:
            self._last_usage = TokenUsage(
                input=response.usage.prompt_tokens,
                output=response.usage.completion_tokens,
                model=getattr(response, "model", self.model),
            )
            self._total_usage = self._total_usage + self._last_usage

    def chat(
        self,
        messages: list[dict[str, str]],
        response_model: type[T] | None = None,
        temperature: float = 0.0,
    ) -> str | T:
        """Send chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            response_model: Optional Pydantic model for structured output
            temperature: Sampling temperature

        Returns:
            String response or parsed Pydantic model instance
        """
        if response_model is not None:
            response = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,
                response_format=response_model,
                temperature=temperature,
            )
            self._track_usage(response)
            return response.choices[0].message.parsed

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        self._track_usage(response)
        return response.choices[0].message.content

    def summarize(self, text: str, max_sentences: int = 3) -> str:
        """Generate a summary of the given text.

        Args:
            text: Text to summarize
            max_sentences: Maximum sentences in summary

        Returns:
            Summary string
        """
        messages = [
            {
                "role": "system",
                "content": f"You are a helpful assistant. Summarize the following text in {max_sentences} sentences or fewer. Be concise and capture the main points.",
            },
            {"role": "user", "content": text},
        ]
        return self.chat(messages)
