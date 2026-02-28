import asyncio
import json
import os
import re
import time
import uuid
from typing import Any
from urllib.parse import urlparse

import chromadb
import httpx
import redis.asyncio as redis
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed
from starlette.responses import StreamingResponse

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))

CHROMA_URL = os.getenv("CHROMA_URL", "http://localhost:8000")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "rag_docs")
CHROMA_TOP_K = int(os.getenv("CHROMA_TOP_K", "3"))

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3")
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "60"))

ACTIVE_REQUESTS = Gauge(
    "gateway_llm_active_requests",
    "Current number of active requests calling the LLM backend.",
)

app = FastAPI(title="LLM Gateway", version="1.0.0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)


class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float | None = 0.7
    stream: bool = False
    max_tokens: int | None = None


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content)


def _extract_api_key(authorization: str | None, x_api_key: str | None) -> str:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    raise HTTPException(status_code=401, detail="Missing API key")


async def _enforce_rate_limit(api_key: str) -> None:
    minute_slot = int(time.time() // 60)
    redis_key = f"gateway:rate_limit:{api_key}:{minute_slot}"
    try:
        current = await redis_client.incr(redis_key)
        if current == 1:
            await redis_client.expire(redis_key, 65)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Redis unavailable") from exc

    if current > RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def _build_chroma_client() -> chromadb.ClientAPI:
    normalized = CHROMA_URL if "://" in CHROMA_URL else f"http://{CHROMA_URL}"
    parsed = urlparse(normalized)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 8000)
    return chromadb.HttpClient(host=host, port=port, ssl=parsed.scheme == "https")


chroma_client = _build_chroma_client()


def _extract_embedding(response_json: dict[str, Any]) -> list[float] | None:
    embeddings = response_json.get("embeddings")
    if isinstance(embeddings, list) and embeddings:
        first = embeddings[0]
        if isinstance(first, list) and first and all(isinstance(x, (int, float)) for x in first):
            return [float(x) for x in first]

    embedding = response_json.get("embedding")
    if isinstance(embedding, list) and embedding and all(isinstance(x, (int, float)) for x in embedding):
        return [float(x) for x in embedding]

    return None


def _flatten_documents(results: dict[str, Any]) -> list[str]:
    docs: list[str] = []
    for row in results.get("documents", []):
        if isinstance(row, list):
            for item in row:
                if isinstance(item, str) and item.strip():
                    docs.append(item)
        elif isinstance(row, str) and row.strip():
            docs.append(row)
    return docs


def _keyword_candidates(query_text: str) -> list[str]:
    raw = query_text.strip()
    if not raw:
        return []

    normalized = raw
    normalized = re.sub(r"[？?。！!，,、；;：:（）()\"“”'‘’]", "", normalized).strip()
    normalized = re.sub(
        r"(是什么|是啥|指什么|啥意思|是什么意思|有哪些|有哪几种|如何|怎么|吗|么|呢)$",
        "",
        normalized,
    ).strip()

    candidates: list[str] = []
    for item in (normalized, raw):
        value = item.strip()
        if value and len(value) >= 2 and value not in candidates:
            candidates.append(value)
    return candidates


async def _embed_query_with_ollama(query_text: str) -> list[float] | None:
    if not query_text.strip():
        return None

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        # Preferred Ollama endpoint.
        embed_resp = await client.post(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/embed",
            json={"model": OLLAMA_EMBED_MODEL, "input": query_text},
        )
        if embed_resp.is_success:
            return _extract_embedding(embed_resp.json())

        # Fallback for older Ollama versions.
        legacy_resp = await client.post(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/embeddings",
            json={"model": OLLAMA_EMBED_MODEL, "prompt": query_text},
        )
        legacy_resp.raise_for_status()
        return _extract_embedding(legacy_resp.json())


def _query_chroma_sync(query_text: str, query_embedding: list[float] | None = None) -> list[str]:
    if not query_text.strip():
        return []

    docs: list[str] = []
    seen_docs: set[str] = set()

    try:
        collection = chroma_client.get_collection(name=CHROMA_COLLECTION)
    except Exception:
        return []

    # Keyword contains search helps exact term questions even when collection
    # embeddings are from an old/incompatible model.
    for keyword in _keyword_candidates(query_text):
        try:
            keyword_results = collection.get(
                where_document={"$contains": keyword},
                include=["documents"],
                limit=CHROMA_TOP_K,
            )
        except Exception:
            continue

        for item in _flatten_documents(keyword_results):
            if item not in seen_docs:
                seen_docs.add(item)
                docs.append(item)

        if len(docs) >= CHROMA_TOP_K:
            return docs[:CHROMA_TOP_K]

    try:
        if query_embedding:
            try:
                semantic_results = collection.query(
                    query_embeddings=[query_embedding], n_results=CHROMA_TOP_K
                )
            except Exception:
                # Fallback for old collections with incompatible embedding dimensions.
                semantic_results = collection.query(query_texts=[query_text], n_results=CHROMA_TOP_K)
        else:
            semantic_results = collection.query(query_texts=[query_text], n_results=CHROMA_TOP_K)
    except Exception:
        return docs[:CHROMA_TOP_K]

    for item in _flatten_documents(semantic_results):
        if item not in seen_docs:
            seen_docs.add(item)
            docs.append(item)

    return docs[:CHROMA_TOP_K]


async def _query_chroma(query_text: str) -> list[str]:
    query_embedding: list[float] | None = None
    try:
        query_embedding = await _embed_query_with_ollama(query_text)
    except Exception:
        query_embedding = None
    return await asyncio.to_thread(_query_chroma_sync, query_text, query_embedding)


def _build_ollama_messages(messages: list[ChatMessage], docs: list[str]) -> list[dict[str, str]]:
    ollama_messages: list[dict[str, str]] = []

    if docs:
        context = "\n\n".join(f"[{i + 1}] {doc}" for i, doc in enumerate(docs))
        rag_system_prompt = (
            "You are a helpful assistant. Use the retrieved context first when answering.\n"
            "If the context is insufficient, clearly say what is uncertain.\n\n"
            f"Retrieved context:\n{context}"
        )
        ollama_messages.append({"role": "system", "content": rag_system_prompt})

    for message in messages:
        content = _normalize_content(message.content).strip()
        if not content:
            continue
        ollama_messages.append({"role": message.role, "content": content})

    return ollama_messages


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(1),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True,
)
async def _call_ollama_with_retry(payload: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
        response = await client.post(f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat", json=payload)
        response.raise_for_status()
        return response.json()


def _sse_chunk(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sse_done() -> str:
    return "data: [DONE]\n\n"


async def _stream_ollama_to_openai(payload: dict[str, Any], model_name: str):
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    role_sent = False

    ACTIVE_REQUESTS.inc()
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            async with client.stream(
                "POST", f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat", json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        piece = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if not role_sent:
                        yield _sse_chunk(
                            {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model_name,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {"role": "assistant"},
                                        "finish_reason": None,
                                    }
                                ],
                            }
                        )
                        role_sent = True

                    content = piece.get("message", {}).get("content")
                    if isinstance(content, str) and content:
                        yield _sse_chunk(
                            {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model_name,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {"content": content},
                                        "finish_reason": None,
                                    }
                                ],
                            }
                        )

                    if piece.get("done") is True:
                        yield _sse_chunk(
                            {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model_name,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {},
                                        "finish_reason": "stop",
                                    }
                                ],
                            }
                        )
                        break
        yield _sse_done()
    except Exception as exc:
        yield _sse_chunk(
            {
                "error": {
                    "message": f"LLM backend call failed: {exc}",
                    "type": "gateway_error",
                }
            }
        )
        yield _sse_done()
    finally:
        ACTIVE_REQUESTS.dec()


def _get_rag_query(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return _normalize_content(message.content).strip()
    return _normalize_content(messages[-1].content).strip()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: ChatCompletionRequest,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> Any:

    api_key = _extract_api_key(authorization, x_api_key)
    await _enforce_rate_limit(api_key)

    rag_query = _get_rag_query(request.messages)
    docs = await _query_chroma(rag_query)
    ollama_messages = _build_ollama_messages(request.messages, docs)

    payload: dict[str, Any] = {
        "model": request.model or OLLAMA_MODEL,
        "messages": ollama_messages,
        "stream": request.stream,
    }
    if request.temperature is not None:
        payload["options"] = {"temperature": request.temperature}

    if request.stream:
        return StreamingResponse(
            _stream_ollama_to_openai(payload=payload, model_name=payload["model"]),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    ACTIVE_REQUESTS.inc()
    try:
        ollama_response = await _call_ollama_with_retry(payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM backend call failed: {exc}") from exc
    finally:
        ACTIVE_REQUESTS.dec()

    assistant_content = (
        ollama_response.get("message", {}).get("content")
        if isinstance(ollama_response, dict)
        else None
    )
    if not isinstance(assistant_content, str):
        assistant_content = ""

    prompt_tokens = sum(
        len(_normalize_content(message.content).split()) for message in request.messages
    )
    completion_tokens = len(assistant_content.split())
    now = int(time.time())

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": now,
        "model": payload["model"],
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": assistant_content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await redis_client.aclose()
