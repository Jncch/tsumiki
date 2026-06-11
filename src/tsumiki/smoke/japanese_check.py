"""日本語サニティチェック.

3 モデル候補（Qwen2.5 14B/7B、ELYZA-JP 8B）を順に呼び、
業務文書・法務ドメインの最小プロンプトで日本語出力を確認する。

実行:
    LLM_BASE_URL=http://localhost:11434/v1 uv run python -m tsumiki.smoke.japanese_check
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass

from dotenv import load_dotenv

from tsumiki.llm.client import LLMSettings, build_client


@dataclass
class ModelSpec:
    label: str
    tag: str


DEFAULT_MODELS: list[ModelSpec] = [
    ModelSpec(label="qwen2.5-14b", tag="hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M"),
    ModelSpec(label="qwen2.5-7b", tag="hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M"),
    ModelSpec(label="elyza-jp-8b", tag="hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF:latest"),
]


PROMPT = (
    "次の契約条項案の日本語としての自然さを 5 段階で評価し、"
    "問題点があれば 1 文で指摘してください。\n\n"
    "【条項案】乙は、甲の事前の書面による承諾を得ることなく、"
    "本契約に基づく権利義務の全部又は一部を第三者に譲渡し又は承継させてはならない。"
)


def run_one(spec: ModelSpec, base_url: str) -> tuple[bool, str, float]:
    os.environ["LLM_MODEL"] = spec.tag
    os.environ["LLM_BASE_URL"] = base_url
    settings = LLMSettings.from_env()
    client = build_client(settings)
    t0 = time.monotonic()
    try:
        resp = client.chat.completions.create(
            model=settings.model,
            messages=[{"role": "user", "content": PROMPT}],
            temperature=settings.temperature,
        )
    except Exception as e:  # noqa: BLE001
        return False, f"ERROR: {type(e).__name__}: {e}", time.monotonic() - t0
    elapsed = time.monotonic() - t0
    content = resp.choices[0].message.content or ""
    return True, content.strip(), elapsed


def main() -> int:
    load_dotenv()
    base_url = os.environ.get("LLM_BASE_URL") or "http://localhost:11434/v1"
    print(f"[smoke] base_url={base_url}")
    print(f"[smoke] prompt:\n{PROMPT}\n")
    overall_ok = True
    for spec in DEFAULT_MODELS:
        print(f"--- {spec.label} ({spec.tag}) ---")
        ok, body, elapsed = run_one(spec, base_url)
        overall_ok = overall_ok and ok
        print(f"[elapsed] {elapsed:.2f}s")
        print(body)
        print()
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
