from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol


ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]


class LLMClient(Protocol):

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict,
        tools: list[dict[str, Any]] | None = None,
        tool_handlers: dict[str, ToolHandler] | None = None,
    ) -> dict:
        ...