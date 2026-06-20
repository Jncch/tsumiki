"""自然言語の目的を LLM 経由で TaskSpec に変換する.

Q1=C ハイブリッド方式: 自然言語入力 → LLM 構造化 → ユーザー確認.
本モジュールは「LLM 構造化」部分を担う. 確認・修正フローは runner/e2e.py で扱う.

設計: docs/experiments/phase5c_design.md §1.2
"""

from __future__ import annotations

from collections.abc import Callable
from textwrap import dedent

from tsumiki.goal._json_helpers import extract_json_object
from tsumiki.goal.specs import (
    InputRole,
    KnowledgeSource,
    OutputSchema,
    TaskSpec,
)

ChatFn = Callable[[str], str]

PARSE_PROMPT_VERSION_LATEST = "v1"

_PARSE_PROMPT_V1 = dedent(
    """
    あなたはユーザーが入力した目的を、AI エージェント自動構成のためのタスク仕様 (TaskSpec) に変換するアシスタントです.

    ユーザーの目的:
    '''
    {goal}
    '''

    以下の JSON 構造で必ず出力してください. JSON のみを返し、説明文や ``` フェンスは付けないでください.

    {{
      "task_class": "detect" | "modify" | "detect_and_modify" | "extract" | "compare",
      "domain": "<ドメインの短い英数字スラッグ. 例: nda, iso27001, personal_info>",
      "input_roles": [
        {{
          "name": "<入力役割名のスネークケース文字列. 例: target_document>",
          "formats": ["<拡張子文字列. 例: pdf, docx, md, txt>"],
          "role": "target" | "reference" | "rule",
          "description": "<1 文の説明>"
        }}
      ],
      "knowledge": {{
        "source_type": "existing" | "extract" | "hybrid",
        "catalog_path": "<既存のナレッジカタログパス, 該当が無いなら null>",
        "extraction_hints": ["<ナレッジ抽出時のヒント文字列>"]
      }},
      "outputs": [
        {{
          "name": "<出力名のスネークケース文字列. 例: findings, modified_document>",
          "schema_id": "<出力スキーマ id. 例: ng_findings_v1, modified_text_v1>",
          "description": "<1 文の説明>"
        }}
      ],
      "evaluator_hints": ["<評価器を生成するための短いヒント文字列>"]
    }}

    判断ガイド (task_class):
    - 目的文に含まれる動詞をすべて拾い、含まれる動作の組み合わせで決める.
      - 「チェック / 検出 / レビュー / 監査」だけ → detect
      - 「修正 / 直す / 是正 / 書き直す」だけ → modify
      - 検出系と修正系の両方の動作が 1 文に含まれる場合 (例: 「レビューして直す」「検出して修正する」「NG を見つけて是正する」) → detect_and_modify
      - 「抽出」 → extract
      - 「比較」 → compare
    - 検出と修正の 2 動作がある場合は必ず detect_and_modify を選び、modify や detect 単独にしない.

    判断ガイド (outputs):
    - task_class=detect の場合、outputs は必ず以下の 1 つだけ:
      [{{"name": "findings", "schema_id": "ng_findings_v1", "description": "<検出された NG リスト>"}}]
    - task_class=modify の場合、outputs は必ず以下の 1 つだけ:
      [{{"name": "modified_document", "schema_id": "modified_text_v1", "description": "<修正後の文書>"}}]
    - task_class=detect_and_modify の場合、outputs は必ず以下の 2 つを順に列挙:
      [
        {{"name": "findings", "schema_id": "ng_findings_v1", "description": "<検出された NG リスト>"}},
        {{"name": "modified_document", "schema_id": "modified_text_v1", "description": "<修正後の文書>"}}
      ]
    - task_class=extract / compare の場合は目的に合わせて自由に決める.

    判断ガイド (その他):
    - input_roles で target は必須. 標準は [{{"name": "target_document", "formats": ["pdf", "docx", "md", "txt"], "role": "target", "description": "<チェック対象>"}}].
    - 既存ドメインのナレッジ（nda 等）が使えそうなら catalog_path に "knowledge/skills/<domain>/ng_patterns/" を提案.
    - 該当ドメインのナレッジが未知なら source_type を "extract" にし、extraction_hints に抽出方針を 1〜3 件挙げる.
    """
).strip()

_PROMPT_REGISTRY: dict[str, str] = {"v1": _PARSE_PROMPT_V1}


def build_parse_prompt(goal: str, *, prompt_version: str = PARSE_PROMPT_VERSION_LATEST) -> str:
    template = _PROMPT_REGISTRY.get(prompt_version)
    if template is None:
        raise ValueError(f"unsupported prompt_version: {prompt_version}")
    return template.format(goal=goal)


def parse_goal(
    goal: str,
    chat_fn: ChatFn,
    *,
    prompt_version: str = PARSE_PROMPT_VERSION_LATEST,
) -> TaskSpec:
    """ChatFn で LLM を呼び TaskSpec を返す.

    LLM 出力は JSON object 1 つ. ``` フェンスや前後の説明文を吸収するため
    `_extract_json_object` で先頭の `{` 以降を切り出してパースする.
    """
    prompt = build_parse_prompt(goal, prompt_version=prompt_version)
    text = chat_fn(prompt)
    doc = extract_json_object(text)
    return _spec_from_dict(doc, raw_goal=goal)


def _spec_from_dict(doc: dict, *, raw_goal: str) -> TaskSpec:
    input_roles = tuple(
        InputRole(
            name=str(r["name"]),
            formats=tuple(str(x) for x in r.get("formats", []) or []),
            role=r["role"],
            description=str(r.get("description", "") or ""),
        )
        for r in doc.get("input_roles", []) or []
    )
    knowledge_raw = doc.get("knowledge") or {}
    catalog_path = knowledge_raw.get("catalog_path")
    if catalog_path is not None:
        catalog_path = str(catalog_path)
    knowledge = KnowledgeSource(
        source_type=knowledge_raw.get("source_type", "extract"),
        catalog_path=catalog_path,
        extraction_hints=tuple(
            str(x) for x in knowledge_raw.get("extraction_hints", []) or []
        ),
    )
    outputs = tuple(
        OutputSchema(
            name=str(o["name"]),
            schema_id=str(o["schema_id"]),
            description=str(o.get("description", "") or ""),
        )
        for o in doc.get("outputs", []) or []
    )
    return TaskSpec(
        task_class=doc["task_class"],
        domain=str(doc["domain"]),
        input_roles=input_roles,
        knowledge=knowledge,
        outputs=outputs,
        evaluator_hints=tuple(str(x) for x in doc.get("evaluator_hints", []) or []),
        raw_goal=raw_goal,
    )
