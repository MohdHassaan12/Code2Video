"""
Unified LLM Client Adapter Module.
Provides an extensible multi-provider interface supporting Google Gemini,
OpenAI, Anthropic, local Ollama/vLLM endpoints, and offline pedagogical simulation.
"""

import os
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any


class UnifiedLLMClient:
    """Multi-provider client for planning, code generation, and multimodal visual critique."""

    def __init__(
        self,
        provider: str = "auto",
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.provider = provider
        self.api_key = (
            api_key or
            os.environ.get("GEMINI_API_KEY") or
            os.environ.get("GOOGLE_API_KEY") or
            os.environ.get("OPENAI_API_KEY") or
            os.environ.get("ANTHROPIC_API_KEY")
        )
        self.base_url = base_url

        # Auto-detect provider if auto
        if self.provider == "auto":
            if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
                self.provider = "gemini"
                self.model_name = model_name or "gemini-2.5-pro"
            elif os.environ.get("OPENAI_API_KEY"):
                self.provider = "openai"
                self.model_name = model_name or "gpt-4o"
            elif os.environ.get("ANTHROPIC_API_KEY"):
                self.provider = "anthropic"
                self.model_name = model_name or "claude-3-5-sonnet-20241022"
            else:
                self.provider = "mock"
                self.model_name = model_name or "offline-synthesizer"
        else:
            self.model_name = model_name or "gemini-2.5-pro"

    def generate(self, prompt: str, temperature: float = 0.2) -> str:
        """Dispatches prompt to selected LLM provider."""
        if self.provider == "gemini" and self.api_key:
            return self._call_gemini(prompt, temperature)
        elif self.provider == "openai" and self.api_key:
            return self._call_openai(prompt, temperature)
        elif self.provider == "anthropic" and self.api_key:
            return self._call_anthropic(prompt, temperature)
        elif self.provider == "ollama":
            return self._call_ollama(prompt, temperature)
        else:
            raise RuntimeError("Live LLM generation called without an active API key or provider.")

    def _call_gemini(self, prompt: str, temperature: float) -> str:
        """Direct REST call to Gemini 2.5 API."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature}
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=45) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            return res_json["candidates"][0]["content"]["parts"][0]["text"]

    def _call_openai(self, prompt: str, temperature: float) -> str:
        """Direct REST call to OpenAI API."""
        url = self.base_url or "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=45) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            return res_json["choices"][0]["message"]["content"]

    def _call_anthropic(self, prompt: str, temperature: float) -> str:
        """Direct REST call to Anthropic Messages API."""
        url = "https://api.anthropic.com/v1/messages"
        payload = {
            "model": self.model_name,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=45) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            return res_json["content"][0]["text"]

    def _call_ollama(self, prompt: str, temperature: float) -> str:
        """Call to local Ollama server."""
        url = (self.base_url or "http://localhost:11434") + "/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature}
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            return res_json["response"]

