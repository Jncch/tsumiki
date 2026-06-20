---
id: iso_log_retention_undefined
name: ログの保持期間と改ざん防止策の不明確
domain: iso27001
schema_version: 1
task_classes:
- detect
- modify
severity: medium
applicable_topics:
- logging
references:
- ISO/IEC 27001:2022 Annex A 8.15 ログ取得
last_updated: '2026-06-19'
maintainer: tsumiki
---

# ログの保持期間と改ざん防止策の不明確

## 対象条項

「ログ」「監査証跡」「監視」を主題とする規程・手順書のみが判定対象。

## 検出すべき

ログ取得の規定はあるが、ログの保持期間が「適切に」「必要な期間」等の抽象表現で具体的期間が定められていない、または改ざん防止・アクセス制限措置が記述されていない。

## 紛らわしい

「1 年間以上保持する」「3 年間保持し読み取り専用領域に保管する」等、保持期間と改ざん防止策が具体的に書かれていれば該当しない。

## 例

- システムログは適切な期間保持する。
- 監査ログは必要な期間保管し、必要に応じてレビューする。
