---
id: iso_supplier_risk_assessment_missing
name: 供給者・委託先のリスク評価不在
domain: iso27001
schema_version: 1
task_classes:
- detect
- modify
severity: high
applicable_topics:
- supplier
references:
- ISO/IEC 27001:2022 Annex A 5.19 情報セキュリティの供給者関係
last_updated: '2026-06-19'
maintainer: tsumiki
---

# 供給者・委託先のリスク評価不在

## 対象条項

「供給者管理」「委託先管理」「外部委託」を主題とする規程・手順書のみが判定対象。

## 検出すべき

供給者・委託先選定時のセキュリティリスク評価・契約上のセキュリティ要件の確認・定期的な遵守状況確認の手順が定められていない。

## 紛らわしい

「委託先選定時にセキュリティチェックリストで評価し、年 1 回遵守状況を確認する」等、評価手順と継続確認の頻度が明示されていれば該当しない。

## 例

- 委託先選定は調達部門で行う。
- 業務委託先には機密保持を遵守させる。
