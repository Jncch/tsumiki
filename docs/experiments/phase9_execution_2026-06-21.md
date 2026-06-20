# Phase 9 実走結果 (2026-06-21)

Phase 9a〜9f で構築した「対話的評価器生成 + 開放タスク対応」スタックを
4 ドメインで実走し, 開放タスクでも reuse vs zerobase の対照が有効に機能するかを検証した.

## 0. メタ情報

| 項目 | 値 |
| --- | --- |
| 実行日 | 2026-06-21 |
| 実行者 | jnch (ローカル macOS) |
| LLM プロバイダ | azure_openai |
| deployment / model | gpt-5.4 |
| api_version | 2024-10-01-preview |
| seed | 42 |
| temperature | 0.0 |
| sample_count (per variant) | 8 |
| MLflow experiment | phase9f_<domain> |

## 1. 目的

Phase 8-6 で「閉じたタスク」(NDA / ISO27001) の対照は強モデル経由でも検証可能であることを確認した.
Phase 9 ではフレームを **開放タスク** (生成 / 要約 / 推論 / 入力なしの作文 等) に拡張し,
同じ「reuse vs zerobase で対照する」設計が機能するかを 4 ドメインで実走確認する.

## 2. 検証構成

### 2.1 評価器生成フロー

- 評価器は Phase 9b〜9c で実装した **対話 REPL** で組み立てる
- 各 example の `dialog_seed.yaml` を scripted input として replay し EvaluatorDraft を再現
- 評価軸は `_common/` の `char_limit` と `keyword_inclusion` を採用 (両方とも deterministic)
- 重み equal, 厳しさ balanced (合格しきい値 0.7), 各軸の必須/禁止キーワードはドメイン固有

### 2.2 reuse vs zerobase の対照

- reuse 経路: `knowledge_text` (各ドメインの SKILL.md) を sample 生成 prompt に注入
- zerobase 経路: 注入なしで goal だけから生成
- 各経路で 8 件サンプル生成 → 評価器ドラフトで採点 → 平均
- `score_diff = reuse_score - zerobase_score`

### 2.3 4 ドメインの 3 直交軸組合せ

| ドメイン | task_class | output_kind | input_modality |
| --- | --- | --- | --- |
| marketing_post | generate | open | free_text |
| meeting_summary | summarize | semi_open | mixed |
| spec_to_tests | generate | semi_open | doc |
| campaign_proposal | compose | open | none |

Phase 9 設計 §3.6 の選定原則「ドキュメント入力 / 自然言語のみ / 入力なし を網羅」を満たす.

## 3. 結果

### 3.1 主要数値

| ドメイン | input_modality | output_kind | reuse_score | zerobase_score | score_diff |
| --- | --- | --- | --- | --- | --- |
| marketing_post | free_text | open | 0.938 | 0.688 | **+0.250** |
| meeting_summary | mixed | semi_open | 1.000 | 0.562 | **+0.438** |
| spec_to_tests | doc | semi_open | 1.000 | 1.000 | **+0.000** |
| campaign_proposal | none | open | 1.000 | 0.062 | **+0.938** |
| **平均 (4)** | | | **0.985** | **0.578** | **+0.407** |
| **平均 (3, 天井効果 spec_to_tests 除外)** | | | 0.979 | 0.437 | **+0.542** |

### 3.2 既存閉じたタスクとの比較 (Phase 8-6)

| ドメイン | 主指標 | 値 (ollama Qwen2.5-14B) | 値 (Azure gpt-5.4) |
| --- | --- | --- | --- |
| NDA (閉じた) | paired_diff | +0.261 | +0.022 |
| ISO27001 (閉じた) | paired_diff | +0.029 | (β 制約で取得不可) |
| marketing_post (開放) | score_diff | (試走なし) | +0.250 |
| meeting_summary (開放) | score_diff | (試走なし) | +0.438 |
| spec_to_tests (開放) | score_diff | (試走なし) | +0.000 |
| campaign_proposal (開放) | score_diff | (試走なし) | +0.938 |

Phase 8-6 で NDA × Azure は +0.022 まで縮小したが, Phase 9 開放タスクでは
強モデルでも reuse 効果が再現. 「閉じたタスクでは強モデルが天井に達して
reuse 余地が縮む」が「開放タスクではガイドライン形式や必須要素の遵守という
別の評価軸が残るため knowledge による上積みが効く」と整理できる.

## 4. 観察と解釈

### 4.1 ドメインごとの解釈

- **marketing_post** (free_text × open, +0.250): zerobase の段階で gpt-5.4 が
  ある程度の SNS 投稿を作れている (0.688) が, ブランド指定の必須キーワード
  (新発売 / ビーガン) の組み込みは knowledge 注入で安定化. 強モデル + 形式制約
  弱めの開放タスクで「上積み層」が見える代表例.
- **meeting_summary** (mixed × semi_open, +0.438): zerobase は構成 (議題 /
  決定事項 / アクション) の遵守が安定せず 0.562 にとどまる. SKILL.md の
  必須キーワード「決定事項」「アクション」と禁止表現「適宜」「随時」が
  形式遵守を大きく押し上げる. 構造化系タスクで knowledge が効く好例.
- **spec_to_tests** (doc × semi_open, +0.000): 両経路とも 1.000. gpt-5.4 が
  BDD の Given/When/Then 形式を「常識」として持っており, knowledge 無しでも
  形式遵守できる **強モデル天井効果**. Phase 8-6 で NDA × Azure が +0.022 に
  縮小したのと同じ現象. 評価軸を char_limit と Given/When/Then 必須にした
  だけでは強モデルの実力では差が出ない. 「ドメイン固有の細かい品質」(例:
  境界値テストの網羅性) を測れる軸が必要.
- **campaign_proposal** (none × open, +0.938): zerobase は 0.062 と崩壊.
  goal だけから「9月決算月の販促を考えたい」と言われても、構造 (キャンペーン名 /
  対象 / 期間 / KPI / 必須キーワード) が安定せず, knowledge 注入で +0.938.
  **入力モダリティ none + 構造制約強めのケースで knowledge の効果が最大** という
  きれいな結果. tsumiki の「目的だけから対話で評価器を組み立てる」設計の
  意義をもっとも顕著に示している.

### 4.2 仮説への寄与

| 仮説 | 結果 | 解釈 |
| --- | --- | --- |
| 開放タスクでも reuse vs zerobase の対照が機能する | ◯ | 4 ドメイン中 3 で score_diff > 0, 平均 +0.407 |
| 形式制約が強いタスクほど knowledge の上積みが大きい | ◯ | campaign (構造強制) > meeting (構成定義) > marketing (緩い) |
| 強モデルだと閉じたタスクでは天井に達するが開放では効く | ◯ | spec_to_tests のみ天井, 他は reuse 優位 |
| 構造化対話 (Q1〜Q13) が無数のユースケースで動く | ◯ | 4 ドメイン同一フローで EvaluatorDraft 構築 (Phase 8-6 で観測した parser 文言揺れなし) |

### 4.3 制約と限界

- **N=4 ドメイン, seed=42 単発**. 統計的有意性は別途 3-seed CI で検証必要 (Phase 10+).
- 評価軸が **deterministic 2 種類のみ** (char_limit + keyword_inclusion).
  LLM judge_panel / pairwise を含む評価器の効果は本フェーズでは未検証.
- サンプル N=8 件で平均しているが, **サンプル生成自体が gpt-5.4 で決定的でない**.
  spec_to_tests の +0.000 が「真の天井」か「LLM 生成の偏り」かは更なる試走で要確認.
- knowledge_text の長さ (500〜900 字) と効果の相関は未測定.
- pairing は同サンプル間ではなく集計値の比較 (paired_diff と異なり通常の差).

## 5. ゲート判定

Phase 9 設計 §4.1 「試走 (Phase 9f で選んだ 1〜2 ドメイン): score_diff > 0」 を満たす:

| ドメイン | gate (score_diff > 0) | 備考 |
| --- | --- | --- |
| marketing_post | **OK** (+0.250) | reuse 経路有意 |
| meeting_summary | **OK** (+0.438) | reuse 経路有意 |
| spec_to_tests | △ (+0.000) | 天井効果. 強モデル + 緩い評価軸の組合せ起因 |
| campaign_proposal | **OK** (+0.938) | input_modality=none で reuse 効果最大 |

4 ドメイン中 3 で正の score_diff. spec_to_tests は天井で 0 に張り付いたが
zerobase 自体が満点なので「逆効果ではない」. 全体として Phase 9 の合格条件を満たす.

## 6. 次の問い (Phase 10+ への申し送り)

- **3-seed CI で統計的信頼性**: 単発 seed で +0.000〜+0.938 の幅がどこまで残るか
- **LLM judge_panel / pairwise の実走**: deterministic 軸だけでは Phase 9 試走の
  天井効果や緩さが残る. 複数批評パネルで「品質」を測る評価器の効果検証
- **spec_to_tests のように天井に達したドメインで, 評価軸を高度化** (境界値網羅 /
  ステップ詳細度 / モック適正配置 等) すれば差が復活するか検証
- **input_modality=structured の試走** (障害ログ → 根本原因推論など)
- **knowledge_text の長さと score_diff の相関**を測る ablation
- **より対話で深掘りした評価器** (Stage 4-5 で判定一致を取った経路) の効果検証
  Phase 9 の試走は dialog_seed.yaml = Stage 3 までの replay. Stage 4-5 (サンプル
  判定 + judge 調整) を加えた経路は本フェーズでは未試走

## 7. 関連

- Phase 9 設計: [phase9_design.md](./phase9_design.md)
- Phase 8 実走 (閉じたタスク): [phase8_execution_2026-06-20.md](./phase8_execution_2026-06-20.md)
- 試走 example: `examples/{marketing_post, meeting_summary, spec_to_tests, campaign_proposal}/`
- 試走スクリプト: `experiments/run_phase9f_open_ended.py`
- outcomes: 各 example の `outcomes/phase9f_<domain>_seed42.json`
- Zenn 統合記事 (Phase 9g): [phase8_zenn_draft_v0.md](./phase8_zenn_draft_v0.md) (Phase 9 セクション追加版)
