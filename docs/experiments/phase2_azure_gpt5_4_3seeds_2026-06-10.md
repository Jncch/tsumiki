# Phase 2 クラウド確認: Azure GPT-5.4（3 seed CI, 2026-06-10）

CLAUDE.md §3 と検証計画書 §5.4 の「**最終確認はクラウドの強モデル**」要件に従い、
Phase 2 (reuse vs zerobase) を Azure GPT-5.4 で 3 seed 走らせた結果。

> **重要な観察**:
> - ローカル qwen 2.5 14B での **reuse 優位性 (paired diff +0.212, 全 seed 正方向) は、
>   GPT-5.4 では大幅縮小** (+0.074, 95% CI [-0.095, +0.243]、0 を含む)。
> - ただし seed 別 paired diff = (+0.000, +0.133, +0.089) で **2/3 seed では reuse 優位**。
>   seed=42 単発の「優位性消失 (0.000)」は **3 seed で見ると外れ値** だった。
> - 仮説「知識層再利用は成立する」は **モデル能力で減衰するが、消失したとは言い切れない**。
>   3 seed CI が 0 を含むため統計的有意性は不足。
> - per-pattern では derivative (+0.267), disclosure (+0.267) で明確に reuse 優位、
>   duration (-0.133) で zerobase 優位。

## 0. 設計

| 項目 | 値 |
| --- | --- |
| ドメイン | NDA |
| T1 (検出) | P2 ベースライン (検出 prompt v0.3.0) |
| T2 (修正) | reuse / zerobase の 2 variant |
| モデル | **Azure OpenAI gpt-5.4 (model gpt-5.4-2026-03-05)** |
| プロバイダ | Azure OpenAI (deployment: gpt-5.4) |
| API 仕様 | reasoning モデル: temperature 1.0 固定 / seed 受け付けず / max_completion_tokens=4096 |
| 再現性 | seed は合成器の選択順序にのみ影響、LLM 内部は確率的 |
| seeds | **42, 43, 44**（ローカルと同条件比較） |
| n_synth_per_pattern | 5（各 seed 45 sample） |
| 合成プロンプト | `synthesis.v0.1.0` |
| MLflow experiments | `phase2_azure_gpt5_4_seed42`, `phase2_azure_gpt5_4_seeds_43_44` |
| 所要 (3 seed 合計) | **約 41 分**（ローカル qwen 14B の 330 分の 1/8） |

## 1. 集約結果（3 seed mean ± std, 95% CI は t 分布 df=2, t=4.303）

### 1.1 主要指標

| 指標 | 3 seed mean ± std | 95% CI | per-seed (42, 43, 44) |
| --- | --- | --- | --- |
| **reuse success_rate** | **0.822 ± 0.022** | [0.767, 0.877] | 0.844, 0.800, 0.822 |
| **zerobase success_rate** | **0.748 ± 0.090** | [0.525, 0.971] | 0.844, 0.667, 0.733 |
| **paired diff (success)** | **+0.074 ± 0.068** | **[-0.095, +0.243]** | 0.000, +0.133, +0.089 |
| reuse negative_transfer | 0.407 ± 0.068 | [0.239, 0.576] | 0.467, 0.422, 0.333 |
| zerobase negative_transfer | 0.437 ± 0.090 | [0.214, 0.660] | 0.533, 0.356, 0.422 |
| paired diff (neg) | -0.030 ± 0.084 | [-0.239, +0.179] | -0.067, +0.067, -0.089 |

**paired diff success_rate**: 3 seed で正方向 2/3, ゼロ 1/3。**95% CI が 0 を含む** ため統計的有意性は不足。
mean +0.074 は小さいながら正方向の効果が残存している可能性を示唆。

### 1.2 ローカル vs クラウド の paired diff 比較

| 指標 | ローカル qwen 14B | **Azure GPT-5.4** | 差 |
| --- | --- | --- | --- |
| **paired diff (success)** | **+0.212** (全 seed 正方向) | **+0.074** (2/3 seed 正方向) | **-0.138** |
| reuse success | 0.612 ± 0.098 | 0.822 ± 0.022 | +0.210 |
| zerobase success | 0.400 ± 0.102 | 0.748 ± 0.090 | +0.348 |
| 所要 (3 seed) | 約 330 分 | 約 41 分 | -289 分 |

→ **paired diff が +0.212 → +0.074 へ約 65% 縮小**。
zerobase の絶対性能の向上 (+0.348) が reuse の改善 (+0.210) を上回るため、
相対的な reuse 優位は縮小したが消失していない。

### 1.3 per-pattern success_rate（3 seed mean ± std）

| pattern_id | reuse | zerobase | 差 | 解釈 |
| --- | --- | --- | --- | --- |
| nda_scope_overbroad | **1.000 ± 0.000** | **1.000 ± 0.000** | 0.000 | 両方完璧 |
| nda_derivative_undefined | 0.667 ± 0.115 | 0.400 ± 0.346 | **+0.267** | **reuse 優位** |
| nda_disclosure_exception_missing | 0.933 ± 0.115 | 0.667 ± 0.115 | **+0.267** | **reuse 優位** |
| nda_jurisdiction_one_sided | 0.667 ± 0.231 | 0.533 ± 0.306 | +0.133 | reuse 優位 |
| nda_purpose_undefined | 0.733 ± 0.115 | 0.600 ± 0.000 | +0.133 | reuse 優位 |
| nda_return_destroy_missing | 0.800 ± 0.000 | 0.733 ± 0.231 | +0.067 | わずか reuse 優位 |
| nda_remedy_imbalanced | 0.867 ± 0.115 | 0.867 ± 0.115 | 0.000 | 同等 |
| nda_survival_missing | 0.933 ± 0.115 | 1.000 ± 0.000 | -0.067 | わずか zerobase 優位 |
| nda_duration_unbounded | 0.800 ± 0.200 | 0.933 ± 0.115 | **-0.133** | **zerobase 優位** |

**reuse 優位 (+0.1 以上): 4/9（derivative, disclosure, jurisdiction, purpose）**
**同等: 3/9（scope, remedy, return_destroy）**
**zerobase 優位 (-0.1 以下): 1/9（duration）+ 1/9（survival はわずか）**

明示型でも欠落型でも reuse がやや優位、ただしローカルでの 8/9 reuse 優位と比べると弱い。

### 1.4 seed 単発の影響を再考

| seed | reuse | zerobase | paired diff |
| --- | --- | --- | --- |
| 42 | 0.844 | 0.844 | **0.000** ← 前回ドキュメント時の seed=42 単発の値 |
| 43 | 0.800 | 0.667 | +0.133 |
| 44 | 0.822 | 0.733 | +0.089 |

**seed=42 単発の paired diff = 0.000 は 3 seed 中の外れ値**。
1 seed だけでは「reuse 優位性消失」と誤判定するリスクがあった。
検証計画書 §5.4 「単発の好スコアで合否判定しない」と整合的な学び。

## 2. 検証計画書 §5.4 合格条件の再判定

ローカル＋人手レビューで「合格条件 3/3 達成、仮説支持」と判定。
クラウド確認で再判定すると:

| 条件 | ローカル qwen (3 seed) | **Azure GPT-5.4 (3 seed)** |
| --- | --- | --- |
| コールドスタート工数の削減 | ✅ | **△**（zerobase も 0.748 に達するため、辞書の追加価値は限定的） |
| 最終スコアを劣化させない | ✅ (+0.212) | **△→○**（+0.074 だが 95% CI が 0 を含む） |
| 負の転移が出ない | ✅（人手レビューで真の値 ≒ 0） | 要レビュー（observed paired diff -0.030 with wide CI） |

→ クラウドでは **「仮説の支持は弱まるが完全否定でもない」**。

## 3. 解釈

### 3.1 主要発見の修正

**前ドキュメント（seed=42 単発）の結論**:
- 「強モデルでは reuse 優位完全消失（paired diff = 0.000）」

**3 seed で修正された結論**:
- **paired diff = +0.074 ± 0.068**、3 seed 中 2 つで reuse 優位、1 つでゼロ
- ローカルの +0.212 から大幅縮小（約 65%）だが、完全消失ではない
- per-pattern 4/9 で +0.1 以上の reuse 優位、特に **derivative (+0.267)** と **disclosure (+0.267)**

### 3.2 仮説への含意（更新版）

| シナリオ | 知識層再利用の価値 |
| --- | --- |
| ローカル小型モデル (qwen 14B 等) | **大**（paired diff +0.212, 全 seed 正方向、CI 0 を含まない） |
| クラウド強モデル (GPT-5.4) | **小〜中**（paired diff +0.074, 2/3 seed 正、CI 0 を含む） |
| pattern 別の偏り | **derivative, disclosure 等の明確型 NG で強モデルでも reuse は有効** |

クラウド強モデルが zerobase でも 0.748 まで到達するため辞書の限界価値は減るが、
特定パターン（特に「派生資料」「開示例外」のような **意味的に細かい NG**）では
クラウドモデルでも辞書注入が +0.267 押し上げる。

### 3.3 seed=42 のばらつき源

GPT-5.4 は reasoning モデルで内部に確率性を持つ。temperature=1.0 固定で seed も受けないため、
完全再現はできない。seed 42 / 43 / 44 で paired diff が 0.000, +0.133, +0.089 と振れた。

**含意**: クラウド強モデルでの結論は **必ず CI 付き** で報告する必要がある。
1 seed の結果だけで判断するのは危険。

## 4. 検証全体の再評価

| Phase | 評価軸 | ローカル qwen 14B | **Azure GPT-5.4** |
| --- | --- | --- | --- |
| Phase 1 (T1) | macro_F2 | 0.651 ± 0.047 | 未測定 |
| Phase 2 (T2) | reuse 優位 (paired diff) | **+0.212**（CI 0 不含） | **+0.074**（CI 0 含む） |
| Phase 2 | per-pattern 優位 | 8/9 | 4/9（+0.1 以上） |
| Phase 2 | 仮説支持 | ✅ | **△**（弱い支持） |
| Phase 3 | 頑健性 (paired diff 維持) | △→✅ | **要再走** |

### 4.1 検証計画書 §5.4 の最終結論（修正版）

**仮説「知識層再利用は成立する」は、モデル能力で減衰するが完全否定はされない**:

| 条件 | 判定 |
| --- | --- |
| ローカル弱モデル (qwen 2.5 14B) | **✅ 強く支持**（paired diff +0.212, CI 0 不含） |
| **クラウド強モデル (GPT-5.4)** | **△ 弱く支持**（paired diff +0.074, CI 0 含む） |

これは「弱モデルの能力補完として強く効き、強モデルでも特定パターンでは依然有効」という条件付き支持。
検証計画書 §11「忖度せず、不合理・非効率・危険な案は否定する」に従い、
**Local-only で「強く支持」と結論することはできない** を明示記録。

### 4.2 知識層再利用の現実的価値（更新版）

| 用途 | 価値 |
| --- | --- |
| ローカル弱モデルでのコスト効率運用 | 大（paired diff +0.212, 全 seed 正方向） |
| クラウド強モデル運用（最高性能優先） | **中**（paired diff +0.074, 特に意味的に細かい NG で有効） |
| ハイブリッド運用（クラウド + 辞書） | **特定パターン (derivative, disclosure) で +0.267 の上積み** |
| 教育・説明可能性 | 中（モデル能力に関わらず有用） |

## 5. 次のステップ

### 5.1 確証のため (優先順)

| 案 | 内容 | 所要 |
| --- | --- | --- |
| **A** | **Azure reuse の負の転移サンプル人手レビュー**（ローカル同様、真の値の推定） | 2 時間（手作業） |
| B | **より難解な合成サンプル**で天井効果を回避し、reuse 優位を明確化（例: 7B モデルで合成し 5.4 で修正） | 約 30 分 |
| C | Phase 3 頑健性を Azure GPT-5.4 で再走 | 約 45 分 |
| D | 別ドメイン (業務委託契約等) で同実験を再現 | 1+ 日 |
| E | Phase 1 を Azure GPT-5.4 で再走（T1 検出器の能力上限を見る） | 約 15 分 |

### 5.2 検証計画書の更新候補

| 更新箇所 | 内容 |
| --- | --- |
| §1 結論サマリ | 「ローカルでの再利用優位は強モデルで減衰、ただし特定パターンで残存」を明示 |
| §3 中核仮説 | 「知識層再利用は弱モデルで強く、強モデルでは限定的に有効」と限定 |
| §5.4 合格条件 | クラウド強モデルでの再評価を必須化、判定は CI 付きで行う |
| §11 | Local-only での「強く支持」結論は誤りであることを記録 |

## 6. 関連

- ローカル Phase 2 baseline v0: [`phase2_baseline_v0_2026-06-10.md`](phase2_baseline_v0_2026-06-10.md)
- 人手レビュー結果: [`phase2_negative_transfer_review_results_2026-06-10.md`](phase2_negative_transfer_review_results_2026-06-10.md)
- Phase 3 頑健性 (ローカル): [`phase3_robustness_2026-06-10.md`](phase3_robustness_2026-06-10.md)
- 検出器 P4/P5-A 廃案: [`phase1_p4_v0.4.0_2026-06-10.md`](phase1_p4_v0.4.0_2026-06-10.md), [`phase1_p5_a_v0.5.0_2026-06-10.md`](phase1_p5_a_v0.5.0_2026-06-10.md)
- 検証計画書: [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md)
- 集計スクリプト: [`../../experiments/aggregate_phase2_seeds.py`](../../experiments/aggregate_phase2_seeds.py)
- outcomes JSONL:
  - reuse: [`phase2_outcomes_azure/reuse_azure_gpt5_4_seed42.jsonl`](phase2_outcomes_azure/reuse_azure_gpt5_4_seed42.jsonl),
    [seed43](phase2_outcomes_azure/reuse_azure_gpt5_4_seed43.jsonl),
    [seed44](phase2_outcomes_azure/reuse_azure_gpt5_4_seed44.jsonl)
  - zerobase: [`phase2_outcomes_azure/zerobase_azure_gpt5_4_seed42.jsonl`](phase2_outcomes_azure/zerobase_azure_gpt5_4_seed42.jsonl),
    [seed43](phase2_outcomes_azure/zerobase_azure_gpt5_4_seed43.jsonl),
    [seed44](phase2_outcomes_azure/zerobase_azure_gpt5_4_seed44.jsonl)

## 7. 再現

```bash
# 前提: .env で LLM_PROVIDER=azure_openai に設定、AZURE_OPENAI_* 環境変数を設定
# 前提: data/processed/nda_clean_clauses.jsonl が存在

mkdir -p docs/experiments/phase2_outcomes_azure

# seed=42（既に走り済みなら skip）
uv run python experiments/run_phase2_dryrun.py \
  --seeds 42 \
  --n-synth-per-pattern 5 \
  --experiment phase2_azure_gpt5_4_seed42 \
  --outcomes-dir docs/experiments/phase2_outcomes_azure \
  --variant-suffix _azure_gpt5_4

# seed=43, 44 を追加で
uv run python experiments/run_phase2_dryrun.py \
  --seeds 43 44 \
  --n-synth-per-pattern 5 \
  --experiment phase2_azure_gpt5_4_seeds_43_44 \
  --outcomes-dir docs/experiments/phase2_outcomes_azure \
  --variant-suffix _azure_gpt5_4

# 3 seed 集計
uv run python experiments/aggregate_phase2_seeds.py \
  --outcomes-dir docs/experiments/phase2_outcomes_azure \
  --suffix _azure_gpt5_4 \
  --seeds 42 43 44
```
