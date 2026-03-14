"""
HTTP clients for local vLLM endpoints.
"""
import json
import re
import time
from dataclasses import asdict, dataclass
from threading import Lock
from typing import Any, Dict, Optional

import requests

from config import (
    MODEL_NAME_1B,
    MODEL_NAME_7B,
    VLLM_API_URL_1B,
    VLLM_API_URL_7B,
    VLLM_MODELS_URL_1B,
    VLLM_MODELS_URL_7B,
)


@dataclass
class ClientGeneration:
    text: str
    latency_seconds: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    endpoint: str
    model_name: str
    raw_response: Dict[str, Any]
    parse_ok: bool = False
    parsed_json: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class VLLMClient:
    """Minimal resilient vLLM client."""

    def __init__(self, timeout_seconds: int = 120, max_retries: int = 1):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.headers = {"Content-Type": "application/json"}
        self._checked = set()
        self._lock = Lock()

    def generate_text(
        self,
        prompt: str,
        endpoint: str,
        model_name: str,
        max_tokens: int,
        temperature: float,
    ) -> ClientGeneration:
        payload = {
            "model": model_name,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        last_error: Optional[str] = None
        for _ in range(self.max_retries + 1):
            start_time = time.perf_counter()
            try:
                self._ensure_ready(endpoint)
                response = requests.post(
                    endpoint,
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                latency_seconds = time.perf_counter() - start_time
                response.raise_for_status()
                response_json = response.json()
                usage = response_json.get("usage", {})
                text = response_json.get("choices", [{}])[0].get("text", "").strip()
                return ClientGeneration(
                    text=text,
                    latency_seconds=latency_seconds,
                    prompt_tokens=int(usage.get("prompt_tokens", 0)),
                    completion_tokens=int(usage.get("completion_tokens", 0)),
                    total_tokens=int(usage.get("total_tokens", 0)),
                    endpoint=endpoint,
                    model_name=model_name,
                    raw_response=response_json,
                )
            except Exception as error:
                last_error = str(error)
        return ClientGeneration(
            text=f"[ERROR: {last_error}]",
            latency_seconds=0.0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            endpoint=endpoint,
            model_name=model_name,
            raw_response={"error": last_error},
        )

    def generate_json(
        self,
        prompt: str,
        endpoint: str,
        model_name: str,
        max_tokens: int,
        temperature: float,
    ) -> ClientGeneration:
        generation = self.generate_text(prompt, endpoint, model_name, max_tokens, temperature)
        json_payload = self._extract_json_payload(generation.text)
        if not json_payload:
            return generation
        try:
            generation.parsed_json = json.loads(json_payload)
            generation.parse_ok = True
            return generation
        except json.JSONDecodeError:
            return generation

    def _ensure_ready(self, endpoint: str) -> None:
        models_endpoint = endpoint.replace("/v1/completions", "/v1/models")
        with self._lock:
            if models_endpoint in self._checked:
                return
            response = requests.get(models_endpoint, timeout=5)
            response.raise_for_status()
            self._checked.add(models_endpoint)

    def _extract_json_payload(self, text: str) -> Optional[str]:
        fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
        if fenced:
            return fenced.group(1).strip()
        object_match = re.search(r"(\{.*\})", text, re.DOTALL)
        if object_match:
            return object_match.group(1).strip()
        array_match = re.search(r"(\[.*\])", text, re.DOTALL)
        if array_match:
            return array_match.group(1).strip()
        return None


class ClientRegistry:
    """Lookup table for the two supported local vLLM endpoints."""

    def __init__(self):
        self._clients = {"default": VLLMClient()}
        self._targets = {
            "1b": {
                "endpoint": VLLM_API_URL_1B,
                "models_endpoint": VLLM_MODELS_URL_1B,
                "model_name": MODEL_NAME_1B,
            },
            "7b": {
                "endpoint": VLLM_API_URL_7B,
                "models_endpoint": VLLM_MODELS_URL_7B,
                "model_name": MODEL_NAME_7B,
            },
        }

    def get(self, tier: str) -> Dict[str, str]:
        if tier not in self._targets:
            raise KeyError(f"Unknown client tier: {tier}")
        return self._targets[tier]

    def client(self) -> VLLMClient:
        return self._clients["default"]
