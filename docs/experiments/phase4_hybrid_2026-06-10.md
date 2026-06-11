# Phase 4 ハイブリッド戦略: クラウド辞書 × ローカル実行（seed=42, 2026-06-10）

「**クラウド強モデルで生成した知識層を、ローカル弱モデルで使えば良い性能が出るのではないか**」
という仮説を検証した結果。

> **結論**: **NO**。クラウド GPT-5.4 で精緻化した辞書 v0.4.0 をローカル qwen 2.5 14B で使っても、
> reuse の success_rate は **変化なし (0.548 vs 0.550)**。
> ローカル弱モデルの天井は **辞書品質ではなくテキスト理解・生成能力の限界** にあることが実証された。

## 0. 設計と仮説

### 0.1 仮説

> 弱モデルの性能限界が「辞書の質の低さ」にあるなら、
> クラウド強モデルが作った精緻な辞書を弱モデルに与えれば、
> クラウド水準に近い性能が出るはず。

### 0.2 検証構成

| 項目 | 値 |
| --- | --- |
| 辞書生成モデル | Azure OpenAI GPT-5.4 (model gpt-5.4-2026-03-05) |
| 辞書生成プロンプト | `experiments/generate_hybrid_dictionary.py` |
| 生成された辞書 | `src/tsumiki/knowledge/nda/ng_patterns_v0_4_0.yaml` |
| 辞書のサイズ変化 | description: 3 行 → **11 行** (約 3.6 倍に精緻化)、excerpt_examples: 1 件 → **3 件** |
| 実行モデル (T2 修正、T1 検出) | ローカル qwen 2.5 14B Instruct (Q4_K_M) on ollama |
| ollama context size | **8192** (カスタムモデル `qwen25-14b-ctx8k`、辞書冗長化で 4096 では不足) |
| seed | 42（Phase 2 baseline v0 と公正比較） |
| n_synth_per_pattern | 5 |
| MLflow experiment | `phase4_hybrid_local_seed42_v3` |
| 所要 | 約 127 分（synth 26 分 + reuse 50 分 + zerobase 35 分） |

### 0.3 比較対象

| variant | 辞書 | T2 実行モデル | 出典 |
| --- | --- | --- | --- |
| **ローカル baseline** | 人手 v0.2.0 | qwen 14B | Phase 2 baseline v0 seed=42 |
| **ハイブリッド (本検証)** | クラウド生成 v0.4.0 | qwen 14B | 本 Phase 4 |
| クラウド baseline | 人手 v0.2.0 | GPT-5.4 | Phase 2 Azure 3 seeds |

## 1. 集約結果

### 1.1 主要指標

| 指標 | ローカル + 人手辞書 | **ローカル + クラウド辞書** | 差 |
| --- | --- | --- | --- |
| reuse success_rate | 0.550 | **0.548** | **-0.002** |
| zerobase success_rate | 0.289 | 0.364 | +0.075 |
| **paired diff (reuse - zerobase)** | **+0.261** | **+0.184** | **-0.077** |
| reuse negative_transfer | 0.700 | 0.595 | -0.105 |
| zerobase negative_transfer | 0.444 | 0.477 | +0.033 |
| reuse n_samples | 40 | 42 (3 skip) | - |
| zerobase n_samples | 45 | 44 (1 skip) | - |

### 1.2 per-pattern success_rate

| pattern_id | ローカル+人手辞書 reuse | ハイブリッド reuse | 差 | 解釈 |
| --- | --- | --- | --- | --- |
| nda_jurisdiction_one_sided | 0.867 | **1.000** | +0.133 | 改善 |
| nda_purpose_undefined | 0.667 | 0.750 | +0.083 | 改善 |
| nda_duration_unbounded | 0.806 | 0.800 | -0.006 | 不変 |
| nda_disclosure_exception_missing | 0.850 | 0.600 | -0.250 | 悪化 |
| nda_derivative_undefined | 0.250 | 0.500 | +0.250 | 改善 |
| nda_remedy_imbalanced | 0.600 | 0.600 | 0.000 | 不変 |
| nda_return_destroy_missing | 0.350 | 0.250 | -0.100 | 悪化 |
| **nda_scope_overbroad** | 0.667 | **0.200** | **-0.467** | **大幅悪化** |
| nda_survival_missing | 0.467 | 0.200 | -0.267 | 悪化 |

**改善: 3/9 / 不変: 2/9 / 悪化: 4/9**。
パターン別にはマチマチで、トータルでは ≈ 0。

## 2. 解釈

### 2.1 仮説 2 への明確な答え

| 問い | 答え |
| --- | --- |
| 「クラウドで作った辞書をローカルで使えば良い性能が出るか」 | **NO** |
| reuse success_rate の改善 | -0.002（実質ゼロ） |
| ローカル弱モデルの天井 | 辞書品質ではない、**モデル能力** |

### 2.2 なぜ辞書を精緻化しても reuse は伸びないのか

クラウド辞書 v0.4.0 はローカル弱モデルにとって:

| 課題 | 内容 |
| --- | --- |
| **情報量の過多** | description が 3 倍長くなり、ローカル弱モデルが要点を抽出しきれない |
| **抽象表現の理解力不足** | GPT-5.4 が書いた精緻な法務表現を、qwen 14B が修正タスクに変換できない |
| **コンテキスト使用の効率** | 8192 token context を使い切る形になり、修正対象テキストへの注意配分が薄まる |
| **本質的なボトルネック** | 修正後文を法律文書として書く能力、多段落の整合性チェック能力に天井がある |

要するに **「教科書を高度にしても、生徒の能力が上がらない」** という結果。

### 2.3 zerobase が +0.075 改善した理由（注意）

zerobase variant は辞書を使わないのに success が向上した。
これは **「修正自体の改善」ではなく「検出器の判定変化」** による見かけの効果と解釈できる:

- zerobase: 修正プロンプトは辞書なし（変化なし）
- 検出器 (T1): 辞書 v0.4.0 を使う（変化あり）
- 「target NG が修正後に検出されない」割合を測る指標が、検出器の判定変化で動いた

つまり Phase 4 の zerobase 改善は **検出器の判定変化を観測しているだけ** で、実際の修正品質は変わっていない可能性が高い。

### 2.4 reuse の neg_transfer 改善 (-0.105) の解釈

reuse の negative_transfer が 0.700 → 0.595 と改善している。
これは **クラウド辞書が「対象条項」セクションを精緻化したため、検出器の条文範囲外検出（FP）が減った** ためと解釈できる。

辞書改善は **T1 検出器の精度を上げる効果はある** が、T2 修正自体の改善はない。

## 3. ハイブリッド戦略の現実的価値

| 用途 | 価値判定 |
| --- | --- |
| ローカル弱モデル運用での **T2 修正性能向上** | **価値なし**（success_rate +0.0） |
| ローカル弱モデル運用での **T1 検出精度向上** | あり（neg_transfer -0.105 から推定） |
| クラウドで生成 → ローカルで運用するコスト削減シナリオ | **限定的**。性能は人手辞書と同等、辞書メンテ自動化の価値は別途あり |
| 「弱モデルの天井を辞書で破る」期待 | **不可** |

## 4. 検証全体（Phase 1〜4）の最終結論

### 4.1 仮説に対する判定

| 仮説 | 結果 |
| --- | --- |
| 弱モデル運用での知識層再利用は成立する | ✅ 強く支持（paired diff +0.212） |
| クラウド強モデル運用での知識層再利用は成立する | △ 弱く支持（paired diff +0.074, CI 0 含む） |
| 真の負の転移なし | ✅ 両モデルで真の値 ≒ 0 |
| **クラウドで辞書を作ればローカルで強モデル並み性能が出る** | **❌ NO**（reuse +0.000、Phase 4 で実証） |

### 4.2 「再利用は何のために効くか」の整理

| 設計選択 | 主たる効果 |
| --- | --- |
| **辞書を人手で作る** | ローカル弱モデルでは大きな改善源（+0.212） |
| **辞書をクラウドで精緻化する** | T1 検出器の precision 向上、T2 reuse 自体は伸ばさない |
| **クラウド強モデルそのものを使う** | zerobase が +0.459 改善、辞書は補助的価値 |
| **特定パターンに絞った辞書投入** | クラウドでも +0.267 効く（derivative, disclosure） |

### 4.3 結論を一文で

> **知識層再利用は、弱モデルの能力補完として強く効く（+0.212）。
> 強モデルでは zerobase 自身が高性能になるため相対的価値は縮小（+0.074）。
> 辞書品質を上げてもローカル弱モデルの天井は破れない（+0.000）。
> モデル能力 > 辞書品質 という非対称性が、本検証で繰り返し観測された。**

## 5. 関連

- ローカル Phase 2 baseline v0: [`phase2_baseline_v0_2026-06-10.md`](phase2_baseline_v0_2026-06-10.md)
- クラウド Phase 2 (Azure GPT-5.4 3 seed): [`phase2_azure_gpt5_4_3seeds_2026-06-10.md`](phase2_azure_gpt5_4_3seeds_2026-06-10.md)
- ローカル人手レビュー: [`phase2_negative_transfer_review_results_2026-06-10.md`](phase2_negative_transfer_review_results_2026-06-10.md)
- クラウド人手レビュー: [`phase2_azure_negative_transfer_review_results_2026-06-10.md`](phase2_azure_negative_transfer_review_results_2026-06-10.md)
- Phase 3 頑健性: [`phase3_robustness_2026-06-10.md`](phase3_robustness_2026-06-10.md)
- 検証計画書: [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md)
- 生成スクリプト: [`../../experiments/generate_hybrid_dictionary.py`](../../experiments/generate_hybrid_dictionary.py)
- クラウド生成辞書: [`../../src/tsumiki/knowledge/nda/ng_patterns_v0_4_0.yaml`](../../src/tsumiki/knowledge/nda/ng_patterns_v0_4_0.yaml)
- outcomes JSONL:
  - [`phase4_outcomes/reuse_hybrid_seed42.jsonl`](phase4_outcomes/reuse_hybrid_seed42.jsonl)
  - [`phase4_outcomes/zerobase_hybrid_seed42.jsonl`](phase4_outcomes/zerobase_hybrid_seed42.jsonl)

## 6. 再現

```bash
# 前提: .env で Azure OpenAI 接続情報を設定
# 1) クラウドで辞書 v0.4.0 を生成
uv run python experiments/generate_hybrid_dictionary.py

# 2) ollama カスタムモデル qwen25-14b-ctx8k を作成（8k context）
cat > /tmp/Modelfile.ctx8k <<EOF
FROM hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M
PARAMETER num_ctx 8192
EOF
ollama create qwen25-14b-ctx8k -f /tmp/Modelfile.ctx8k

# 3) ローカル qwen + クラウド辞書 で Phase 2 を再走
LLM_PROVIDER=openai_compatible \
LLM_BASE_URL=http://localhost:11434/v1 \
LLM_API_KEY=ollama \
LLM_MODEL=qwen25-14b-ctx8k \
uv run python experiments/run_phase2_dryrun.py \
  --seeds 42 \
  --n-synth-per-pattern 5 \
  --experiment phase4_hybrid_local_seed42 \
  --outcomes-dir docs/experiments/phase4_outcomes \
  --variant-suffix _hybrid \
  --ng-patterns-path src/tsumiki/knowledge/nda/ng_patterns_v0_4_0.yaml
```
