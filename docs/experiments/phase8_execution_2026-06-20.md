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

| ドメイン | gate (±0.05) | 備考 |
| --- | --- | --- |
| NDA | **OK** (差 0.000) | Phase 5c +0.261 と完全一致 |
| ISO27001 | **OK** (差 0.000) | Phase 6 +0.029 と完全一致 |

両 OK のため Phase 8-7 (記事 §7/§9 への反映) に進行可.

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
