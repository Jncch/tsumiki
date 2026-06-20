---
id: nda_purpose_undefined
name: 利用目的の不明確
domain: nda
schema_version: 1
task_classes:
- detect
- modify
severity: medium
applicable_topics:
- purpose
- secrecy
references:
- JIPDEC 秘密情報の取扱いに関するガイドブック
last_updated: '2026-06-10'
maintainer: tsumiki
---

# 利用目的の不明確

## 対象条項

「目的」「秘密保持義務」（目的外利用禁止を含む条項）が判定対象。

## 検出すべき

秘密情報の利用目的（合意目的）が「本件」「関連する目的」等の抽象表現で、具体的範囲が読み取れない。または目的の定義自体が欠落している。

## 紛らわしい

「〇〇プロジェクトのための事前検討」「特定の業務委託に関する協議」等、具体的事業・取引名が明示されていれば該当しない。

## 例

- 受領者は本件に関連する目的のために秘密情報を利用できる。
