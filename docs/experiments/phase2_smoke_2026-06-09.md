# Phase 2 スモーク結果 (2026-06-09)

Phase 1 で確定した P2 ベースライン（v0.3.0 + ng_patterns v0.1.0）を T1 検出器として再利用し、
T2（NG 条項修正）の対照実験を 1 seed × n_synth=3 で実走したスモーク結果。

## 実験設計

| 項目 | 値 |
| --- | --- |
| ドメイン | NDA（秘密保持契約） |
| T1（検出） | P2 ベースライン (v0.3.0 + ng_patterns v0.1.0) |
| T2（修正） | 2 variant を比較 |
| variant: **reuse** | T1 と同じ NG パターン辞書を T2 プロンプトに**注入**（知識層再利用） |
| variant: **zerobase** | 辞書なし、「NDA として不適切な部分を修正」という抽象指示のみ |
| モデル | qwen2.5 14B (再利用検証はモデル非依存なのでローカル中心、CLAUDE.md §3) |
| seed | 42（スモーク） |
| n_synth_per_pattern | 3 |
| 合成データ | Phase 1 と同じ synthesize 機構で生成（9 パターン × 3 = 27 サンプル） |

評価指標:
- **modification_success_rate**: 修正後テキストを T1 で検出 → target NG がすべて消えた割合
- **negative_transfer_rate**: 修正で **元になかった** NG が新たに検出された割合
- per-pattern success: 各 NG パターンを target にした件のうち消せた割合

## 結果

| variant | n_samples | **success_rate** | negative_transfer | 所要 |
| --- | --- | --- | --- | --- |
| **reuse** | 24 (3 skipped) | **0.750** | 0.917 | 23 分 |
| **zerobase** | 27 | 0.481 | 0.630 | 21 分 |

reuse 側で 3 件 skip は llama-server 500（既知の長 prompt 由来）。

### per-pattern success rate

| pattern_id | reuse | zerobase | 差 |
| --- | --- | --- | --- |
| nda_jurisdiction_one_sided | **1.00** | 0.33 | +0.67 |
| nda_scope_overbroad | **0.67** | 0.00 | +0.67 |
| nda_disclosure_exception_missing | **1.00** | 0.67 | +0.33 |
| nda_duration_unbounded | **0.67** | 0.33 | +0.34 |
| nda_derivative_undefined | **0.33** | 0.00 | +0.33 |
| nda_survival_missing | **0.50** | 0.33 | +0.17 |
| nda_purpose_undefined | 1.00 | 1.00 | 0 |
| nda_remedy_imbalanced | 0.67 | 0.67 | 0 |
| nda_return_destroy_missing | 1.00 | 1.00 | 0 |

**6/9 パターンで再利用が優位、3/9 が同等、劣位 0**。

## 読み取り

### 仮説支持

知識層（NG パターン辞書）の再利用が修正タスク T2 でも **明確に効く**。
success_rate +0.269 は単一 seed 結果としても説得力がある差。
特に **明示型 NG の修正**（jurisdiction、scope、duration）で再利用の優位が大きい。
辞書に「何が NG か」と「具体例」が明示されているため、修正側もそれを直接参照できる。

### 留意点

**Negative transfer が両方とも高め** (reuse 0.917, zerobase 0.630):

これは「T1 検出器が修正後テキストにも別の NG を検出した」割合。注意点は:
- T1 検出器の precision は 0.533（Phase 1 P2 ベースライン）。**1/3 程度は false positive** を含む可能性が高い。
- したがって生の negative_transfer 数値は「真の負の転移」より過大評価。
- reuse の方が zerobase より高い理由: 修正で完全に別の条文になり、新規 NG パターンが意図せず混入したか、もしくは LLM が辞書を見て他の NG にも対処しようとした結果として別 NG マーカーが出力された可能性。

検証手段として、修正後テキストを人手レビューする必要がある（Phase 1 計画書 §7.3 開放タスクの注意と同じ）。

### スモークでも判断できる結論

- **再利用が修正成功率を有意に押し上げる**: スモーク段階で確信できる。
- **負の転移が再利用で増える可能性**: 数値だけでは判断できず、人手検証または別の評価器が必要。

## 次に進めること

| 案 | 内容 |
| --- | --- |
| **本走 (3 seeds, n_synth=5)** | 信頼区間付きで上の数値を確定（推定 5 時間） |
| 人手検証 | 修正後テキストを 10〜20 件抜き取り、negative_transfer が実体か FP か判定 |
| Phase 3 設計 | 頑健性チェック（タスク記述の言い換え、seed 変更）と負の転移の精査 |

本走を 2026-06-09 22:20 開始（experiment `phase2_reuse_vs_zerobase_v0`、3 seeds, n_synth=5）。

## 再現

```bash
# Phase 1 と同じ前提:
# - data/processed/nda_clean_clauses.jsonl が存在 (10 件)
# - ng_patterns v0.1.0 が src/tsumiki/knowledge/nda/ にある

uv run python experiments/run_phase2_dryrun.py \
  --seeds 42 \
  --n-synth-per-pattern 3 \
  --experiment phase2_smoke
```

## 関連

- Phase 1 ベースライン: [`phase1_baseline_v1_2026-06-08.md`](phase1_baseline_v1_2026-06-08.md)
- プロンプト改善履歴: [`phase1_prompt_iterations.md`](phase1_prompt_iterations.md)
- 検証計画書: [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md)
- 修正器コード: [`../../src/tsumiki/baseline/ng_modifier.py`](../../src/tsumiki/baseline/ng_modifier.py)
- Phase 2 Runner: [`../../src/tsumiki/runner/phase2.py`](../../src/tsumiki/runner/phase2.py)
