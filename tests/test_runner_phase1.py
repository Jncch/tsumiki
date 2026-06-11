"""Phase 1 統合 Runner のテスト. ChatFn をモックして LLM 不要."""

from __future__ import annotations

import re
from pathlib import Path

import mlflow

from tsumiki.data.clauses import CleanClause
from tsumiki.data.synthesis import ChatFn, ChatResult, SynthesisConfig
from tsumiki.eval.split import SplitConfig
from tsumiki.exp import setup_tracking
from tsumiki.knowledge import load_ng_patterns
from tsumiki.runner import build_labeled_samples, run_phase1

_PATTERN_RE = re.compile(r"\[(?P<pid>[A-Za-z_0-9]+)\]")


def _omniscient_synth_chat() -> ChatFn:
    """注入プロンプト中の [pattern_id] を返答に含める「正しい」合成器."""

    def fn(prompt: str) -> ChatResult:
        ids = [m.group("pid") for m in _PATTERN_RE.finditer(prompt)]
        text = "改変後本文: " + " ".join(f"<{i}>" for i in ids) if ids else "本文"
        return ChatResult(content=text, tokens_in=50, tokens_out=10, elapsed_ms=1.0)

    return fn


def _oracle_detector_chat() -> ChatFn:
    """対象条項の `<id>` トークンを読み取り正解 id を返す「神予測器」.

    実 LLM ではなく runner の orchestration をテストするためのもの。
    """

    def fn(prompt: str) -> ChatResult:
        # prompt 末尾の対象条項本体に `<id>` がある想定
        ids = re.findall(r"<([A-Za-z_0-9]+)>", prompt)
        return ChatResult(content="\n".join(ids), tokens_in=80, tokens_out=20, elapsed_ms=1.0)

    return fn


def _clean_clauses() -> list[CleanClause]:
    return [
        CleanClause(
            clause_id=f"src1:{i}",
            contract_type="nda",
            source_id="src1",
            article_no=str(i),
            text=f"第{i}条 本文。",
        )
        for i in range(1, 11)
    ]


def test_build_labeled_samples_counts() -> None:
    book = load_ng_patterns("nda")
    patterns = (book.by_id("nda_scope_overbroad"), book.by_id("nda_duration_unbounded"))
    cfg = SynthesisConfig(model="x", seed=42)
    labels = build_labeled_samples(
        _clean_clauses(),
        patterns,
        cfg,
        n_synth_per_pattern=3,
        n_clean=4,
        synth_chat_fn=_omniscient_synth_chat(),
        seed=42,
    )
    # clean 4 + synth (3 * 2 patterns) = 10
    assert len(labels) == 10
    n_clean = sum(1 for x in labels if not x.ng_pattern_ids)
    n_synth = sum(1 for x in labels if x.ng_pattern_ids)
    assert n_clean == 4 and n_synth == 6


def test_build_labeled_samples_no_duplicate_clause_ids() -> None:
    """同じ (clean, pattern) ペアが衝突して label clause_id が重複しないこと."""
    book = load_ng_patterns("nda")
    patterns = tuple(book.patterns)
    cfg = SynthesisConfig(model="x", seed=42)
    # n_synth_per_pattern=10, clean 数=10 → 各パターンで全 clean が使われる
    labels = build_labeled_samples(
        _clean_clauses(),
        patterns,
        cfg,
        n_synth_per_pattern=10,
        n_clean=10,
        synth_chat_fn=_omniscient_synth_chat(),
        seed=42,
    )
    ids = [lab.clause_id for lab in labels]
    assert len(ids) == len(set(ids))  # 全 label の clause_id が一意


def test_build_labeled_samples_caps_at_available_clean() -> None:
    """n_synth_per_pattern が clean 数を超えた場合は available 件数で頭打ち."""
    book = load_ng_patterns("nda")
    patterns = (book.by_id("nda_scope_overbroad"),)
    cfg = SynthesisConfig(model="x", seed=42)
    # clean 10 件に対し n_synth=20 を要求
    labels = build_labeled_samples(
        _clean_clauses(),
        patterns,
        cfg,
        n_synth_per_pattern=20,
        n_clean=0,
        synth_chat_fn=_omniscient_synth_chat(),
        seed=42,
    )
    # 10 件で頭打ちのはず
    assert len(labels) == 10


def test_run_phase1_end_to_end_high_recall_on_oracle(tmp_path: Path) -> None:
    setup_tracking(f"file:{tmp_path / 'mlruns'}")
    mlflow.set_experiment("test_phase1")
    book = load_ng_patterns("nda")
    # 評価が安定するよう synth 件数を多めに
    out = run_phase1(
        clean_clauses=_clean_clauses(),
        ng_book=book,
        synth_config=SynthesisConfig(model="synth-x", seed=42),
        split_config=SplitConfig(seed=42),
        n_synth_per_pattern=4,
        n_clean=6,
        synth_chat_fn=_omniscient_synth_chat(),
        baseline_chat_fn=_oracle_detector_chat(),
        baseline_model="oracle",
        baseline_quant_tag="n/a",
        baseline_prompt_version="v0.1.0",
        run_name="r_oracle",
    )
    assert out.n_train + out.n_val + out.n_test == 6 + len(book.patterns) * 4
    # oracle 予測器なので test の macro_recall は十分に高いはず
    assert out.test_report.macro_recall >= 0.8


def test_run_phase1_records_required_params(tmp_path: Path) -> None:
    uri = setup_tracking(f"file:{tmp_path / 'mlruns'}")
    mlflow.set_experiment("test_phase1_params")
    book = load_ng_patterns("nda")
    out = run_phase1(
        clean_clauses=_clean_clauses(),
        ng_book=book,
        synth_config=SynthesisConfig(model="synth-x", seed=7),
        split_config=SplitConfig(seed=7),
        n_synth_per_pattern=2,
        n_clean=3,
        synth_chat_fn=_omniscient_synth_chat(),
        baseline_chat_fn=_oracle_detector_chat(),
        baseline_model="m",
        baseline_quant_tag="q",
        baseline_prompt_version="v0.1.0",
        run_name="r_params",
    )
    client = mlflow.MlflowClient(tracking_uri=uri)
    exp = client.get_experiment_by_name("test_phase1_params")
    assert exp is not None
    runs = client.search_runs(exp.experiment_id)
    r = runs[0]
    assert r.data.params["model"] == "m"
    assert r.data.params["phase"] == "phase1_baseline"
    assert "val.macro_recall" in r.data.metrics
    assert "test.macro_recall" in r.data.metrics
    assert out.test_report.beta == 2.0
