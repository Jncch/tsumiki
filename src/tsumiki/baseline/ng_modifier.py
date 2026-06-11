"""T2: NG 条項修正器（Phase 2 対照実験用）.

設計:
- 入力: 条項テキスト + 修正すべき NG パターン id 集合
- 出力: 修正後の条項テキスト
- 2 つの prompt 戦略:
  - reuse  : NG パターン辞書を T1 から流用して LLM に提示（知識層の転用）
  - zerobase: 辞書を使わず「NDA として不適切な部分を修正」と抽象指示
- LLM 抽象は ChatFn プロトコルを再利用しテスト容易性を保つ.

prompt versioning は `<variant>.<version>` 命名（例: `reuse.v0.1.0`, `zerobase.v0.1.0`）。
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from tsumiki.data.synthesis import ChatFn
from tsumiki.knowledge.loader import NGPattern

MODIFICATION_PROMPT_VERSION_LATEST_REUSE = "reuse.v0.1.0"
MODIFICATION_PROMPT_VERSION_LATEST_ZEROBASE = "zerobase.v0.1.0"

# Phase 3 頑健性試験用の言い換え版（同意味・別表現）。
# 文体・順序・接続詞を変えつつ、制約と入力スロットの意味は同じ。
MODIFICATION_PROMPT_VERSION_PARAPHRASE_REUSE = "reuse.v0.1.1"
MODIFICATION_PROMPT_VERSION_PARAPHRASE_ZEROBASE = "zerobase.v0.1.1"


_PROMPT_REUSE_V0_1_0 = """あなたは NDA（秘密保持契約）の条項を改善する担当です。
以下の条項案には指定された NG パターンが含まれています。
当該 NG パターンが除去されるように、条項を最小限の変更で修正してください。

# 制約
- 元条項の主題・条番号・見出しは保つ。
- 元条項に無関係な NG パターンを新たに混入させない。
- 出力は修正後の条項本文のみ。前置き・解説・コードフェンスを出さない。
- 修正後も法律文書の硬い書き方を保つ。

# 元条項
{clause_text}

# 取り除くべき NG パターン
{target_block}

# 参考: NG パターン定義（取り除く際の判断基準）
{patterns_block}

# 修正後の条項本文
"""


_PROMPT_REUSE_V0_1_1 = """次の業務を担当してください: NDA（秘密保持契約）における問題のある条項のリライト。

下記の条項テキストには、指定された NG パターンに該当する記述が含まれている。
あなたの仕事は、それらの NG が解消されるように、変更箇所を最小化したリライトを出力することです。

リライトにあたっての守るべき条件:
- 条番号・条見出し・主題はそのまま維持する。
- 指定 NG 以外の新たな NG を持ち込まない。
- 修正後本文のみを出力する（説明文・前置き・マークダウンコードフェンスは禁止）。
- 法律文書としての堅さを保つ。

【リライト対象の条項】
{clause_text}

【除去すべき NG パターン ID 一覧】
{target_block}

【NG パターンの定義（判定の根拠）】
{patterns_block}

【リライト後本文】
"""


_PROMPT_ZEROBASE_V0_1_0 = """あなたは NDA（秘密保持契約）の条項を改善する担当です。
以下の条項案には不適切な部分があります。NDA として不適切な部分を修正してください。

# 制約
- 元条項の主題・条番号・見出しは保つ。
- 出力は修正後の条項本文のみ。前置き・解説・コードフェンスを出さない。
- 修正後も法律文書の硬い書き方を保つ。

# 元条項
{clause_text}

# 修正後の条項本文
"""


_PROMPT_ZEROBASE_V0_1_1 = """次の業務を担当してください: NDA（秘密保持契約）における不適切な条項のリライト。

下記の条項テキストには、NDA として不適切な記述が含まれている可能性がある。
あなたの仕事は、不適切な部分を見つけ、それらが解消されるようにリライトを出力することです。

リライトにあたっての守るべき条件:
- 条番号・条見出し・主題はそのまま維持する。
- 修正後本文のみを出力する（説明文・前置き・マークダウンコードフェンスは禁止）。
- 法律文書としての堅さを保つ。

【リライト対象の条項】
{clause_text}

【リライト後本文】
"""


_PROMPT_REGISTRY: dict[str, str] = {
    MODIFICATION_PROMPT_VERSION_LATEST_REUSE: _PROMPT_REUSE_V0_1_0,
    MODIFICATION_PROMPT_VERSION_LATEST_ZEROBASE: _PROMPT_ZEROBASE_V0_1_0,
    MODIFICATION_PROMPT_VERSION_PARAPHRASE_REUSE: _PROMPT_REUSE_V0_1_1,
    MODIFICATION_PROMPT_VERSION_PARAPHRASE_ZEROBASE: _PROMPT_ZEROBASE_V0_1_1,
}


def _format_target_block(target_pattern_ids: Sequence[str]) -> str:
    return "\n".join(f"- {pid}" for pid in target_pattern_ids)


def _format_patterns_block(patterns: Sequence[NGPattern]) -> str:
    """検出器と同じフォーマットを使う（辞書の全文を展開）."""
    lines: list[str] = []
    for p in patterns:
        desc_lines = p.description.strip().splitlines() if p.description else [""]
        first = desc_lines[0]
        rest = desc_lines[1:]
        lines.append(f"- {p.id} ({p.name}): {first}")
        for r in rest:
            lines.append(f"    {r.strip()}")
    return "\n".join(lines)


def build_modification_prompt(
    clause_text: str,
    target_pattern_ids: Sequence[str],
    patterns: Sequence[NGPattern],
    prompt_version: str,
) -> str:
    """修正プロンプトを構築する.

    reuse 版は patterns_block を埋め込む（target_pattern_ids に該当するもののみ）。
    zerobase 版は patterns_block を一切使わない（辞書非依存）。
    """
    if not clause_text.strip():
        raise ValueError("clause_text is empty")
    template = _PROMPT_REGISTRY.get(prompt_version)
    if template is None:
        raise ValueError(f"unsupported prompt_version: {prompt_version}")
    if prompt_version.startswith("reuse."):
        if not target_pattern_ids:
            raise ValueError("target_pattern_ids is empty for reuse variant")
        target_set = set(target_pattern_ids)
        relevant = [p for p in patterns if p.id in target_set]
        return template.format(
            clause_text=clause_text.strip(),
            target_block=_format_target_block(target_pattern_ids),
            patterns_block=_format_patterns_block(relevant),
        )
    # zerobase: 引数の patterns / target は使わない
    return template.format(clause_text=clause_text.strip())


_PREAMBLE_RE = re.compile(
    r"^(以下|下記|修正後|改変後|出力|回答)[^\n]*[:：]\s*\n+",
    flags=re.MULTILINE,
)
_CODEFENCE_RE = re.compile(r"^```[a-zA-Z]*\n|\n```$", flags=re.MULTILINE)


def clean_modification_response(raw: str) -> str:
    """LLM 応答から余計な前置き・コードフェンスを除く."""
    text = raw.strip()
    text = _CODEFENCE_RE.sub("", text)
    text = _PREAMBLE_RE.sub("", text, count=1)
    return text.strip()


def modify_clause(
    clause_text: str,
    target_pattern_ids: Sequence[str],
    patterns: Sequence[NGPattern],
    chat_fn: ChatFn,
    prompt_version: str,
) -> str:
    """1 条項を修正する."""
    prompt = build_modification_prompt(clause_text, target_pattern_ids, patterns, prompt_version)
    result = chat_fn(prompt)
    return clean_modification_response(result.content)
