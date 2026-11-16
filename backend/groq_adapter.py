"""Groq API Adapter for Iryax AI Assistant and Orchestration.

Provides an LLMAdapter implementation that connects to the
official Groq cloud API for high-speed inference.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

load_dotenv()

import groq
from groq import AsyncGroq

logger = logging.getLogger(__name__)


# ── Data Types & Contracts ───────────────────────────────────────────────────

@dataclass
class TextBlock:
    text: str


@dataclass
class ToolUseBlock:
    id: str
    name: str
    input: dict[str, Any] = field(default_factory=dict)


ContentBlock = TextBlock | ToolUseBlock


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMMessage:
    role: str
    content: list[ContentBlock] | str


@dataclass
class LLMChatOptions:
    model: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    system_prompt: str | None = None
    tools: list[dict[str, Any]] | None = None
    reasoning_effort: str | None = None


@dataclass
class LLMStreamOptions:
    model: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    system_prompt: str | None = None
    tools: list[dict[str, Any]] | None = None
    reasoning_effort: str | None = None


@dataclass
class LLMResponse:
    id: str
    content: list[ContentBlock]
    model: str
    stop_reason: str
    usage: TokenUsage


@dataclass
class StreamEvent:
    type: str  # "text", "tool_use", "done", "error"
    data: Any


# ── Helpers ──────────────────────────────────────────────────────────────────

def redact_groq_key(text: str, api_key: str | None = None) -> str:
    """Mask any Groq API key patterns from strings to prevent secret leakage."""
    if not text:
        return ""
    if api_key:
        text = text.replace(api_key, "[REDACTED_GROQ_KEY]")
    return re.sub(r"gsk_[A-Za-z0-9_\-]{20,}", "[REDACTED_GROQ_KEY]", text)


def safe_exception_message(e: Exception) -> str:
    return str(e) or type(e).__name__


def parse_json_safe(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except Exception:
        return {}


def map_messages(messages: list[LLMMessage], system_prompt: str | None = None) -> list[dict[str, Any]]:
    oai_msgs: list[dict[str, Any]] = []
    if system_prompt:
        oai_msgs.append({"role": "system", "content": system_prompt})

    for msg in messages:
        if isinstance(msg.content, str):
            content_str = msg.content
        else:
            parts = []
            for b in msg.content:
                if isinstance(b, TextBlock):
                    parts.append(b.text)
                elif isinstance(b, ToolUseBlock):
                    parts.append(f"[tool_use: {b.name} args={json.dumps(b.input)}]")
            content_str = "\n".join(parts)
        oai_msgs.append({"role": msg.role, "content": content_str})
    return oai_msgs


def map_stop_reason(reason: str | None) -> str:
    if reason in ("stop", "end_turn", None):
        return "end_turn"
    if reason in ("tool_calls", "tool_use"):
        return "tool_use"
    if reason in ("length", "max_tokens"):
        return "max_tokens"
    return reason


def parse_token_usage(usage_obj: Any) -> TokenUsage:
    if not usage_obj:
        return TokenUsage()
    inp = getattr(usage_obj, "prompt_tokens", 0) or 0
    out = getattr(usage_obj, "completion_tokens", 0) or 0
    tot = getattr(usage_obj, "total_tokens", inp + out) or (inp + out)
    return TokenUsage(input_tokens=inp, output_tokens=out, total_tokens=tot)


def parse_chat_response(completion: Any) -> tuple[list[ContentBlock], str, TokenUsage]:
    content_blocks: list[ContentBlock] = []
    choice = completion.choices[0]
    msg = choice.message
    if getattr(msg, "content", None):
        content_blocks.append(TextBlock(text=msg.content))
    if getattr(msg, "tool_calls", None):
        for tc in msg.tool_calls:
            content_blocks.append(
                ToolUseBlock(
                    id=getattr(tc, "id", "") or "",
                    name=getattr(tc.function, "name", "") or "",
                    input=parse_json_safe(getattr(tc.function, "arguments", "") or "{}"),
                )
            )
    stop = map_stop_reason(getattr(choice, "finish_reason", "end_turn"))
    usage = parse_token_usage(getattr(completion, "usage", None))
    return content_blocks, stop, usage


# ── GroqAdapter ──────────────────────────────────────────────────────────────

class GroqAdapter:
    """Wraps the official Groq Python SDK into an async inference adapter."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        *,
        client: AsyncGroq | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not self._api_key and client is None:
            raise ValueError(
                "GROQ_API_KEY is not set. Set the GROQ_API_KEY environment variable or pass api_key."
            )
        self._configured_model = model
        if client is not None:
            self._client = client
        else:
            client_kwargs: dict[str, Any] = {"api_key": self._api_key}
            if base_url:
                client_kwargs["base_url"] = base_url
            self._client = AsyncGroq(**client_kwargs)

    @property
    def name(self) -> str:
        return "groq"

    def resolve_model(self, options_model: str | None = None) -> str:
        """Resolve model name from options, adapter config, or environment."""
        resolved = options_model or self._configured_model or os.environ.get("GROQ_MODEL")
        if not resolved:
            raise ValueError(
                "No Groq model specified. Set GROQ_MODEL in environment or pass model in options."
            )
        return resolved

    async def chat(
        self,
        messages: list[LLMMessage],
        options: LLMChatOptions,
        *,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        model = self.resolve_model(options.model)
        oai_msgs = map_messages(messages, options.system_prompt)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": oai_msgs,
        }
        if options.max_tokens is not None:
            kwargs["max_tokens"] = options.max_tokens
        if options.temperature is not None:
            kwargs["temperature"] = options.temperature
        if options.tools:
            kwargs["tools"] = options.tools
        if response_format:
            kwargs["response_format"] = response_format

        try:
            completion = await self._client.chat.completions.create(**kwargs)
            content, stop, usage = parse_chat_response(completion)
            return LLMResponse(
                id=getattr(completion, "id", "") or "completion_id",
                content=content,
                model=getattr(completion, "model", "") or model,
                stop_reason=stop,
                usage=usage,
            )
        except Exception as e:
            msg = redact_groq_key(safe_exception_message(e), self._api_key)
            logger.error("Groq chat error: %s", msg)
            raise RuntimeError(msg) from None

    async def stream(
        self,
        messages: list[LLMMessage],
        options: LLMStreamOptions,
    ) -> AsyncIterator[StreamEvent]:
        model = self.resolve_model(options.model)
        oai_msgs = map_messages(messages, options.system_prompt)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": oai_msgs,
            "stream": True,
        }
        if options.max_tokens is not None:
            kwargs["max_tokens"] = options.max_tokens
        if options.temperature is not None:
            kwargs["temperature"] = options.temperature
        if options.tools:
            kwargs["tools"] = options.tools

        completion_id = ""
        completion_model = model
        last_stop = "stop"
        usage = TokenUsage(input_tokens=0, output_tokens=0)
        json_buffers: dict[int, dict[str, str]] = {}
        full_text = ""

        try:
            stream_resp = await self._client.chat.completions.create(**kwargs)
            async for chunk in stream_resp:
                completion_id = getattr(chunk, "id", "") or completion_id
                completion_model = getattr(chunk, "model", "") or completion_model
                if getattr(chunk, "usage", None):
                    usage = parse_token_usage(chunk.usage)

                if not getattr(chunk, "choices", None):
                    continue
                choice = chunk.choices[0]
                delta = getattr(choice, "delta", None)
                if delta is None:
                    continue

                if getattr(delta, "content", None):
                    full_text += delta.content
                    yield StreamEvent(type="text", data=delta.content)

                for tc_delta in getattr(delta, "tool_calls", None) or []:
                    idx = getattr(tc_delta, "index", 0)
                    if idx not in json_buffers:
                        func = getattr(tc_delta, "function", None)
                        init_name = getattr(func, "name", "") if func and isinstance(getattr(func, "name", None), str) else ""
                        init_id = getattr(tc_delta, "id", "") if isinstance(getattr(tc_delta, "id", None), str) else ""
                        json_buffers[idx] = {
                            "id": init_id,
                            "name": init_name,
                            "args": "",
                        }
                    buf = json_buffers[idx]
                    tc_id = getattr(tc_delta, "id", None)
                    if tc_id and isinstance(tc_id, str):
                        buf["id"] = tc_id
                    func = getattr(tc_delta, "function", None)
                    if func:
                        func_name = getattr(func, "name", None)
                        if func_name and isinstance(func_name, str):
                            buf["name"] = func_name
                        func_args = getattr(func, "arguments", None)
                        if func_args and isinstance(func_args, str):
                            buf["args"] += func_args

                if getattr(choice, "finish_reason", None):
                    last_stop = choice.finish_reason

            tool_blocks: list[ToolUseBlock] = []
            for buf in json_buffers.values():
                block = ToolUseBlock(
                    id=buf["id"],
                    name=buf["name"],
                    input=parse_json_safe(buf["args"]),
                )
                tool_blocks.append(block)
                yield StreamEvent(type="tool_use", data=block)

            done_content: list[ContentBlock] = []
            if full_text:
                done_content.append(TextBlock(text=full_text))
            done_content.extend(tool_blocks)

            yield StreamEvent(
                type="done",
                data=LLMResponse(
                    id=completion_id,
                    content=done_content,
                    model=completion_model,
                    stop_reason=map_stop_reason(last_stop),
                    usage=usage,
                ),
            )
        except Exception as e:
            redacted_err = redact_groq_key(safe_exception_message(e), self._api_key)
            logger.error("Groq stream error: %s", redacted_err)
            yield StreamEvent(type="error", data=RuntimeError(redacted_err))


async def create_groq_adapter(
    api_key: str | None = None,
    *,
    base_url: str | None = None,
    model: str | None = None,
    **kwargs: Any,
) -> GroqAdapter:
    """Factory function for creating a GroqAdapter instance."""
    return GroqAdapter(api_key=api_key, model=model, base_url=base_url)
