# CLAUDE.md

このファイルは Claude Code がこのリポジトリで作業する際の指針である。
検証の詳細な方針・計画は `docs/agent_reuse_verification_plan.md` を参照すること。本ファイルは運用ルールに絞る。
「暫定（要確認）」と記した項目は未確定であり、確定後に更新する。

---

## 1. プロジェクト概要

- プロジェクト名: tsumiki（積み木）。再利用可能な部品を合成してタスクごとのエージェントを構築する、という中核を表す。
- 目的: タスク実行エージェント自動生成における「知識層再利用」仮説の最小検証。
- 中核仮説: 再利用が成立するのは知識層とツール層のみ。最適化済みポリシー層はタスクごとに再構築かつ再評価する。
- 検証の正味の価値: 既知の原理を未検証の縦ドメインで確認し、工数削減効果と負の転移の有無を実測する。
- テーゼの立ち位置: 「自然言語 ＋ 評価駆動の生成 ＋ ドメイン資産の再利用」に賭ける。評価なしで理想が出る汎用生成（壮大版）には賭けない。下層（AFlow / AgentSquare）はコンパイル先・ランタイムとして扱い再発明しない。
- 詳細は `docs/agent_reuse_verification_plan.md`。

---

## 2. 環境

| 項目 | 内容 |
| --- | --- |
| 開発OS | macOS |
| コンテナ | colima 上の Docker。検証はコンテナ内で実行する |
| バックエンド言語 | Python |
| Python パッケージ・環境管理 | uv（確定）。pyproject.toml と uv.lock をコミットする |
| Python バージョン | 3.13 系で固定（`requires-python = "==3.13.*"`）。3.14 系は pyarrow 等の科学計算 wheel が未配布のためフォールバック |
| 依存の配置 | コンテナ内に直接インストールする（uv.lock 駆動）。ホスト側に環境を作らない |
| 実験管理 | MLflow |
| リポジトリ構成 | 当面 Python のみ（確定）。UI は後で追加する |
| UI | TypeScript + React（着手は後。当面は対象外） |
| LLM プロバイダ | ローカルの ollama を主体とする（確定）。クラウドの強モデルは結論の最終確認用 |

---

## 3. LLM プロバイダの扱い（ローカル主体＋クラウド確認）

- 開発・配管・探索ループ（MCTS / DSPy）はローカルの ollama を使う。コストを抑え反復を速くするため。
- ベースラインの上限確認と検証の最終結論はクラウドの強モデルで行う。弱いローカルモデルでの結論は強モデル運用に外挿できないため。
- 知識・ツール層の再利用仮説はモデル非依存なのでローカル中心で測ってよい。自動生成・探索の品質やマルチ対単体の結論はモデル能力が交絡するため、最終確認はクラウドで行う。
- LLM アクセスはプロバイダ非依存の設定層に隔離する。アプリ本体から特定プロバイダの SDK を直接呼ばない。ollama は OpenAI 互換エンドポイントを提供するため、base_url と環境変数の切替でローカルとクラウドを差し替える。AFlow は config ファイル、DSPy は base_url 差し替えで対応する。
- macOS 固有の注意: ollama はホスト（ネイティブ macOS、Metal 加速）で動かす。colima のコンテナ内では Metal GPU が使えず CPU only になり実用速度が出ない。コンテナ内の Python からは `host.docker.internal:11434` 経由で呼ぶ。
- 現実的なローカルモデルサイズは 7B から 14B 級の量子化が目安。
- ホストの footprint を一箇所に閉じ込めるため、ollama のモデル保存先を OLLAMA_MODELS で本プロジェクト内のパス `./var/ollama/models` に固定する。`.gitignore` で除外しコミットしない。ollama 起動前に `OLLAMA_MODELS` をエクスポートする（起動後の変更は反映されない）。
- ollama のインストールは Homebrew Cask の `brew install --cask ollama-app` を使う。Homebrew Formula の `brew install ollama` は llama-server バイナリを同梱せず Metal が無効化される（CPU only にフォールバック）実績がある（2026-06-08 実測）。

### 3.1.x モデル取得（運用上の確定知見）

- モデルタグは `hf.co/<repo>/<name>:<quant>` 形式で取得する。`ollama.com` の `qwen2.5:*` 等は CDN 経由で 16 並列 chunk download が `stalled; retrying` を多発させ、進捗が前後する実績がある（2026-06-08 複数回再現）。
- `Qwen/Qwen2.5-*-Instruct-GGUF` 等の公式 GGUF は **sharded GGUF**（複数ファイル分割）で ollama 未対応。`bartowski/Qwen2.5-*-Instruct-GGUF` のような単一ファイル版を採用する。
- 大型 GGUF（>5GB）が `ollama pull` で stall を繰り返す場合は、ブラウザまたは `curl --continue-at -` で HF から直接 DL し、`var/downloads/` に保存して以下の Modelfile で登録する:
  ```
  FROM /abs/path/to/Model-Q4_K_M.gguf
  ```
  `ollama create '<tag>' -f Modelfile` で登録する。タグは smoke スクリプトや `.env.example` で参照している `hf.co/...` と完全一致させる。
- `ollama create` 後、`var/downloads/*.gguf` は削除可能（blob は ollama の `var/ollama/models/blobs/` に新規名で再格納される。元名のコピーは孤児になるので別途 prune が必要）。
- `ollama` には公式 prune コマンドが無い。マニフェスト未参照の `sha256-*` および `sha256-*-partial*` blob は自前で削除して構わない（参照は `manifests/.../<tag>` の JSON `config.digest` と `layers[].digest` のみ）。

### 3.1 ローカル LLM の後始末（teardown）

検証終了後にホストをクリーンに戻すための手順。アプリ削除だけではモデル（数 GB から数十 GB）が残る点に注意する。

1. プロセスを停止する（メニューバーから終了、または `pkill ollama`）。起動中にディレクトリ削除をしない。
2. アプリ削除: `rm -rf /Applications/Ollama.app`（Homebrew で入れた場合は `brew uninstall ollama`）。
3. モデル・鍵・キャッシュ削除: 本プロジェクトでは `rm -rf ./var/ollama`（OLLAMA_MODELS で指定したプロジェクト内パス）を削除する。`~/.ollama` に過去のモデルが残っている場合のみそちらも削除する。
4. 補助ファイル: `rm -rf ~/Library/"Application Support"/Ollama`、`~/Library/LaunchAgents` の ollama plist があれば削除する。
5. CLI 残骸確認: `which ollama` が返すパスがあれば削除する。

個別モデルの削除は `ollama rm <model>` を使う。容量が解放されない場合は ollama serve を再起動する。SHA256 名の blob を手で消さない。

---

## 4. 再現性ルール（最優先）

- test 分割は層化して固定し、一度確定したら変更しない。
- LLM 呼び出しは temperature=0、モデルのバージョンを固定する。
- 乱数シードを固定し記録する。
- ローカルモデル使用時は、モデル名・量子化タグ・ollama バージョンも MLflow に記録する。
- すべての試行（構成、プロンプト、スコア、コスト、レイテンシ）を MLflow に記録する。
- 合格スコアのしきい値は実験前に決め、後出ししない。
- 依存は uv.lock で固定し、ロックファイルをコミットする。
- コンテナ内の依存インストールは `uv sync --frozen` で uv.lock に厳密一致させる。アドホックな `pip install` をしない。
- Docker ベースイメージの Python バージョンはタグで固定する（latest を使わない）。
- 勝手なリファクタリングや表現変更をしない。変更時は意図と差分を明示する。

---

## 5. コーディング規約

Python:
- フォーマッタ・リンタ: ruff
- 型チェック: pyright または mypy（暫定）
- テスト: pytest
- 型注釈を付ける。

共通:
- コードと Markdown に絵文字・環境依存文字を使わない。
- コメントとドキュメントは日本語可、識別子は英語。
- 大きな変更は小さなコミットに分割し、各コミットで何をなぜ変えたかを書く。

UI（着手時に有効化。当面は対象外）:
- TypeScript + React。リンタ: eslint、フォーマッタ: prettier、型: tsc を strict で運用、テスト: vitest（いずれも暫定）。

---

## 6. ディレクトリ構成（Python のみ。暫定）

- `pyproject.toml`, `uv.lock` リポジトリ直下
- `src/tsumiki/` パッケージ本体（`knowledge/` 知識資産、`data/` データ層、`eval/` 評価器、`baseline/` ベースライン、`runner/` 実験 Runner、`exp/` MLflow ロガー、`llm/` プロバイダ非依存設定層、`smoke/` サニティ）
- `experiments/` 実験スクリプトと設定（再現可能な ad-hoc CLI）
- `tests/` pytest
- `docs/` 方針・計画。`agent_reuse_verification_plan.md` 本体、`experiments/` 配下に各試走の結果報告
- `data/raw/<dataset>/<source_id>/` 入手元別の生データ。`data/processed/` で加工済み。すべてコミットしない
- `var/ollama/models/` ローカル LLM モデル保存先（`OLLAMA_MODELS`、コミットしない）
- `var/downloads/` 大型 GGUF の curl 直接 DL 用作業ディレクトリ（`ollama create` 後に削除可、コミットしない）
- `Dockerfile`, `compose.yaml` コンテナ定義
- `.env.example` のみ追跡。`.env` はコミットしない

UI 着手時に `ui/` を追加する。

---

## 7. データとシークレットの取り扱い（ガードレール）

- 業務データ・契約データはコミットしない。`data/` を .gitignore に入れる。
- 機密性のあるデータはコンテナ内とローカルに限定する。
- API キー等の秘密情報は .env で管理しコミットしない。追跡するのは `.env.example` のみ。
- 知識資産には鮮度管理（出典、更新日、有効性）を付ける。古い知識の再利用はポリシーが正しくても誤出力を生む。
- ツールの流用は入出力契約が同じ範囲でのみ安全。契約が変われば改修対象とする。

---

## 8. 検証フェーズ（計画からの要約）

| フェーズ | 内容 |
| --- | --- |
| Phase 0 | データ・ラベル監査（粒度、件数、クラス比、付与基準の一貫性） |
| Phase 1 | 評価器と単一プロンプトのベースライン構築 |
| Phase 2 | 再利用の対照実験（ゼロベース vs 知識・ツール層を注入） |
| Phase 3 | 頑健性と負の転移の確認 |

詳細・指標・合格条件は `docs/agent_reuse_verification_plan.md`。

---

## 9. やってはいけないこと

- 固定した test セットを学習・探索に使う、または変更する。
- 評価器が無い状態で自動探索を回す。探索はスカラー評価器を前提とする。
- 生の LLM 判定スカラーへ直接最適化する。報酬ハッキングを招く。開放タスクではペアワイズ・複数批評パネル・多様性指標・人手較正を使う。
- 汎用エージェント自動生成フレームワークをゼロから自作する。AFlow または AgentSquare を fork し差分で進める。
- 最適化済みポリシー層を再評価なしで別タスクへ流用する。
- 合否を単発の好スコアで判断する。頑健性チェックを経る。
- アプリ本体から特定 LLM プロバイダの SDK を直接呼ぶ。設定層を経由する。
- アドホックな `pip install` でコンテナに依存を入れる。uv.lock 駆動でインストールする。
- ollama をコンテナ内（colima）で動かす。Metal が使えず CPU only になる。ホストで動かしコンテナから呼ぶ。
- ローカルモデルだけで検証の結論を確定する。モデル能力が交絡するため、結論はクラウドの強モデルで最終確認する。

---

## 10. 参考 OSS と評価指標

`docs/agent_reuse_verification_plan.md` の参考 OSS および評価指標セクションを参照する。
要点のみ:

- ポリシー層探索エンジン候補: AFlow（fork 前提）。モジュール分離の土台: AgentSquare。
- ポリシー再最適化: DSPy。実験記録: MLflow。
- 主指標: ラベル系タスクは NG Recall を主に、F-beta 等で補助。コストとレイテンシを併記。
- 再利用実験: reuse rate、cross-task success delta、コールドスタート工数、負の転移の有無。

---

## 11. コミュニケーション方針

- 日本語で応答する。
- 結論と整理された要点を先に述べ、その後に詳細を述べる。
- 説明は table 形式を優先する。
- 忖度せず、不合理・非効率・危険な案は否定する。
- わからないことは「わからない」と明言し、曖昧な推測をしない。
- 一貫性と再現性を最優先し、勝手なアレンジや表現変更をしない。

---

## 12. ビルド・実行コマンド（uv ベース。暫定）

ローカル:
- 依存同期: `uv sync --frozen`
- 依存追加: `uv add <package>`（uv.lock を更新しコミット）
- 実行: `uv run python -m <module>`
- テスト: `uv run pytest`
- リンタ・フォーマット: `uv run ruff check` / `uv run ruff format`
- 型チェック: `uv run pyright`（暫定）

コンテナ（colima 上の Docker）:
- 前提: Dockerfile で Python を固定タグにし、pyproject.toml と uv.lock を先に COPY して `uv sync --frozen` で依存をイメージに焼く。
- 起動: `colima start` の後に `docker compose up`。
- 開発時はソースをバインドマウントし、依存変更時のみイメージを再ビルドする。

LLM エンドポイント:
- 既定はホストの ollama（OpenAI 互換）。ホストから直接呼ぶ場合は `http://localhost:11434/v1`、コンテナ内から呼ぶ場合は `http://host.docker.internal:11434/v1`。
- クラウドでの確認時は環境変数で base_url と認証情報を切り替える。

主要モデル（2026-06-08 確定。タグは smoke / `.env.example` と一致）:
- 主力: `hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M`
- 速度優先: `hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF:Q4_K_M`
- 日本語対照: `hf.co/elyza/Llama-3-ELYZA-JP-8B-GGUF:latest`

Phase 1 試走の最小フロー:
1. NDA 雛形（中小企業庁の `guideline02.docx` 等）を `data/raw/nda/chusho_chizai_guideline/` に配置する。
2. `uv run python experiments/build_clean_clauses.py` で `data/processed/nda_clean_clauses.jsonl` を生成する。
3. `uv run python experiments/run_phase1_dryrun.py` で end-to-end（合成→層化分割→ベースライン予測→評価→MLflow 記録）を実行する。
4. 結果は `mlruns/` の `phase1_dryrun` 実験に集約される。`mlflow ui --backend-store-uri file:./mlruns` で閲覧可能。
