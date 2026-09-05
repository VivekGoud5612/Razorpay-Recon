from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from openai import AsyncOpenAI


ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]


class _ToolCallingUnsupported(Exception):
    """Raised when the provider rejects a `responses.create` call that
    combines `tools` with strict `text.format.json_schema` output -- this is
    the HuggingFace-hosted `responses` endpoint returning
    status="failed"/422 on the very first round, before any tool actually
    ran. Confirmed live for the currently configured model/provider. Only
    raised for a first-round rejection; a failure after tool calls have
    already been exchanged is a real error, not silently swallowed.
    """


class HuggingFaceLLMClient:

    def __init__(
        self,
        api_key: str,
        model: str,
    ) -> None:
        self._client = AsyncOpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=api_key,
            timeout=60.0,
        )
        self._model = model

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict,
        tools: list[dict[str, Any]] | None = None,
        tool_handlers: dict[str, ToolHandler] | None = None,
    ) -> dict:
        if tools:
            try:
                return await self._complete_with_tools(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=response_schema,
                    tools=tools,
                    tool_handlers=tool_handlers or {},
                )
            except _ToolCallingUnsupported:
                # The provider rejected tools+structured-output outright,
                # before any document was ever retrieved. Fall back to a
                # plain structured completion so the investigation still
                # runs -- document-tool access just isn't available this
                # round, which is no worse than the previous (tools=None)
                # behavior.
                pass

        return await self._complete_without_tools(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=response_schema,
        )

    async def _complete_without_tools(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict,
    ) -> dict:
        completion = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "investigation_response",
                    "schema": response_schema,
                    "strict": True,
                },
            },
        )

        content = completion.choices[0].message.content

        if not content:
            raise RuntimeError(
                "HF returned an empty investigation response"
            )

        return json.loads(content)

    # Hard ceiling on tool-call round trips per investigation. A well-behaved
    # investigation needs at most a couple of document lookups; this exists
    # only to guarantee termination if a model gets stuck re-calling tools
    # instead of returning a final response.
    _MAX_TOOL_ROUNDS = 6

    async def _complete_with_tools(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict,
        tools: list[dict[str, Any]] | None = None,
        tool_handlers: dict[str, ToolHandler] | None = None,
    ) -> dict:
        input_items: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": user_prompt,
            }
        ]

        handlers = tool_handlers or {}

        for round_index in range(self._MAX_TOOL_ROUNDS):
            response = await self._client.responses.create(
                model=self._model,
                instructions=system_prompt,
                input=input_items,
                tools=tools or [],
                tool_choice="auto" if tools else None,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "investigation_response",
                        "strict": True,
                        "schema": response_schema,
                    }
                },
            )

            if getattr(response, "status", "completed") != "completed":
                if round_index == 0:
                    raise _ToolCallingUnsupported(
                        getattr(response, "error", None)
                    )
                raise RuntimeError(
                    f"Investigation tool-calling request failed mid-"
                    f"conversation: {getattr(response, 'error', None)}"
                )

            input_items.extend(response.output)

            tool_calls = [
                item
                for item in response.output
                if getattr(item, "type", None) == "function_call"
            ]

            if not tool_calls:
                return json.loads(response.output_text)

            for tool_call in tool_calls:
                handler = handlers.get(tool_call.name)

                if handler is None:
                    raise RuntimeError(
                        f"Unknown investigation tool: {tool_call.name}"
                    )

                arguments = json.loads(tool_call.arguments)
                result = await handler(arguments)

                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": tool_call.call_id,
                        "output": result,
                    }
                )

        raise RuntimeError(
            f"Investigation exceeded {self._MAX_TOOL_ROUNDS} tool-call rounds "
            "without producing a final response."
        )