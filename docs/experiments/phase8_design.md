# Phase 8 設計: Zenn 続編記事 + OSS リリース

本書は Phase 8 の事前設計. 記事執筆と OSS 公開に向けた構成・分量・トーン・対象範囲を後出ししないため.
実装後の結果は別途 `phase8_execution_<date>.md` に記録する.

## 0. 位置づけと方針

Phase 5c〜7e で達成した内容を, **前回記事 `https://zenn.dev/jnch/articles/68b0ede8c04aa8` の関連別記事** として 1 本にまとめる.
連載 (Part 3 / Part 4) ではなく単発記事として独立完結させ, 冒頭で前回記事を引用してリンクで接続する.

OSS リリースは記事公開と並行で実施 (GitHub リポジトリの README / CONTRIBUTING 整備).

## 1. ユーザー確定事項 (2026-06-19 ヒアリング)

| 質問 | 回答 |
| --- | --- |
| 記事構成 | **単発 1 本** (Phase 5c + 6 + 7 を 1 本に統合) |
| 前回接続 | **冒頭で前回結論を引用 + リンク** |
| AgentSquare 統合の扱い | **実装詳細を含めて報告** (vendoring 方針, ChatFn DI, β 機能の正直な扱い) |

## 2. 記事のメタ情報

| 項目 | 内容 |
| --- | --- |
| プラットフォーム | Zenn |
| 著者 | jnch |
| タイトル案 | `【Agentic AI 検証 続編】目的駆動とドメイン横展開で「再利用の土俵」を作り直す` |
| 副題 | (なし。前回記事と同じくリード文で目的明示) |
| ターゲット字数 | 15,000〜18,000 字 (前回 12,000〜15,000 字より長め, 内容が多面的なため) |
| 文体 | です/ます調. 一人称表現 (「私の予想は」等) も適度に. 学術的+実装的の混在は前回踏襲 |
| 公開タイミング | 記事ドラフト確定 → ユーザーレビュー → OSS リリース と同時公開 |
| ライセンス | 記事本文は Zenn 標準 (CC BY-NC 等). リポジトリは Apache-2.0 |

## 3. 主題と論旨

### 3.1 前回記事からの問いの引き継ぎ

前回記事の結論:
- 弱モデル (Qwen 2.5 14B) で paired_diff +0.212
- 強モデル (Azure GPT-5.4) で paired_diff +0.074
- **「モデル能力 > 知識層の品質」. 知識層だけでは能力差は埋まらない**

残った問い:
- **(問い 1)** 1 ドメイン (NDA) で出た +0.212 はドメイン横断で再現するか? 負の転移は?
- **(問い 2)** 「目的駆動」で TaskSpec → 評価器流用 → 知識・ツール再利用 → ポリシー再構築 という再利用の「土俵」自体を組み立てられるか?
- **(問い 3)** policy 探索エンジン (AgentSquare) を tsumiki の枠組みに統合できるか?

### 3.2 本稿の主題 (一文)

「Agentic AI の **再利用の土俵を組み立て直す** ことに挑戦した. 目的駆動 E2E + ドメイン横展開 + policy 探索エンジン統合の 3 段階を 1 ヶ月で実装し, **N=2 で仮説再現**を確認した. 一方, ドメインによる効きの差と β 機能の限界も観測した.」

### 3.3 結論の要旨 (記事末尾)

1. **N=2 で仮説再現**: NDA paired_diff +0.261, ISO27001 +0.029. 両方とも正の寄与で再利用仮説は外延的に確認.
2. **ドメインによる効きの差**: NDA は +0.261 だが ISO27001 は +0.029 (約 1/9). zerobase 性能の違いに引きずられる現象が再現.
3. **目的駆動の土俵は組めた**: 自然言語目的 → TaskSpec → 評価器流用 → ナレッジ層ロード → E2E 完走まで実装完了. Phase 5c で paired_diff +0.261 完全再現.
4. **AgentSquare 統合は薄いラッパに留めた**: ChatFn DI 化で alfworld 依存を剥がし, policy/compose ラッパで評価器 gate を強制. ただし本物の benchmark_fn (合成 chat_fn 構築) は Phase 9+ に持ち越し. β 機能としての正直な扱い.

## 4. 構成と見出し階層

```
H1: 【Agentic AI 検証 続編】目的駆動とドメイン横展開で「再利用の土俵」を作り直す
  H2: 全体像
  H2: この記事で扱うこと
  H2: 0. 前回記事との関係
  H2: 1. 前回の結論と残った 3 つの問い
  H2: 2. 本稿の仮説と検証設計
    H3: 2.1 検証する 3 つのこと
    H3: 2.2 ドメインの追加 (NDA + ISO27001 = N=2)
    H3: 2.3 フェーズ構成
  H2: 3. Phase 5c: 目的駆動 E2E へ
    H3: 3.1 TaskSpec / EvaluatorSpec という構造化
    H3: 3.2 評価器の lookup (流用) と generator (生成) の二系統
    H3: 3.3 知識層を Agent Skills 形式に揃える
    H3: 3.4 paired_diff +0.261 を完全再現
  H2: 4. Phase 6: ISO27001 への横展開 (N=2)
    H3: 4.1 9 不備パターンの定義 (運用文書のレビュー)
    H3: 4.2 同一フレームで NDA と ISO27001 を回す
    H3: 4.3 paired_diff +0.029, N=2 で仮説再現確認
    H3: 4.4 ドメインによる効きの差 (NDA 0.261 vs ISO27001 0.029)
  H2: 5. Phase 7: AgentSquare partial vendoring + policy/compose
    H3: 5.1 なぜ fork でなく partial vendoring (B-2) を選んだか
    H3: 5.2 ChatFn DI でタスク固有 utils と langchain を剥がす
    H3: 5.3 policy/compose 薄いラッパと評価器 gate
    H3: 5.4 benchmark_fn は Phase 9+ に持ち越した正直な事情 (β 機能扱い)
  H2: 6. 本稿で得た 4 つの実装知見
  H2: 7. 主要結果サマリ (表)
  H2: 8. 結論
    H3: 8.1 3 つの問いへの答え
    H3: 8.2 投資先判断アップデート
    H3: 8.3 最終結論 (一文まとめ)
  H2: 9. 制約と次の問い
  H2: 10. 参考文献・関連 OSS
  H2: 11. 著者からの注記
```

前回記事の構成 (全体像 → 仮説 → 検証設計 → 結果 → 結論 → 知見 → 制約 → 参考文献 → 注記) と **同じ骨格** を踏襲しつつ, 本稿固有のセクションを追加.

## 5. 各セクションの執筆方針

### 5.1 全体像 (H2)

前回記事と同じ表形式. 5 列程度 (項目 / Phase / 内容 / 主指標 / 結論). 読者は表だけ見ても主旨が掴める形に.

### 5.2 この記事で扱うこと (H2)

スコープを表で明示. 「扱う / 扱わない」を分けて誤読を防ぐ.

### 5.3 0. 前回記事との関係 (H2)

100〜200 字程度で接続を示し, 前回記事へのリンクを貼る. ユーザー選択肢の「冒頭で前回結論を引用 + リンク」と一致.

例:
> 前回記事「[【Agentic AI 検証】知識層は本当に再利用できるのか](https://zenn.dev/jnch/articles/68b0ede8c04aa8)」では、NDA ドメインで knowledge 層の再利用が paired_diff +0.212 (弱モデル) / +0.074 (強モデル) を出すことを示しました。残った問いは「ではこの再利用の土俵をどう組み立てるか」「N=1 のドメインだけで結論していいのか」です。本稿はそれらに対する続編として、目的駆動 E2E と ISO27001 への横展開、AgentSquare 統合までを 1 本にまとめます。

### 5.4 1. 前回の結論と残った 3 つの問い (H2)

200〜400 字. §3.1 の引き継ぎを文章化.

### 5.5 2. 本稿の仮説と検証設計 (H2)

3 つの問い → 3 つの検証 (Phase 5c / 6 / 7) を表で対応付ける. 数値の合格条件を**事前固定**で書く (前回記事も合格条件先出しスタイル).

### 5.6 3. Phase 5c: 目的駆動 E2E へ (H2)

中核セクション. 2,500〜3,500 字.
- TaskSpec / EvaluatorSpec の概念図を表で示す (Mermaid 等の図は使わない. 前回と整合)
- 評価器の lookup (流用) と generator (生成) を二系統で扱う設計理由
- 知識層を YAML から Agent Skills (Markdown) に揃えた理由
- paired_diff +0.261 完全再現の数値 (Phase 5c の結果報告書から)

### 5.7 4. Phase 6: ISO27001 への横展開 (H2)

2,500〜3,500 字.
- ISO27001 の 9 不備パターン (運用文書レビュー観点)
- NDA と同一フレーム (`runner/e2e.py`) で回せたこと
- paired_diff +0.029, gate OK 通過
- **ドメインによる効きの差** の解釈 (前回記事 §4.3 の知見と同型: 強モデルほど相対効果が縮む現象が, ドメイン間でも再現)

### 5.8 5. Phase 7: AgentSquare partial vendoring + policy/compose (H2)

3,000〜4,000 字. ユーザー要望の「実装の詳細を含めて報告」に応える.
- §5.1: なぜ fork でなく partial vendoring (B-2) を選んだか. 上流追随コスト, alfworld 依存の重さ, ライセンス遵守.
- §5.2: ChatFn DI 導入. `from utils import llm_response` を撤去し, `Callable[[str], str]` を `__init__` で受ける. langchain 系の Chroma / OpenAIEmbeddings も削除.
- §5.3: policy/compose 薄いラッパ + 評価器 gate. CLAUDE.md §9 の体現. `EvaluatorSpec.is_approved()` で `approved_by` を判定.
- §5.4: **正直な事情**. benchmark_fn は trivial (reuse_sr をそのまま返す). 本物の合成 chat_fn 構築は Phase 9+ に持ち越し. β 機能としての扱いを README にも明記.

### 5.9 6. 本稿で得た 4 つの実装知見 (H2)

前回記事の「検証から得た 4 つの実装知見」と対応する形式. 1 知見あたり 200〜300 字.

候補:
1. 目的駆動の TaskSpec / EvaluatorSpec は薄い構造で機能した. domain × task_class × io_signature の 3 列で流用判定できる.
2. N=2 でも「ドメインによる効きの差」は無視できない. zerobase 性能の高さに引きずられる現象が観測.
3. ChatFn DI は OSS 統合の基本パターン. 上流の SDK 直接呼び出しを剥がす作業はテストの単純化にも効く.
4. β 機能を「β と明記する」ことが OSS の信頼性に直結. 完成度を偽らない正直さが続編記事の説得力になる.

### 5.10 7. 主要結果サマリ (表)

NDA / ISO27001 の paired_diff, gate 通過, AgentSquare 統合の達成項目を表でまとめる.

### 5.11 8. 結論 (H2)

§3.3 の結論要旨を 3 〜 4 ブロックに分けて記述. 前回記事と同じく「投資先判断マトリクス」をアップデートして示す.

### 5.12 9. 制約 (H2)

正直に書く. ユーザー実走待ち項目 (例: `--use-compose` 経由の paired_diff 確認は本稿執筆時点で未実走), N=2 では汎用性主張に限界がある (N=3+ は Phase 9+), Phase 7-bonus-1 / 2 は未着手 (generator 改修), 等.

### 5.13 10. 参考文献・関連 OSS

前回踏襲. AgentSquare (Apache-2.0) を新規追加. DSPy / MLflow も再掲.

### 5.14 11. 著者からの注記

前回と同じく一人称表現で簡潔に. 「実装は GitHub で公開. PR / issue 歓迎」など.

## 6. 用語と表記の統一 (前回記事整合)

| 用語 | 表記 |
| --- | --- |
| 再利用変種 | reuse / zerobase / paired diff (前回と同じ) |
| paired diff の符号 | + / - を必ず付ける (例: +0.212, +0.074, -0.05) |
| モデル名 | 「Qwen 2.5 14B」「Azure GPT-5.4」(前回踏襲. GPT-5.4 は前回記事の表記をそのまま使う) |
| NG パターン ID | 前回記事の `nda_scope_overbroad` 等の snake_case を踏襲. ISO27001 用は新規 (例: `iso27001_access_control_incomplete`) |
| ドメイン | 「NDA」「ISO27001」(大文字統一) |
| フェーズ表記 | 「Phase 5c」「Phase 6」「Phase 7」(前回踏襲) |
| 評価指標 | `modification_success_rate`, `findings_recall`, `negative_transfer_rate` (実装と一致) |

## 7. コード例と図表の方針

| 種類 | 採用方針 |
| --- | --- |
| 表 | **多用**. 前回記事踏襲. 数値結果は全て表で見せる |
| 図 (Mermaid 等) | **使わない**. 前回記事と整合 |
| コード | **最小限**. 必要に応じて短い Python スニペット (TaskSpec dataclass, ChatFn DI before/after 等) を 1 セクション 1〜2 個まで |
| GitHub リンク | 文末参考文献 + 本文内で実装参照箇所のみ |
| 表数 | 前回 5 個 → 本稿は 8〜10 個 (N=2 と AgentSquare 追加分) |

## 8. 合格条件 (記事執筆完了の判定)

| 項目 | 条件 |
| --- | --- |
| 字数 | 15,000〜18,000 字 (±10%) |
| 構成 | §4 の見出し階層と一致 |
| 用語 | §6 の表記と一致 |
| 数値 | 全て実装結果報告書 (`docs/experiments/phase{5c,6,7e}_*.md`) と一致. 改竄なし |
| 前回引用 | §5.3 のテンプレートに沿って引用 + リンク |
| 制約セクション | β 機能 / ユーザー実走待ち / N=2 限界を明記 |
| 著者一人称 | 前回踏襲のトーンを維持 |
| ユーザーレビュー | 公開前に必ずユーザー確認 |

## 9. OSS リリース (記事と並行)

| 項目 | 内容 |
| --- | --- |
| リポジトリ | GitHub `Jncch/tsumiki` (既存) を public 化 |
| ライセンス | Apache-2.0 (LICENSE / NOTICE / THIRD_PARTY_LICENSES 配置済) |
| README | 新規作成. tsumiki の概要 + Phase 5〜7e の検証結果サマリ + クイックスタート (Docker, ollama, examples/) + β 機能の明示 |
| CONTRIBUTING.md | 新規作成. テスト方針 (`uv run pytest`), 設計事前固定ワークフロー (CLAUDE.md §4), PR 規約 |
| examples/ README | NDA と ISO27001 のリファレンス実装の使い方 |
| .env.example | 既存. Phase 7d で 3 系統対応済 |
| GitHub Actions CI | (Phase 9+ 検討). 本 Phase ではローカル test 通過のみ. |
| issue テンプレート | (任意). bug / feature の 2 種類 |

## 10. 実行手順

| ステップ | 内容 | 担当 |
| --- | --- | --- |
| 8-1 | 設計文書 (本書) 作成 | Claude |
| 8-2 | 記事ドラフト 0 版作成 (構成だけ) | Claude |
| 8-3 | ドラフト 0 版をユーザーレビュー | ユーザー |
| 8-4 | フィードバック反映 → ドラフト 1 版 | Claude |
| 8-5 | README / CONTRIBUTING / examples/README 作成 | Claude |
| 8-6 | ユーザー実走 (`examples/*/run.sh --use-compose`) で paired_diff 確認 | ユーザー |
| 8-7 | 実走結果を記事 §7 と §9 に反映 | Claude |
| 8-8 | 記事最終版 + リポジトリ public 化 | ユーザー |
| 8-9 | 結果報告書 `phase8_execution_<date>.md` | Claude |

## 11. リスクと対応

| リスク | 対応 |
| --- | --- |
| 記事が長くなりすぎる (20,000 字超) | 表に逃がす. 詳細は GitHub リポジトリへのリンクで切り出す |
| 前回記事と用語ズレが発生 | §6 の表記表を執筆中チェックリストとして使う |
| ユーザー実走の paired_diff が baseline から外れる | 制約セクションに正直に書く. β 機能の正当化として使える |
| AgentSquare 統合の「薄いラッパ」批判 | §5.4 で持ち越しの事情を先出しすることで正直な記述に. β 機能と明示 |
| OSS 公開時の機密混入 | `data/raw/` を `.gitignore` 済. `.env` 追跡なし. ライセンス記載は確認済 |
| 前回記事との重複が多すぎる | §4 構成で「前回踏襲」と明示しつつ, 本稿固有 (目的駆動 / N=2 / AgentSquare) を中心に配分 |

## 12. Phase 9+ への申し送り

本稿執筆と並行 / 公開後に着手:
- Phase 7-bonus-1 / 7-bonus-2 (generator 改修): β 機能の品質向上
- benchmark_fn の本物実装 (agentsquare 合成 chat_fn): Phase 7e-6 の補助情報モードを本探索に格上げ
- N=3 ドメイン追加 (規程レビュー以外で): 汎用性主張の強化
- 3 seed CI: 統計的信頼性
- 人手較正: LLM judge の偏り検証

## 13. 関連

| 項目 | パス |
| --- | --- |
| 前回記事 | https://zenn.dev/jnch/articles/68b0ede8c04aa8 |
| 計画書 | [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md) |
| Phase 5c 結果 | [`phase5c_e2e_2026-06-19.md`](phase5c_e2e_2026-06-19.md) |
| Phase 6 結果 | [`phase6_e2e_2026-06-19.md`](phase6_e2e_2026-06-19.md) |
| Phase 7e 統合結果 | [`phase7e_summary_2026-06-19.md`](phase7e_summary_2026-06-19.md) |
| 上流 AgentSquare | https://github.com/tsinghua-fib-lab/AgentSquare |
