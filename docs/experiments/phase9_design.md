# Phase 9 設計: 対話的評価器生成 + 開放タスク対応 (ドメイン非依存)

## 0. メタ情報

| 項目 | 値 |
| --- | --- |
| 起票日 | 2026-06-20 |
| 親 | Phase 9 (タスク #130) |
| 前提 | Phase 5c (目的駆動 E2E) / Phase 6 (N=2 横展開) / Phase 7 (AgentSquare 統合) 完了 |
| ブロック先 | Phase 8-8 (公開) — Phase 9 完了後に Phase 5c/6/7/9 統合 1 本記事として実施 |
| 期間目安 | 約 2 週間 |

## 1. 動機と原則

### 1.1 tsumiki の core thesis

「無数のユースケースに対応できる評価器の生成手法を確立し, それを再利用可能な蓄積として持つ」 — これが tsumiki の存在意義.

| 価値の源泉 | 内容 |
| --- | --- |
| **評価器生成の汎用化** | ドキュメントチェック, 文書生成, 推論, 要約, テストケース起こし, 広報原稿, 議事録要約, ログ調査... どんなユースケースが来ても同じ手順で評価器を組み立てる |
| **再利用可能な蓄積** | `domain + task_class + input_signature` の lookup key で **同じような入力には同じ評価器を再利用する**. 一度承認された評価器は次回以降ノータイム |
| **対話による承認** | ユーザーと対話して評価軸を引き出し, サンプル判定一致で承認した評価器のみが流用蓄積に入る (CLAUDE.md §9 強制) |
| **対照実験で効果検証** | reuse vs zerobase で paired_diff (閉じた) または score_diff (開放) を MLflow に記録. 再利用が効くかを定量化 |

Phase 5c/6/7 までで「閉じたタスク」と「ドメイン横展開」と「ポリシー探索エンジン統合」の足場を作った.
Phase 9 では **「ユースケースの形 (閉じた/開放, 入力のモダリティ, ドメイン) を問わずに乗せられる汎用フレーム」** を仕上げる.

### 1.2 想定ユースケース (限定列挙ではない)

形態の幅を明示する目的で例を挙げる. **ここに無いユースケースを排除するためのリストではない**.

| 例 | task_class | output_kind | 入力モダリティ |
| --- | --- | --- | --- |
| NDA / ISO27001 文書レビュー (既存) | detect_and_modify | closed | ドキュメント |
| 仕様書からテストケース起こし | generate | semi_open | ドキュメント |
| 議事録要約 | summarize | semi_open | ドキュメント |
| 障害ログから根本原因推論 | infer | open | テキスト (構造化ログ) |
| 広報原稿の作成 | generate | open | **自然言語のみ** (例:「ビーガン向けプロテインバーの 9 月発売を訴求」) |
| 販促キャンペーン案 | compose | open | **自然言語のみ** (例:「9 月決算月の販促を考えたい」) |
| 個人の悩み相談からの整理 | extract + summarize | semi_open | **自然言語のみ** |
| データ分析結果の解釈付け | transform | semi_open | 構造化データ (CSV/JSON) + 自然言語 |

「ドキュメント入力」「自然言語のみ」「構造化データ」「混在」のいずれも同じスタックで扱う.

### 1.3 設計原則 (前提を固めない)

| 原則 | 内容 |
| --- | --- |
| **ユースケース非依存** | 特定の業種・タスクを前提にしない. tsumiki は「評価器を組む手順」を提供する. 個別の評価軸はドメイン知識として `schemas/eval_dimensions/<domain>/` に蓄積 |
| **入力モダリティ非依存** | ドキュメント, 自然言語のみ, 構造化データ, 混在のいずれも `input_roles` で表現. parser は「ドキュメントを期待する」前提を持たない |
| **タスク形態非依存** | 「閉じた / 開放」「検出 / 生成 / 要約 / 推論」を `TaskClass` + `output_kind` の直交軸で表現. dispatcher が機械的に分岐 |
| **評価器型非依存** | 決定論的 / LLM judge 単一 / 複数批評パネル / ペアワイズ / 人手較正混合のいずれも同じ `EvaluatorSpec` 形式で扱える |
| **プロバイダ非依存** | Phase 7d の方針 (ChatFn DI) を踏襲. 対話 LLM もユーザー選択可能 |
| **対話の有無は任意** | 既存 lookup (ワンショット) を壊さず, 対話パスは fallback として追加. CI 用に対話履歴復元モードを併設 |
| **試走ターゲットは別決定** | フレーム動作確認用の examples ターゲットは Phase 9f 着手時に協議. 設計書で決め打ちしない. 「入力にドキュメントを伴うケース」と「自然言語のみのケース」を少なくとも各 1 件は試走対象に含めることだけ事前に確定 |

## 2. ゴール

### 2.1 In scope (汎用フレームとして)

1. `TaskClass` 拡張 (汎用 dispatcher 化)
2. 対話 REPL (`goal/dialog.py`) — ドメイン非依存の対話プロトコル
3. 対話ベース評価器生成 (`eval/core/dialog_generator.py`) — 評価軸タイプの汎用化
4. サンプル提示 + 判定一致確認の対話ループ
5. 閉じた + 開放を統一する `runner/e2e.py` 拡張
6. **汎用フレームの試走サンプル example** (ターゲットドメインは Phase 9f で協議)
7. 結果報告書 + Zenn 統合記事最終版

### 2.2 Out of scope (Phase 10+ 持ち越し)

- 評価器の継続的較正 (Active Learning, A/B test 連携)
- 開放タスク用の本物 benchmark_fn (AgentSquare 探索) → β 制約のまま
- マルチユーザー / マルチセッション対話
- ドメイン特化の評価軸テンプレ整備 (Phase 9f で 1 ドメイン分の参照実装のみ用意, 他は Phase 10+)

## 3. 設計 (汎用フレーム部)

### 3.1 TaskClass + output_kind + InputModality 直交軸 (Phase 9a)

`TaskClass` は単に「動詞」を表すラベルとし, タスクの形態は **3 つの直交軸** で表現する.

```python
# src/tsumiki/goal/specs.py
TaskClass = Literal[
    # 既存 (Phase 5c/6 で対応)
    "detect", "modify", "detect_and_modify", "extract", "compare",
    # Phase 9 で追加
    "generate", "compose", "summarize", "transform", "infer",
]

OutputKind = Literal["closed", "semi_open", "open"]
# closed:    決定論的に正解が決まる (検出, 抽出, 単純な修正)
# semi_open: 部分的に正解が決まる (要約, 一部のテンプレ生成)
# open:      正解の自由度が高い (広報原稿, 創作, オープン推論)

InputModality = Literal["doc", "free_text", "structured", "mixed", "none"]
# doc:        ドキュメント (テキスト本体が長文ファイル)
# free_text:  自然言語のフリーテキスト (短文〜中文の意図表現)
# structured: 構造化データ (CSV/JSON/YAML 等)
# mixed:      上記の混在
# none:       入力なし (目的だけから生成. 例:「9月販促キャンペーン案を考えたい」)
```

`TaskSpec` に `output_kind: OutputKind` と `input_modality: InputModality` を追加.
dispatcher は `(task_class, output_kind)` の組合せで分岐:

- `output_kind="closed"` → 既存 lookup → generator (ワンショット) → seed パス
- `output_kind in ("semi_open", "open")` → 既存 lookup → **対話パス** (新規) → seed パス

`input_modality` は parser とサンプル合成器の挙動を切り替えるための情報:

- `doc` → 入力ドキュメント本体を `target_document` として TaskSpec の inputs に含める (既存 NDA/ISO27001 と同形)
- `free_text` → 自然言語の意図文を `intent_text` として持つ. 例:「ビーガン向けプロテインバーの 9 月発売を訴求」
- `structured` → 構造化データを `input_record` として持つ
- `mixed` → 複数 input_role を持つ. 例:`(doc=ガイドライン, free_text=意図)`
- `none` → 入力なし. 目的 (raw_goal) だけから生成

既存 NDA/ISO27001 は `output_kind="closed"`, `input_modality="doc"` 扱いで既存挙動を維持. リグレッションなし.

#### 例: 入力モダリティ別の TaskSpec

```python
# 広報原稿 (free_text のみ, ドキュメントなし)
TaskSpec(
    task_class="generate",
    output_kind="open",
    input_modality="free_text",
    domain="marketing_post",
    input_roles=(InputRole("intent_text", str),),
    outputs=(OutputSchema("post_text", str),),
    raw_goal="ビーガン向けプロテインバーの 9 月発売をインスタで訴求したい",
    knowledge=KnowledgeSource(catalog_path="knowledge/skills/marketing_post"),
)

# 議事録要約 (doc + free_text の混在)
TaskSpec(
    task_class="summarize",
    output_kind="semi_open",
    input_modality="mixed",
    domain="meeting_minutes",
    input_roles=(InputRole("transcript", str), InputRole("focus_hint", str)),
    outputs=(OutputSchema("summary", str), OutputSchema("action_items", list)),
    raw_goal="議事録から決定事項とアクションアイテムを抽出して 500 字で要約",
    knowledge=KnowledgeSource(catalog_path="knowledge/skills/meeting_minutes"),
)

# 障害推論 (structured: ログ)
TaskSpec(
    task_class="infer",
    output_kind="open",
    input_modality="structured",
    domain="incident_log",
    input_roles=(InputRole("log_records", list),),
    outputs=(OutputSchema("root_cause", str), OutputSchema("evidence", list)),
    raw_goal="ログから障害の根本原因を推定したい",
    knowledge=KnowledgeSource(catalog_path="knowledge/skills/incident_log"),
)
```

### 3.2 対話プロトコル (Phase 9b) — ドメイン非依存

`src/tsumiki/goal/dialog.py` で REPL を実装. ステージは以下:

| stage | 内容 | ドメイン依存性 |
| --- | --- | --- |
| 1. 目的受領 | 自然言語目的を受領 → TaskSpec 試案提示 → ユーザー確認 | 非依存 (parser がドメインから推測) |
| 2. 評価軸の引き出し | `schemas/eval_dimensions/<domain>.yaml` から候補軸を提示 → ユーザー選択 | テンプレはドメイン依存だが loader は非依存 |
| 3. 評価器コード案提示 | 軸選択 → EvaluatorSpec ドラフト生成 → ユーザー確認 | 非依存 |
| 4. サンプル判定一致確認 | 典型例 A/B 提示 → ユーザー判定 → 判定差分記録 | 非依存 |
| 5. judge プロンプト調整 | 判定不一致時に修正案 → 再 stage 4 | 非依存 |
| 6. 承認 | approved_by 設定 → 流用蓄積に保存 | 非依存 |

すべて `(input_signature, eval_dimensions, task_class, output_kind)` を抽象化して扱うので,
**広報原稿でも議事録要約でも障害推論でも同じ REPL が動く**.

対話ログは `goal/dialog_logs/<run_id>.jsonl` に保存 (再現性, CLAUDE.md §4).
CI モード `--from-dialog-log <path>` で対話を replay 可能.

### 3.3 評価器対話生成 (Phase 9c)

`src/tsumiki/eval/core/dialog_generator.py` を新設.

#### 評価軸タイプの汎用化

`EvaluatorType` を以下のように拡張:

```python
EvaluatorType = Literal[
    "deterministic",       # 既存. Python コードで判定
    "llm_judge",           # 既存. 単一 LLM judge (信頼性低)
    "llm_judge_panel",     # 新規. 複数モデル多数決
    "llm_judge_pairwise",  # 新規. A vs B のペアワイズ
    "hybrid",              # 既存. 複数軸の重み付き合算
]
```

#### 軸テンプレの配置

`src/tsumiki/knowledge/schemas/eval_dimensions/` にドメイン別 YAML を配備. **コアフレームは loader のみ持ち, テンプレ自体はドメイン知識として扱う** (Phase 9f で 1 ドメイン分の参照実装を作る).

```
src/tsumiki/knowledge/schemas/eval_dimensions/
├── _common/                          # ドメイン非依存の汎用軸
│   ├── char_limit.yaml               # 文字数 (decisive)
│   ├── format_validity.yaml          # 形式妥当性 (decisive)
│   └── llm_panel_template.yaml       # 複数 LLM panel の汎用ラッパ
├── nda/                              # 既存ドメイン (Phase 5c で seeded)
├── iso27001/                         # 既存ドメイン (Phase 6 で seeded)
└── <new_domain>/                     # Phase 9f で 1 ドメイン分追加 (ターゲットは協議)
```

loader は `_common/` を常にロードし, 加えて `<domain>/` を merge. ドメインフォルダがない場合でも汎用軸だけで対話が成立する.

#### LLM judge の堅牢化 (CLAUDE.md §9 整合)

| 軸タイプ | 集計方式 | 利用条件 |
| --- | --- | --- |
| `llm_judge` (単一) | スコア直接 | 警告: 報酬ハッキングのリスクあり. `hybrid` の構成要素としてのみ採用 |
| `llm_judge_panel` | 多数決 / 加重平均 | 異なるプロバイダ (Anthropic + Gemini + Azure) で構成. 1 つだけのモデルでは不可 |
| `llm_judge_pairwise` | Bradley-Terry 集計 | サンプル数 ≥ 6 で有意 |
| `hybrid` | 各軸スコアの重み付き合算 | 重みは対話の stage 3 でユーザー指定 |

### 3.4 サンプル提示 (Phase 9d)

stage 4 の「典型例 A / B 提示」は:

1. `task_spec` から strong model でサンプル N 件生成 (デフォルト N=6, 強モデル必須)
2. 各サンプルを評価器ドラフトで判定 → スコア分布を取る
3. 判定境界に近いサンプル 2 件 (合格寄り A, 不合格寄り B) を提示
4. ユーザーの判定との差分を `dialog_logs/<run_id>.jsonl` に記録
5. 不一致があれば次の judge プロンプト修正のヒントとして使う

このループは **ドメインに依存しない** — task_spec と評価器ドラフトさえあれば動く.

### 3.5 統一 runner (Phase 9e) — 閉じた + 開放 + 全入力モダリティを 1 つのコードで

現状の `runner/e2e.py` は「同じドキュメントサンプルへの修正」型 paired 比較.
これを以下の 2 軸で汎化:

| 軸 | 拡張内容 |
| --- | --- |
| 閉じた / 開放 | `output_kind` で paired_diff (閉じた) と score_diff (開放) を切替 |
| 入力モダリティ | `input_modality` で sample 合成戦略を切替. `doc` は既存. `free_text` は「意図文のパラフレーズで N 件展開」. `structured` は「フィールド摂動で N 件展開」. `none` は「目的のバリエーションで N 件展開」 |

```python
@dataclass(frozen=True)
class E2EResult:
    domain: str
    task_class: TaskClass
    output_kind: OutputKind
    # 閉じたタスク (output_kind="closed")
    paired_diff: float | None
    reuse_success_rate: float | None
    zerobase_success_rate: float | None
    # 開放タスク (output_kind in ("semi_open", "open"))
    score_diff: float | None
    reuse_score: float | None
    zerobase_score: float | None
    reuse_samples: tuple[GeneratedSample, ...] | None
    zerobase_samples: tuple[GeneratedSample, ...] | None
    # 共通
    evaluator_id: str
    reused_existing: bool
    compose_selected_modules: dict[str, str] | None
    compose_search_score: float | None
    mlflow_run_ids: tuple[str, str]
```

dispatcher は `output_kind` を見て paired_diff / score_diff のどちらを記録するか決める.
gate 判定は両方とも ±0.05 ルールで揃える.

### 3.6 試走 example の枠組み (Phase 9f) — 入力モダリティを問わない

**ターゲットドメインは Phase 9f 着手時に協議で決定**. ここでは枠組みだけ.

入力モダリティ別に inputs/ の中身が変わるので, ディレクトリ構成は柔軟にする:

```
examples/<target_domain>/
├── README.md
├── goal.yaml                      # 自然言語目的 + TaskSpec 期待値 (input_modality を含む)
├── knowledge/                     # symlink → src/tsumiki/knowledge/skills/<domain>/
├── inputs/                        # 入力サンプル. モダリティ別:
│   ├── docs/                      #   input_modality="doc" のときの参照ドキュメント
│   ├── intents.yaml               #   input_modality="free_text" のときの意図サンプル集
│   ├── records.jsonl              #   input_modality="structured" のときの構造化入力
│   └── (none の場合は inputs/ 自体が空 or 不在)
├── dialog_seed.yaml               # 対話履歴 seed (CI 用)
└── run.sh                         # --dialog (対話) / --from-dialog-log (CI) 両対応
```

選定基準 (Phase 9f で協議):
- (a) 権利問題が軽い (合成データで賄えるか, 公開資料で済むか)
- (b) 対照実験で有意差が出やすそうな尺度がある (zerobase との分離が見える)
- (c) 他ドメインへの応用が見えやすい (汎用 `_common/` 評価軸が再利用できる)
- (d) **入力モダリティの多様性**: 設計原則 1.3 に従い, **「ドキュメント入力」と「自然言語のみ」を少なくとも各 1 件は試走対象に含める**

ターゲット候補 (限定列挙ではない):

| 候補 | task_class | output_kind | input_modality |
| --- | --- | --- | --- |
| 議事録要約 | summarize | semi_open | doc または mixed |
| 仕様書からテストケース生成 | generate | semi_open | doc |
| ログから障害根本原因推論 | infer | open | structured |
| 広報原稿の作成 | generate | open | **free_text** (ドキュメント無し) |
| 販促キャンペーン案 | compose | open | **free_text** (ドキュメント無し) |
| 個人の悩み相談からの整理 | extract + summarize | semi_open | **free_text** |

最終選定はユーザー協議で決める. **設計書側は「どの組合せが来ても乗る」ことを保証する**.

### 3.7 結果報告書 + 統合 Zenn 記事 (Phase 9g)

- `docs/experiments/phase9_execution_<date>.md`: Phase 9 試走結果
- `docs/experiments/phase8_zenn_final.md`: Phase 5c + 6 + 7 + 9 を 1 本に統合した最終版
  - 既存 §1.1 アーキテクチャ図に「対話層」追加 (Mermaid 更新)
  - §2.1 検証する対象に Phase 9 追加 (閉じた + 開放の N+M 構造)
  - 新セクション §6 (Phase 9) を追加
  - §7 主要結果サマリに開放タスクの score_diff を追加
  - §8 結論を再構成 — 「閉じた仮説」と「開放への汎用化」両方の到達点を書く

## 4. 検証 (合格条件 — 事前固定)

### 4.1 全体ゲート

| 指標 | 合格条件 |
| --- | --- |
| 既存 test (NDA / ISO27001, 閉じた 5 種類) | 290/290 PASS 維持 (リグレッションなし) |
| 新規 test | TaskClass + output_kind / dialog REPL / dialog_generator / 統一 runner で各 5 件以上 |
| 試走 (Phase 9f で選んだ 1〜2 ドメイン, Azure 強モデル, seed=42) | `score_diff > 0` (reuse > zerobase), 対話で承認された評価器の verify gate 通過 |
| CI 再現 | `--from-dialog-log <path>` で同一スコア再現 (誤差 ±0.01) |

### 4.2 サブフェーズゲート

| サブ | ゲート |
| --- | --- |
| 9a | 既存 5 種類の lookup hit 維持 + `output_kind` 推論が NDA/ISO27001 で "closed" を返す |
| 9b | 対話 REPL の 6 stage を mock LLM + scripted input で完走 |
| 9c | 評価軸 4 種類 (deterministic / llm_judge_panel / llm_judge_pairwise / hybrid) のスコア計算が正しい |
| 9d | 判定不一致時に judge プロンプト修正案を生成 |
| 9e | E2EResult が両モードで MLflow に正しく記録される |
| 9f | examples/<target>/run.sh --from-dialog-log が CI で決定論的に走る |
| 9g | 統合記事の Mermaid 図が Zenn で render する |

## 5. リスクと緩和

| リスク | 緩和策 |
| --- | --- |
| 対話が長すぎてユーザー離脱 | 各 stage の質問は最小限. デフォルト承認できる pre-set テンプレ提示 |
| LLM judge の偏り | 複数プロバイダ panel + ペアワイズの組合せ必須. 単一 judge は `hybrid` の構成要素として limit |
| 開放タスクで paired_diff が意味を失う | dispatcher で `output_kind` 判定 → 集計指標 (score_diff) に切替 |
| Azure 課金増 | サンプル提示は強モデル必須だが N=6 で抑制. CI モードは API call 不要 |
| 試走ドメインの権利問題 | Phase 9f 着手時に出典・ライセンスを確認した上で選定 |
| ドメイン拡張のたびに dialog_logs が肥大 | 圧縮 + 古いログの ttl 設定 (Phase 10+ 検討) |

## 6. 段取りと工数

| サブ | 内容 | 工数 |
| --- | --- | --- |
| 9-1 (本書) | 設計文書 (汎用フレーム原則を確定) | 完了 |
| 9a | TaskClass + output_kind 拡張 + dispatcher | 0.5 日 |
| 9b | goal/dialog.py 対話 REPL (ドメイン非依存) + `_common/` 評価軸テンプレ | 2 日 |
| 9c | eval/core/dialog_generator.py + llm_judge_panel/pairwise 実装 | 2〜3 日 |
| 9d | sample 提示 + 判定一致確認の対話ループ | 1 日 |
| 9e | runner/e2e.py 統一拡張 (閉じた + 開放) | 1〜2 日 |
| 9f | 試走 example 整備 (ターゲット協議 + 実装 + 試走) | 2 日 |
| 9g | 結果報告書 + 統合 Zenn 記事最終版 | 1 日 |

合計 約 2 週間.

## 7. オープン質問 (実装着手前に確定)

| 質問 | 暫定 | 確定方法 |
| --- | --- | --- |
| Q1: Phase 9f の試走ターゲットドメインは? | 未定 (議事録要約 / テストケース生成 / 障害推論 / 広報原稿 etc) | Phase 9f 着手時にユーザー協議 |
| Q2: 対話の永続化フォーマットは JSONL でよいか? | YES (MLflow 記録と整合) | Phase 9b で確認 |
| Q3: pairwise judge の集計は Bradley-Terry / Elo どちら? | Bradley-Terry (実装容易) | Phase 9c |
| Q4: 人手較正は Phase 9 内で実施するか? | NO (対話の判定一致確認で代用, 真の人手較正は Phase 10+) | 本書で確定 |
| Q5: 対話 LLM のプロバイダは? | デフォルト Azure 強モデル. `--llm-provider` で切替可能 | Phase 9b で実装 |
| Q6: 既存 closed タスクの lookup hit パスは無傷か? | YES | 9a ゲートで確認 |
| Q7: `output_kind` をユーザー対話で確認するか, 機械推論のみか? | parser が推論 + 対話 stage 1 でユーザー確認 | 本書で確定 |
| Q8: 評価軸テンプレの命名規則は? | `<domain>/<dimension_id>.yaml` (id は決定論的) | Phase 9c で確定 |

## 8. 関連

- 計画書: [agent_reuse_verification_plan.md](../agent_reuse_verification_plan.md)
- Phase 5c 設計: [phase5c_design.md](./phase5c_design.md)
- Phase 6 設計: [phase6_design.md](./phase6_design.md)
- Phase 7e 設計: [phase7e_design.md](./phase7e_design.md)
- CLAUDE.md §9 やってはいけないこと (評価器 gate + 開放タスク評価ルール)
