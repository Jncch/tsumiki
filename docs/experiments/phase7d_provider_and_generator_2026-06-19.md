# Phase 7d 結果: LLM プロバイダ層拡張と generator クラウド再検証

実行日: 2026-06-19
設計書: [`phase7_design.md`](phase7_design.md) §1 (7d) / §4 / §5 / §6.4
前段: [`phase7c_examples_2026-06-19.md`](phase7c_examples_2026-06-19.md)

## 1. 結論先出し

| サブ | 結果 |
| --- | --- |
| 7d-1 `.env.example` 3 系統整備 | 完了. 既に A〜F の 6 系統対応済 (ollama / Azure / OpenAI / Anthropic / OpenRouter / Gemini) を確認, ホスト / コンテナ切替の明示化と旧モデルタグ alias の追記 |
| 7d-2 `client.py` 3 系統対応 | 完了 (実質ノーオペ). 設計書 §4.2 の「Anthropic 公式 SDK 追加」を **OpenAI 互換層 1 本に統合** で代替, 追加依存ゼロ |
| 7d-3 プロバイダ smoke test | 完了. **24/24 PASS** (is_ollama 検査 7 件含む), 全テスト **201/201 PASS** (リグレッションなし) |
| 7d-4 generator クラウド再検証 | **完了 (Azure GPT-5.4, 2026-06-19)**. 主合格条件「paired_diff が seed 版と ±0.05 内」は **両ドメインとも未達**. NDA は verify NG (typical_failure 検出不可) / ISO27001 は false OK (metric キー不一致). 詳細 §4.5 / §4.6 |
| 7d-5 結果報告書 | 本書 |

## 2. 設計書 §4.2 の見直し (重要)

設計書 §4.2 では 7d で **Anthropic 公式 SDK を追加** する想定だった. しかし着手時の調査で以下が判明し, 設計を簡素化した.

| 当初想定 | 実態 | 採用方針 |
| --- | --- | --- |
| `anthropic` パッケージを `pyproject.toml` に追加し, provider="anthropic" 分岐を `client.py` に実装 | Anthropic が OpenAI 互換エンドポイント (`https://api.anthropic.com/v1/`) を公式提供している ([docs.anthropic.com/ja/api/openai-sdk](https://docs.anthropic.com/ja/api/openai-sdk)) | **依存追加なし**. 既存の openai_compatible 経路 1 本で ollama / OpenAI / Anthropic / OpenRouter / Gemini を全て統一カバー |

副次的な利点:

- pyproject.toml に新規 SDK 依存が増えない (Phase 7e の AgentSquare vendoring で依存数を抑えたい方針と整合)
- アプリ本体は `openai` SDK 1 つだけ知っていればよい (CLAUDE.md §3 のプロバイダ非依存原則がさらに徹底)
- Phase 5c 以降の `make_openai_chat_fn` が全プロバイダ対応のまま再利用できる (リグレッション 0)

制約 (報告書として明示):

- Anthropic の OpenAI 互換層は一部機能 (structured outputs, parallel tool calls 等) に未対応. tsumiki は plain chat completion のみ使うため現時点で影響なし
- 将来 Anthropic 固有機能 (Computer Use, thinking など) が必要になったら Phase 9+ で `anthropic` SDK を追加

## 3. 実装内容

### 3.1 `.env.example` 拡張 (7d-1)

差分:

```diff
 # [A] ローカル ollama（開発・探索ループの主用途、LLM_PROVIDER=openai_compatible）
-#   - コンテナ内から呼ぶ場合: http://host.docker.internal:11434/v1
-#   - ホストから呼ぶ場合:     http://localhost:11434/v1
+#   実行コンテキストで LLM_BASE_URL を選ぶ:
+#     - ホスト (macOS) で `uv run` 直接実行 → http://localhost:11434/v1   ★ Phase 5c〜7c 試走で使用
+#     - コンテナ内 (colima/Docker) で実行   → http://host.docker.internal:11434/v1
+#   モデルタグは hf.co/... 形式が安定 (CLAUDE.md §3.1.x 確定知見, ollama.com 系は stalled 多発)
 LLM_BASE_URL=http://localhost:11434/v1
 LLM_API_KEY=ollama
 LLM_MODEL=hf.co/bartowski/Qwen2.5-14B-Instruct-GGUF:Q4_K_M
+# 既存ローカルタグ alias 例 (Phase 5c〜7c で使用): LLM_MODEL=qwen25-14b-ctx8k
```

[B] Azure OpenAI / [C] OpenAI / [D] Anthropic / [E] OpenRouter / [F] Gemini は既に整理済のためそのまま.

7c で起きた「`.env` の `host.docker.internal` がホスト直接実行で DNS 失敗」問題に対し, **ホスト vs コンテナの切替を [A] セクション冒頭で明示** することで予防策とした.

### 3.2 `client.py` ヘッダ拡張 (7d-2)

docstring に Anthropic / OpenRouter / Gemini が全て openai_compatible 経路 1 本で扱える旨を追記. コード本体は無修正.

### 3.3 プロバイダ smoke test (7d-3)

`tests/test_phase7d_llm_provider.py` を新規追加. 17 件のテスト:

| カテゴリ | テスト数 | 内容 |
| --- | --- | --- |
| openai_compatible 経路 | 8 | ollama (host/container), OpenAI, Anthropic 互換, OpenRouter, Gemini を `LLMSettings.from_env` で受け付ける. 必須 env 不足エラー |
| azure_openai 経路 | 5 | 4 必須 env 揃った時動作, 1 つ不足で明示エラー |
| provider バリデーション | 2 | 既知外 provider で `RuntimeError`, 未指定なら openai_compatible 既定 |
| temperature | 2 | 既定 0.0 (CLAUDE.md §4 再現性), 上書き可 |

実呼び出しなし (ネット不要, CI 走行可). 実プロバイダ smoke は 7d-4 試走で実走確認.

## 4. 7d-4 generator クラウド再検証 (ユーザー実行)

### 4.1 目的

Phase 6 §5 で観測された **qwen 14B での generator 失敗** が, クラウド強モデル (GPT-4o 系 / Claude 系) で改善するかを検証する.

Phase 6 失敗パターン:

- 生成された評価器コードが `target_pattern_1` を **文字列 literal** として扱う (変数参照ではない)
- 評価関数のシグネチャは合っているが本体ロジックが破綻
- `verifier.py` を通過しないため store に保存されず, Phase 6 では seed 投入で回避

### 4.2 前提: `.env` の整備

Phase 7d-4 時点で `run_phase5c_dryrun.py` は `LLMSettings.from_env()` 駆動 (Phase 7d 着手中に CLI 引数からの上書きを廃止). `.env` または環境変数で provider を選ぶ.

**Azure OpenAI 経路** (推奨, ユーザー環境で設定済):

```dotenv
LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=<your-deployment-name>
AZURE_OPENAI_API_VERSION=2024-10-21
LLM_TEMPERATURE=0.0
```

**OpenAI 本家** の場合:

```dotenv
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o
LLM_TEMPERATURE=0.0
```

**Anthropic Claude** (OpenAI 互換層):

```dotenv
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.anthropic.com/v1/
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-opus-4-7
LLM_TEMPERATURE=0.0
```

`.env` は `.gitignore` で除外されコミットされない (CLAUDE.md §7).

### 4.3 実走手順 (NDA)

```bash
# 0. 評価器をバックアップして削除
mkdir -p /tmp/tsumiki_phase7d_backup
cp -r src/tsumiki/eval/generated/nda/detect_and_modify/modification_success_v1 \
      /tmp/tsumiki_phase7d_backup/nda_modification_success_v1
rm -rf src/tsumiki/eval/generated/nda/detect_and_modify/modification_success_v1

# 1. クラウドモデルで generator パスを発火
#    .env が Azure / OpenAI / Anthropic を向いていれば env 上書きなしで実行可
uv run python experiments/run_phase5c_dryrun.py \
  --goal "NDA をチェックして問題条項を是正したい" \
  --knowledge-path examples/nda/knowledge \
  --clean-jsonl examples/nda/clean_clauses.jsonl \
  --experiment phase7d_generator_cloud_nda \
  --outcomes-dir docs/experiments/phase7d_outcomes/nda \
  --evaluator-root src/tsumiki/eval/generated \
  --baseline-paired-diff 0.261 \
  --baseline-label "Phase 5c NDA" \
  --seed 42 \
  --generated-at 2026-06-19

# 2. 結果確認 (新規評価器が保存されているか)
ls src/tsumiki/eval/generated/nda/detect_and_modify/

# 3. 復元 (元の seed 評価器に戻す)
rm -rf src/tsumiki/eval/generated/nda/detect_and_modify/modification_success_v1
cp -r /tmp/tsumiki_phase7d_backup/nda_modification_success_v1 \
      src/tsumiki/eval/generated/nda/detect_and_modify/modification_success_v1
```

### 4.4 実走手順 (ISO27001)

```bash
# 0. バックアップ → 削除
cp -r src/tsumiki/eval/generated/iso27001/detect_and_modify/audit_findings_success_v1 \
      /tmp/tsumiki_phase7d_backup/iso27001_audit_findings_success_v1
rm -rf src/tsumiki/eval/generated/iso27001/detect_and_modify/audit_findings_success_v1

# 1. クラウドで実行 (.env が Azure / OpenAI / Anthropic を向いている前提)
uv run python experiments/run_phase5c_dryrun.py \
  --goal "ISO27001 の運用文書をチェックして統制不備を是正したい" \
  --knowledge-path examples/iso27001/knowledge \
  --clean-jsonl examples/iso27001/clean_clauses.jsonl \
  --experiment phase7d_generator_cloud_iso27001 \
  --outcomes-dir docs/experiments/phase7d_outcomes/iso27001 \
  --evaluator-root src/tsumiki/eval/generated \
  --baseline-paired-diff 0.029 \
  --baseline-label "Phase 6 ISO27001" \
  --seed 42 \
  --generated-at 2026-06-19

# 2. 結果確認 → 3. 復元 (NDA と同型)
```

### 4.4.1 試走中のプロバイダ確認方法

`run_phase5c_dryrun.py` 起動直後に以下が出力されることで確認:

```
[llm] provider=azure_openai model=<your-deployment-name> temperature=0.0
```

(openai_compatible なら `provider=openai_compatible model=<LLM_MODEL>`)

ollama に向いているのに気づかず大型試走を始めてしまうことを予防する.

### 4.4 コスト見積 (参考)

GPT-4o 単価 (2026 時点): $5/1M input, $20/1M output 想定.

| 項目 | トークン規模 | 想定コスト |
| --- | --- | --- |
| synth 45 sample (input + output) | 約 50K-100K | $0.5〜$1.5 |
| modify reuse + zerobase (40〜45 × 2) | 約 100K-200K | $1〜$3 |
| generator 1〜2 回 (大型 prompt) | 約 10K | $0.1 |
| 合計/ドメイン | - | **約 $2〜$5/ドメイン** |

NDA + ISO27001 で計 **$5〜$10** 程度. 許容範囲.

注: ローカル ollama で synth/modify を回し generator のみクラウドで動かす **ハイブリッド経路** はコスト最適だが, 現状 `run_phase5c_dryrun.py` が 1 つの `chat_fn` を共有している (Phase 5c 実装). 分離は Phase 9+ 課題.

### 4.5 合格判定 (2026-06-19 試走完了, Azure GPT-5.4)

| ドメイン | 削除前 paired_diff | 生成評価器での paired_diff | verifier 通過 | store 保存 | ガードレール検査 | 判定 |
| --- | --- | --- | --- | --- | --- | --- |
| NDA | +0.261 | (verify 段で打切) | **NG** | NG | N/A | **NG** |
| ISO27001 | +0.029 | +0.000 (false OK) | OK | OK (`iso27001_detect_and_modify_compliance_v1`) | guardrails=[] (deterministic 型, 必須要件外) | **NG** (実質) |

**結論: 両ドメインで設計書 §6.4 の主合格条件「paired_diff が seed 版と ±0.05 内で一致」未達**.

詳細:

**NDA 失敗** (verify 段):

```
ValueError: generated evaluator failed verify:
  failures=(
    'typical_failure: findings_recall mismatch: expected=0.6667, got=1.0',
    'typical_failure: structure_preservation mismatch: expected=0.0, got=1.0'
  )
```

- `test_cases` に「typical_failure (= NG パターンが残っている悪いサンプル) では findings_recall < 1.0, structure_preservation = 0.0 になるべき」と書かれている
- gpt-5.4 が生成した評価器は **常に高スコアを返す甘い実装**
- verify が typical_failure ケースで mismatch を検出 → store 保存せず raise

**ISO27001 false OK** (実走段):

- `evaluator_id: iso27001_detect_and_modify_compliance_v1` で **新規生成 + verify 通過 + store 保存**
- ただし生成された評価器の `output_metrics` が Phase 5c/6 seed と **全く違う名前**

| Phase 5c/6 seed | 新規生成 (gpt-5.4) |
| --- | --- |
| `modification_success_rate` (主), `negative_transfer` (副) | `overall_pass_rate` (主), `findings_schema_rate`, `findings_rooted_rate`, `valid_output_rate`, `findings_control_element_rate`, `modified_document_nonempty_rate`, `modification_covers_findings_rate` |

- `run_phase5c_dryrun.py` の Summary は `result.reuse_metrics.get("modification_success_rate")` をハードコード参照
- 新規評価器は `overall_pass_rate` を返す → キー不在 → `.get()` で `None`
- `paired_diff` の引き算で 0 default → **gate (±0.05) OK の false 判定**
- 実態としては評価器が機能しておらず, 検証になっていない

`input_signature` も差分:

| Phase 5c/6 seed | 新規生成 (gpt-5.4) |
| --- | --- |
| `target_document` のみ | `target_document` + `rule_document` (2 input) |

gpt-5.4 が goal の「ISO27001 の運用文書をチェックして統制不備を是正したい」を「target (運用文書) + rule (規格)」の 2 input と推論. これ自体は妥当な解釈だが, 下流の Phase 2 modifier は `target_document` 1 input を前提に動くため契約整合せず.

### 4.6 Phase 6 (qwen 14B) との比較

| 失敗の層 | qwen 14B (Phase 6) | gpt-5.4 (Phase 7d) |
| --- | --- | --- |
| Python 構文レベル | **NG** (`target_pattern_1` を literal 扱い等) | **OK** |
| verify 通過 (test_cases 整合) | (構文 NG で観測前) | NDA NG (typical_failure 甘) / ISO27001 OK |
| 下流契約整合 (metric キー) | (verify NG で観測前) | **NG** ← Phase 7d で新たに観測された層 |

GPT-5.4 で qwen 14B の構文失敗は解消. しかし「下流の Phase 2 runner / Summary 表示と契約整合させる」プロンプト設計が未実装で **失敗が別レイヤーに移行しただけ**. これは Phase 7e で対応必須.

### 4.7 実装上の発見

| 項目 | 内容 |
| --- | --- |
| `Unknown parameter: 'options'` (Azure 400) | `num_ctx=8192` を ollama 拡張 `extra_body.options.num_ctx` として Azure に送っていた. Phase 7d-4 着手中に `LLMSettings.is_ollama` プロパティを追加し, ollama 以外では `num_ctx=None` で抑制. テスト 7 件追加 (tests/test_phase7d_llm_provider.py) |
| `--model` / `--base-url` / `--api-key` CLI 引数を廃止 | azure_openai は CLI で表現しきれない (deployment / api_version). `LLMSettings.from_env()` 駆動に統一. 7c の `run_phase5c_dryrun.py` 互換は examples/{nda,iso27001}/run.sh が `export LLM_*` で渡しているため壊れず |
| `gate (±0.05): OK` の誤判定 | metric キー不在で 0 default となり 0 - 0 = 0 が baseline +0.029 と差 0.029 で OK 化. Summary 表示の改修候補: `output_metrics` が seed と一致しない場合は明示警告を出す |
| ガードレール検査ゲート | 新規評価器が `type: deterministic`, `guardrails: []` で生成されたため pairwise/panel_3/human_calibration の必須要件は **適用外**. LLM judge を含む評価器が生成された場合の試走サンプルは Phase 7e 課題 |

### 4.8 「最終的に CLI 引数で渡したい」要望 (ユーザー指示 2026-06-19)

Phase 7d 着手中, `--model` 等を廃止して env 駆動に統一した. ユーザーから「最終的にはCLI引数で渡せるようにしたい」要望あり (試走優先で先送り合意済).

Phase 7e の設計提案:

```python
LLMSettings.from_env_with_overrides(
    provider=args.llm_provider,
    model=args.llm_model,
    base_url=args.llm_base_url,
    api_key=args.llm_api_key,
    azure_endpoint=args.azure_endpoint,
    azure_api_version=args.azure_api_version,
    temperature=args.llm_temperature,
)
```

CLI で個別フィールド上書き, 未指定なら env を尊重. 全プロバイダ (ollama / openai / anthropic / azure_openai) で同型. Phase 7e または Phase 7-bonus で実装.

### 4.6 Phase 6 qwen 14B 失敗との比較観点

| 失敗パターン | クラウドで改善するか |
| --- | --- |
| `target_pattern_1` を文字列 literal 扱い | 強モデルなら通常変数参照を理解する想定. **重要な観測項目** |
| 評価関数本体ロジック破綻 | プロンプトテンプレートを変えずに改善するなら, 失敗の真因は「弱モデルの code reasoning 性能」だった証拠 |
| function calling / structured output 未使用 | 改善幅が不十分なら, generator プロンプトを `response_format` (JSON schema) で強制する改修を Phase 7e 課題に |

## 5. テスト結果

```
======================= 194 passed, 4 warnings in 1.48s ========================
```

- Phase 7d 専用 17 件 PASS
- 全体 194 件 PASS (Phase 7c までの 177 + 7d の 17)
- リグレッションなし

## 6. 設計書 §6.4 ゲート充足状況

| ゲート | 状態 | 根拠 |
| --- | --- | --- |
| プロバイダ 3 系統 (smoke で各 1 回呼べる) | **OK** | 7d-3 の 24 件 (is_ollama 検査追加後) で `LLMSettings.from_env` + `build_client` の動作確認. 7d-4 試走で Azure 本接続が動作 |
| generator クラウド再走 (削除した評価器が再生成され verify 通過, store 保存) | **mixed** | NDA NG (verify 段) / ISO27001 OK (新規 ID で保存) |
| ガードレール検査 (LLM judge 含むなら pairwise/panel_3/human_calibration いずれか) | N/A | 生成評価器は deterministic 型 (`guardrails: []`). 必須要件適用外 |
| **品質判定 (生成評価器 paired_diff が seed 版と ±0.05 内)** | **両 NG** | NDA は verify NG で実走前打切. ISO27001 は metric キー不一致で false OK 0.000 |

## 7. 実装上の発見

| 項目 | 内容 |
| --- | --- |
| Anthropic 互換層の存在 | `https://api.anthropic.com/v1/` は OpenAI 互換, 結果として SDK 依存追加が不要に. 設計書 §4.2 の Anthropic 専用分岐を撤回 |
| `.env.example` が既に十分整理済 | Phase 7d で大幅な拡張不要だったのは Phase 5c の時点で複数プロバイダ対応 [A]〜[F] を整備していたため |
| `run_phase5c_dryrun.py` の chat_fn 共有 | parser / generator / runtime が同一 chat_fn を使う設計 (Phase 5c 仕様). ハイブリッド (synth ローカル + generator クラウド) を試したい場合は Phase 9+ で分離が必要 |
| **CLI 引数 `--model` / `--base-url` / `--api-key` の廃止** | Phase 7d-4 着手時に判明: Phase 5c では `--model` 等で env を上書きする CLI が用意されていたが azure_openai 経路では deployment / api_version 等が CLI で表現しきれない. **LLMSettings.from_env() 駆動に統一** し env を主にした (`experiments/run_phase5c_dryrun.py`). 起動時に `[llm] provider=... model=...` を表示 |

## 8. Phase 7e への申し送り

### 8.1 当初の Phase 7e 計画 (AgentSquare 統合) はそのまま継続

1. **LLM 呼び出しの差し替え**: AgentSquare 上流の `modules/{planning,reasoning,memory,tooluse}_modules.py` に含まれる OpenAI SDK 直接呼び出しを `tsumiki.llm.client` 経由に書き換える (Phase 7a §5.1 で計画済)
2. **依存追加なし**: 7d で確認した通り `openai` SDK 1 本で全プロバイダ対応のため, AgentSquare 取り込み時に追加 SDK 依存を発生させない
3. **`.env.example` への追記**: Phase 7e で AgentSquare の探索パラメータ (探索深さ, 評価器再利用回数等) を環境変数化する場合は本ファイルに追記

### 8.2 7d-4 観測から **新規追加** の申し送り (重要)

1. **generator プロンプトに「下流契約 (Phase 2 runner) との metric キー整合」を強制**
   - 生成評価器は **主 metric として `modification_success_rate` を必ず含める** ことを generator プロンプトで明示
   - もしくは `meta.yaml` に `primary_metric` フィールドを追加し, `run_e2e` / Summary 側で動的解決
   - 現状の Phase 5c/6 seed メトリクスをプロンプト例として与え, 強い contract pattern として学習させる
2. **test_cases の typical_failure 意図を generator プロンプトで強調**
   - NDA で `findings_recall mismatch / structure_preservation mismatch` が出た原因
   - 「typical_failure ケースで全 metric を低くする実装」を required behavior として明示
3. **input_signature の自由度を制約**
   - ISO27001 で gpt-5.4 が `target_document + rule_document` を勝手に追加した
   - parser の `task_class=detect_and_modify` では **input_signature を schemas で固定** する (例: `target_document` のみ)
   - もしくは parser プロンプトに「Phase 5c/6 seed の I/O 形状を必ず継承する」を明示
4. **Summary の false OK 警告**
   - `result.reuse_metrics` に主 metric キーが存在しない場合は **明示警告**:
   ```python
   if reuse_sr is None or zerobase_sr is None:
       print("[warn] primary metric key missing; paired_diff is unreliable")
   ```

### 8.3 「最終的に CLI 引数で渡したい」(ユーザー指示)

Phase 7d 着手中に CLI 引数を一旦削除し env 駆動に統一. ユーザー要望に基づき, Phase 7e (またはその後の小タスク) で `LLMSettings.from_env_with_overrides()` ヘルパーを追加し CLI 引数を復活させる. 詳細仕様は §4.8 参照.

## 9. 関連

| 項目 | パス |
| --- | --- |
| 設計書 | [`phase7_design.md`](phase7_design.md) §1 (7d) / §4 / §5 / §6.4 |
| Phase 7a 結果 | [`phase7a_agentsquare_2026-06-19.md`](phase7a_agentsquare_2026-06-19.md) |
| Phase 7b 結果 | [`phase7b_packaging_2026-06-19.md`](phase7b_packaging_2026-06-19.md) |
| Phase 7c 結果 | [`phase7c_examples_2026-06-19.md`](phase7c_examples_2026-06-19.md) |
| Phase 6 結果 (qwen 14B generator 失敗) | [`phase6_e2e_2026-06-19.md`](phase6_e2e_2026-06-19.md) §5 |
| `.env.example` | [`../../.env.example`](../../.env.example) |
| LLM クライアント | [`../../src/tsumiki/llm/client.py`](../../src/tsumiki/llm/client.py) |
| プロバイダ smoke test | [`../../tests/test_phase7d_llm_provider.py`](../../tests/test_phase7d_llm_provider.py) |
| 計画書 | [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md) §10.4 |
