---
id: nda_survival_missing
name: 存続条項の欠落
domain: nda
schema_version: 1
task_classes:
- detect
- modify
severity: low
applicable_topics:
- duration
- survival
references:
- 経済産業省 秘密情報の保護ハンドブック
last_updated: '2026-06-10'
maintainer: tsumiki
---

# 存続条項の欠落

## 対象条項

「有効期間」「終了」「解除」「存続」を主題とする条項のみが判定対象。「目的」「定義」「秘密保持義務」本体等の条項では判定対象外。

## 検出すべき

契約終了後にどの義務が存続するか（秘密保持義務、損害賠償義務、管轄等）が明示されていない。終了後の義務範囲を巡って解釈が分かれる。

## 紛らわしい

「本契約終了後も第〇条の義務は存続する」「秘密保持義務は契約終了後 N 年間継続する」等の明示があれば該当しない。

## 例

- 本契約は、契約期間の満了をもって終了する。
