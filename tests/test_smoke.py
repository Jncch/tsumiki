"""最小スモーク: パッケージが import できることを確認."""

from __future__ import annotations


def test_import_package() -> None:
    import tsumiki

    assert tsumiki.__version__


def test_import_llm_settings() -> None:
    from tsumiki.llm import LLMSettings, build_client  # noqa: F401
