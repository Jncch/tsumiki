# Phase 5b 結果: Agent Skills 経由の paired diff 一致確認 (seed=42)

設計: [phase5b_design.md](phase5b_design.md)

## 0. 結論

> Markdown スキル経由で読み込んだ NGPatternBook で reuse + zerobase を走らせた結果、
> **全指標が Phase 5a V0（YAML 経由）と完全一致**した。
> paired diff = +0.261、|diff| = 0.000 で baseline 一致ゲートを通過。
> modify skip も同じ 5 件 (`chusho_chizai_guideline:2|nda_duration_unbounded` ほか) が同順で発生し、
> prompt が文字単位で同一になっていることが間接的に確認された。
> Phase 5b の全合格条件を満たしたため Phase 5c に進む。

## 1. 主指標 (Phase 5a V0 との完全比較)

| 指標 | Phase 5a V0 (YAML) | Phase 5b (Agent Skills) | 差 |
| --- | --- | --- | --- |
| reuse n_samples | 40 | 40 | 0 |
| reuse success_rate | 0.550 | 0.550 | 0.000 |
| reuse negative_transfer | 0.700 | 0.700 | 0.000 |
| zerobase n_samples | 45 | 45 | 0 |
| zerobase success_rate | 0.289 | 0.289 | 0.000 |
| zerobase negative_transfer | 0.444 | 0.444 | 0.000 |
| **paired diff (reuse - zerobase)** | **+0.261** | **+0.261** | **0.000** |

ゲート判定: 設計 §4.2「paired diff が +0.261 ± 0.05 内」→ **通過**（|diff| = 0.000）。

## 2. modify skip パターンの完全一致

| # | skip 対象 | Phase 5a V0 | Phase 5b |
| --- | --- | --- | --- |
| 1 | chusho_chizai_guideline:2 \| nda_duration_unbounded | ◯ | ◯ |
| 2 | chusho_chizai_guideline:2 \| nda_purpose_undefined | ◯ | ◯ |
| 3 | chusho_chizai_guideline:1 \| nda_disclosure_exception_missing | ◯ | ◯ |
| 4 | chusho_chizai_guideline:2 \| nda_derivative_undefined | ◯ | ◯ |
| 5 | chusho_chizai_guideline:1 \| nda_survival_missing | ◯ | ◯ |

ollama / llama-cpp の grammar parse error は input の文字列に依存する。skip が同じ 5 件で同順発生したことは、modifier に渡される prompt 文字列が完全同一であることの強い証拠。

## 3. per-pattern success_rate の一致

| pattern_id | Phase 5a V0 reuse | Phase 5b reuse | 差 |
| --- | --- | --- | --- |
| nda_derivative_undefined | 0.250 | 0.250 | 0.000 |
| nda_disclosure_exception_missing | 1.000 | 1.000 | 0.000 |
| nda_duration_unbounded | 0.750 | 0.750 | 0.000 |
| nda_jurisdiction_one_sided | 1.000 | 1.000 | 0.000 |
| nda_purpose_undefined | 0.500 | 0.500 | 0.000 |
| nda_remedy_imbalanced | 0.600 | 0.600 | 0.000 |
| nda_return_destroy_missing | 0.200 | 0.200 | 0.000 |
| nda_scope_overbroad | 0.400 | 0.400 | 0.000 |
| nda_survival_missing | 0.250 | 0.250 | 0.000 |

zerobase 側も全 9 パターンで一致（省略、outcomes JSONL に記録済み）。

## 4. 所要時間

| 段階 | Phase 5a V0 | Phase 5b | 差 |
| --- | --- | --- | --- |
| synth | 28.7 分 | 24.2 分 | -4.5 分 |
| reuse | 47.1 分 | 42.6 分 | -4.5 分 |
| zerobase | 34.6 分 | 31.4 分 | -3.2 分 |
| 合計 | 110.4 分 | 98.2 分 | -12.2 分 |

時間差は実行マシンの負荷状態の違いに起因（同じ ollama / qwen 14B、同じカスタムモデル `qwen25-14b-ctx8k`）。Phase 5b のほうが約 11 % 短いが、結果値は完全一致しているので prompt 内容は同じ。

## 5. 情報等価性の最終確認

unit test `tests/test_skills_loader.py`（11 件通過）は Markdown スキル経由でロードした `NGPatternBook` が YAML 経由と
- `id`, `name`, `description`, `severity`, `excerpt_examples`, `references`, `applicable_topics`
- `topics`, `version`, `contract_type`, `last_updated`, `maintainer`

の全フィールドで等価であることを確認していた。本試走でこの等価性が **実行レベル**（paired diff 一致）でも保たれることが実証された。

## 6. Knowledge schema 設計の妥当性

Phase 5a で確定した分類（§5）がそのまま Markdown スキルの構造に落とせ、情報損失なく往復変換できることが確認された。

| Phase 5a 分類 | Markdown 上の配置 | 寄与 | 検証結果 |
| --- | --- | --- | --- |
| 対象条項 | 本文 H2 セクション | 寄与大 (Δ+0.172) | description 経由で LLM prompt に投入される |
| 検出すべき | 本文 H2 セクション | 寄与中 (Δ+0.073) | 同上 |
| 紛らわしい | 本文 H2 セクション | 寄与中 (Δ+0.083) | 同上 |
| excerpt_examples | 「## 例」セクション | 寄与中 (Δ+0.098) | description には含まれず、別 prompt 経由（既存挙動） |
| applicable_topics | フロントマター | dead code (v0.3.0 prompt) | フロントマターに残し、v0.5.0 検証時に参照 |
| severity, references | フロントマター | LLM prompt 非投入 | 鮮度管理のメタデータとして保持 |
| id, name | フロントマター | パターン同一性 | 機械検索キーとして機能 |

## 7. Phase 5c への申し送り

- Knowledge 層の正規フォーマットは **Agent Skills 標準（Markdown スキル）** に確定
- `load_ng_patterns_auto` がディレクトリと YAML を自動判別するため、Phase 5c の `runner/e2e.py` は Agent Skills 経路を主として実装する
- 既存 YAML 形式 (`src/tsumiki/knowledge/nda/ng_patterns.yaml`) は後方互換のため当面残置
- Phase 6 (ISO27001) では `src/tsumiki/knowledge/skills/iso27001/<task_class>/` 配下に最初から Markdown スキル形式でナレッジを起こす
- フロントマター必須キー: `id, name, domain, schema_version`
- フロントマター推奨キー: `task_classes, severity, applicable_topics, references, last_updated, maintainer`
- 本文必須セクション: `## 対象条項`, `## 検出すべき`, `## 紛らわしい`, `## 例`

## 8. 再現コマンド

```bash
# 1) YAML → Markdown スキル変換
uv run python experiments/build_nda_skills.py

# 2) 情報等価性 unit test
uv run pytest tests/test_skills_loader.py -v

# 3) Agent Skills 経由の試走
LLM_PROVIDER=openai_compatible \
LLM_BASE_URL=http://localhost:11434/v1 \
LLM_API_KEY=ollama \
LLM_MODEL=qwen25-14b-ctx8k \
uv run python experiments/run_phase2_dryrun.py \
  --seeds 42 \
  --n-synth-per-pattern 5 \
  --experiment phase5b_skills_v1 \
  --outcomes-dir docs/experiments/phase5b_outcomes \
  --variant-suffix _V0 \
  --ng-patterns-path src/tsumiki/knowledge/skills/nda/ng_patterns

# 4) 集約
uv run python experiments/aggregate_phase5a.py \
  --outcomes-dir docs/experiments/phase5b_outcomes \
  --seed 42 \
  --variants V0 \
  --baseline-paired-diff 0.261
```

## 9. 関連

| 項目 | パス |
| --- | --- |
| 設計 | [`phase5b_design.md`](phase5b_design.md) |
| 結果報告（本書） | `docs/experiments/phase5b_skills_2026-06-19.md` |
| Phase 5a 設計 | [`phase5a_design.md`](phase5a_design.md) |
| Phase 5a 結果（Knowledge schema 確定） | [`phase5a_ablation_2026-06-19.md`](phase5a_ablation_2026-06-19.md) |
| Phase 5c 設計 | [`phase5c_design.md`](phase5c_design.md) |
| 計画書 | [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md) §10 |
| 変換コンバータ | `experiments/build_nda_skills.py` |
| Markdown ローダ | `src/tsumiki/knowledge/skills_loader.py` |
| 自動判別ファクトリ | `src/tsumiki/knowledge/loader.py` の `load_ng_patterns_auto` |
| 情報等価性テスト | `tests/test_skills_loader.py` (11 件) |
| 生成スキル | `src/tsumiki/knowledge/skills/nda/ng_patterns/*.md` (9 件) |
