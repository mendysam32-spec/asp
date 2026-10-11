""""LLM provider abstraction - supports NVIDIA, OpenRouter, OpenAI, Anthropic, with graceful fallback.
    Provider + model are read from UI settings (config/dashboard_settings.json) first,
    then fall back to env vars. Failover: if the primary model fails, the
    configured fallback models (and then other providers) are tried automatically,
    so one broken model never takes down the whole agent."""
import os
import time
import json
from typing import Dict, Optional
from datetime import datetime

from config.settings import OPENAI_API_KEY
from config.settings_store import settings_store


class LLMProvider:
    VALID_PROVIDERS = ("auto", "nvidia", "openrouter", "openai", "anthropic")
    REASONING_LEVELS = ("off", "low", "medium", "high")

    def __init__(self):
        ai = settings_store.get_section("ai")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.nvidia_key = os.getenv("NVIDIA_API_KEY")
        self.nvidia_model = os.getenv("NVIDIA_MODEL", "meta/muse-glimmer-30b")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY")
        self.openrouter_model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        self.temperature = float(ai.get("temperature", 0.8))
        self.max_tokens_default = int(ai.get("maxTokens", 1000))
        self.reasoning = (ai.get("reasoning") or "low").lower()
        if self.reasoning not in self.REASONING_LEVELS:
            self.reasoning = "low"

        provider = (ai.get("provider", "nvidia") or "nvidia").lower()
        if provider not in self.VALID_PROVIDERS:
            provider = "nvidia"
        model = ai.get("model", "").strip()
        if model:
            if provider == "openrouter":
                self.openrouter_model = model
            if "llama" in model or "nemotron" in model or "muse" in model or "deepseek" in model:
                if provider != "openrouter":
                    self.nvidia_model = model
                elif "/" not in model:
                    self.nvidia_model = model
        self._forced_provider = provider
        self.active_provider = None
        self.fallback_models = [m.strip() for m in (ai.get("fallbackModels") or []) if m and m.strip()]
        self.last_model = self.nvidia_model
        self.last_error = None
        self.last_failover: list = []  # [{provider, model, error}] for the last complete() call

    @property
    def available(self) -> bool:
        return bool(self.openai_key or self.anthropic_key or self.nvidia_key or self.openrouter_key)

    @property
    def provider_name(self) -> str:
        if self._forced_provider in ("openai", "anthropic", "nvidia", "openrouter") and getattr(self, f"{self._forced_provider}_key", None):
            return self._forced_provider
        if self._forced_provider == "auto":
            return f"auto→{self.active_provider or 'none'}"
        if self.nvidia_key:
            return "nvidia"
        if self.openrouter_key:
            return "openrouter"
        if self.anthropic_key:
            return "anthropic"
        if self.openai_key:
            return "openai"
        return "fallback"

    @property
    def model(self) -> str:
        return self.last_model or self.nvidia_model

    def _model_chain(self, provider: str):
        if provider == "nvidia":
            chain = [self.nvidia_model] + self.fallback_models
        elif provider == "openrouter":
            chain = [self.openrouter_model] + self.fallback_models
        elif provider == "openai":
            chain = ["gpt-4o-mini"]
        else:
            chain = ["claude-3-5-haiku-latest"]
        seen, out = set(), []
        for m in chain:
            if m and m not in seen:
                seen.add(m)
                out.append(m)
        return out or [self.nvidia_model]

    async def complete(self, system_prompt: str, user_prompt: str, max_tokens: Optional[int] = None,
                       provider: Optional[str] = None, model: Optional[str] = None,
                       reasoning: Optional[str] = None, temperature: Optional[float] = None) -> Optional[str]:
        """Generate text. Tries the requested/forced provider's models, then auto-fails
        over to every other configured provider. Failures are recorded in
        self.last_failover so the UI can show what was tried."""
        if max_tokens is None:
            max_tokens = self.max_tokens_default
        if reasoning is None:
            reasoning = self.reasoning
        reasoning = (reasoning or "off").lower()
        if temperature is None:
            temperature = self.temperature
        forced = (provider or self._forced_provider or "auto").lower()
        if forced not in self.VALID_PROVIDERS:
            forced = "auto"
        if forced == "auto":
            order = ["nvidia", "openrouter", "openai", "anthropic"]
        else:
            order = [forced, "nvidia", "openrouter", "openai", "anthropic"]
        self.last_failover = []
        tried = set()
        for name in order:
            if name in tried or name == "auto":
                continue
            tried.add(name)
            if not getattr(self, f"{name}_key", False):
                continue
            chain = [model] if (model and name == forced) else self._model_chain(name)
            for m in chain:
                self.last_model = m
                result = await self._try(name, m, system_prompt, user_prompt, max_tokens,
                                         reasoning=reasoning, temperature=temperature)
                if result is not None:
                    return result
                self.last_failover.append({"provider": name, "model": m,
                                           "error": (self.last_error or "")[:300]})
        return None

    async def test_model(self, model: str, provider: Optional[str] = None) -> Dict:
        """Quick ping to verify a model works (used by the dashboard model tester)."""
        if provider is None or provider == "auto":
            provider = self._forced_provider if getattr(self, f"{self._forced_provider}_key", None) else "nvidia"
            if provider == "auto":
                provider = "openrouter" if self.openrouter_key else "nvidia"
        t = time.time()
        try:
            text = await self._try(
                provider, model,
                system_prompt="You are a health check. Reply with exactly: OK",
                user_prompt="ping",
                max_tokens=8,
            )
            latency = round(time.time() - t, 1)
            if text:
                return {"ok": True, "provider": provider, "model": model, "latency": latency, "error": None}
            return {"ok": False, "provider": provider, "model": model, "latency": latency,
                    "error": self.last_error or "empty response"}
        except Exception as e:
            return {"ok": False, "provider": provider, "model": model,
                    "latency": round(time.time() - t, 1), "error": str(e)}

    async def _try(self, name: str, model: str, system_prompt: str, user_prompt: str, max_tokens: int,
                   reasoning: str = "low", temperature: float = None):
        if temperature is None:
            temperature = self.temperature
        if name == "nvidia":
            return await self._try_nvidia(model, system_prompt, user_prompt, max_tokens, reasoning, temperature)
        if name == "openrouter":
            return await self._try_openrouter(model, system_prompt, user_prompt, max_tokens, reasoning, temperature)
        if name == "openai":
            return await self._try_openai(model, system_prompt, user_prompt, max_tokens, reasoning, temperature)
        if name == "anthropic":
            return await self._try_anthropic(model, system_prompt, user_prompt, max_tokens, reasoning, temperature)
        return None

    @staticmethod
    def _reasoning_budget(level: str) -> int:
        return {"low": 1024, "medium": 2048, "high": 4096}.get((level or "off").lower(), 0)

    async def _try_nvidia(self, model: str, system_prompt: str, user_prompt: str, max_tokens: int,
                          reasoning: str = "low", temperature: float = 0.8) -> Optional[str]:
        if not self.nvidia_key:
            return None
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=self.nvidia_key,
                base_url="https://integrate.api.nvidia.com/v1",
                timeout=180,
            )
            kwargs = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            # NOTE: NVIDIA's API rejects unknown params (incl. reasoning) with 400,
            # so never send extra_body there — reasoning models think on their own.
            response = await client.chat.completions.create(**kwargs)
            self.active_provider = "nvidia"
            self.last_error = None
            msg = response.choices[0].message
            text = (msg.content or "").strip() or (msg.reasoning_content or "").strip()
            return text or None
        except Exception as e:
            self.last_error = f"nvidia/{model}: {e}"
            print(f"[LLM] NVIDIA {model} failed: {e}")
            return None

    async def _try_openrouter(self, model: str, system_prompt: str, user_prompt: str, max_tokens: int,
                              reasoning: str = "low", temperature: float = 0.8) -> Optional[str]:
        """OpenRouter (OpenAI-compatible, https://openrouter.ai/api/v1). Free models available."""
        if not self.openrouter_key:
            return None
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=self.openrouter_key,
                base_url="https://openrouter.ai/api/v1",
                timeout=180,
                default_headers={
                    "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "http://localhost:5001"),
                    "X-Title": os.getenv("OPENROUTER_TITLE", "GodEye AI Agent"),
                },
            )
            kwargs = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if (reasoning or "off").lower() != "off":
                kwargs["extra_body"] = {"reasoning": {"effort": reasoning.lower()}}
            response = await client.chat.completions.create(**kwargs)
            self.active_provider = "openrouter"
            self.last_error = None
            msg = response.choices[0].message
            text = (msg.content or "").strip() or getattr(msg, "reasoning_content", "") or ""
            return (text or "").strip() or None
        except Exception as e:
            self.last_error = f"openrouter/{model}: {e}"
            print(f"[LLM] OpenRouter {model} failed: {e}")
            return None

    async def _try_openai(self, model: str, system_prompt: str, user_prompt: str, max_tokens: int,
                          reasoning: str = "low", temperature: float = 0.8) -> Optional[str]:
        if not self.openai_key:
            return None
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.openai_key, timeout=60)
            kwargs = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            # o1/o3/gpt-5 reasoning models accept reasoning_effort
            ml = model.lower()
            if (reasoning or "off").lower() != "off" and (ml.startswith("o1") or ml.startswith("o3") or ml.startswith("gpt-5")):
                kwargs["reasoning_effort"] = reasoning.lower()
            response = await client.chat.completions.create(**kwargs)
            self.active_provider = "openai"
            self.last_error = None
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.last_error = f"openai/{model}: {e}"
            print(f"[LLM] OpenAI call failed: {e}")
            return None

    async def _try_anthropic(self, model: str, system_prompt: str, user_prompt: str, max_tokens: int,
                             reasoning: str = "low", temperature: float = 0.8) -> Optional[str]:
        if not self.anthropic_key:
            return None
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.anthropic_key)
            kwargs = dict(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            budget = self._reasoning_budget(reasoning)
            # extended thinking (claude-3-7+): temperature must be 1.0 with thinking
            if budget > 0:
                kwargs["thinking"] = {"type": "enabled", "budget_tokens": budget}
                kwargs.pop("temperature", None)
            else:
                kwargs["temperature"] = temperature
            response = client.messages.create(**kwargs)
            self.active_provider = "anthropic"
            self.last_error = None
            return response.content[0].text.strip()
        except Exception as e:
            self.last_error = f"anthropic/{model}: {e}"
            print(f"[LLM] Anthropic call failed: {e}")
            return None