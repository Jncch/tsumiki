"""プロバイダ非依存の LLM クライアント設定層.

CLAUDE.md §3 に従い、アプリ本体から特定プロバイダ SDK を直接呼ばず、
ここで base_url と認証情報を切り替える。

サポートプロバイダ:
- openai_compatible: ollama / OpenAI / Anthropic OpenAI 互換 / OpenRouter / Gemini OpenAI 互換 等
- azure_openai: Azure OpenAI（デプロイ名でモデル指定、API バージョン必須）

LLM_PROVIDER 環境変数で分岐する（未指定なら openai_compatible）。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from openai import AzureOpenAI, OpenAI

Provider = Literal["openai_compatible", "azure_openai"]


@dataclass(frozen=True)
class LLMSettings:
    """LLM 接続設定. provider によって意味が変わる:

    - provider="openai_compatible":
        base_url: OpenAI 互換エンドポイント (e.g. https://api.openai.com/v1, ollama)
        api_key:  API キー（ollama は "ollama" 等のダミーで OK）
        model:    モデル名（chat.completions.create の model 引数に渡す）

    - provider="azure_openai":
        base_url: Azure リソースのエンドポイント (e.g. https://<resource>.openai.azure.com/)
        api_key:  Azure API キー
        model:    Azure の **デプロイ名**（モデル名ではない）
        api_version: Azure OpenAI の API バージョン (e.g. 2024-10-21)
    """

    provider: Provider
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.0
    api_version: str = ""  # azure_openai でのみ意味を持つ

    @classmethod
    def from_env(cls) -> LLMSettings:
        provider_raw = os.environ.get("LLM_PROVIDER", "openai_compatible").strip()
        if provider_raw not in ("openai_compatible", "azure_openai"):
            raise RuntimeError(
                f"unsupported LLM_PROVIDER: {provider_raw!r} "
                "(expected 'openai_compatible' or 'azure_openai')"
            )
        provider: Provider = provider_raw  # type: ignore[assignment]
        temperature = float(os.environ.get("LLM_TEMPERATURE", "0.0"))

        if provider == "azure_openai":
            endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
            api_key = os.environ.get("AZURE_OPENAI_API_KEY")
            deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
            api_version = os.environ.get("AZURE_OPENAI_API_VERSION")
            if not endpoint:
                raise RuntimeError("AZURE_OPENAI_ENDPOINT is not set")
            if not api_key:
                raise RuntimeError("AZURE_OPENAI_API_KEY is not set")
            if not deployment:
                raise RuntimeError("AZURE_OPENAI_DEPLOYMENT is not set")
            if not api_version:
                raise RuntimeError("AZURE_OPENAI_API_VERSION is not set")
            return cls(
                provider=provider,
                base_url=endpoint,
                api_key=api_key,
                model=deployment,
                temperature=temperature,
                api_version=api_version,
            )

        # openai_compatible
        base_url = os.environ.get("LLM_BASE_URL")
        api_key = os.environ.get("LLM_API_KEY", "ollama")
        model = os.environ.get("LLM_MODEL")
        if not base_url:
            raise RuntimeError("LLM_BASE_URL is not set")
        if not model:
            raise RuntimeError("LLM_MODEL is not set")
        return cls(
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            model=model,
            temperature=temperature,
        )


def build_client(settings: LLMSettings) -> OpenAI | AzureOpenAI:
    """settings から OpenAI / AzureOpenAI クライアントを作る.

    どちらも chat.completions.create インターフェースは同一なので、
    呼び出し側 (make_openai_chat_fn) は変更不要。
    """
    if settings.provider == "azure_openai":
        return AzureOpenAI(
            azure_endpoint=settings.base_url,
            api_key=settings.api_key,
            api_version=settings.api_version,
        )
    return OpenAI(base_url=settings.base_url, api_key=settings.api_key)
