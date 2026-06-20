"""TaskSpec から EvaluatorSpec を LLM 経由で生成する.

Q2=C: 評価器自動生成 + ユーザー承認 + 流用蓄積.
Q3=B: 決定関数 + LLM judge (後者はガードレール必須).

設計: docs/experiments/phase5c_design.md §1.4
"""

from __future__ import annotations

from collections.abc import Callable
from textwrap import dedent

from tsumiki.goal._json_helpers import extract_json_object
from tsumiki.goal.render import task_spec_to_yaml
from tsumiki.goal.specs import EvaluatorSpec, TaskSpec, TestCase

ChatFn = Callable[[str], str]

GENERATE_PROMPT_VERSION_LATEST = "v1"

_GENERATE_PROMPT_V1 = dedent(
    """
    あなたは TaskSpec から評価器コードを生成するアシスタントです.

    TaskSpec:
    '''
    {task_spec_yaml}
    '''

    要件:
    - 出力は決定関数 (type="deterministic") を優先する. ラベル系・構造一致系で済むなら必ず deterministic を選ぶ.
    - LLM judge を含む場合は type を "llm_judge" または "hybrid" にし、guardrails に少なくとも 1 つ ("pairwise", "panel_3", "human_calibration" のいずれか) を含める.
    - implementation は Python ソースコード文字列で、`def evaluate(outcomes: list[dict]) -> dict:` を 1 つ含むこと.
    - test_cases は最低 3 件: 空入力、典型成功、典型失敗.
    - 既存実装の流用候補があれば sources にパス・文献を列挙する.

    以下の JSON 構造で必ず出力してください. JSON のみを返し、説明文や ``` フェンスは付けないでください.

    {{
      "id": "<id のスネークケース. 例: nda_modification_success_v1>",
      "type": "deterministic" | "llm_judge" | "hybrid",
      "output_metrics": ["<指標名>"],
      "implementation": "<Python ソースコード文字列. evaluate 関数を含む>",
      "test_cases": [
        {{
          "name": "<テスト名>",
          "input": {{"outcomes": [<dict>, ...]}},
          "expected": {{"<指標名>": <値>}}
        }}
      ],
      "guardrails": ["<ガードレール名>"],
      "sources": ["<参照した既存実装・文献>"],
      "notes": "<既知の偏り・適用条件>"
    }}
    """
).strip()

_PROMPT_REGISTRY: dict[str, str] = {"v1": _GENERATE_PROMPT_V1}


def build_generate_prompt(
    task_spec: TaskSpec,
    *,
    prompt_version: str = GENERATE_PROMPT_VERSION_LATEST,
) -> str:
    template = _PROMPT_REGISTRY.get(prompt_version)
    if template is None:
        raise ValueError(f"unsupported prompt_version: {prompt_version}")
    return template.format(task_spec_yaml=task_spec_to_yaml(task_spec))


def generate_evaluator(
    task_spec: TaskSpec,
    chat_fn: ChatFn,
    *,
    generated_at: str,
    approved_by: str = "auto",
    prompt_version: str = GENERATE_PROMPT_VERSION_LATEST,
) -> EvaluatorSpec:
    """ChatFn で LLM を呼び EvaluatorSpec を返す.

    domain / task_class / input_signature は task_spec から継承する.
    LLM 側で正しく生成されなくても、TaskSpec の整合性で上書きする.
    """
    prompt = build_generate_prompt(task_spec, prompt_version=prompt_version)
    text = chat_fn(prompt)
    doc = extract_json_object(text)
    return _spec_from_dict(
        doc, task_spec, generated_at=generated_at, approved_by=approved_by
    )


def _spec_from_dict(
    doc: dict,
    task_spec: TaskSpec,
    *,
    generated_at: str,
    approved_by: str,
) -> EvaluatorSpec:
    test_cases = tuple(
        TestCase(
            name=str(tc.get("name", "")),
            input=dict(tc.get("input", {}) or {}),
            expected=dict(tc.get("expected", {}) or {}),
        )
        for tc in doc.get("test_cases", []) or []
    )
    return EvaluatorSpec(
        id=str(doc["id"]),
        domain=task_spec.domain,
        task_class=task_spec.task_class,
        type=doc["type"],
        input_signature=task_spec.io_signature(),
        output_metrics=tuple(str(x) for x in doc.get("output_metrics", []) or []),
        implementation=str(doc["implementation"]),
        test_cases=test_cases,
        guardrails=tuple(str(x) for x in doc.get("guardrails", []) or []),
        sources=tuple(str(x) for x in doc.get("sources", []) or []),
        generated_at=generated_at,
        approved_by=approved_by,
        notes=str(doc.get("notes", "") or ""),
    )
