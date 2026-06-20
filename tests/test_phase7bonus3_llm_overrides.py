"""Phase 7-bonus-3: LLMSettings.from_env_with_overrides() の優先順位検証.

ユーザー要望:「最終的にはCLI引数で渡せるようにしたいです」
優先順位: CLI 引数 (明示値) > 環境変数 > デフォルト.

7d-4 で from_env() に統一した経路を保ちつつ, CLI 引数による上書き経路を復活する.
"""

from __future__ import annotations

import pytest

from tsumiki.llm.client import LLMSettings


@pytest.fixture(autouse=True)
def _clear_llm_env(monkeypatch):
    """各 test 開始時に LLM_* / AZURE_OPENAI_* 関連環境変数をクリアする."""
    for k in (
        "LLM_PROVIDER",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_TEMPERATURE",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_VERSION",
    ):
        monkeypatch.delenv(k, raising=False)


# === openai_compatible 経路 ===


def test_overrides_only_no_env(monkeypatch):
    """環境変数を一切設定せず CLI 引数だけで構築できる."""
    settings = LLMSettings.from_env_with_overrides(
        provider="openai_compatible",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        model="qwen2.5:7b",
        temperature=0.3,
    )
    assert settings.provider == "openai_compatible"
    assert settings.base_url == "http://localhost:11434/v1"
    assert settings.api_key == "ollama"
    assert settings.model == "qwen2.5:7b"
    assert settings.temperature == 0.3


def test_env_only_no_overrides(monkeypatch):
    """環境変数のみで構築できる (from_env と同型)."""
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:14b")
    settings = LLMSettings.from_env_with_overrides()
    assert settings.model == "qwen2.5:14b"
    assert settings.api_key == "ollama"  # デフォルト


def test_overrides_take_priority_over_env(monkeypatch):
    """CLI 引数が環境変数より優先される."""
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.0")
    settings = LLMSettings.from_env_with_overrides(
        model="qwen2.5:14b",  # override
        temperature=0.5,      # override
    )
    assert settings.model == "qwen2.5:14b"
    assert settings.temperature == 0.5
    # 上書きしなかった base_url は env 由来
    assert settings.base_url == "http://localhost:11434/v1"


def test_temperature_explicit_zero_is_not_treated_as_missing(monkeypatch):
    """temperature=0.0 を明示した場合 None と区別される (重要: 再現性関連)."""
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "any")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.7")
    settings = LLMSettings.from_env_with_overrides(temperature=0.0)
    assert settings.temperature == 0.0  # env 0.7 を上書き


def test_missing_required_raises_when_no_env_no_override(monkeypatch):
    """LLM_BASE_URL も override も無いと raise (provider=openai_compatible)."""
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b")
    with pytest.raises(RuntimeError, match="LLM_BASE_URL"):
        LLMSettings.from_env_with_overrides()


# === azure_openai 経路 ===


def test_azure_overrides_only(monkeypatch):
    """Azure 経路で全フィールドを CLI 引数で構築できる."""
    settings = LLMSettings.from_env_with_overrides(
        provider="azure_openai",
        base_url="https://example.openai.azure.com/",
        api_key="azure-key",
        model="gpt-5",
        api_version="2024-10-21",
        temperature=0.2,
    )
    assert settings.provider == "azure_openai"
    assert settings.base_url == "https://example.openai.azure.com/"
    assert settings.api_key == "azure-key"
    assert settings.model == "gpt-5"
    assert settings.api_version == "2024-10-21"


def test_azure_env_overridden_by_args(monkeypatch):
    """Azure 経路で env と override が混在 (override 優先)."""
    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://env.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-08-01")
    settings = LLMSettings.from_env_with_overrides(
        model="gpt-5",  # deployment 上書き
    )
    assert settings.model == "gpt-5"
    assert settings.base_url == "https://env.openai.azure.com/"
    assert settings.api_version == "2024-08-01"


def test_azure_missing_api_version_raises(monkeypatch):
    """Azure で api_version 未指定なら raise."""
    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "d")
    with pytest.raises(RuntimeError, match="API_VERSION"):
        LLMSettings.from_env_with_overrides()


# === provider 不正値 ===


def test_invalid_provider_raises():
    with pytest.raises(RuntimeError, match="unsupported LLM_PROVIDER"):
        LLMSettings.from_env_with_overrides(provider="anthropic")


# === from_env() が from_env_with_overrides() に委譲 ===


def test_from_env_delegates_to_overrides(monkeypatch):
    """from_env() は from_env_with_overrides() の薄い委譲 (互換性確認)."""
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen2.5:7b")
    a = LLMSettings.from_env()
    b = LLMSettings.from_env_with_overrides()
    assert a == b
