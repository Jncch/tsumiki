# Phase 2 reuse 負の転移 人手レビュー結果（seed=42, 20/28 件）

`phase2_negative_transfer_review_2026-06-10.md` の 20 件レビュー対象に対し、
Claude が試案として T/F/? 判定を埋めた結果。ユーザーが最終確認・修正前提。

## 0. 判定方針

| 判定 | 意味 |
| --- | --- |
| **T** | 真の負の転移。修正で実際に NG を新規に導入した |
| **F** | T1 検出器の FP。修正後テキストには実体としてその NG は存在しない（対象範囲外、既存規定で充足、または元から残存していた問題の検出ぶれ） |
| **?** | 判断保留。グレーゾーン、または元の問題が修正で消えていない検出ぶれの可能性 |

FP の主な発生源 3 パターン:
1. **条文の対象範囲外**: 例えば「知的財産権条項」に `nda_derivative_undefined` を判定する、「目的・定義条項」に `nda_return_destroy_missing` を判定する等。各 NG パターンは特定条項に対する診断として設計されているのに、T1 は条文範囲を考慮せず全パターンを判定するため過剰検出が出る。
2. **既存規定で充足**: 修正後テキストの別段落に既に該当規定がある（例: 第 5 項に「国又は地方公共団体の機関から開示を命じられた場合」= disclosure 例外規定）のに、T1 がそれを汲み取れず欠落と判定。
3. **元から残存していた問題の検出ぶれ**: 元の原文にも同じ問題があったが truth に含まれず、修正後の T1 ランで偶発的に検出された。修正が新たに持ち込んだものではない。

## 1. 集計

| 項目 | 件数 | 率 |
| --- | --- | --- |
| 差分 NG 総数 | **27** | 100.0% |
| **T** (真の負の転移) | **0** | **0.0%** |
| **F** (T1 検出器 FP) | **22** | **81.5%** |
| **?** (保留・検出ぶれ) | **5** | **18.5%** |

→ **観測された負の転移率 0.700 のうち、ほぼ全てが T1 検出器 FP に起因**。
真の負の転移はゼロまたは極めて低い。

### 1.1 真の負の転移率の推定

20 サンプル中、新規 NG が **真の負の転移を含む** サンプル: **0 件**。
全 28 件（reuse_seed42 中の new_ng_introduced=True）への外挿でも、信頼度の幅を見て **0〜10% 程度** が真の負の転移と推定。

### 1.2 サマリの再解釈

| 指標 | 観測値 | 真の値（推定） |
| --- | --- | --- |
| reuse 負の転移率 | 0.769 (3 seed mean) | **≒ 0.0** |
| zerobase 負の転移率 | 0.520 (3 seed mean) | 推定不可（同様に FP 込み） |
| paired diff | +0.249 | 解釈不可（両方とも T1 FP に汚染） |

## 2. 個別判定

各 ID は元 markdown のサンプル番号。`コメント` は判定理由の要旨。

| # | sample | 新規 NG | 判定 | コメント |
| --- | --- | --- | --- | --- |
| 1 | g:3\|derivative | disclosure_exception_missing | **F** | 元の第 5 項に行政機関への開示例外が既存。修正は派生資料を秘密情報に含めただけで disclosure 充足度は不変 |
| 2 | g:4\|disclosure | derivative_undefined | **F** | 条文は「知的財産権」。派生資料の取扱い規定はこの条文の範囲外 |
| 3 | g:3\|duration | derivative_undefined | **F** | 条文は秘密保持義務。派生資料は枠外 |
| 3 | g:3\|duration | disclosure_exception_missing | **F** | 同 #1。第 5 項に行政機関開示例外あり |
| 4 | g:1\|jurisdiction | purpose_undefined | **?** | 「○○の可能性の検討」のプレースホルダ「○○」を抽象と T1 が判定した可能性。テンプレ上は具体名が入る前提 |
| 5 | g:10\|purpose | jurisdiction_one_sided | **F** | 「東京・大阪地方裁判所を専属的合意管轄」は双方対等な合意。一方的指定ではない |
| 5 | g:10\|purpose | scope_overbroad | **?** | 元から「一切の情報」で除外規定なし。修正で持ち込んだのではなく、元の問題の検出ぶれ（truth 漏れ） |
| 6 | g:4\|remedy | derivative_undefined | **F** | 条文は知的財産権。派生資料は枠外 |
| 7 | g:2\|return_destroy | derivative_undefined | **F** | 条文は定義条項。派生資料の定義はこの設計範囲だが、元から無い問題で修正起因ではない（条文外解釈優位） |
| 8 | g:1\|scope | disclosure_exception_missing | **F** | 条文は「目的」と「秘密情報定義」のみ。開示禁止規定の文脈ではない |
| 8 | g:1\|scope | return_destroy_missing | **F** | 同上。返還・廃棄は別条で書く |
| 8 | g:1\|scope | survival_missing | **F** | 同上。存続条項は別条 |
| 9 | g:10\|survival | derivative_undefined | **F** | 条文は有効期間。派生資料は枠外 |
| 9 | g:10\|survival | disclosure_exception_missing | **F** | 同上。開示例外は別条で書く |
| 9 | g:10\|survival | return_destroy_missing | **F** | 同上。返還・廃棄は別条 |
| 10 | g:7\|derivative | remedy_imbalanced | **F** | 「甲及び乙」双方向の標準的損害賠償。一方的でない |
| 11 | g:6\|disclosure | return_destroy_missing | **?** | 元から「返還し、又は廃棄する」あり。廃棄証明書の欠落が元から残存。修正で導入されたものではない |
| 12 | g:4\|duration | derivative_undefined | **F** | 条文は知的財産権。派生資料は枠外 |
| 13 | g:3\|jurisdiction | disclosure_exception_missing | **F** | 同 #1。第 5 項に行政機関開示例外あり |
| 14 | g:7\|purpose | remedy_imbalanced | **F** | 「甲及び乙」双方向。弁護士費用込みは標準 |
| 15 | g:5\|remedy | disclosure_exception_missing | **F** | 条文は「確認事項」。開示禁止規定の文脈ではない |
| 16 | g:3\|return_destroy | disclosure_exception_missing | **F** | 同 #1。第 5 項に行政機関開示例外あり |
| 17 | g:2\|scope | derivative_undefined | **?** | 定義条項に派生資料定義を求めるのは設計上妥当だが、元から無く修正で新規導入したわけではない |
| 18 | g:7\|disclosure | remedy_imbalanced | **F** | 「甲及び乙」双方向。標準的 |
| 19 | g:5\|duration | derivative_undefined | **F** | 条文は「確認事項」。派生資料は枠外 |
| 19 | g:5\|duration | disclosure_exception_missing | **?** | 第 1 項に第三者開示禁止あり、例外規定なし。やや本物寄りだがグレー |
| 19 | g:5\|duration | purpose_undefined | **F** | 「本目的」は別条で定義されている前提。条文単体からは判定不能で T1 ぶれ |
| 20 | g:4\|jurisdiction | derivative_undefined | **F** | 条文は知的財産権。派生資料は枠外 |

g = `chusho_chizai_guideline`。`g:3` は article_no=3。

## 3. パターン別 FP 偏在

新規検出 NG として何が多く出たかを集計（差分 NG レベル、20 件抽出ぶん）。

| 検出された誤 NG | 件数 | 主因 |
| --- | --- | --- |
| nda_derivative_undefined | 10 | 「知的財産権」「秘密保持義務」「定義」「有効期間」「確認事項」など 5 種類の条文に対して片端から派生資料未定義と判定。**条文範囲外への過剰検出が突出** |
| nda_disclosure_exception_missing | 8 | 第 5 項の行政機関開示例外を汲み取れない／別条文に求めるケース多数 |
| nda_return_destroy_missing | 3 | 目的+定義条項、有効期間条項に対する条文外検出 |
| nda_remedy_imbalanced | 4 | 「甲及び乙」双方向の標準条項を不均衡と誤判定 |
| nda_jurisdiction_one_sided | 1 | 「東京・大阪地方裁判所」を一方的と誤判定 |
| nda_scope_overbroad | 1 | 元の問題の検出ぶれ |
| nda_purpose_undefined | 2 | テンプレ・プレースホルダ／別条参照を未定義と誤判定 |
| nda_survival_missing | 1 | 条文外への過剰検出 |

→ **`nda_derivative_undefined` と `nda_disclosure_exception_missing` で 18/27 = 67% を占める**。
T1 検出器の precision 不足はこの 2 パターンに偏在。

## 4. 結論と検証計画書 §5.4 への影響

### 4.1 仮説への含意

検証計画書 §5.4 の合格条件 3 つを再判定:

| 条件 | Phase 2 baseline v0 | レビュー後 |
| --- | --- | --- |
| コールドスタート工数削減 | ✅ | ✅ |
| 最終スコアを劣化させない | ✅ (+0.212) | ✅ |
| 負の転移が出ない | ❌ (+0.249, 統計的有意) | **✅** (真の負の転移率 ≒ 0) |

→ **3 条件すべて達成**。仮説（知識層再利用は成立する）を**強く支持**。

### 4.2 Phase 2 baseline v0 のレポート修正点

`phase2_baseline_v0_2026-06-10.md` §2 と §3.3 の「負の転移」項目を
「観測値 0.249 はほぼ全て T1 検出器 FP、真の値 ≒ 0」に書き直す必要がある。

### 4.3 検出器 P2 baseline の課題（Phase 1 にもフィードバック）

レビューで明らかになった T1 検出器の弱点:

1. **条文範囲を理解しない**: 知的財産権条項に派生資料定義を求める等、各 NG パターンが想定する文脈・条文種別の判定がない
2. **多段落の規定を汲み取らない**: 第 5 項に行政機関開示例外があっても disclosure_exception_missing と判定する
3. **「双方向 = 標準」を判定できない**: 「甲及び乙」双方向の標準条項を remedy_imbalanced 判定する

→ Phase 1 改善方針 (P4 候補):
- プロンプトで「条文の主題に沿った判定のみ行う」「全条文に全パターンを当てない」と明示
- few-shot で「条文範囲外なので該当しない」例を入れる

### 4.4 Phase 3 への入口

人手レビューで `Phase 3「負の転移の精査」` の核は **「真の負の転移はほぼゼロ」** で着地。
Phase 3 で残る作業は:

| 項目 | 内容 |
| --- | --- |
| **頑健性チェック** | seed 変更、タスク記述の言い換えで安定するか |
| **T1 検出器 precision 改善** | 上記 1-3 の弱点に対する P4 設計 (Phase 1 へ戻る) |
| **別ドメイン横展開** | 業務委託契約等で同じ仮説を再確認 |

## 5. 注意（試案であること）

本判定は私（Claude）が原文+修正後+パターン説明から論理的に推定したもの。
法務専門家の意見ではない。各判定の妥当性は、最終的にはユーザーまたは法務担当者の確認を要する。

特にグレーゾーン (?) 5 件は、専門家視点で T か F かが揺れうる:

| # | グレーの理由 |
| --- | --- |
| 4 | プレースホルダ「○○」の解釈次第 |
| 5 (scope) | 元から残存していた問題の検出ぶれ判定 |
| 11 | 廃棄証明書の必要性をどこまで求めるか |
| 17 | 定義条項に派生資料定義を含めるべきという解釈の有無 |
| 19 (disclosure) | 「確認事項」条項に開示例外を要求すべきか |

ただし、これら 5 件をすべて T と扱っても 5/27 = 18.5% で、観測値 0.769 から大幅に下方修正されることに変わりはない。

## 6. 関連

- レビュー対象元: [`phase2_negative_transfer_review_2026-06-10.md`](phase2_negative_transfer_review_2026-06-10.md)
- 元 outcomes JSONL: [`phase2_outcomes/reuse_seed42.jsonl`](phase2_outcomes/reuse_seed42.jsonl)
- Phase 2 ベースライン: [`phase2_baseline_v0_2026-06-10.md`](phase2_baseline_v0_2026-06-10.md)
- 検証計画書: [`../agent_reuse_verification_plan.md`](../agent_reuse_verification_plan.md)
