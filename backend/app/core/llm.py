"""LangChain-based LLM client for structured outputs."""

from typing import TypeVar

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from .config import get_settings

T = TypeVar("T", bound=BaseModel)

_llm_instance: ChatOpenAI | None = None


def get_llm() -> ChatOpenAI:
    """Get or create the LangChain ChatOpenAI instance."""
    global _llm_instance
    if _llm_instance is None:
        settings = get_settings()
        _llm_instance = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
        )
    return _llm_instance


async def generate_structured_output(
    prompt: str,
    output_schema: type[T],
    system_prompt: str | None = None,
    temperature: float | None = None,
) -> T:
    """Generate structured output from the LLM.
    """
    llm = get_llm()
    if temperature is not None:
        settings = get_settings()
        llm = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
        )
    structured_llm = llm.with_structured_output(output_schema)

    messages: list[tuple[str, str]] = []
    if system_prompt:
        messages.append(("system", system_prompt))
    messages.append(("user", prompt))

    result = await structured_llm.ainvoke(messages)
    return result  # type: ignore[return-value]
