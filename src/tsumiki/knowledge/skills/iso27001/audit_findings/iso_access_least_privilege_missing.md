---
id: iso_access_least_privilege_missing
name: 最小権限の原則の不備
domain: iso27001
schema_version: 1
task_classes:
- detect
- modify
severity: high
applicable_topics:
- access
references:
- ISO/IEC 27001:2022 Annex A 5.15 アクセス制御
- IPA 中小企業の情報セキュリティ対策ガイドライン
last_updated: '2026-06-19'
maintainer: tsumiki
---

# 最小権限の原則の不備

## 対象条項

「アクセス制御」「権限付与」「ID 管理」を主題とする規程・手順書のみが判定対象。

## 検出すべき

アクセス制御の規定にもかかわらず「業務に必要な範囲」「最小限の権限」「Need-to-Know」等、最小権限の原則を示す制約が明記されていない、または全員に同一権限を付与している記述がある。

## 紛らわしい

「業務上必要な最小限の権限のみ付与する」「職務分離に基づき権限を分離する」等、最小権限を明示している記述は該当しない。

## 例

- 従業員は業務システムにアクセスできるものとする。
- 全ての職員は管理者権限を付与する。
