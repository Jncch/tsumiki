# Evaluator: modification_success_v1

- domain: `nda`
- task_class: `detect_and_modify`
- type: `deterministic`
- generated_at: 2026-06-19
- approved_by: jncch

## 出力指標

- modification_success_rate
- negative_transfer_rate
- per_pattern_success

## 参照元

- src/tsumiki/eval/modification.py (Phase 1〜4)
- docs/experiments/phase2_baseline_v0_2026-06-10.md
- docs/experiments/phase5b_skills_2026-06-19.md

## 既知の偏り / 適用条件

Phase 1〜4 の compute_modification_report を Q3=B 決定関数として移植. Agent Skills 経由のロード前提. Phase 5b で paired diff +0.261 完全一致を確認済み.
