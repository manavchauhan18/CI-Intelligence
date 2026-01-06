"""
LLM adapter layer supporting multiple providers (OpenAI, Claude).
"""
import logging
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod

from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from .config import settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """Generate completion from prompt."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI LLM provider."""

    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """Generate completion using OpenAI."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            raise


class ClaudeProvider(LLMProvider):
    """Claude (Anthropic) LLM provider."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """Generate completion using Claude."""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt if system_prompt else "",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Claude API error: {e}", exc_info=True)
            raise


class LLMClient:
    """
    Unified LLM client with provider abstraction and fallback support.
    """

    def __init__(self):
        self.providers: Dict[str, LLMProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize available LLM providers."""
        # OpenAI
        if settings.openai_api_key:
            self.providers["openai"] = OpenAIProvider(
                api_key=settings.openai_api_key,
                model=settings.default_model if "gpt" in settings.default_model else "gpt-4-turbo-preview"
            )
            logger.info("Initialized OpenAI provider")

        # Claude
        if settings.anthropic_api_key:
            self.providers["claude"] = ClaudeProvider(
                api_key=settings.anthropic_api_key,
                model=settings.default_model if "claude" in settings.default_model else "claude-3-5-sonnet-20241022"
            )
            logger.info("Initialized Claude provider")

        if not self.providers:
            logger.warning("No LLM providers configured")

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        provider: Optional[str] = None
    ) -> str:
        """
        Generate completion with automatic fallback.

        Args:
            prompt: User prompt
            system_prompt: System prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            provider: Specific provider to use (optional)

        Returns:
            Generated text
        """
        if not self.providers:
            raise RuntimeError("No LLM providers available")

        # Use specific provider or default
        target_provider = provider or settings.default_llm_provider

        # Try primary provider
        if target_provider in self.providers:
            try:
                return await self.providers[target_provider].complete(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            except Exception as e:
                logger.error(f"Primary provider {target_provider} failed: {e}")

        # Fallback to any available provider
        for name, provider_instance in self.providers.items():
            if name != target_provider:
                try:
                    logger.info(f"Falling back to provider: {name}")
                    return await provider_instance.complete(
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                except Exception as e:
                    logger.error(f"Fallback provider {name} failed: {e}")

        raise RuntimeError("All LLM providers failed")


# Global LLM client instance
llm_client = LLMClient()
