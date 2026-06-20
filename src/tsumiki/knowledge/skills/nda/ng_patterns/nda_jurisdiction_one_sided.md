---
id: nda_jurisdiction_one_sided
name: 準拠法・管轄の欠落または一方的指定
domain: nda
schema_version: 1
task_classes:
- detect
- modify
severity: medium
applicable_topics:
- jurisdiction
references:
- 民事訴訟法 11条
last_updated: '2026-06-10'
maintainer: tsumiki
---

# 準拠法・管轄の欠落または一方的指定

## 対象条項

「準拠法」「管轄」「紛争の解決」を主題とする条項のみが判定対象。

## 検出すべき

準拠法・合意管轄が記載されていない、または開示者側に著しく有利な専属管轄（遠隔地、開示者本店所在地、開示者指定等）を指定している。国際取引で準拠法が不明確な場合も含む。

## 紛らわしい

中立的な合意管轄（東京地方裁判所等）、双方の本店所在地のどちらかを選択可能な規定は該当しない。

## 例

- 本契約に関する紛争は、開示者の指定する裁判所を専属管轄とする。
