# Phase 7a 結果: AgentSquare 上流調査と統合方針確定

実行日: 2026-06-19
設計書: [`phase7_design.md`](phase7_design.md) §1 (7a) / §2

## 1. 結論先出し

| 項目 | 確定内容 |
| --- | --- |
| 採用方針 | **B-2: partial vendoring (modules/ + search/ + module_evolution/recombination/predictor/ のみを `src/tsumiki/policy/agentsquare/` 配下に取り込み)** |
| 不採用 | A (PyPI 依存利用)、B-1 (full fork)、C (ゼロ再実装) |
| ライセンス | Apache-2.0。tsumiki も Apache-2.0 を採用、NOTICE で上流の著作権を保持 |
| LLM 呼び出しの扱い | 取り込み時に上流の OpenAI SDK / LangChain 直接呼び出しを **tsumiki の `src/tsumiki/llm/` 経由に差し替え** (CLAUDE.md §3 と整合) |
| 不要持ち込み | `tasks/` (alfworld, webshop, m3tooleval, sciworld) は全捨て。`requirements.txt` 由来の alfworld / langchain / langchain_chroma / langchain_openai も持ち込まない |
| 上流追随コスト | 取り込み範囲が 4 〜 5 ディレクトリに限定、上流の活動は 2024-10〜11 が直近のため低 |

## 2. 調査ソース

| 項目 | URL |
| --- | --- |
| リポジトリ | https://github.com/tsinghua-fib-lab/AgentSquare |
| 論文 | https://arxiv.org/abs/2410.06153 |
| README | https://raw.githubusercontent.com/tsinghua-fib-lab/AgentSquare/main/README.md |
| requirements | https://raw.githubusercontent.com/tsinghua-fib-lab/AgentSquare/main/requirements.txt |
| modules/ ディレクトリ | https://github.com/tsinghua-fib-lab/AgentSquare/tree/main/modules |

LICENSE / LICENSE.md は WebFetch で 404 (リポジトリトップに同名ファイルが配置されていない可能性、または HTML 経由のみ閲覧可)。README に **"Code License: Apache-2.0"** と明記されているのを採用根拠とする。Phase 7e 着手時に Apache-2.0 全文の同梱を確認する。

## 3. AgentSquare の構造把握

### 3.1 トップレベル

```
AgentSquare/
├── modules/                    # 4 モジュールの実装本体
│   ├── memory_modules.py       # MemoryBase, MemoryDILU, MemoryGenerative ...
│   ├── planning_modules.py     # PlanningBase, PlanningIO, PlanningDILU ...
│   ├── reasoning_modules.py    # ReasoningBase, ReasoningCOT, ReasoningIO, ReasoningTOT ...
│   ├── tooluse_modules.py      # ToolUseBase, ToolUseIO, ToolUseBench ...
│   └── README.md / test_new_modules.md
├── module_evolution/           # モジュール進化
├── module_predictor/           # in-context surrogate による性能予測
├── module_recombination/       # モジュール再結合
├── search/                     # 探索実験
├── tasks/                      # ベンチマーク統合 (alfworld, webshop, m3tooleval, sciworld)
│   └── alfworld/alfworld_run.py 等
├── requirements.txt
└── README.md
```

### 3.2 依存

| ライブラリ | バージョン | tsumiki での扱い |
| --- | --- | --- |
| alfworld | 0.3.5 | **捨てる** (embodied AI ベンチ、tsumiki と無関係) |
| langchain | 0.3.3 | **捨てる** (CLAUDE.md §3 違反、tsumiki は未採用) |
| langchain_chroma | 0.1.4 | **捨てる** (RAG 用、計画書 §10.2「RAG なし」と整合) |
| langchain_openai | 0.2.2 | **捨てる** (上記理由 + LLM 抽象化を tsumiki 側で行う) |
| openai | 1.43.0 | **抽象化** (`src/tsumiki/llm/` 経由) |
| backoff | 2.2.1 | 採用検討 (リトライ用、tsumiki に既に同等機能あれば不要) |
| numpy | 1.24.1 | 既に tsumiki 採用済 (バージョン整合必要) |
| PyYAML | 6.0.1 | 既に採用済 |
| tenacity | 8.5.0 | 採用検討 |
| tqdm | 4.66.2 | 既に採用済 |
| typing_extensions | 4.12.2 | 既に採用済 |

### 3.3 公開 API のスタイル

README の Quickstart:

```bash
python3 alfworld_run.py \
    --planning deps \
    --reasoning cot \
    --tooluse none \
    --memory dilu \
    --model gpt-3.5-turbo-0125
```

→ **タスクごとに CLI スクリプトを直接実行** する設計。`workflow.py` のようなライブラリ API は限定的で、`modules/` のクラス群を直接 import して組み合わせる方式と推測。Library として呼び出せる程度には設計されているが、PyPI 配布されていないため pip 経由の依存にできない。

## 4. 方針 A / B-1 / B-2 / C の比較

| 方針 | 採用条件 | 採否 | 理由 |
| --- | --- | --- | --- |
| **A. PyPI 依存利用** | AgentSquare が PyPI 公開かつ stable API | **不採用** | PyPI 配布なし。依存 (alfworld, langchain) が tsumiki と非互換 |
| **B-1. Full fork** | 上流全体を継続的にメンテ | **不採用** | tasks/ の 90% が tsumiki に無関係。メンテ範囲が肥大 |
| **B-2. Partial vendoring** | コアアルゴリズムのみ取り込み、LICENSE / NOTICE 保持 | **採用** | 取り込みは 5 ディレクトリ + 4 ファイル、上流追随コスト最小 |
| **C. ゼロ再実装** | アルゴリズム再発明 | **不採用** | CLAUDE.md §2 「フレームをゼロから自作しない」に違反。学術的にも価値が薄い |

## 5. 採用方針 B-2 の詳細

### 5.1 取り込み対象 (vendoring 範囲)

| 上流パス | 取り込み先 | 改変内容 |
| --- | --- | --- |
| `modules/memory_modules.py` | `src/tsumiki/policy/agentsquare/memory.py` | OpenAI SDK 直接呼び出しを `tsumiki.llm.client.LLMClient` に差し替え |
| `modules/planning_modules.py` | `src/tsumiki/policy/agentsquare/planning.py` | 同上 |
| `modules/reasoning_modules.py` | `src/tsumiki/policy/agentsquare/reasoning.py` | 同上 |
| `modules/tooluse_modules.py` | `src/tsumiki/policy/agentsquare/tooluse.py` | 同上 + tsumiki の `tools/` (Phase 7b 新規) との接続点を追加 |
| `module_evolution/` | `src/tsumiki/policy/agentsquare/evolution/` | 評価器呼び出し部を tsumiki の `eval/generated/` 流用 lookup に差し替え |
| `module_recombination/` | `src/tsumiki/policy/agentsquare/recombination/` | 同上 |
| `module_predictor/` | `src/tsumiki/policy/agentsquare/predictor/` | in-context surrogate モデル。LLM 呼び出しを `tsumiki.llm` 経由に |
| `search/` | `src/tsumiki/policy/agentsquare/search/` | 同上 |

### 5.2 捨てるもの

- `tasks/alfworld/`, `tasks/webshop/`, `tasks/m3tooleval/`, `tasks/sciworld/` 全捨て
- `alfworld`, `langchain*` 依存
- 上流の `requirements.txt` (tsumiki の `pyproject.toml` に必要分のみ追加)

### 5.3 LICENSE / NOTICE の扱い

- tsumiki ルートに `LICENSE` (Apache-2.0)
- `THIRD_PARTY_LICENSES/AgentSquare/LICENSE` に上流 Apache-2.0 全文を配置
- `NOTICE` ファイルで上流の著作権者 (Shang et al., tsinghua-fib-lab) を表示
- 取り込み元の各ファイル冒頭にコメントで「derived from AgentSquare commit <sha>, Apache-2.0」を明示

### 5.4 上流追随ポリシー

- 取り込み元の commit SHA を `docs/agentsquare_vendoring.md` に記録
- 上流更新の確認は四半期に 1 回 (Phase 9+ の運用)
- セキュリティ修正があれば即時取り込み (取り込み範囲は modules/ + search/ 系のみ)

## 6. tsumiki の各層との接続点 (確定版)

設計書 §2.2 表を、3.1 で判明した実装ファイル名に基づいて確定:

| AgentSquare 側 | tsumiki 側 | 接続方法 |
| --- | --- | --- |
| `policy/agentsquare/planning.py:PlanningBase` | `goal/specs.py:TaskSpec` | TaskSpec を Planning モジュールの初期化制約として渡す |
| `policy/agentsquare/reasoning.py:ReasoningBase` | `policy/optimize/` (Phase 9+) | Phase 7 では既存実装 (COT/IO/TOT) を素通り |
| `policy/agentsquare/tooluse.py:ToolUseBase` | `tools/` (Phase 7b 新規) | tsumiki 側で `BaseTool` プロトコルを定義し ToolUseBase に登録 |
| `policy/agentsquare/memory.py:MemoryBase` | `knowledge/skills/` | Agent Skills を Memory モジュールの参照対象として供給 |
| `policy/agentsquare/search/` の評価器コール | `eval/generated/<domain>/<task_class>/<id>/` | 探索開始前に `goal/lookup.py` を必ず通過 (CLAUDE.md §9 と整合) |
| `policy/agentsquare/predictor/` | `eval/runners/` (Phase 7b 新規) | MLflow 連動の自動検証ランナーから予測モデルを呼ぶ (Phase 9+) |

## 7. 計画書 §10.1 との解釈差分の確定

| 計画書記載 | 確定後の解釈 |
| --- | --- |
| "tsumiki/ AgentSquare fork ベース" | tsumiki/ は **独立パッケージ**。AgentSquare は `policy/agentsquare/` に partial vendoring (方針 B-2) |
| AgentSquare が root | **goal/ が root**。AgentSquare は下流モジュール (Phase 5c 以降の構造) |
| fork として上流追随 | 取り込み範囲を modules/ + search/ 系に限定し追随コスト最小化 |

計画書 §10.1 のディレクトリツリー記述 (`policy/compose/`) を `policy/compose/` 直下に AgentSquare を `agentsquare/` として配置する形に解釈する。

## 8. リスクと対応 (確定)

| リスク | 対応 |
| --- | --- |
| Apache-2.0 全文の LICENSE が GitHub トップに見つからない | Phase 7e 着手時に上流 issue で確認、または PR で追加提案。当面は README の宣言を採用根拠とする |
| 上流の API が今後リファクタされ取り込み済コードと乖離 | 取り込み範囲を 4 ファイル + 4 ディレクトリに限定し、上流更新のレビュー範囲を最小化 |
| LLM 呼び出し差し替えで上流テストが通らない | tsumiki 側の test ハーネス (Phase 7b で新規) を整備し、上流の振る舞いを stub で再現 |
| 取り込み元の OpenAI SDK 呼び出しに gpt-3.5-turbo がハードコード | `tsumiki.llm.client` 経由に置換時に `LLM_MODEL` 環境変数で差し替えできるように改修 |
| numpy 1.24.1 と tsumiki の numpy のバージョン衝突 | tsumiki 側で >=1.24,<2.0 等に緩める。Phase 7e で pyproject.toml 整合確認 |

## 9. Phase 7b への申し送り

Phase 7b (パッケージ再構成) 着手前に以下を確定:

1. tsumiki の LICENSE を **Apache-2.0** で固定 (`LICENSE` ファイル新規作成、§5.3 と整合)
2. `pyproject.toml` の license フィールドを `{ text = "Apache-2.0" }` に
3. `THIRD_PARTY_LICENSES/` ディレクトリと `NOTICE` ファイルの雛形を作る
4. `src/tsumiki/policy/agentsquare/` のサブディレクトリは Phase 7b の §6 接続点表に従って空 `__init__.py` だけ先に作る
5. Phase 7e で AgentSquare 取り込みを着手する際の vendoring commit SHA を `docs/agentsquare_vendoring.md` に記録

## 10. Phase 7a 完了の判定

設計書 §6.1 (7a ゲート) の充足:

| ゲート | 判定 | 根拠 |
| --- | --- | --- |
| AgentSquare のレイヤー把握 | OK | §3.1 / §6 表で確定 |
| ライセンス整合 | OK | Apache-2.0 を双方採用 (§5.3 で NOTICE 等の運用確定) |
| 方針確定 | OK | B-2 partial vendoring を採用 (§4) |

→ **Phase 7a 完了**。Phase 7b に進む。

## 11. 関連

| 項目 | パス |
| --- | --- |
| 設計書 (Phase 7 全体) | [`phase7_design.md`](phase7_design.md) |
| 計画書 | [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md) §10 |
| メモリ | `[[project-phase7-next-step]]`, `[[project-framework-goal-decisions]]` |
