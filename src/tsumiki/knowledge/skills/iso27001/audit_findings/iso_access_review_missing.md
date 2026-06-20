---
id: iso_access_review_missing
name: アクセス権の定期見直し手順の欠落
domain: iso27001
schema_version: 1
task_classes:
- detect
- modify
severity: high
applicable_topics:
- access
references:
- ISO/IEC 27001:2022 Annex A 5.18 アクセス権
last_updated: '2026-06-19'
maintainer: tsumiki
---

# アクセス権の定期見直し手順の欠落

## 対象条項

「アクセス権」「ID 管理」「権限管理」を主題とする規程・手順書のみが判定対象。

## 検出すべき

アクセス権付与の手順はあるが、付与後の定期見直し（例: 半年毎・人事異動時のレビュー）に関する手順・責任者・頻度が定められていない。

## 紛らわしい

「四半期毎にアクセス権を見直す」「人事異動時に権限を再評価する」等、見直しの頻度・契機・責任者が明示されていれば該当しない。

## 例

- アクセス権は申請に基づき付与する。
- 退職時の権限剥奪については別途定める。
