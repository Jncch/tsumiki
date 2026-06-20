"""プロバイダ非依存の LLM クライアント設定層.

CLAUDE.md §3 に従い、アプリ本体から特定プロバイダ SDK を直接呼ばず、
ここで base_url と認証情報を切り替える。

サポートプロバイダ:
- openai_compatible: 1 つの OpenAI SDK で以下を統一呼び出し
    * ollama (ホスト or コンテナ内, http://localhost:11434/v1 / host.docker.internal)
    * OpenAI 本家 (https://api.openai.com/v1, gpt-4o, gpt-5 等)
    * Anthropic Claude (https://api.anthropic.com/v1/, claude-opus-4-7 等.
      公式 OpenAI 互換層を使うため anthropic SDK 不要)
    * OpenRouter (https://openrouter.ai/api/v1, 横断プロキシ)
    * Google Gemini (https://generativelanguage.googleapis.com/v1beta/openai/)
- azure_openai: Azure OpenAI (デプロイ名でモデル指定、API バージョン必須)

Phase 7d 設計時点では Anthropic 公式 SDK 追加を検討していたが、
Anthropic が OpenAI 互換エンドポイントを公式提供している (docs.anthropic.com/ja/api/openai-sdk)
ため、追加依存なしで openai_compatible 経路 1 本で全プロバイダをカバーできる.

LLM_PROVIDER 環境変数で分岐する (未指定なら openai_compatible).
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

    @property
    def is_ollama(self) -> bool:
        """ollama (ローカル LLM サーバ) を指している場合のみ True.

        Phase 7d-4 で追加. ollama 拡張パラメータ (`options.num_ctx` 等) を
        Azure / OpenAI / Anthropic クラウド系に送らないための判定子.
        """
        if self.provider != "openai_compatible":
            return False
        base = self.base_url.lower()
        return ":11434" in base

    @classmethod
    def from_env(cls) -> LLMSettings:
        """環境変数のみから設定を構築する (CLI 引数による上書きなし)."""
        return cls.from_env_with_overrides()

    @classmethod
    def from_env_with_overrides(
        cls,
        *,
        provider: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        api_version: str | None = None,
    ) -> LLMSettings:
        """環境変数 + CLI 引数による上書きから設定を構築する.

        Phase 7-bonus-3 (2026-06-19) で復活. 7d-4 の `from_env()` 経路と互換性を保ちつつ,
        `experiments/*.py` の CLI 引数から個別フィールドを上書きできるようにする.

        優先順位: CLI 引数 (明示値) > 環境変数 > デフォルト.

        Args:
            provider: "openai_compatible" / "azure_openai". 未指定なら LLM_PROVIDER.
            base_url: openai_compatible なら LLM_BASE_URL, azure_openai なら
                AZURE_OPENAI_ENDPOINT を上書き.
            api_key: 同様に LLM_API_KEY / AZURE_OPENAI_API_KEY を上書き.
            model: openai_compatible なら LLM_MODEL, azure_openai なら
                AZURE_OPENAI_DEPLOYMENT を上書き.
            temperature: LLM_TEMPERATURE を上書き.
            api_version: AZURE_OPENAI_API_VERSION を上書き (azure_openai でのみ意味あり).

        Raises:
            RuntimeError: 必須フィールド (base_url, model 等) が環境変数にも引数にも無い場合.
        """
        provider_raw = (
            provider
            if provider is not None
            else os.environ.get("LLM_PROVIDER", "openai_compatible").strip()
        )
        if provider_raw not in ("openai_compatible", "azure_openai"):
            raise RuntimeError(
                f"unsupported LLM_PROVIDER: {provider_raw!r} "
                "(expected 'openai_compatible' or 'azure_openai')"
            )
        provider_typed: Provider = provider_raw  # type: ignore[assignment]
        effective_temperature = (
            temperature
            if temperature is not None
            else float(os.environ.get("LLM_TEMPERATURE", "0.0"))
        )

        if provider_typed == "azure_openai":
            endpoint = base_url or os.environ.get("AZURE_OPENAI_ENDPOINT")
            effective_api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY")
            deployment = model or os.environ.get("AZURE_OPENAI_DEPLOYMENT")
            effective_api_version = api_version or os.environ.get(
                "AZURE_OPENAI_API_VERSION"
            )
            if not endpoint:
                raise RuntimeError("AZURE_OPENAI_ENDPOINT is not set")
            if not effective_api_key:
                raise RuntimeError("AZURE_OPENAI_API_KEY is not set")
            if not deployment:
                raise RuntimeError("AZURE_OPENAI_DEPLOYMENT is not set")
            if not effective_api_version:
                raise RuntimeError("AZURE_OPENAI_API_VERSION is not set")
            return cls(
                provider=provider_typed,
                base_url=endpoint,
                api_key=effective_api_key,
                model=deployment,
                temperature=effective_temperature,
                api_version=effective_api_version,
            )

        # openai_compatible
        effective_base_url = base_url or os.environ.get("LLM_BASE_URL")
        effective_api_key = api_key or os.environ.get("LLM_API_KEY", "ollama")
        effective_model = model or os.environ.get("LLM_MODEL")
        if not effective_base_url:
            raise RuntimeError("LLM_BASE_URL is not set")
        if not effective_model:
            raise RuntimeError("LLM_MODEL is not set")
        return cls(
            provider=provider_typed,
            base_url=effective_base_url,
            api_key=effective_api_key,
            model=effective_model,
            temperature=effective_temperature,
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
