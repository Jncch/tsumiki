# コントリビューション方針

tsumiki への変更を歓迎する. 提案前に以下を確認してほしい.

## スコープ

本リポジトリは「タスク実行エージェント自動生成における知識層再利用仮説の最小検証」の
検証フレームである. 以下のスコープ外提案は基本的にマージしない.

- 評価器なしで自動探索を回すパス
- 単発の好スコアで合否判断するロジック
- 汎用エージェント自動生成フレームワークの自作実装 (代わりに AgentSquare partial vendoring を拡張する)
- 業務データ・契約データを `data/` に追加する PR (出典・ライセンス未明示)

スコープ詳細は [`docs/agent_reuse_verification_plan.md`](docs/agent_reuse_verification_plan.md) と
[`CLAUDE.md`](CLAUDE.md) §9 を参照.

## 開発フロー

```bash
# 依存同期 (uv.lock 駆動, アドホックな pip install は不可)
uv sync --frozen

# 変更後の確認 4 点セット
uv run pytest                       # 290+ 件, 全 PASS を維持
uv run ruff check
uv run ruff format
uv run pyright                      # 暫定 (型エラーゼロを目指す)
```

`uv add <package>` で依存追加すると `uv.lock` が更新される. 必ずコミット対象に含める.

## 再現性ルール (最優先)

[`CLAUDE.md`](CLAUDE.md) §4 と同一だが要点:

- test 分割は層化して固定. 一度確定したら変更しない.
- LLM 呼び出しは temperature=0, モデルバージョン固定. seed=42 を既定とする.
- 全試行 (構成, プロンプト, スコア, コスト, レイテンシ) を MLflow に記録.
- 合格スコアしきい値は実験前に決める. 後出ししない.
- ローカル LLM (ollama 主体) は配管・探索ループ用. 検証の結論はクラウド強モデルで最終確認する.

## コーディング規約

- Python: ruff (フォーマッタ・リンタ), pyright (型, 暫定), pytest (テスト).
- 型注釈を付ける. 識別子は英語, コメント/ドキュメントは日本語可.
- 絵文字・環境依存文字を使わない.
- 大きな変更は小さなコミットに分割. 各コミットで何をなぜ変えたかを書く.

## テスト方針

新規機能 / リファクタリングには test を添える. 最低限:

- `tests/test_<feature>.py` 形式で配置.
- 既存 test を壊さない (`uv run pytest` で 290+ 件 PASS 維持).
- LLM 呼び出しを伴う test は ChatFn DI を使い, fake / stub で済ませる.
  ライブ LLM 依存 test は `@pytest.mark.live` 等で分離.

## PR ガイドライン

- 1 PR = 1 論点. 関連しない変更を混ぜない.
- PR 説明に **何を / なぜ / どう検証したか** を書く. CLAUDE.md §11 に倣い結論先出し.
- 既存 Phase の paired_diff 数値 (NDA +0.261, ISO27001 +0.029) を変える PR は
  対照実験スクリプトと MLflow run id を添える.
- 大きな依存追加 (新規 LLM SDK, fork した上流など) は事前に issue で相談.

## AgentSquare vendoring 取り扱い

`src/tsumiki/policy/agentsquare/` は AgentSquare (Apache-2.0) からの partial vendoring.
詳細は [`docs/agentsquare_vendoring.md`](docs/agentsquare_vendoring.md) を参照.

- 上流変更を取り込む場合は SHA を `docs/agentsquare_vendoring.md` に記録.
- LLM 呼び出しは ChatFn / JsonChatFn DI を必ず経由する. 直接 `openai.ChatCompletion` を呼ばない.
- benchmark / 評価器も同様に `benchmark_fn` DI を経由する.
- alfworld 固有のコード (archives, prompts) は段階的に domain 非依存化する. 急いで丸ごと書き換えない.
- ruff per-file-ignores E501 は vendoring 由来の長行プロンプト用. 新規コードには使わない.

## ライセンス

- 本リポジトリ: Apache License 2.0 ([`LICENSE`](LICENSE)).
- 既存コードへの変更は同ライセンスで取り込む.
- 外部由来コードを取り込む場合はライセンス互換性を確認し, [`NOTICE`](NOTICE) と
  [`THIRD_PARTY_LICENSES/`](THIRD_PARTY_LICENSES/) を更新する.

## コミュニケーション

- 不明点は issue で先に相談する.
- 結論と要点を先に述べる. 詳細は後.
- 表現の好みでの書き換え (リファクタリング目的以外) は受け付けない.

不明な点があれば気軽に質問してほしい.
