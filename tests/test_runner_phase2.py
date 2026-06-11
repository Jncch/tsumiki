"""Phase 2 統合 Runner のテスト. ChatFn はモック."""

from __future__ import annotations

import re
from pathlib import Path

import mlflow

from tsumiki.baseline import (
    MODIFICATION_PROMPT_VERSION_LATEST_REUSE,
    MODIFICATION_PROMPT_VERSION_LATEST_ZEROBASE,
)
from tsumiki.data.synthesis import ChatFn, ChatResult
from tsumiki.exp import setup_tracking
from tsumiki.knowledge import load_ng_patterns
from tsumiki.runner.phase2 import (
    _build_synth_only_samples,
    run_phase2_variant,
)

_PATTERN_RE = re.compile(r"\[(?P<pid>[A-Za-z_0-9]+)\]")
_HAS_ID_RE = re.compile(r"<(?P<pid>[A-Za-z_0-9]+)>")


def _omniscient_synth_chat() -> ChatFn:
    def fn(prompt: str) -> ChatResult:
        ids = [m.group("pid") for m in _PATTERN_RE.finditer(prompt)]
        text = "合成本文: " + " ".join(f"<{i}>" for i in ids) if ids else "本文"
        return ChatResult(content=text, tokens_in=10, tokens_out=5, elapsed_ms=1.0)

    return fn


def _perfect_modifier_chat() -> ChatFn:
    """target id をすべて除去するモック."""

    def fn(prompt: str) -> ChatResult:
        # prompt から target id を読み取り、対応する <id> マーカーを除去
        target_lines = re.findall(r"^- ([a-z_0-9]+)$", prompt, flags=re.MULTILINE)
        text = "合成本文: 元の <X> を消した"
        # シンプルに全 target id を消す体で返す
        for tid in target_lines:
            text = text.replace(f"<{tid}>", "")
        return ChatResult(content=text.strip(), tokens_in=10, tokens_out=5, elapsed_ms=1.0)

    return fn


def _oracle_detector_chat() -> ChatFn:
    """テキスト中の <id> を検出して返すモック."""

    def fn(prompt: str) -> ChatResult:
        # 「対象条項」ブロック内の <id> を返す
        idx = prompt.find("# 対象条項")
        body = prompt[idx:] if idx >= 0 else prompt
        ids = re.findall(r"<([A-Za-z_0-9]+)>", body)
        return ChatResult(content="\n".join(ids), tokens_in=10, tokens_out=5, elapsed_ms=1.0)

    return fn


def _clean_clauses() -> list:
    from tsumiki.data.clauses import CleanClause

    return [
        CleanClause(
            clause_id=f"src1:{i}",
            contract_type="nda",
            source_id="src1",
            article_no=str(i),
            text=f"第{i}条 本文。",
        )
        for i in range(1, 6)
    ]


def test_build_synth_only_samples_no_duplicates() -> None:
    from tsumiki.data.synthesis import SynthesisConfig

    book = load_ng_patterns("nda")
    patterns = tuple(book.patterns)
    samples = _build_synth_only_samples(
        _clean_clauses(),
        patterns,
        SynthesisConfig(model="x", seed=42),
        n_synth_per_pattern=3,
        synth_chat_fn=_omniscient_synth_chat(),
        seed=42,
    )
    # clean 5 × patterns 9 だが、n_synth=3 で capped
    assert len(samples) == 3 * len(patterns)
    ids = [s[0] for s in samples]
    assert len(ids) == len(set(ids))


def test_run_phase2_variant_records_metrics(tmp_path: Path) -> None:
    uri = setup_tracking(f"file:{tmp_path / 'mlruns'}")
    mlflow.set_experiment("test_phase2")
    book = load_ng_patterns("nda")

    # 手動でサンプルを作る（合成器に依存しない）
    samples = [
        ("c1|nda_scope_overbroad", "本文 <nda_scope_overbroad>", ("nda_scope_overbroad",)),
        ("c2|nda_duration_unbounded", "本文 <nda_duration_unbounded>", ("nda_duration_unbounded",)),
    ]

    out = run_phase2_variant(
        variant_name="reuse",
        samples=samples,
        ng_book=book,
        modifier_chat_fn=_perfect_modifier_chat(),
        detector_chat_fn=_oracle_detector_chat(),
        modifier_prompt_version=MODIFICATION_PROMPT_VERSION_LATEST_REUSE,
        detector_prompt_version="v0.3.0",
        run_params_extra={"seed": 42, "model": "test", "phase": "phase2_dryrun"},
        run_name="r_test",
    )

    assert out.variant == "reuse"
    assert out.n_samples == 2
    # 完璧な modifier なので 100% 成功
    assert out.report.modification_success_rate == 1.0
    assert out.report.negative_transfer_rate == 0.0

    client = mlflow.MlflowClient(tracking_uri=uri)
    exp = client.get_experiment_by_name("test_phase2")
    assert exp is not None
    runs = client.search_runs(exp.experiment_id)
    r = runs[0]
    assert r.data.params["variant"] == "reuse"
    assert "modification_success_rate" in r.data.metrics
    assert r.data.metrics["modification_success_rate"] == 1.0


def test_run_phase2_variant_zerobase_omits_dict(tmp_path: Path) -> None:
    """zerobase variant が辞書を見せないことを間接確認（modifier への prompt 中身）."""
    uri = setup_tracking(f"file:{tmp_path / 'mlruns'}")
    mlflow.set_experiment("test_phase2_zerobase")
    book = load_ng_patterns("nda")

    seen_prompts: list[str] = []

    def capture_chat(prompt: str) -> ChatResult:
        seen_prompts.append(prompt)
        return ChatResult(content="修正本文", tokens_in=1, tokens_out=1, elapsed_ms=0)

    samples = [
        ("c1|A", "本文", ("nda_scope_overbroad",)),
    ]
    run_phase2_variant(
        variant_name="zerobase",
        samples=samples,
        ng_book=book,
        modifier_chat_fn=capture_chat,
        detector_chat_fn=_oracle_detector_chat(),
        modifier_prompt_version=MODIFICATION_PROMPT_VERSION_LATEST_ZEROBASE,
        detector_prompt_version="v0.3.0",
        run_params_extra={"seed": 42, "model": "test", "phase": "phase2_dryrun"},
        run_name="r_zerobase",
    )
    assert seen_prompts, "modifier was not called"
    assert "nda_scope_overbroad" not in seen_prompts[0]
    _ = uri  # silence unused