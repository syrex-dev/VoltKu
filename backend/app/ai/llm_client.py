import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class LLMToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    tokens: int = 0


class LLMClient(ABC):
    """Antarmuka tunggal untuk seluruh pemanggilan LLM (Gemini, OpenAI, atau Stub)."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout_s: float = 20.0,
    ) -> LLMResponse:
        """Menghasilkan respons teks atau permintaan pemanggilan tool."""


class LLMStub(LLMClient):
    """Stub deterministik untuk pengujian otomatis tanpa memanggil API eksternal."""

    def __init__(
        self,
        scripted_responses: Optional[list[LLMResponse]] = None,
        handler: Optional[
            Callable[[list[dict[str, Any]], list[dict[str, Any]]], LLMResponse]
        ] = None,
        fail_with: Optional[Exception] = None,
    ) -> None:
        self._responses = list(scripted_responses or [])
        self._handler = handler
        self._fail_with = fail_with
        self.calls: list[dict[str, Any]] = []

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout_s: float = 20.0,
    ) -> LLMResponse:
        self.calls.append({"messages": messages, "tools": tools, "timeout_s": timeout_s})
        if self._fail_with is not None:
            raise self._fail_with
        if self._handler is not None:
            return self._handler(messages, tools)
        if self._responses:
            return self._responses.pop(0)
        return LLMResponse(text="Tidak ada respons dari stub.", tokens=0)


class GeminiLLMClient(LLMClient):
    """Klien HTTP Gemini REST API (tanpa mencatat API key ke log)."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._api_key = api_key
        self._model = model

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout_s: float = 20.0,
    ) -> LLMResponse:
        system_instruction = ""
        contents: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                system_instruction = str(msg.get("content", ""))
            elif role == "assistant":
                parts: list[dict[str, Any]] = []
                if msg.get("content"):
                    parts.append({"text": str(msg["content"])})
                for tc in msg.get("tool_calls", []):
                    parts.append(
                        {
                            "functionCall": {
                                "name": tc["name"],
                                "args": tc.get("arguments", {}),
                            }
                        }
                    )
                if parts:
                    contents.append({"role": "model", "parts": parts})
            elif role == "tool":
                contents.append(
                    {
                        "role": "function",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": msg.get("name", "tool"),
                                    "response": {"result": msg.get("content", {})},
                                }
                            }
                        ],
                    }
                )
            else:
                contents.append({"role": "user", "parts": [{"text": str(msg.get("content", ""))}]})

        fn_declarations = [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            }
            for t in tools
        ]
        body: dict[str, Any] = {"contents": contents}
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if fn_declarations:
            body["tools"] = [{"functionDeclarations": fn_declarations}]

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent"
        )
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                url,
                headers={"x-goog-api-key": self._api_key, "Content-Type": "application/json"},
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates") or []
        if not candidates:
            return LLMResponse(text="", tokens=0)
        parts = candidates[0].get("content", {}).get("parts") or []
        text_parts: list[str] = []
        tool_calls: list[LLMToolCall] = []
        for idx, part in enumerate(parts):
            if "text" in part and part["text"]:
                text_parts.append(str(part["text"]))
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(
                    LLMToolCall(
                        id=f"gem_{idx}",
                        name=str(fc.get("name", "")),
                        arguments=dict(fc.get("args") or {}),
                    )
                )

        usage = data.get("usageMetadata") or {}
        tokens = int(usage.get("totalTokenCount") or 0)
        return LLMResponse(text="\n".join(text_parts).strip(), tool_calls=tool_calls, tokens=tokens)


class OpenAICompatibleLLMClient(LLMClient):
    """Klien HTTP OpenAI Chat Completions API (kompatibel OpenAI / OpenRouter / vLLM)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    async def generate(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout_s: float = 20.0,
    ) -> LLMResponse:
        formatted_msgs: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "tool":
                formatted_msgs.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.get("tool_call_id", "call_0"),
                        "content": json.dumps(msg.get("content", {}), ensure_ascii=False),
                    }
                )
            elif role == "assistant" and msg.get("tool_calls"):
                formatted_msgs.append(
                    {
                        "role": "assistant",
                        "content": msg.get("content") or None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": json.dumps(tc.get("arguments", {})),
                                },
                            }
                            for tc in msg["tool_calls"]
                        ],
                    }
                )
            else:
                formatted_msgs.append({"role": role, "content": str(msg.get("content", ""))})

        oai_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                },
            }
            for t in tools
        ]
        payload: dict[str, Any] = {"model": self._model, "messages": formatted_msgs}
        if oai_tools:
            payload["tools"] = oai_tools

        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices") or []
        if not choices:
            return LLMResponse(text="", tokens=0)
        message = choices[0].get("message") or {}
        tool_calls: list[LLMToolCall] = []
        for tc in message.get("tool_calls") or []:
            fn = tc.get("function") or {}
            raw_args = fn.get("arguments") or "{}"
            try:
                parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except Exception:
                parsed_args = {}
            tool_calls.append(
                LLMToolCall(
                    id=str(tc.get("id", "")),
                    name=str(fn.get("name", "")),
                    arguments=parsed_args,
                )
            )
        usage = data.get("usage") or {}
        tokens = int(usage.get("total_tokens") or 0)
        return LLMResponse(
            text=str(message.get("content") or "").strip(),
            tool_calls=tool_calls,
            tokens=tokens,
        )


def get_llm_client(settings=None) -> Optional[LLMClient]:
    """Mengembalikan instance LLMClient aktif sesuai env, atau None bila API key kosong."""
    if settings is None:
        from app.config import get_settings

        settings = get_settings()

    api_key = (getattr(settings, "llm_api_key", None) or "").strip()
    if not api_key:
        return None
    provider = (getattr(settings, "llm_provider", "gemini") or "gemini").strip().lower()
    model = (getattr(settings, "llm_model", "gemini-2.5-flash") or "gemini-2.5-flash").strip()
    base_url = (getattr(settings, "llm_base_url", None) or "").strip()

    if provider in ("openai", "openrouter", "openai_compatible", "groq"):
        return OpenAICompatibleLLMClient(
            api_key=api_key,
            model=model,
            base_url=base_url or "https://api.openai.com/v1",
        )
    return GeminiLLMClient(api_key=api_key, model=model)
