"""Phase 4: クラウド強モデル (Azure GPT-5.4) で NG パターン辞書を精緻化する.

既存 v0.3.0 の 9 パターンを **id/name/severity/topics は維持** したまま、
description と excerpt_examples を GPT-5.4 で書き直す。
これにより「クラウド辞書」と「人手辞書」の比較を公正に行う。

出力: src/tsumiki/knowledge/nda/ng_patterns_v0_4_0.yaml
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

from tsumiki.llm import LLMSettings, build_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DICT = PROJECT_ROOT / "src" / "tsumiki" / "knowledge" / "nda" / "ng_patterns.yaml"
OUT_DICT = PROJECT_ROOT / "src" / "tsumiki" / "knowledge" / "nda" / "ng_patterns_v0_4_0.yaml"

load_dotenv(PROJECT_ROOT / ".env", override=False)


REFINE_PROMPT = """あなたは日本の NDA (秘密保持契約) のリーガル AI 知識ベース設計者です。
以下の NG パターン辞書 (v0.3.0) を、より精緻で実用的な辞書 v0.4.0 に書き直してください。

# 厳守する制約

1. パターン数は変えない (9 パターン)。
2. 各パターンの `id`, `name`, `severity`, `applicable_topics`, `references` は **変えない**。
3. `topics` (主題語彙) も **変えない**。
4. 改善するのは `description` と `excerpt_examples` のみ。

# description の改善方針

- 「検出すべき」「紛らわしい」「対象条項」の 3 セクション構成を維持する。
- 「検出すべき」は **具体的な NG 表現の例** を 2〜3 個示す（より精緻に）。
- 「紛らわしい」は **NG ではない表現の例** を 2〜3 個示す（FP を抑える）。
- 「対象条項」は **判定すべき条文の主題** を明確化（applicable_topics と整合）。
- 日本の法務実務 (中小企業庁ハンドブック、JIPDEC、不正競争防止法、民法等) に即した記述に。

# excerpt_examples の改善方針

- 各パターンに **NG 例を 2〜3 件** 入れる (元の 1 件から増やす)。
- 表現の多様性を持たせる (短文・長文、明示型・欠落型、口語的・硬い文体)。

# 入力辞書 (v0.3.0)

```yaml
{input_yaml}
```

# 出力形式

YAML 形式で v0.4.0 全体を出力する。
- 最初の行は `# tsumiki ng_patterns v0.4.0 - クラウド強モデル (GPT-5.4) 生成版`
- 続けて version: "0.4.0", contract_type: nda, last_updated, maintainer, topics, patterns を出力
- topics は v0.3.0 と同じ内容
- maintainer は "tsumiki-cloud-generated-gpt5_4" に変える
- description は文字列ブロック (|) で複数行記述

YAML 以外の説明文・前置き・コードフェンスを出力しない (純粋な YAML のみ)。
"""


def main() -> int:
    settings = LLMSettings.from_env()
    if settings.provider != "azure_openai":
        print(f"[error] LLM_PROVIDER は azure_openai を期待しますが {settings.provider} でした.")
        print("       .env で Azure OpenAI に切り替えてから実行してください.")
        return 1

    input_yaml = SRC_DICT.read_text(encoding="utf-8")
    prompt = REFINE_PROMPT.format(input_yaml=input_yaml)

    client = build_client(settings)
    print(f"[generate] model={settings.model}, calling chat completion...")
    resp = client.chat.completions.create(
        model=settings.model,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=16000,
    )
    content = resp.choices[0].message.content or ""
    usage = resp.usage
    print(
        f"[generate] OK: tokens_in={usage.prompt_tokens} "
        f"tokens_out={usage.completion_tokens}"
    )

    # コードフェンスや前置きが混入していたら除去
    content = content.strip()
    if content.startswith("```"):
        # ```yaml 〜 ``` の中身を抜き出す
        lines = content.splitlines()
        body = []
        in_block = False
        for line in lines:
            if line.startswith("```"):
                in_block = not in_block
                continue
            if in_block:
                body.append(line)
        content = "\n".join(body).strip()

    # YAML として読めるか検証
    try:
        doc = yaml.safe_load(content)
    except yaml.YAMLError as e:
        print(f"[error] 出力が YAML として無効: {e}")
        print("--- raw content (first 1000 chars) ---")
        print(content[:1000])
        OUT_DICT.with_suffix(".raw.txt").write_text(content, encoding="utf-8")
        return 2

    if not isinstance(doc, dict):
        print(f"[error] YAML root が dict ではない: {type(doc).__name__}")
        return 3

    # 基本構造の検証
    if doc.get("version") != "0.4.0":
        print(f"[warn] version が 0.4.0 ではない: {doc.get('version')}")
    if "patterns" not in doc or not isinstance(doc["patterns"], list):
        print("[error] patterns が見つからないか list ではない")
        return 4
    if len(doc["patterns"]) != 9:
        print(f"[error] パターン数が 9 ではない: {len(doc['patterns'])}")
        return 5

    OUT_DICT.write_text(content, encoding="utf-8")
    print(f"[ok] wrote {OUT_DICT}")
    print(f"[stats] patterns={len(doc['patterns'])} topics={len(doc.get('topics', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
