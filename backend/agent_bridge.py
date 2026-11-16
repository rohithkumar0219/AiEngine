"""Agent Bridge Module — Bridges Groq LLM Adapter to Iryax NDJSON streaming.

Converts Groq streaming events (StreamEvent) into the NDJSON format expected
by Iryax API clients while preserving ChromaDB RAG retrieval and source citations.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import pathlib
from collections.abc import AsyncIterator, Iterator
from typing import Any

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

from groq_adapter import (
    GroqAdapter,
    LLMMessage,
    LLMStreamOptions,
    StreamEvent,
    TextBlock,
    redact_groq_key,
)

# Load environment configuration
load_dotenv()

logger = logging.getLogger(__name__)

# Constants and paths
ROOT_DIR = pathlib.Path(__file__).parent.resolve()
CHROMA_DIR = ROOT_DIR / "data" / "chromadb"
DEFAULT_COLLECTION_NAME = "iryax_context_v2"
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "info@ingrainsystem.com")
CONTACT_PHONE = os.getenv("CONTACT_PHONE", "+91-9010481048")

# Initialize ChromaDB client lazily
_chroma_client: chromadb.PersistentClient | None = None
_chroma_collection = None


def get_chroma_collection():
    """Lazily load and return the persistent ChromaDB collection."""
    global _chroma_client, _chroma_collection
    if _chroma_collection is None:
        try:
            _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            embed_fn = embedding_functions.DefaultEmbeddingFunction()
            _chroma_collection = _chroma_client.get_or_create_collection(
                name=DEFAULT_COLLECTION_NAME,
                embedding_function=embed_fn,
            )
        except Exception as e:
            logger.warning("Failed to initialize ChromaDB collection: %s", e)
            return None
    return _chroma_collection


def retrieve_rag_context(
    query: str,
    top_k: int = 5,
    collection_override=None,
) -> tuple[str, list[str]]:
    """Retrieve relevant documents and sources from ChromaDB."""
    coll = collection_override or get_chroma_collection()
    if coll is None:
        return "", []

    try:
        results = coll.query(query_texts=[query], n_results=top_k)
    except Exception as e:
        logger.warning("ChromaDB query failed: %s", e)
        return "", []

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    sources_set: set[str] = set()
    context_chunks: list[str] = []

    for doc, meta in zip(documents, metadatas):
        context_chunks.append(doc)
        if isinstance(meta, dict):
            url = meta.get("url")
            if url:
                sources_set.add(url)
            elif meta.get("label"):
                sources_set.add(meta["label"])

    context_str = "\n\n---\n\n".join(context_chunks)
    sources = sorted(sources_set)
    return context_str, sources


def build_system_prompt(rag_context: str) -> str:
    """Build system instructions incorporating retrieved context and company guardrails."""
    parts = [
        "You are the official Iryax AI Assistant. You provide helpful, concise, and professional answers "
        "about Iryax products, services, solutions, pricing, and company information.",
    ]
    if rag_context:
        parts.append(f"Context from Iryax knowledge base:\n{rag_context}")
    parts.append(
        f"Always provide polite and accurate assistance. If you do not have sufficient information, "
        f"direct users to contact {CONTACT_EMAIL} or call {CONTACT_PHONE}."
    )
    return "\n\n".join(parts)


def format_ndjson_token(token: str, sources: list[str]) -> str:
    """Format a stream token line in standard NDJSON."""
    return json.dumps({"token": token, "sources": sources}) + "\n"


def format_ndjson_final(
    answer: str,
    sources: list[str],
    session_id: str = "default_session",
) -> str:
    """Format the terminal NDJSON line with full answer and session_id (token is empty to prevent duplicates)."""
    return json.dumps({"token": "", "sources": sources, "answer": answer, "session_id": session_id}) + "\n"


def format_ndjson_error(error_message: str, sources: list[str] | None = None) -> str:
    """Format an error payload in NDJSON, masking sensitive information."""
    sanitized = redact_groq_key(str(error_message))
    return json.dumps({"error": sanitized, "token": "", "sources": sources or []}) + "\n"


class Agent:
    """Lightweight autonomous agent driven by the GroqAdapter."""

    def __init__(
        self,
        name: str = "iryax-agent",
        model: str | None = None,
        provider: str = "groq",
        system_prompt: str | None = None,
        adapter: GroqAdapter | None = None,
        max_turns: int = 3,
    ) -> None:
        self.name = name
        self.model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        self.system_prompt = system_prompt
        self.adapter = adapter or GroqAdapter(model=self.model)
        self.max_turns = max_turns

    async def stream(self, prompt: str) -> AsyncIterator[StreamEvent]:
        messages = [LLMMessage(role="user", content=[TextBlock(text=prompt)])]
        options = LLMStreamOptions(
            model=self.model,
            system_prompt=self.system_prompt,
            temperature=0.1,
            max_tokens=800,
        )
        async for event in self.adapter.stream(messages, options):
            yield event


async def generate_agent_stream(
    user_message: str,
    history: list[dict[str, str]] | None = None,
    *,
    session_id: str = "default_session",
    website_id: str = "https://iryax.com",
    groq_api_key: str | None = None,
    groq_model: str | None = None,
    top_k: int = 5,
    agent_override: Agent | None = None,
    collection_override=None,
) -> AsyncIterator[str]:
    """Asynchronous generator that runs an agent on Groq and streams NDJSON."""
    clean_query = user_message.strip()
    if not clean_query:
        yield json.dumps({"error": "Empty message received."}) + "\n"
        return

    # 1. Retrieve RAG context from ChromaDB
    context_str, sources = retrieve_rag_context(
        clean_query,
        top_k=top_k,
        collection_override=collection_override,
    )

    # 2. Build or obtain Agent
    if agent_override is not None:
        agent = agent_override
    else:
        api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            yield format_ndjson_error("GROQ_API_KEY is not configured.", sources)
            return

        model_name = groq_model or os.getenv("GROQ_MODEL")
        if not model_name:
            yield format_ndjson_error("GROQ_MODEL is not configured.", sources)
            return

        system_prompt = build_system_prompt(context_str)
        try:
            adapter = GroqAdapter(api_key=api_key, model=model_name)
            agent = Agent(
                name="iryax-rag-agent",
                provider="groq",
                model=model_name,
                system_prompt=system_prompt,
                adapter=adapter,
                max_turns=3,
            )
        except Exception as e:
            yield format_ndjson_error(f"Failed to initialize agent: {e}", sources)
            return

    # 3. Stream events and convert to NDJSON
    accumulated_tokens: list[str] = []
    final_output = ""

    try:
        async for event in agent.stream(clean_query):
            if event.type == "text" and isinstance(event.data, str):
                accumulated_tokens.append(event.data)
                yield format_ndjson_token(event.data, sources)
            elif event.type == "done":
                # Agent completed turn: extract terminal text
                if hasattr(event.data, "content") and event.data.content:
                    texts = [b.text for b in event.data.content if hasattr(b, "text")]
                    final_output = "".join(texts)
            elif event.type == "error":
                err_text = str(event.data)
                yield format_ndjson_error(err_text, sources)
                return

        # 4. Emit terminal payload line
        full_text = final_output or "".join(accumulated_tokens)
        yield format_ndjson_final(full_text, sources, session_id=session_id)

    except Exception as e:
        logger.exception("Agent bridge streaming error: %s", e)
        yield format_ndjson_error(f"Stream error: {e}", sources)
