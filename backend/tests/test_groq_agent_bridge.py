"""Unit and integration tests for GroqAdapter and AgentBridge.

Mocked tests verify:
- Adapter configuration and model resolution
- Streaming token handling and tool call accumulation
- Exception handling and secret redaction
- NDJSON output formatting and duplicate prevention
- RAG source preservation

Live tests are explicitly separated and require a valid GROQ_API_KEY.
"""

from __future__ import annotations

import asyncio
import json
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from dotenv import load_dotenv

# Ensure local .env variables are loaded for live test capability
load_dotenv()

from groq_adapter import (
    GroqAdapter,
    LLMChatOptions,
    LLMMessage,
    LLMResponse,
    LLMStreamOptions,
    StreamEvent,
    TextBlock,
    TokenUsage,
    ToolUseBlock,
    create_groq_adapter,
    redact_groq_key,
)
from agent_bridge import (
    format_ndjson_error,
    format_ndjson_final,
    format_ndjson_token,
    generate_agent_stream,
    retrieve_rag_context,
)


class TestGroqAdapterMocked(unittest.IsolatedAsyncioTestCase):
    """Mocked unit tests for GroqAdapter — zero external network calls."""

    def test_adapter_initialization_with_custom_key_and_model(self):
        adapter = GroqAdapter(api_key="gsk_mock_test_key_1234567890123456", model="mock-model-v1")
        self.assertEqual(adapter.name, "groq")
        self.assertEqual(adapter.resolve_model(), "mock-model-v1")

    def test_adapter_missing_api_key_raises(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                GroqAdapter(api_key=None)
            self.assertIn("GROQ_API_KEY is not set", str(ctx.exception))

    def test_adapter_missing_model_raises(self):
        adapter = GroqAdapter(api_key="gsk_mock_key_1234567890123456", model=None)
        with patch.dict(os.environ, {"GROQ_MODEL": ""}, clear=True):
            with self.assertRaises(ValueError) as ctx:
                adapter.resolve_model(None)
            self.assertIn("No Groq model specified", str(ctx.exception))

    def test_secret_redaction(self):
        fake_key = "gsk_secretKey9876543210abcdefghijklmnop"
        error_msg = f"Failed to authenticate with key {fake_key} at endpoint."
        redacted = redact_groq_key(error_msg, fake_key)
        self.assertNotIn(fake_key, redacted)
        self.assertIn("[REDACTED_GROQ_KEY]", redacted)

    async def test_chat_mocked_success(self):
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.id = "chatcmpl-test-123"
        mock_completion.model = "mock-groq-model"
        mock_choice = MagicMock()
        mock_choice.message.content = "Mocked answer from Groq"
        mock_choice.message.tool_calls = None
        mock_choice.finish_reason = "stop"
        mock_completion.choices = [mock_choice]
        mock_completion.usage.prompt_tokens = 12
        mock_completion.usage.completion_tokens = 8

        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        adapter = GroqAdapter(api_key="gsk_mock_key_1234567890123456", model="mock-model", client=mock_client)
        messages = [LLMMessage(role="user", content=[TextBlock(text="Hello")])]
        options = LLMChatOptions(model="mock-model")

        response = await adapter.chat(messages, options)
        self.assertIsInstance(response, LLMResponse)
        self.assertEqual(response.model, "mock-groq-model")
        self.assertEqual(response.stop_reason, "end_turn")
        self.assertEqual(len(response.content), 1)
        self.assertEqual(response.content[0].text, "Mocked answer from Groq")

    async def test_stream_mocked_tokens_and_done(self):
        mock_client = MagicMock()

        # Chunk 1: text token "Hello"
        c1 = MagicMock()
        c1.id = "chunk-1"
        c1.model = "mock-model"
        c1.usage = None
        c1.choices = [MagicMock(delta=MagicMock(content="Hello", tool_calls=None), finish_reason=None)]

        # Chunk 2: text token " World"
        c2 = MagicMock()
        c2.id = "chunk-2"
        c2.model = "mock-model"
        c2.usage = None
        c2.choices = [MagicMock(delta=MagicMock(content=" World", tool_calls=None), finish_reason=None)]

        # Chunk 3: finish_reason="stop"
        c3 = MagicMock()
        c3.id = "chunk-3"
        c3.model = "mock-model"
        c3.usage = MagicMock(prompt_tokens=5, completion_tokens=2)
        c3.choices = [MagicMock(delta=MagicMock(content=None, tool_calls=None), finish_reason="stop")]

        async def _mock_stream():
            for c in [c1, c2, c3]:
                yield c

        mock_client.chat.completions.create = AsyncMock(return_value=_mock_stream())

        adapter = GroqAdapter(api_key="gsk_mock_key_1234567890123456", model="mock-model", client=mock_client)
        messages = [LLMMessage(role="user", content=[TextBlock(text="Hi")])]
        options = LLMStreamOptions(model="mock-model")

        events = []
        async for event in adapter.stream(messages, options):
            events.append(event)

        text_events = [e for e in events if e.type == "text"]
        done_events = [e for e in events if e.type == "done"]

        self.assertEqual(len(text_events), 2)
        self.assertEqual(text_events[0].data, "Hello")
        self.assertEqual(text_events[1].data, " World")
        self.assertEqual(len(done_events), 1)
        self.assertEqual(done_events[0].data.stop_reason, "end_turn")

    async def test_stream_mocked_tool_call_accumulation(self):
        mock_client = MagicMock()

        # Chunk 1: tool call start
        tc1 = MagicMock()
        tc1.index = 0
        tc1.id = "call_abc123"
        tc1.function = MagicMock()
        tc1.function.name = "search_knowledge"
        tc1.function.arguments = '{"query":'
        c1 = MagicMock(id="c1", model="mock-model", usage=None, choices=[MagicMock(delta=MagicMock(content=None, tool_calls=[tc1]), finish_reason=None)])

        # Chunk 2: tool call args continuation
        tc2 = MagicMock()
        tc2.index = 0
        tc2.id = None
        tc2.function = MagicMock()
        tc2.function.name = None
        tc2.function.arguments = ' "pricing"}'
        c2 = MagicMock(id="c2", model="mock-model", usage=None, choices=[MagicMock(delta=MagicMock(content=None, tool_calls=[tc2]), finish_reason="tool_calls")])

        async def _mock_stream():
            for c in [c1, c2]:
                yield c

        mock_client.chat.completions.create = AsyncMock(return_value=_mock_stream())

        adapter = GroqAdapter(api_key="gsk_mock_key_1234567890123456", model="mock-model", client=mock_client)
        messages = [LLMMessage(role="user", content=[TextBlock(text="Check pricing")])]
        options = LLMStreamOptions(model="mock-model")

        events = []
        async for event in adapter.stream(messages, options):
            events.append(event)

        tool_events = [e for e in events if e.type == "tool_use"]
        self.assertEqual(len(tool_events), 1)
        tool_block = tool_events[0].data
        self.assertEqual(tool_block.id, "call_abc123")
        self.assertEqual(tool_block.name, "search_knowledge")
        self.assertEqual(tool_block.input, {"query": "pricing"})

    async def test_stream_error_redacts_credentials(self):
        fake_key = "gsk_fake_secret_key_1234567890"
        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception(f"Invalid API request using {fake_key}"))

        adapter = GroqAdapter(api_key=fake_key, model="mock-model", client=mock_client)
        messages = [LLMMessage(role="user", content=[TextBlock(text="Test")])]
        options = LLMStreamOptions(model="mock-model")

        events = []
        async for event in adapter.stream(messages, options):
            events.append(event)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].type, "error")
        err_msg = str(events[0].data)
        self.assertNotIn(fake_key, err_msg)
        self.assertIn("[REDACTED_GROQ_KEY]", err_msg)


class TestAgentBridgeMocked(unittest.IsolatedAsyncioTestCase):
    """Mocked unit tests for AgentBridge NDJSON streaming and RAG integration."""

    def test_ndjson_token_formatter(self):
        line = format_ndjson_token("Hello", ["https://iryax.com/contact"])
        data = json.loads(line)
        self.assertEqual(data["token"], "Hello")
        self.assertEqual(data["sources"], ["https://iryax.com/contact"])

    def test_ndjson_final_formatter_prevents_duplicate_tokens(self):
        line = format_ndjson_final("Full Answer Text", ["https://iryax.com"], session_id="test_session")
        data = json.loads(line)
        # Token must be empty string so client does not double-append
        self.assertEqual(data["token"], "")
        self.assertEqual(data["answer"], "Full Answer Text")
        self.assertEqual(data["session_id"], "test_session")

    def test_ndjson_error_formatter(self):
        fake_key = "gsk_secretKey9876543210abcdefghijklmnop"
        line = format_ndjson_error(f"Error with key {fake_key}")
        data = json.loads(line)
        self.assertNotIn(fake_key, data["error"])
        self.assertIn("[REDACTED_GROQ_KEY]", data["error"])

    async def test_empty_message_returns_json_error(self):
        lines = []
        async for line in generate_agent_stream("   "):
            lines.append(line)
        self.assertEqual(len(lines), 1)
        data = json.loads(lines[0])
        self.assertEqual(data.get("error"), "Empty message received.")

    async def test_agent_stream_converts_events_to_ndjson_with_mocked_agent(self):
        mock_agent = MagicMock()

        async def _mock_stream(prompt):
            yield StreamEvent(type="text", data="Iryax")
            yield StreamEvent(type="text", data=" Platform")
            yield StreamEvent(type="done", data=MagicMock(output="Iryax Platform"))

        mock_agent.stream = _mock_stream

        mock_coll = MagicMock()
        mock_coll.query.return_value = {
            "documents": [["Iryax is an AI platform."]],
            "metadatas": [[{"url": "https://iryax.com/about"}]],
        }

        lines = []
        async for line in generate_agent_stream(
            "What is Iryax?",
            session_id="session_42",
            agent_override=mock_agent,
            collection_override=mock_coll,
        ):
            lines.append(line)

        # Expected: token 1 ("Iryax"), token 2 (" Platform"), and final line (token: "", answer: "Iryax Platform")
        self.assertEqual(len(lines), 3)

        c1 = json.loads(lines[0])
        self.assertEqual(c1["token"], "Iryax")
        self.assertEqual(c1["sources"], ["https://iryax.com/about"])

        c2 = json.loads(lines[1])
        self.assertEqual(c2["token"], " Platform")

        final = json.loads(lines[2])
        self.assertEqual(final["token"], "")
        self.assertEqual(final["answer"], "Iryax Platform")
        self.assertEqual(final["session_id"], "session_42")
        self.assertEqual(final["sources"], ["https://iryax.com/about"])


class TestGroqLiveIntegration(unittest.IsolatedAsyncioTestCase):
    """Live API integration tests against the Groq Cloud endpoint.

    Clearly distinguished from mocked tests. Only executed when GROQ_API_KEY is present.
    """

    @unittest.skipUnless(os.getenv("GROQ_API_KEY"), "Skipping live Groq test: GROQ_API_KEY not configured.")
    async def test_live_groq_streaming_completion(self):
        adapter = GroqAdapter()
        messages = [LLMMessage(role="user", content=[TextBlock(text="Respond with the single word: OK")])]
        options = LLMStreamOptions(model=adapter.resolve_model())

        tokens = []
        done_seen = False
        async for event in adapter.stream(messages, options):
            if event.type == "text":
                tokens.append(event.data)
            elif event.type == "done":
                done_seen = True

        full_output = "".join(tokens).strip()
        self.assertTrue(done_seen, "Expected done event from live Groq stream")
        self.assertIn("OK", full_output)


if __name__ == "__main__":
    unittest.main()
