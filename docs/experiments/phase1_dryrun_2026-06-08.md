# Phase 1 軽量試走 結果（2026-06-08）

NDA（秘密保持契約）における NG 条項検出を題材に、再利用可能な部品（知識層 = NG パターン辞書、評価層 = NG Recall）を組み立て、ベースラインを 1 本通すまでの最小実証。

## 1. 何をしたか

| 項目 | 内容 |
| --- | --- |
| ドメイン | 業務文書・法務（日本契約） |
| 契約類型 | NDA（秘密保持契約） |
| T1 | NG 条項検出（多ラベル分類） |
| T2（保留） | NG 条項修正（同じ NG パターン辞書を再利用予定） |
| 目的 | 評価器と単一プロンプトのベースラインを 1 本通すこと |
| 主指標 | NG Recall（補助に F2、precision） |

評価器・データ・モデルを最小規模で組み、合成データ生成 → 層化分割 → ベースライン予測 → 評価 → MLflow 記録までを 1 コマンドで回した。

## 2. 環境

| 項目 | 値 |
| --- | --- |
| OS | macOS（Apple M4） |
| Python | 3.13.13（uv 管理） |
| パッケージ管理 | uv 0.11.19 |
| LLM ランタイム | ollama-app 0.30.6（Homebrew cask、Metal 加速） |
| 実験管理 | MLflow 2.22 |
| コンテナ | colima + Docker 28.4（疎通は確認、本試走はホスト直叩き） |

ollama のモデル保存先は `OLLAMA_MODELS=./var/ollama/models` でプロジェクト内固定。アンインストール時の footprint をリポジトリ内に閉じ込める意図。

## 3. モデル選定

業務文書・法務（日本語）ドメインなので、**日本語が実用的に扱えるモデル**から選定。

| 用途 | モデル（ollama タグ） | サイズ |
| --- | --- | --- |
| 主力 | `hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M` | 9.0 GB |
| 速度優先（試走） | `hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M` | 4.7 GB |
| 日本語自然さ対照 | `hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF:latest` | 4.9 GB |

Llama 3.2 3B は **日本語が公式サポート外**（英・独・仏・伊・葡・印・西・泰の 8 言語のみ）で除外。

簡易日本語サニティチェック（典型的な NDA 条項の品質指摘）の結果:

| モデル | 速度 | 指摘の質 |
| --- | --- | --- |
| qwen2.5-14b | 4.3 tok/s | 簡潔・的を絞った指摘 |
| qwen2.5-7b | 11.7 tok/s | 簡潔だが指摘内容が浅い |
| elyza-jp-8b | 11.4 tok/s | 日本語生成は流暢だが**指摘内容に誤り** |

主力は qwen2.5 14B に決定。本記事の軽量試走は速度優先で qwen2.5 7B。

## 4. データ

公開雛形の中小企業庁 NDA ひな形（Word）を 1 本使用。

| 項目 | 値 |
| --- | --- |
| 出典 | [中小企業庁 知的財産取引ガイドライン 秘密保持契約書ひな形](https://www.chusho.meti.go.jp/keiei/torihiki/chizai_guideline.html) |
| ライセンス | 政府標準利用規約 (PSI) version 2.0 相当（CC BY 4.0 互換） |
| 形式 | `.docx`（3,621 文字） |
| 抽出された CleanClause | 14 件（条単位） |

合成データを `LLM で雛形条項に NG パターンを注入する` 方式で生成。Phase 1 の合成データは 18 件（9 パターン × 2 件）+ クリーン 10 件 = 28 件。

## 5. NG パターン辞書（知識層）

NDA で典型的に問題になる 9 パターンを起草。各パターンに id、severity、出典、例文（excerpt_examples）を持たせ、`src/tsumiki/knowledge/nda/ng_patterns.yaml` に格納（コミット対象、SemVer 管理）。

| id | 名称 | severity |
| --- | --- | --- |
| nda_scope_overbroad | 秘密情報の範囲過大 | high |
| nda_duration_unbounded | 秘密保持期間の無期限・過長 | high |
| nda_purpose_undefined | 利用目的の不明確 | medium |
| nda_disclosure_exception_missing | 法令・規制当局等への開示例外不在 | high |
| nda_remedy_imbalanced | 損害賠償・違約金の不均衡 | high |
| nda_jurisdiction_one_sided | 準拠法・管轄の欠落または一方的指定 | medium |
| nda_return_destroy_missing | 返還・廃棄義務の不在または確認手段なし | medium |
| nda_derivative_undefined | 派生情報・成果物の取扱い未定義 | medium |
| nda_survival_missing | 存続条項の欠落 | low |

辞書は **タスク非依存** に書く（T1 でも T2 でも同じ辞書を使う）。これがプロジェクトの再利用仮説の核。

## 6. 実装の核

### 6.1 評価器（多ラベル NG Recall）

`src/tsumiki/eval/metrics.py`。

- per-pattern: TP / FP / FN / Recall / Precision / F-beta(β=2)
- macro 平均は **test 集合に出現したパターン (support>0)** のみで取る（出現しないパターンを 0 で混ぜると見かけのスコアが不当に下がる）
- weighted 平均は support による重み付き

### 6.2 層化 train/val/test 分割

`src/tsumiki/eval/split.py`。多ラベル分類の厳密な層化（iterative stratification）は重いので、各サンプルを **最重大の NG パターン** を strata キーにする実用的代替を採用。同 severity ならパターン id の辞書順で安定的に決める。

### 6.3 合成データ生成

`src/tsumiki/data/synthesis.py`。`ChatFn` プロトコル経由で LLM 抽象を隔離し、テストは決定論的なモック関数で完結。実 LLM 呼び出しは試走時のみ。

`sample_id` は入力ハッシュから決定論的に作る（同じ入力で同じ ID）。

### 6.4 ベースライン NG 検出器

`src/tsumiki/baseline/ng_detector.py`。単一プロンプト一発で多ラベル NG 検出を実行。応答は改行区切りで NG パターン id を返させ、定義済み id 以外は捨てる（ハルシ対策）。

### 6.5 統合 Runner

`src/tsumiki/runner/phase1.py`。`run_phase1()` で `合成 → 層化分割 → ベースライン予測 → 評価 → MLflow 記録` を 1 コール。`val/test` をそれぞれ別 prefix で記録。

## 7. 結果

軽量試走の結果（qwen2.5 7B、n_synth_per_pattern=2、n_clean=10、seed=42）:

| 指標 | TEST |
| --- | --- |
| total_support | 9 |
| macro_recall | **0.667** |
| macro_precision | 0.537 |
| macro_F2 | 0.616 |
| 試走時間 | 237.6 秒 |

per-pattern（TEST、各 support=1 の小規模）:

| パターン | 結果 |
| --- | --- |
| nda_scope_overbroad | ✓ 検出（FP 2） |
| nda_duration_unbounded | ✓ 検出（FP 1） |
| nda_purpose_undefined | ✓ 検出 |
| nda_remedy_imbalanced | ✓ 検出 |
| nda_jurisdiction_one_sided | ✓ 検出 |
| nda_derivative_undefined | ✓ 検出 |
| nda_disclosure_exception_missing | ✗ 見逃し |
| nda_return_destroy_missing | ✗ 見逃し |
| nda_survival_missing | ✗ 見逃し |

## 8. 観察

| 観察 | 含意 |
| --- | --- |
| 9 パターン中 6 件を qwen 7B で検出 | ベースラインとして機能している |
| 見逃した 3 件は「欠落の検出」系（開示例外、返還義務、存続条項） | 「条文に書かれていないこと」を読み取る難しさ。本質的に難しい論点 |
| Precision が低め（0.537）、FP あり | プロンプト精度向上余地。"否定的サイン" の混入禁止指示が必要 |
| VAL の support=0（規模小） | n_synth_per_pattern を上げると改善。本走時は 5〜10 が妥当 |
| macro/weighted の挙動差なし（support=1 ずつ） | 信頼区間を測るには複数 seed が必要 |

## 9. 試行錯誤（実装で詰まった点）

「ollama でモデルが pull できれば 30 分」と思って始めたが、実際は **モデル取得に 6 時間以上を費やした**。これは記録に値する。

### 9.1 `ollama pull` の不安定さ

最初は `qwen2.5:14b-instruct-q4_K_M` を `ollama.com` 経由で取得しようとしたが、16 並列 chunk download が `stalled; retrying` を多発させ、進捗が前後する。3 時間で 0% から 35% まで進んだ後、35% → 1% へロールバック、という挙動を再現。

「ELYZA-JP 8B（hf.co 経由）」だけはスムーズに完了したことで、`ollama.com` の CDN 側に問題があると推測。

### 9.2 `Qwen/*-GGUF` 公式は sharded

`hf.co/Qwen/Qwen2.5-7B-Instruct-GGUF:Q4_K_M` に切り替えたら ollama 側がエラー:

```
Error: pull model manifest: 400: The specified tag is a sharded GGUF.
Ollama does not support this yet.
```

Qwen 公式は複数ファイルに分割された GGUF。ollama は単一ファイル GGUF しか受けない。

### 9.3 `bartowski/*-GGUF` で単一ファイル化

`hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M`（単一ファイル）に再切替。これで取得自体は始まるが、依然として `stalled; retrying` バーストが発生。30 分で 0% → 31% → 14% へロールバック、を繰り返す。

### 9.4 `curl` 直接 DL → `ollama create`

ollama の 16 並列 chunked download を回避するため、`curl` 1 接続での直接 DL に切替:

```bash
curl -L --continue-at - \
  --retry 30 --retry-delay 10 --retry-all-errors \
  --speed-limit 50000 --speed-time 60 \
  -o var/downloads/Qwen2.5-7B-Instruct-Q4_K_M.gguf \
  https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q4_K_M.gguf
```

`--speed-limit 50000 --speed-time 60` で「60 秒間 50KB/s 未満なら stall とみなし再接続」を仕込む。途中 `Recv failure: Operation timed out` も出たが、resume が効いた。

ただし最終的にはブラウザ直接 DL が一番速かった。

### 9.5 `ollama create` で登録

DL した GGUF を ollama に登録:

```
FROM /abs/path/to/Qwen2.5-7B-Instruct-Q4_K_M.gguf
```

```bash
ollama create 'hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M' -f Modelfile
```

タグ名はコード（smoke スクリプト・`.env.example`）と完全一致させる。

### 9.6 Homebrew `ollama` Formula は Metal 無効

最初に `brew install ollama` で入れたが、起動ログに:

```
failure during llama-server GPU discovery
inference compute: cpu, total 16.0 GiB
```

Homebrew Formula 版は `llama-server` バイナリを同梱しておらず、CPU only にフォールバックしていた。**`brew install --cask ollama-app`** (アプリケーション版) に切替で Metal 加速が有効化（`Apple M4, 11.8 GiB VRAM` を認識）。

### 9.7 `ollama` には prune が無い

失敗した `ollama pull` は部分 blob を `var/ollama/models/blobs/` に残し、自動で消えない。`ollama prune` 等のコマンドは存在しない。マニフェストから参照されている blob と、残骸の `-partial*` blob を自前で diff して削除し、29.83 GiB 回収。

## 10. 結論と次のステップ

- 評価器・知識辞書・合成パイプライン・ベースライン検出器・MLflow 記録までを `run_phase1()` 1 コールに集約。実 LLM 込みで end-to-end 動作確認済。
- 9 パターン中 6 検出は **ベースラインとしては妥当**。Phase 1 本走では n_synth を上げ、qwen 14B で同条件を再走して数字を確定する。
- 9.x で記録した取得周りの落とし穴は CLAUDE.md にも反映済（次セッション以降の Claude Code が同じ罠を踏まないように）。

| 次の調整 | 内容 |
| --- | --- |
| 規模拡大 | n_synth_per_pattern を 5〜10 に上げ、各 NG パターンに support>=3 を確保 |
| 主力モデルでの本走 | qwen 14B で同条件を回し、ベース性能の上限を測る |
| プロンプト工夫 | 「欠落の検出」系の負例ヒントをプロンプトに足す |
| 信頼区間 | 複数 seed の繰り返しで CI を出す |
| Phase 2 設計 | 同じ NG パターン辞書を T2（NG 条項修正）の評価器に流用、再利用率を測る |

## 11. 再現手順

```bash
# 1) ホスト ollama 起動（OLLAMA_MODELS をプロジェクト内に固定して serve）
bash scripts/start_ollama.sh

# 2) モデル取得（pull が止まる場合は HF から直接 DL → ollama create を推奨）

# 3) NDA 雛形を保存
#    https://www.chusho.meti.go.jp/keiei/torihiki/chizai_guideline/guideline02.docx
#    → data/raw/nda/chusho_chizai_guideline/guideline02.docx

# 4) CleanClause を生成
uv run python experiments/build_clean_clauses.py

# 5) Phase 1 試走
uv run python experiments/run_phase1_dryrun.py

# 6) MLflow UI で結果閲覧
mlflow ui --backend-store-uri file:./mlruns
```

## 12. 関連リンク

- リポジトリ全体方針: [`docs/agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md)
- Claude Code 運用ルール: [`CLAUDE.md`](../../CLAUDE.md)
- NG パターン辞書: [`src/tsumiki/knowledge/nda/ng_patterns.yaml`](../../src/tsumiki/knowledge/nda/ng_patterns.yaml)
- 出典カタログ: [`src/tsumiki/data/sources/nda_templates.yaml`](../../src/tsumiki/data/sources/nda_templates.yaml)
- 試走スクリプト: [`experiments/run_phase1_dryrun.py`](../../experiments/run_phase1_dryrun.py)
