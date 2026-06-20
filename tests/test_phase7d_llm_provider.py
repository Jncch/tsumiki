"""Phase 7d: LLM プロバイダ層の構造確認 smoke test.

設計書 `phase7_design.md` §6.4 第 1 ゲートに対応 (実呼び出しなし、ネット不要).

- LLMSettings.from_env が openai_compatible / azure_openai 両系統で動く
- 必須 env 不足時に明示エラー
- build_client が provider に応じた SDK クライアントを返す
- Anthropic / OpenRouter / Gemini が同じ openai_compatible 経路で扱えること
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from openai import AzureOpenAI, OpenAI

from tsumiki.llm.client import LLMSettings, build_client

LLM_ENV_KEYS = (
    "LLM_PROVIDER",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_TEMPERATURE",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_API_VERSION",
)


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """LLM_* / AZURE_OPENAI_* env を一切無効化した状態で各テストを走らせる."""
    for key in LLM_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield


# === openai_compatible 経路 ===


@pytest.mark.parametrize(
    "base_url,model,description",
    [
        ("http://localhost:11434/v1", "qwen25-14b-ctx8k", "ollama host"),
        (
            "http://host.docker.internal:11434/v1",
            "qwen25-14b-ctx8k",
            "ollama container",
        ),
        ("https://api.openai.com/v1", "gpt-4o", "OpenAI 本家"),
        ("https://api.anthropic.com/v1/", "claude-opus-4-7", "Anthropic OpenAI 互換"),
        ("https://openrouter.ai/api/v1", "anthropic/claude-opus-4-7", "OpenRouter"),
        (
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            "gemini-2.5-pro",
            "Gemini",
        ),
    ],
)
def test_openai_compatible_accepts_multiple_providers(
    isolated_env: None,
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
    model: str,
    description: str,
) -> None:
    """openai_compatible 経路で ollama / OpenAI / Anthropic / OpenRouter / Gemini を受け付ける."""
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_BASE_URL", base_url)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", model)
    settings = LLMSettings.from_env()
    assert settings.provider == "openai_compatible"
    assert settings.base_url == base_url
    assert settings.model == model
    client = build_client(settings)
    assert isinstance(client, OpenAI), f"{description}: OpenAI client が返らない"


def test_openai_compatible_requires_base_url(
    isolated_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    with pytest.raises(RuntimeError, match="LLM_BASE_URL"):
        LLMSettings.from_env()


def test_openai_compatible_requires_model(
    isolated_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "https://api.openai.com/v1")
    with pytest.raises(RuntimeError, match="LLM_MODEL"):
        LLMSettings.from_env()


# === azure_openai 経路 ===


def test_azure_openai_builds_when_all_env_set(
    isolated_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "my-gpt-4o")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    settings = LLMSettings.from_env()
    assert settings.provider == "azure_openai"
    assert settings.model == "my-gpt-4o"  # デプロイ名
    assert settings.api_version == "2024-10-21"
    client = build_client(settings)
    assert isinstance(client, AzureOpenAI)


@pytest.mark.parametrize(
    "missing_key",
    [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_VERSION",
    ],
)
def test_azure_openai_requires_all_env(
    isolated_env: None, monkeypatch: pytest.MonkeyPatch, missing_key: str
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    for k, v in [
        ("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/"),
        ("AZURE_OPENAI_API_KEY", "test-key"),
        ("AZURE_OPENAI_DEPLOYMENT", "dep"),
        ("AZURE_OPENAI_API_VERSION", "2024-10-21"),
    ]:
        if k != missing_key:
            monkeypatch.setenv(k, v)
    with pytest.raises(RuntimeError, match=missing_key):
        LLMSettings.from_env()


# === provider 名のバリデーション ===


def test_invalid_provider_raises(
    isolated_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic_native")
    with pytest.raises(RuntimeError, match="unsupported LLM_PROVIDER"):
        LLMSettings.from_env()


def test_default_provider_is_openai_compatible(
    isolated_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LLM_PROVIDER 未指定なら openai_compatible (既存挙動)."""
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen25-14b-ctx8k")
    settings = LLMSettings.from_env()
    assert settings.provider == "openai_compatible"


# === is_ollama (Phase 7d-4 fix) ===


@pytest.mark.parametrize(
    "base_url,expected",
    [
        ("http://localhost:11434/v1", True),
        ("http://host.docker.internal:11434/v1", True),
        ("https://api.openai.com/v1", False),
        ("https://api.anthropic.com/v1/", False),
        ("https://openrouter.ai/api/v1", False),
        ("https://generativelanguage.googleapis.com/v1beta/openai/", False),
    ],
)
def test_is_ollama_detection(
    isolated_env: None,
    monkeypatch: pytest.MonkeyPatch,
    base_url: str,
    expected: bool,
) -> None:
    """ollama 判定が ollama / クラウド系で正しく分かれる.

    `make_openai_chat_fn` で `num_ctx` (ollama 拡張 options) を渡すかの判定に使う.
    """
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_BASE_URL", base_url)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "any-model")
    settings = LLMSettings.from_env()
    assert settings.is_ollama is expected


def test_is_ollama_false_for_azure(
    isolated_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """azure_openai は (たとえポートが何でも) ollama ではない."""
    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    settings = LLMSettings.from_env()
    assert settings.is_ollama is False


# === temperature ===


def test_temperature_default_is_zero(
    isolated_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LLM_TEMPERATURE 未指定なら 0.0 (CLAUDE.md §4 再現性ルール)."""
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen25-14b-ctx8k")
    settings = LLMSettings.from_env()
    assert settings.temperature == 0.0


def test_temperature_overridable(
    isolated_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen25-14b-ctx8k")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.7")
    settings = LLMSettings.from_env()
    assert settings.temperature == 0.7
