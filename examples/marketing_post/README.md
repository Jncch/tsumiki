# examples/marketing_post — 広報原稿生成 (Phase 9f)

tsumiki の開放タスク経路 (`output_kind=open`, `input_modality=free_text`) のリファレンス実装.

## 構造

- `goal.yaml` — TaskSpec スナップショット
- `dialog_seed.yaml` — Phase 9b〜9c の対話履歴 seed (replay 用)
- `knowledge/` → `src/tsumiki/knowledge/skills/marketing_post/SKILL.md` 参照
- `run.sh` — 試走スクリプト

## 試走

```bash
# .env で LLM_PROVIDER=azure_openai 等を設定済みであること
bash examples/marketing_post/run.sh
```

`run.sh` は `experiments/run_phase9f_open_ended.py` を呼び:

1. `dialog_seed.yaml` を replay → EvaluatorDraft 構築 (Phase 9b〜9c)
2. `goal.yaml` から TaskSpec 再構築
3. `knowledge/skills/marketing_post/SKILL.md` を knowledge_text として読み込み
4. reuse (knowledge 注入) / zerobase (注入なし) で各 N=8 件サンプル生成
5. 評価器ドラフトで採点 → `score_diff = reuse_score - zerobase_score`
6. MLflow + `outcomes/` に記録

## 期待される結果

knowledge 注入で reuse 経路が brand guideline を踏まえた原稿になり、
zerobase より score (char_limit + keyword_inclusion 合算) が高くなる想定.
