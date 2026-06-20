# Phase 7e-1 結果: AgentSquare 上流取り込み (modules 4 ファイル)

実行日: 2026-06-19
設計書: [`phase7e_design.md`](phase7e_design.md) §2 / §6 / §8.1
前段: [`phase7d_provider_and_generator_2026-06-19.md`](phase7d_provider_and_generator_2026-06-19.md)

## 1. 結論先出し

| 項目 | 結果 |
| --- | --- |
| 上流 SHA | `8f5b3fe5d8a32f9b59d20370823bef2a2c86928c` (main HEAD) |
| 取り込みファイル | `modules/{memory,planning,reasoning,tooluse}_modules.py` の 4 件 |
| 配置先 | `src/tsumiki/policy/agentsquare/{memory,planning,reasoning,tooluse}.py` |
| LICENSE 配置 | `THIRD_PARTY_LICENSES/AgentSquare/LICENSE` (Apache-2.0 全文, Apache 公式から取得) |
| Vendoring 記録 | `docs/agentsquare_vendoring.md` 新規作成 |
| `import` 通過 | **意図的に未達** (7e-2 ゲートに移行, 理由は §2 参照) |
| ruff / pyright | 7e-1 暫定で `src/tsumiki/policy/agentsquare` を `pyproject.toml` で exclude |
| 既存リグレッション | **201/201 pytest PASS**, ruff 改変ファイル全 PASS |

## 2. 設計書 §6.2 ゲートの再解釈

設計書 §6.2 では「7e-1 Vendoring 完了: import 通過」をゲートにしていた. しかし上流 4 ファイルは:

- `from utils import llm_response` ← タスク固有 (tasks/{alfworld,m3tooleval}/utils.py) を参照
- `from planning_prompt import *` ← tasks/alfworld 固有
- `from tooluse_IO_pool import tooluse_IO_pool` ← tasks/m3tooleval 固有
- `from langchain_openai import OpenAIEmbeddings`, `from langchain_chroma import Chroma` ← Phase 7a §5.2 で捨てると決めた依存

を解決できないため, **取り込み直後のまま import は通らない**. これは設計時点では未確認だった事実.

再解釈:

| ゲート | 当初 | 再解釈 |
| --- | --- | --- |
| 7e-1 | ファイル配置 + import 通過 | ファイル配置 + ヘッダ追加 + 書き換え対象識別 + 既存リグレッションなし |
| 7e-2 | LLM 差し替え + smoke | LLM 差し替え + langchain 削除 + プロンプト/ツール pool 代替実装 + **import 通過** |

つまり 7e-1 のゴールから `import` 通過を 7e-2 に移し, 7e-1 は「物理配置 + 書き換え予定の記録」に集中させた.

## 3. 実施内容

### 3.1 上流 clone とファイル取得

```bash
git ls-remote https://github.com/tsinghua-fib-lab/AgentSquare HEAD
# → 8f5b3fe5d8a32f9b59d20370823bef2a2c86928c

git clone --depth 1 https://github.com/tsinghua-fib-lab/AgentSquare /tmp/agentsquare_upstream
# 警告: git-lfs 未インストールで video.mp4 等 LFS 対象の checkout 失敗 (modules/*.py は LFS 対象外, 取得済)

cp /tmp/agentsquare_upstream/modules/memory_modules.py src/tsumiki/policy/agentsquare/memory.py
cp /tmp/agentsquare_upstream/modules/planning_modules.py src/tsumiki/policy/agentsquare/planning.py
cp /tmp/agentsquare_upstream/modules/reasoning_modules.py src/tsumiki/policy/agentsquare/reasoning.py
cp /tmp/agentsquare_upstream/modules/tooluse_modules.py src/tsumiki/policy/agentsquare/tooluse.py
```

### 3.2 LICENSE 配置

上流リポジトリトップに LICENSE ファイル**なし** (README で "Code License: Apache-2.0" 宣言のみ).

→ Apache 公式から全文取得して `THIRD_PARTY_LICENSES/AgentSquare/LICENSE` に配置:

```bash
curl -sS https://www.apache.org/licenses/LICENSE-2.0.txt \
  -o THIRD_PARTY_LICENSES/AgentSquare/LICENSE
# 202 行, Phase 7b で tsumiki ルート LICENSE に配置したのと同一バイト列
```

`THIRD_PARTY_LICENSES/AgentSquare/README.md` を更新し, LICENSE 不在の事実 + commit SHA の参照先を明示.

### 3.3 各ファイルに vendoring ヘッダ追加

4 ファイルの先頭に以下の構造で docstring 挿入:

- 上流 URL + commit SHA
- 取り込み日 (Phase 7e-1)
- **WARNING**: 現状 import 不可の理由
- 7e-2 で書き換え予定の内容

ファイル中身 (クラス定義) は **無改変**.

### 3.4 識別された書き換え対象

| ファイル | クラス数 | `llm_response` 呼び出し | langchain 依存 |
| --- | --- | --- | --- |
| memory.py | 5 (Base, DILU, Generative, TP, Voyager) | 3 箇所 (Generative, TP, Voyager) | OpenAIEmbeddings + Chroma (Base) |
| planning.py | 7 (Base, IO, DEPS, TD, Voyager, OPENAGI, HUGGINGGPT) | 1 箇所 (Base) | なし |
| reasoning.py | 9 (Base, IO, COT, COTSC, TOT, DILU, SelfRefine, StepBack, SelfReflectiveTOT) | 多数 (各 variant) | なし |
| tooluse.py | 5+ (Base, IO, AnyTool, ToolBench, ToolBenchFormer, ToolFormer) | 多数 | OpenAIEmbeddings + Chroma (ToolBench 系) |

### 3.5 pyproject.toml の暫定 exclude

```toml
[tool.ruff]
# Phase 7e-1 暫定: AgentSquare vendored コードは上流のまま. 7e-2 で書き換え後に exclude 解除予定.
extend-exclude = ["src/tsumiki/policy/agentsquare"]

[tool.pyright]
exclude = ["src/tsumiki/policy/agentsquare"]
```

**7e-2 完了時に解除予定**.

### 3.6 既存 lint 違反のクリーンアップ

`uv run ruff check` 全体実行で agentsquare 以外に既存 55 件の lint 違反を確認. うち私の 7b/7c/7d 改変分 4 件のみ修正:

- `loader.py` の `_coerce_severity` / `_parse_topics` 未使用 → `# noqa: F401` + 後方互換注記
- `llm/client.py` の docstring 行長 → 改行
- `tests/test_phase7b_packaging.py` の import 順 → ruff --fix

agentsquare 以外の残存 51 件は **Phase 7e 着手前から存在** (experiments/aggregate_*.py 等). Phase 7-bonus または Phase 9+ で別途対応.

### 3.7 docs/agentsquare_vendoring.md 作成

vendoring の上流情報・取り込み範囲・改変サマリ・上流追随ポリシーを 6 セクションで記録. Phase 7e-2 / 7e-3 で更新.

## 4. 設計書 §6.2 ゲート充足状況

| ゲート | 状態 | 根拠 |
| --- | --- | --- |
| Vendoring 完了 (配置) | OK | 4 ファイル + LICENSE 配置, vendoring 記録 |
| Vendoring 完了 (import) | **7e-2 に移行** | 上流タスク固有依存解決のため (§2) |
| LLM 差し替え | 未着手 (7e-2) | - |
| ライセンス遵守 | OK | LICENSE 全文 + 各ファイル冒頭の vendoring docstring + NOTICE 既配置 |
| 評価器 gate | 未着手 (7e-5) | - |
| `compose.run_compose` 動作 | 未着手 (7e-4) | - |
| 同一フレーム動作 | 未着手 (7e-6) | - |
| リグレッション | OK | **201/201 pytest PASS**, 既存テスト破壊なし |

## 5. 実装上の発見

| 項目 | 内容 |
| --- | --- |
| 上流に LICENSE ファイル不在 | README の宣言 "Code License: Apache-2.0" のみ. Phase 7a §5.3 「上流 issue で確認, または PR で追加提案」の対応として Apache 公式から取得して配置. 将来的に上流 PR を出す検討余地 |
| git-lfs 未インストール | upstream の video.mp4 等 LFS 対象が fetch 失敗. Python ファイルは LFS 対象外で問題なし. 将来 search/ 等の取り込みで LFS が必要になれば `brew install git-lfs` が必要 |
| modules/*.py がタスク固有 utils 前提 | 上流の modules/ は単体動作せず, tasks/*/utils.py を `sys.path` に置く前提のレイアウト. 設計書 §6.2 の「import 通過」ゲートを 7e-1 で達成できない理由. これは Phase 7a 調査時点では未把握 |
| pyproject.toml の暫定 exclude | ruff / pyright の `extend-exclude` / `exclude` で `src/tsumiki/policy/agentsquare` を一時除外. 7e-2 で削除 |
| 既存 lint 違反 51 件 | agentsquare 以外で Phase 7e 着手前から存在. 別タスクで対応 |

## 6. Phase 7e-2 への申し送り

7e-2 で実施する書き換え (3.4 と整合):

1. **`llm_response` → `chat_fn` (DI 化)**
   - 各クラス (`MemoryBase`, `PlanningBase`, `ReasoningBase`, `ToolUseBase`) のコンストラクタに `chat_fn: ChatFn` を追加
   - 各サブクラスの `llm_response(prompt, ...)` を `self.chat_fn(prompt)` に書き換え
   - `model=self.llm_type` のハードコードは `chat_fn` 内部の `settings.model` で吸収

2. **langchain 依存削除**
   - `MemoryBase` の `OpenAIEmbeddings()` / `Chroma(...)` を削除 (knowledge は `tsumiki.knowledge.skills/` 参照)
   - `MemoryDILU`, `MemoryGenerative` 等のメモリ機能は **tsumiki の Agent Skills** で代替可能か検証
   - `ToolUseToolBench`, `ToolUseToolBenchFormer` (langchain ベース embedding 検索) は variant ごと削除を検討

3. **タスク固有 import 削除**
   - `from planning_prompt import *` を tsumiki 側プロンプト (`src/tsumiki/policy/agentsquare/prompts/planning.py` 新規) に置換
   - `from tooluse_IO_pool import tooluse_IO_pool` を `tsumiki.tools` プラグイン経由のツール pool に置換

4. **import smoke test**
   - `tests/test_phase7e_agentsquare.py` を新規作成
   - `from tsumiki.policy.agentsquare import memory, planning, reasoning, tooluse` が通る
   - 各 Base クラスが mock `chat_fn` で初期化できる

5. **pyproject.toml の exclude 解除**
   - 7e-2 完了時に `[tool.ruff].extend-exclude` と `[tool.pyright].exclude` から `src/tsumiki/policy/agentsquare` を削除
   - ruff / pyright で agentsquare ファイル全てが PASS することを確認

## 7. 関連

| 項目 | パス |
| --- | --- |
| Phase 7e 設計 | [`phase7e_design.md`](phase7e_design.md) |
| Phase 7a 結果 (vendoring 方針 B-2) | [`phase7a_agentsquare_2026-06-19.md`](phase7a_agentsquare_2026-06-19.md) |
| Vendoring 記録 | [`../agentsquare_vendoring.md`](../agentsquare_vendoring.md) |
| LICENSE (Apache-2.0) | [`../../THIRD_PARTY_LICENSES/AgentSquare/LICENSE`](../../THIRD_PARTY_LICENSES/AgentSquare/LICENSE) |
| NOTICE | [`../../NOTICE`](../../NOTICE) |
| Vendored 4 ファイル | [`../../src/tsumiki/policy/agentsquare/`](../../src/tsumiki/policy/agentsquare/) |
