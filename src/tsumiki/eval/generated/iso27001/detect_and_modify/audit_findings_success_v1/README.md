# Evaluator: audit_findings_success_v1

- domain: `iso27001`
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
- src/tsumiki/eval/generated/nda/detect_and_modify/modification_success_v1/ (Phase 5c)
- docs/experiments/phase6_design.md §4.3

## 既知の偏り / 適用条件

ISO27001 ドメイン用. outcomes JSONL 構造はドメイン非依存のため NDA seed と 同実装. qwen 14B での generator パスが品質不足を示したため (test_phase6_generator.py での verify 失敗を観測)、流用パスを取るために本 seed を投入. generator パスの 品質改善は Phase 7 以降 (クラウド GPT-5.4) で検証する.
