"""Optional OpenAI-compatible chat client.

The core application remains usable without this dependency through its
deterministic demo mode.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class LLMUnavailable(RuntimeError):
    pass


class OpenAIChatClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 base_url: Optional[str] = None) -> None:
        try:
            from dotenv import load_dotenv
            # Resolve the project-level .env from this file instead of relying
            # on the directory from which Streamlit was launched.
            project_env = Path(__file__).resolve().parents[1] / ".env"
            load_dotenv(dotenv_path=project_env)
        except ImportError:
            # Environment variables exported by the shell still work without
            # python-dotenv; the dependency only makes .env convenient locally.
            pass
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.base_url = base_url or os.getenv("LLM_BASE_URL")
        self._client = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]],
             final: bool = False) -> Any:
        if not self.available:
            raise LLMUnavailable("No LLM_API_KEY or OPENAI_API_KEY configured.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMUnavailable("The openai package is not installed.") from exc
        if self._client is None:
            kwargs: Dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url
            self._client = OpenAI(**kwargs)
        request: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            request["tools"] = tools
            request["tool_choice"] = "auto"
        if final:
            request["response_format"] = {"type": "json_object"}
        return self._client.chat.completions.create(**request)
