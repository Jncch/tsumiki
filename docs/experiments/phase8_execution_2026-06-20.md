# Phase 8 実走結果 (2026-06-20)

`examples/{nda,iso27001}/run.sh --use-compose` をローカル ollama 経由で実走し,
Phase 5c (NDA) / Phase 6 (ISO27001) の paired_diff が ±0.05 範囲で再現することを確認した.

## 0. メタ情報

| 項目 | 値 |
| --- | --- |
| 実行日 | 2026-06-20 |
| 実行者 | jnch (ローカル macOS) |
| LLM プロバイダ | openai_compatible (ollama OpenAI 互換 API) |
| ベース URL | http://localhost:11434/v1 |
| モデル / 量子化タグ | qwen25-14b-ctx8k (Qwen2.5-14B Instruct Q4_K_M, 8k ctx) |
| seed | 42 |
| temperature | 0.0 |
| ollama バージョン | 0.30.6 |
| MLflow experiment | examples_nda (543694810610006661) / examples_iso27001 (907916096646263393) |

## 1. 目的

Phase 7e-6 で導入した `--use-compose` 経由で,
NDA (Phase 5c) / ISO27001 (Phase 6) の paired_diff が ±0.05 範囲で再現することを確認する.
Phase 8 公開前の最終 sanity. 補助情報モードの `compose_selected_modules` / `compose_search_score` を併記する.

## 2. 実行コマンド

```bash
bash examples/nda/run.sh --use-compose
bash examples/iso27001/run.sh --use-compose
```

`--use-compose` 経由で `tsumiki.policy.compose.run_compose` の探索ループも併走させた
(現状は補助情報モードで paired_diff には影響しない. §6 参照).

## 3. 結果

### 3.1 NDA

| 指標 | Phase 5c 基準値 | 今回実測値 | 差 | gate (±0.05) |
| --- | --- | --- | --- | --- |
| reuse success_rate | 0.550 | 0.550 (40/40 サンプル) | 0.000 | - |
| zerobase success_rate | 0.289 | 0.289 (45/45 サンプル) | 0.000 | - |
| **paired_diff** | **+0.261** | **+0.261** | 0.000 | **OK** |
| reuse negative_transfer_rate | (未記録) | 0.700 | - | - |
| zerobase negative_transfer_rate | (未記録) | 0.444 | - | - |

| MLflow run | run_id |
| --- | --- |
| NDA reuse | `f33d26c0a6cc4beead6578cc6c65cf2c` |
| NDA zerobase | `5404f9a6e62a458087ecb8336a4c70e9` |

備考: reuse 試行中, modify 段階で 5 件が `llama-server chat error 500 (Failed to parse input)` で
skip された (`chusho_chizai_guideline:2|nda_duration_unbounded` 等). サンプル単位で skip する
Phase 5a-3 由来のガードが効き, n_samples=40 で算定. zerobase は全 45 サンプル成功.

### 3.2 ISO27001

| 指標 | Phase 6 基準値 | 今回実測値 | 差 | gate (±0.05) |
| --- | --- | --- | --- | --- |
| reuse success_rate | 0.410 | 0.410 (39/42 サンプル) | 0.000 | - |
| zerobase success_rate | 0.381 | 0.381 (42/42 サンプル) | 0.000 | - |
| **paired_diff** | **+0.029** | **+0.029** | 0.000 | **OK** |
| reuse negative_transfer_rate | (未記録) | 0.487 | - | - |
| zerobase negative_transfer_rate | (未記録) | 0.500 | - | - |

| MLflow run | run_id |
| --- | --- |
| ISO27001 reuse | `c405234f43214df58f03fe2623de2fa0` |
| ISO27001 zerobase | `e2e9f82dbe6349ec93cdb57ccd0a9f21` |

備考: synth 段階で 3 件が同じ `llama-server chat error 500` で skip (`iso_log_retention_undefined` 等).
合成サンプル 42 件のうち reuse modify 段階でさらに 3 件 skip → 39 件で算定. zerobase 42 件で算定.

### 3.3 compose 補助情報 (両ドメイン共通)

| 項目 | 値 |
| --- | --- |
| selected_modules | `{planning: PlanningEnhanced, reasoning: IO, tooluse: None, memory: None}` |
| search_score | NDA 0.550 / ISO27001 0.410 (reuse success_rate と一致) |
| search_depth | 1 |

`benchmark_fn` が trivial (reuse success_rate を返すだけ) なので, 探索は「動作確認」相当.
本物の探索評価は Phase 9+ で実装する.

### 3.4 Azure OpenAI 追加実走 (gpt-5.4, 2026-06-20 17:10〜)

ローカル ollama 再現の後, クラウド強モデルで paired_diff がどう変わるかを確認するため
Azure OpenAI (deployment=gpt-5.4, api_version=2024-10-01-preview) で追加実走した.

#### NDA (Azure)

| 指標 | ollama Qwen2.5-14B | Azure gpt-5.4 | 差 |
| --- | --- | --- | --- |
| reuse success_rate | 0.550 (40/40) | **0.800 (45/45)** | +0.250 |
| zerobase success_rate | 0.289 (45/45) | **0.778 (45/45)** | +0.489 |
| paired_diff | +0.261 | **+0.022** | -0.239 |
| compose selected_modules | `{planning: PlanningEnhanced, ...}` | **`{planning: PlanningStateAwareALFWorld, ...}`** | 異なる |
| synth 実時間 | 1352.9s | 142.0s | 約 1/10 |

| MLflow run | run_id |
| --- | --- |
| Azure NDA reuse | `ede369e61bb8436ba8696037c0f36520` |
| Azure NDA zerobase | `251ef5eae4d245aa80e6cf18a7e577d6` |
| experiment | `examples_nda_azure` (984434637058882068) |

観察:

- **強モデルでは reuse 効果が大幅縮小** (+0.261 → +0.022). 前回 Zenn 記事の弱モデル
  +0.212 → 強モデル +0.074 の縮小と同方向。Phase 5c E2E では Phase 2 検出ベースラインより
  さらに縮んだ. 「強モデルは知識層なしでもタスクをこなせる」が再確認された.
- **`zerobase success_rate` が大幅増** (0.289 → 0.778). 強モデルは zerobase 時点ですでに
  問題条項の修正タスクをかなりの精度でこなせる. 一方で reuse でさらに上積みが +0.022 出るのは
  「知識層が完全にゼロ寄与ではない」とも読める (ただし誤差範囲との切り分けは Phase 9+ 3-seed CI 待ち).
- **compose 探索結果がモデルで変わる** (`PlanningEnhanced` → `PlanningStateAwareALFWorld`).
  benchmark_fn は trivial なので探索パスの差は alfworld 由来 archives の偏りに由来するが,
  モデル能力で異なる構成が選ばれる現象は記録に値する.
- **skip 0 件**. ollama で散発した `llama-server chat error 500` は強モデル + Azure API では
  未観測. 安定性の差.

#### ISO27001 (Azure) — β 制約顕在化で停止

```
ValueError: generated evaluator failed verify:
  typical_success: coverage_of_findings_in_modified_doc_ratio mismatch: expected=1.0, got=0.0
  typical_success: format_preservation_score mismatch: expected=1.0, got=0.5
  typical_success: overall_pass mismatch: expected=1.0, got=0.0
```

原因: ISO27001 の goal 文 `'ISO27001 の運用文書をチェックして統制不備を是正したい'` を
gpt-5.4 の input parser が `inputs=['target_document', 'control_requirements']` と解釈.
ollama 時の `inputs=['target_document']` と input_signature が不一致になり, 評価器の
lookup が miss → generator パスに fallback → 再生成された評価器コードが
`typical_success` ケースの verify で失敗 → 実走停止.

これは Phase 7-bonus-2 (input_signature schemas 固定) と Phase 7-bonus-1
(generator 主 metric 整合) で扱う予定だった β 制約が, 強モデル + 別ドメインで
実際に顕在化した形. NDA 時は parser が同じ inputs=['target_document'] を返したため
lookup hit で済んだが, 文言で揺れることが実証された.

→ Phase 9+ の最優先項目に「input_signature schemas 固定 + parser 安定化」を昇格.
ISO27001 Azure の paired_diff 数値は今回取得できなかった.

## 4. 観察

- **paired_diff は両ドメインで基準値と完全一致 (差 0.000)**.
  seed=42 + temperature=0 + ng_book / 評価器 / clean_clauses が同一なので,
  決定論的に再現することは想定通り. `--use-compose` フラグが既存パスに副作用を持たない
  (補助情報モードの分離) ことの実地確証にもなった.
- `llama-server chat error 500` (Failed to parse input at pos 22) は ollama 側の grammar
  parser に起因. Phase 5a-3 で導入したサンプル単位 skip が効くため, batch 全体の中断には至らない.
  ただしクラウドモデルでは観測されない事象なので, Phase 8 公開時の β 機能注記に含める.
- compose 探索は両ドメインとも同じ構成 (PlanningEnhanced + IO) を選んだ. これは archives /
  prompts が alfworld 由来の状態のまま動いたため. domain 適応の必要性が改めて示された.
- 実行時間は NDA 約 32 分, ISO27001 約 32 分 (synth が大半). Qwen2.5-14B-Q4 + ollama Metal で
  この水準. Phase 9+ で軽量モデル併用と並列化を検討.

## 5. gate 判定

| ドメイン × モデル | paired_diff | 基準 | gate (±0.05) | 備考 |
| --- | --- | --- | --- | --- |
| NDA × ollama Qwen2.5-14B | +0.261 | +0.261 | **OK** (差 0.000) | Phase 5c と完全一致 |
| ISO27001 × ollama Qwen2.5-14B | +0.029 | +0.029 | **OK** (差 0.000) | Phase 6 と完全一致 |
| NDA × Azure gpt-5.4 | +0.022 | +0.261 | FAIL (差 -0.239) | 強モデルで縮小、想定通り (前回 Zenn 結論と同方向) |
| ISO27001 × Azure gpt-5.4 | (取得不可) | +0.029 | - | β 制約 (input_signature 不安定 + generator verify FAIL) |

「弱モデル × ollama での再現性」は両ドメイン完全 OK. 「強モデル × Azure」は
NDA で reuse 効果の縮小が想定通り観測, ISO27001 で β 制約が顕在化. 公開には十分.

## 6. compose 補助情報の所感

`--use-compose` は補助情報モードのため paired_diff を直接動かさないが, 以下の点で材料を提供:

- **alfworld 由来 archives でもパス自体は通る**: ChatFn / JsonChatFn / benchmark_fn DI 設計が
  ドメイン非依存に機能することの実地確認.
- **domain 適応の必要性**: 両ドメインで同じ構成 (PlanningEnhanced + IO) を選ぶのは, archives と
  prompts が alfworld の初期構成のままだから. NDA / ISO27001 用 archives を作る投資が
  Phase 9+ の優先事項.
- **benchmark_fn の本物実装が必要**: 現状 `reuse success_rate` を返すだけなので, 探索が真の意味で
  policy 選択をしていない. agentsquare 合成 chat_fn を benchmark に組み込むのが Phase 9+ の正味.

## 7. Phase 9+ への申し送り

- benchmark_fn の本物実装 (agentsquare 合成 chat_fn → variant 実行 → score)
- archives / prompts の domain 適応 (NDA / ISO27001 用初期 archive)
- evolve() 出力 code の chat_fn 化 (上流の `llm_response(...)` を `chat_fn(...)` に書き換え後処理)
- N=3 ドメイン追加
- 3 seed CI で統計的信頼性
- 人手較正 (LLM judge 偏り検証)
- Phase 7-bonus-1 (generator 主 metric 整合)
- Phase 7-bonus-2 (input_signature schemas 固定)
- ollama grammar parse error の調査 (クラウドモデルでは未観測)

## 8. 関連

- 実走チェックリスト: [phase8_execution_checklist.md](./phase8_execution_checklist.md)
- スケルトン: [phase8_execution_skeleton.md](./phase8_execution_skeleton.md)
- Zenn ドラフト: [phase8_zenn_draft_v0.md](./phase8_zenn_draft_v0.md)
- Phase 5c 結果: [phase5c_e2e_2026-06-19.md](./phase5c_e2e_2026-06-19.md)
- Phase 6 結果: [phase6_e2e_2026-06-19.md](./phase6_e2e_2026-06-19.md)
- Phase 7e 統合: [phase7e_summary_2026-06-19.md](./phase7e_summary_2026-06-19.md)
