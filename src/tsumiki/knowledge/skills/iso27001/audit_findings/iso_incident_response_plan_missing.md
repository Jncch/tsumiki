---
id: iso_incident_response_plan_missing
name: インシデント対応手順の未整備
domain: iso27001
schema_version: 1
task_classes:
- detect
- modify
severity: high
applicable_topics:
- incident
references:
- ISO/IEC 27001:2022 Annex A 5.24 情報セキュリティインシデント管理の計画と準備
last_updated: '2026-06-19'
maintainer: tsumiki
---

# インシデント対応手順の未整備

## 対象条項

「インシデント対応」「事故対応」「セキュリティ事故」を主題とする規程・手順書のみが判定対象。

## 検出すべき

情報セキュリティインシデント発生時の連絡先・エスカレーション経路・初動対応者の責任範囲が定められていない、または「速やかに対応する」のような抽象表現に留まっている。

## 紛らわしい

「インシデント受付窓口は CSIRT に通知し、X 時間以内に初動を行う」のように連絡先・時間目標・責任者が明示されていれば該当しない。

## 例

- セキュリティインシデント発生時は速やかに対応する。
- 重大な事故は経営層に報告するものとする。
