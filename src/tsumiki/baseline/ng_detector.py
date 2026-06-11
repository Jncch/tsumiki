"""単一プロンプトの NG 検出器（ベースライン）.

設計:
- LLM 抽象は `tsumiki.data.synthesis.ChatFn` を再利用してテスト容易性を保つ.
- 出力は `frozenset[str]`. 既知の NG パターン id 以外（ハルシ）はフィルタする.
- プロンプトは version で管理し、レジストリ `_PROMPT_REGISTRY` で参照する.
  v0.1.0: ベースライン. シンプルな指示のみ.
  v0.2.0: P1 改修. 欠落型 (id 末尾が `_missing` `_undefined`) の検出を明示.
  v0.3.0: P2 改修. 厳格な (a)(b)(c) 判断ルール + 確信無き場合は列挙しない.
  v0.4.0: P4 廃案. 「条文主題を最初に判定する」構造化手順 + few-shot だが
          明示型 recall を失い、F2 -0.090 で v0.3.0 を下回った.
  v0.5.0: P5-A 改修. 辞書 v0.3.0 の applicable_topics と機械的に照合.
          条文主題を語彙から 1 つだけ選び、含まれないパターンは強制スキップ.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from tsumiki.data.clauses import CleanClause
from tsumiki.data.synthesis import ChatFn
from tsumiki.eval.labels import ClausePrediction
from tsumiki.knowledge.loader import NGPattern, TopicVocab

DETECTION_PROMPT_VERSION_LATEST = "v0.3.0"


_PROMPT_V0_1_0 = """あなたは NDA（秘密保持契約）の品質チェック担当です。
以下の対象条項を読み、定義された NG パターンのうち該当するものをすべて列挙してください。

# 出力形式
- 該当する NG パターンの id を 1 行に 1 つだけ列挙する。
- 一つも該当しない場合は何も出力せず空のまま終える。
- 前置き・解説・コードフェンスは出さない。
- 定義に無い id を出さない。

# NG パターン定義
{patterns_block}

# 対象条項
{clause_text}

# 該当する NG パターン id
"""


_PROMPT_V0_2_0 = """あなたは NDA（秘密保持契約）の品質チェック担当です。
以下の対象条項を読み、定義された NG パターンのうち該当するものをすべて列挙してください。

# NG パターンには 2 種類ある
1. **明示型**: 条項本文に *問題のある記載が書かれている* ことが該当条件
   例: 範囲過大、期間無期限、賠償不均衡、一方的管轄、独占的譲渡禁止
2. **欠落型**: id の末尾が `_missing` または `_undefined` のもの。
   条項本文に *あるべき規定が書かれていない／不明確である* ことが該当条件。
   例: nda_survival_missing は「契約終了後に存続する義務の明示が無い」ことを検出する。
   nda_return_destroy_missing は「秘密情報の返還・廃棄義務の明示が無い」ことを検出する。
   nda_disclosure_exception_missing は「法令・規制当局等への開示例外の明示が無い」ことを検出する。

両タイプを等しく検出すること。**欠落型は当該条項の主題と無関係に評価せず、その条項が
本来カバーすべき範囲で対応する規定の言及が無いとき** に該当と判断する。
例: 「秘密保持義務」条項に第三者開示の例外規定が無ければ disclosure_exception_missing 該当。
   「（有効期間）」条項に契約終了後の存続義務の明示が無ければ survival_missing 該当。

# 検出の偽陽性を避ける指針
- 明示型: 該当する語句・規定が条項内に *書かれていない* なら列挙しない。
- 欠落型: その条項が論じる主題（目的・定義・期間・解除・終了等）から見て、
  あるべき規定が無いことが明らかな場合だけ列挙する。条項の主題と無関係な欠落は列挙しない。

# 出力形式
- 該当する NG パターンの id を 1 行に 1 つだけ列挙する。
- 一つも該当しない場合は何も出力せず空のまま終える。
- 前置き・解説・コードフェンスは出さない。
- 定義に無い id を出さない。

# NG パターン定義
{patterns_block}

# 対象条項
{clause_text}

# 該当する NG パターン id
"""


_PROMPT_V0_3_0 = """あなたは NDA（秘密保持契約）の品質チェック担当です。
以下の対象条項を読み、定義された NG パターンのうち該当するものをすべて列挙してください。

# NG パターンには 2 種類ある
1. **明示型**: 条項本文に *問題のある記載が書かれている* ことが該当条件
   例: 範囲過大、期間無期限、賠償不均衡、一方的管轄、独占的譲渡禁止
2. **欠落型**: id の末尾が `_missing` または `_undefined` のもの。
   条項本文に *あるべき規定が書かれていない／不明確である* ことが該当条件。
   例: nda_survival_missing は「契約終了後に存続する義務の明示が無い」ことを検出する。
   nda_return_destroy_missing は「秘密情報の返還・廃棄義務の明示が無い」ことを検出する。
   nda_disclosure_exception_missing は「法令・規制当局等への開示例外の明示が無い」ことを検出する。

# 判断ルール（厳格に守ること、過剰検出を避ける）

## 明示型の列挙条件
該当する語句・規定が条項内に **明確に書かれている** 場合のみ列挙する。

## 欠落型の列挙条件
以下の (a)(b)(c) **すべて** を満たす場合のみ列挙する:

(a) その条項の主題（例: 目的、定義、秘密保持義務、有効期間、解除、終了など）が、
    当該欠落 NG パターンの対象範囲と **直接的に関連する**。
    例: survival_missing は契約終了後の効力に関する条項（有効期間条項、終了条項）で
        のみ判定対象になる。「目的」条項では判定対象にならない。
(b) 条項本文に該当する規定への **明示的な言及が見当たらない**。
(c) 「黙示的に含意」「他条項で扱う可能性」「実務上当然」等の **推測解釈をしない**。
    あくまで対象条項のテキスト上に明示が無いことのみを根拠とする。

## 共通の判断指針
- 判断に **確信を持てない場合は列挙しない**。条項に対し 1 つも該当しない結論も正当。
- 1 条項につき複数の NG を挙げるときは、それぞれが上の条件を独立に満たすかを確認する。
- 同じ条項内で複数の欠落型を疑う場合は、各 NG の主題関連性 (a) を個別に検討する。

# 出力形式
- 該当する NG パターンの id を 1 行に 1 つだけ列挙する。
- 一つも該当しない場合は何も出力せず空のまま終える。
- 前置き・解説・コードフェンスは出さない。
- 定義に無い id を出さない。

# NG パターン定義
{patterns_block}

# 対象条項
{clause_text}

# 該当する NG パターン id
"""


_PROMPT_V0_4_0 = """あなたは NDA（秘密保持契約）の品質チェック担当です。
以下の対象条項を読み、定義された NG パターンのうち該当するものをすべて列挙してください。

# NG パターンには 2 種類ある
1. **明示型**: 条項本文に *問題のある記載が書かれている* ことが該当条件
2. **欠落型**: id の末尾が `_missing` または `_undefined` のもの。
   条項本文に *あるべき規定が書かれていない／不明確である* ことが該当条件。

# 判定手順（順番に実行する）

## ステップ 1: 対象条項の主題を 1 つだけ判定する
条文の見出し（「（秘密保持義務）」「（有効期間）」等）または冒頭の意味内容から、
この条項が **何を論じる条項か** を 1 つだけ選ぶ。
例: 目的 / 定義 / 秘密保持義務 / 知的財産権 / 損害賠償 / 違約金 / 有効期間 / 終了 / 解除 / 紛争解決・管轄 / 確認事項 / 返還・廃棄

## ステップ 2: パターン定義の「対象条項」と主題を照合する
各 NG パターンの description には「対象条項」セクションがある。
ステップ 1 で判定した主題が、そのパターンの対象条項に **含まれない** なら、
そのパターンは **列挙しない**（条文外の検出は厳禁）。

## ステップ 3: 残ったパターンについて、以下 (a)(b)(c) で判定する

(a) **明示型**: 該当する語句・規定が条項内に **明確に書かれている** か。

(b) **欠落型**: 条項本文（**全段落**）に該当する規定への **明示的な言及が見当たらない** か。
    同一条項の別段落（例: 第 5 項）に該当規定が書かれている場合は **列挙しない**。

(c) **推測解釈をしない**。「黙示的に含意」「他条項で扱う可能性」「実務上当然」は
    根拠にしない。対象条項のテキスト上の明示の有無だけで判定する。

## ステップ 4: 確信を持てない場合は列挙しない
1 条項につき複数の NG を挙げるときは、それぞれ独立にステップ 1-3 を満たすかを確認する。
一つも該当しない結論も正当。

# 判定の例（few-shot: 過剰検出を避ける典型例）

## 例 1: 知的財産権条項 vs 派生情報未定義
対象条項主題: 知的財産権
パターン `nda_derivative_undefined` の対象条項: 「定義」「知的財産権」「成果物」
→ 主題は対象条項に含まれる。ただし条項本文に「発明等」「特許」等の知的財産規定がある場合、
   それは派生情報の規定**ではない**。派生情報・分析結果・成果物への明示的言及が無く、
   かつ「派生情報」自体が条項の主題でない場合は **列挙しない**。

## 例 2: 秘密保持義務条項 vs 開示例外不在
対象条項主題: 秘密保持義務
パターン `nda_disclosure_exception_missing` の対象条項: 「秘密保持義務」「第三者開示の禁止」
→ 主題は対象条項に含まれる。条項本文に「国又は地方公共団体の機関から開示を命じられた場合」
   「法令により開示を要求された場合」等の規定が **同一条項内（別段落含む）** にあれば、
   それは開示例外規定として **充足**。**列挙しない**。

## 例 3: 双方向損害賠償条項 vs 賠償不均衡
対象条項主題: 損害賠償
パターン `nda_remedy_imbalanced` の対象条項: 「損害賠償」「違約金」「差止め」
→ 主題は対象条項に含まれる。ただし「甲及び乙は、本契約に違反して相手方に損害を与えた場合」
   のように **双方向** の標準的規定であれば、これは不均衡ではない。**列挙しない**。

# 出力形式
- 該当する NG パターンの id を 1 行に 1 つだけ列挙する。
- 一つも該当しない場合は何も出力せず空のまま終える。
- 前置き・解説・コードフェンスは出さない。
- 定義に無い id を出さない。

# NG パターン定義
{patterns_block}

# 対象条項
{clause_text}

# 該当する NG パターン id
"""


_PROMPT_V0_5_0 = """あなたは NDA（秘密保持契約）の品質チェック担当です。
以下の対象条項を読み、定義された NG パターンのうち該当するものをすべて列挙してください。

# 判定手順（順番に実行する）

## ステップ 1: 対象条項の主題を 1 つだけ選ぶ
条文の見出し（「（秘密保持義務）」等）または冒頭の内容から、この条項の主題を
**以下の語彙の中から 1 つだけ** 選ぶ:

{topics_block}

複数の主題を持つように見える条項では、**条文の本文の大半が論じている主題** を 1 つ選ぶ。
判断に迷う場合は `other` を選ぶ。

## ステップ 2: パターンの applicable_topics と照合する
各 NG パターン定義には `applicable_topics` が示されている。
ステップ 1 で選んだ主題が **applicable_topics に含まれないパターンは、何があっても列挙しない**。
これは厳守の機械的ルールであり、解釈による上書きは禁止。

## ステップ 3: 残ったパターンに以下 (a)(b)(c) を適用する

(a) **明示型** (id の末尾が `_missing` `_undefined` でないもの):
    該当する語句・規定が条項内に **明確に書かれている** か。

(b) **欠落型** (id 末尾 `_missing` `_undefined`):
    条項本文（**全段落**）に該当する規定への **明示的な言及が見当たらない** か。
    同一条項の別段落（例: 第 5 項）に該当規定が書かれている場合は **列挙しない**。

(c) **推測解釈をしない**。「黙示的に含意」「他条項で扱う可能性」「実務上当然」は
    根拠にしない。対象条項のテキスト上の明示の有無だけで判定する。

## 列挙のバランス指針
- **明示型**: 該当する誤った記載が **明確に書かれていれば必ず列挙する**。recall を優先。
- **欠落型**: ステップ 2 で適用範囲を絞り込んだ上で、(b)(c) を厳格に適用する。precision を優先。

# 出力形式
- まず 1 行目に `topic: <selected_topic_id>` を出力する（デバッグ用、必須）。
- 2 行目以降に、該当する NG パターンの id を 1 行に 1 つ列挙する。
- 該当なしの場合は `topic:` 行のみ出力する。
- 前置き・解説・コードフェンスは出さない。
- 定義に無い id を出さない。

# 主題語彙
{topics_block}

# NG パターン定義（applicable_topics を含む）
{patterns_block}

# 対象条項
{clause_text}

# 出力
"""


_PROMPT_REGISTRY: dict[str, str] = {
    "v0.1.0": _PROMPT_V0_1_0,
    "v0.2.0": _PROMPT_V0_2_0,
    "v0.3.0": _PROMPT_V0_3_0,
    "v0.4.0": _PROMPT_V0_4_0,
    "v0.5.0": _PROMPT_V0_5_0,
}


def _format_patterns_block(
    patterns: Sequence[NGPattern], *, include_applicable_topics: bool = False
) -> str:
    """各パターンの id・name と description 全文をプロンプトに展開する.

    description が複数行の場合は 2 行目以降をインデントして可読性を保つ.
    include_applicable_topics が True なら applicable_topics 行も追加する.
    """
    lines: list[str] = []
    for p in patterns:
        desc_lines = p.description.strip().splitlines() if p.description else [""]
        first = desc_lines[0]
        rest = desc_lines[1:]
        lines.append(f"- {p.id} ({p.name}): {first}")
        for r in rest:
            lines.append(f"    {r.strip()}")
        if include_applicable_topics and p.applicable_topics:
            lines.append(
                f"    applicable_topics: [{', '.join(p.applicable_topics)}]"
            )
    return "\n".join(lines)


def _format_topics_block(topics: Sequence[TopicVocab]) -> str:
    return "\n".join(f"- {t.id} ({t.name})" for t in topics)


def build_detection_prompt(
    clause_text: str,
    patterns: Sequence[NGPattern],
    prompt_version: str = DETECTION_PROMPT_VERSION_LATEST,
    topics: Sequence[TopicVocab] = (),
) -> str:
    if not patterns:
        raise ValueError("at least one pattern is required")
    template = _PROMPT_REGISTRY.get(prompt_version)
    if template is None:
        raise ValueError(f"unsupported prompt_version: {prompt_version}")
    if prompt_version == "v0.5.0":
        if not topics:
            raise ValueError("v0.5.0 requires non-empty topics")
        if any(not p.applicable_topics for p in patterns):
            raise ValueError(
                "v0.5.0 requires all patterns to have non-empty applicable_topics"
            )
        return template.format(
            topics_block=_format_topics_block(topics),
            patterns_block=_format_patterns_block(
                patterns, include_applicable_topics=True
            ),
            clause_text=clause_text.strip(),
        )
    return template.format(
        patterns_block=_format_patterns_block(patterns),
        clause_text=clause_text.strip(),
    )


_LINE_SPLIT = re.compile(r"[\r\n,、]+")


_TOPIC_LINE_RE = re.compile(r"^topic\s*[:：]\s*[A-Za-z_0-9]+", flags=re.MULTILINE)


def parse_detection_response(raw: str, valid_ids: Iterable[str]) -> frozenset[str]:
    """応答テキストから NG パターン id 集合を取り出す.

    - 改行・カンマ・読点で区切る。
    - 各トークンから余計な記号（- * 1. など）を取り除く。
    - 定義済み id 以外は捨てる（ハルシ対策）。
    - v0.5.0 の `topic: <id>` 行は無視する。
    """
    valid = set(valid_ids)
    # v0.5.0 の topic: 行を先に剥がす（id 衝突防止のため、token-by-token ではなく行単位で）
    body = _TOPIC_LINE_RE.sub("", raw or "")
    out: set[str] = set()
    for token in _LINE_SPLIT.split(body):
        cleaned = token.strip().lstrip("-*•・").strip()
        # 「1. id」「(1) id」「id:」など先頭の番号付け・末尾の記号を剥がす
        cleaned = re.sub(r"^[\(（]?\d+[\)）.]\s*", "", cleaned)
        cleaned = cleaned.rstrip(":：。、 ")
        if cleaned in valid:
            out.add(cleaned)
    return frozenset(out)


def detect_ng_patterns(
    clause_text: str,
    patterns: Sequence[NGPattern],
    chat_fn: ChatFn,
    prompt_version: str = DETECTION_PROMPT_VERSION_LATEST,
    topics: Sequence[TopicVocab] = (),
) -> frozenset[str]:
    """1 条項について NG パターン id 集合を返す.

    v0.5.0 を使う場合は topics を指定する。それ以外は省略可。
    """
    prompt = build_detection_prompt(clause_text, patterns, prompt_version, topics)
    result = chat_fn(prompt)
    return parse_detection_response(result.content, valid_ids=(p.id for p in patterns))


def predict_clauses(
    clauses: Sequence[CleanClause],
    patterns: Sequence[NGPattern],
    chat_fn: ChatFn,
    prompt_version: str = DETECTION_PROMPT_VERSION_LATEST,
    topics: Sequence[TopicVocab] = (),
) -> list[ClausePrediction]:
    """複数条項の予測を一気通貫で実行する."""
    out: list[ClausePrediction] = []
    for c in clauses:
        ng_ids = detect_ng_patterns(c.text, patterns, chat_fn, prompt_version, topics)
        out.append(ClausePrediction(clause_id=c.clause_id, ng_pattern_ids=ng_ids))
    return out
