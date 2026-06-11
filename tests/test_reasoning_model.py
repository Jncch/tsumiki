"""reasoning モデル (GPT-5/o1/o3) 判定と make_openai_chat_fn のパラメータ振り分けテスト."""

from __future__ import annotations

from tsumiki.data.synthesis import is_reasoning_model, make_openai_chat_fn


class _DummyUsage:
    prompt_tokens = 10
    completion_tokens = 5


class _DummyChoice:
    class _Msg:
        content = "hello"

    message = _Msg()


class _DummyResp:
    choices = [_DummyChoice()]
    usage = _DummyUsage()


class _DummyChatCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def create(self, **kwargs) -> _DummyResp:  # noqa: ANN003
        self.calls.append(kwargs)
        return _DummyResp()


class _DummyChat:
    def __init__(self, completions: _DummyChatCompletions) -> None:
        self.completions = completions


class _DummyClient:
    def __init__(self) -> None:
        self._completions = _DummyChatCompletions()
        self.chat = _DummyChat(self._completions)

    @property
    def calls(self) -> list[dict]:
        return self._completions.calls


def test_is_reasoning_model_identifies_gpt5_o1_o3() -> None:
    assert is_reasoning_model("gpt-5")
    assert is_reasoning_model("gpt-5.4")
    assert is_reasoning_model("gpt-5-2025-08-07")
    assert is_reasoning_model("o1")
    assert is_reasoning_model("o1-preview")
    assert is_reasoning_model("o3")
    assert is_reasoning_model("o3-mini")
    assert is_reasoning_model("o4")


def test_is_reasoning_model_rejects_classical_models() -> None:
    assert not is_reasoning_model("gpt-4o")
    assert not is_reasoning_model("gpt-4-turbo")
    assert not is_reasoning_model("gpt-3.5-turbo")
    assert not is_reasoning_model("claude-opus-4-7")
    assert not is_reasoning_model("hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M")


def test_chat_fn_classical_model_passes_temperature_and_seed() -> None:
    client = _DummyClient()
    fn = make_openai_chat_fn(client, "gpt-4o", temperature=0.0, seed=42)
    _ = fn("hello")
    assert len(client.calls) == 1
    kw = client.calls[0]
    assert kw["model"] == "gpt-4o"
    assert kw["temperature"] == 0.0
    assert kw["seed"] == 42
    # classical では max_completion_tokens は送らない
    assert "max_completion_tokens" not in kw
    assert "max_tokens" not in kw


def test_chat_fn_reasoning_model_uses_max_completion_tokens_only() -> None:
    client = _DummyClient()
    fn = make_openai_chat_fn(client, "gpt-5.4", temperature=0.0, seed=42)
    _ = fn("hello")
    assert len(client.calls) == 1
    kw = client.calls[0]
    assert kw["model"] == "gpt-5.4"
    # reasoning では temperature/seed を送らない（API が許容しないため）
    assert "temperature" not in kw
    assert "seed" not in kw
    # 代わりに max_completion_tokens を送る
    assert "max_completion_tokens" in kw
    assert kw["max_completion_tokens"] == 4096


def test_chat_fn_reasoning_model_respects_custom_max_completion_tokens() -> None:
    client = _DummyClient()
    fn = make_openai_chat_fn(
        client, "o3-mini", temperature=0.0, seed=42, max_completion_tokens=8000
    )
    _ = fn("hello")
    assert client.calls[0]["max_completion_tokens"] == 8000
