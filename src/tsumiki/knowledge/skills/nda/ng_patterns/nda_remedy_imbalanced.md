---
id: nda_remedy_imbalanced
name: 損害賠償・違約金の不均衡
domain: nda
schema_version: 1
task_classes:
- detect
- modify
severity: high
applicable_topics:
- liability
- confirmation
references:
- 民法 420条 421条
last_updated: '2026-06-10'
maintainer: tsumiki
---

# 損害賠償・違約金の不均衡

## 対象条項

「損害賠償」「違約金」「差止め」等の責任条項が判定対象。

## 検出すべき

受領者側のみに過大な違約金・損害賠償上限なしを課し、開示者側の責任は限定または免除されている。または双方向 NDA であるべき場面で一方向的な責任設計になっている。

## 紛らわしい

双方が同等の責任を負う規定、合理的な賠償上限がある規定は該当しない。

## 例

- 受領者が本契約に違反した場合、違約金として金1億円を直ちに支払うものとする。
