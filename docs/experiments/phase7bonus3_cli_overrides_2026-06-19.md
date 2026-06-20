# Phase 7-bonus-3 結果: LLMSettings.from_env_with_overrides() CLI 復活

実行日: 2026-06-19
設計書: [`phase7e_design.md`](phase7e_design.md) §11 (Phase 7-bonus-3)
ユーザー要望: 「最終的にはCLI引数で渡せるようにしたいです」(7d-4 議論時)

## 1. 結論先出し

| 項目 | 結果 |
| --- | --- |
| `LLMSettings.from_env_with_overrides()` | 追加 (CLI 引数 > env > デフォルト の優先順位) |
| `from_env()` | `from_env_with_overrides()` への薄い委譲に変更 (互換性保持) |
| `run_phase5c_dryrun.py` CLI 引数 | `--llm-provider/--llm-base-url/--llm-api-key/--llm-model/--llm-temperature/--azure-api-version` を追加 |
| **テスト** | **284/284 PASS** (新規 10 + 既存 274) |
| ruff | All checks passed |

## 2. 実装

### 2.1 `LLMSettings.from_env_with_overrides()` (src/tsumiki/llm/client.py)

```python
@classmethod
def from_env_with_overrides(
    cls, *,
    provider: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    api_version: str | None = None,
) -> LLMSettings: ...
```

優先順位: **CLI 引数 (明示値) > 環境変数 > デフォルト**.
provider 別に env 名を切り替え (openai_compatible は `LLM_*`, azure_openai は `AZURE_OPENAI_*`).

`from_env()` は `from_env_with_overrides()` の薄い委譲 (互換性保持).

### 2.2 CLI 引数 (experiments/run_phase5c_dryrun.py)

```
--llm-provider {openai_compatible, azure_openai}
--llm-base-url URL
--llm-api-key KEY
--llm-model MODEL
--llm-temperature FLOAT
--azure-api-version VERSION
```

呼び出し例 (Azure → ollama 試走への切り替え):
```bash
uv run python experiments/run_phase5c_dryrun.py \
  --llm-provider openai_compatible \
  --llm-base-url http://localhost:11434/v1 \
  --llm-model hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M \
  ...
```

## 3. テスト結果

| 項目 | 結果 |
| --- | --- |
| Phase 7-bonus-3 専用 test | 10/10 PASS |
| リグレッション | 284/284 PASS |
| ruff (llm + experiments + 7-bonus-3 tests) | All checks passed |

カバレッジ:
- override のみ / env のみ / 両方 (override 優先)
- `temperature=0.0` 明示と未指定の区別 (再現性関連)
- 必須欠落 raise (openai_compatible / azure_openai 両系統)
- provider 不正値 raise
- `from_env()` ↔ `from_env_with_overrides()` の等価性

## 4. 7e-6 との接続

7e-6 試走時に `--llm-provider` で Azure / ollama を bash 側から切り替え可能.
`examples/{nda,iso27001}/run.sh` 側で CLI 引数の forward を `--use-compose` と並行で追加する予定.

## 5. 申し送り (Phase 7-bonus-1 / 7-bonus-2)

Phase 7-bonus-1 (generator 主 metric 整合, 1 日) と 7-bonus-2 (input_signature schemas 固定, 0.5 日) は **未着手**.
ユーザー指示により 7-bonus-3 完了後は **Phase 7e-6 に直行**. 7-bonus-1 / 7-bonus-2 は Phase 8 (Zenn 公開) 前の任意整理として位置付け.
