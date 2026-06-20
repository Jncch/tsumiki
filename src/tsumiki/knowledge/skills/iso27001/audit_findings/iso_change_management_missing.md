---
id: iso_change_management_missing
name: 変更管理の承認・記録手順の欠落
domain: iso27001
schema_version: 1
task_classes:
- detect
- modify
severity: medium
applicable_topics:
- change
references:
- ISO/IEC 27001:2022 Annex A 8.32 変更管理
last_updated: '2026-06-19'
maintainer: tsumiki
---

# 変更管理の承認・記録手順の欠落

## 対象条項

「変更管理」「リリース管理」「構成管理」を主題とする規程・手順書のみが判定対象。

## 検出すべき

システム変更・構成変更時の承認プロセス、変更内容の記録、影響評価、ロールバック手順のいずれかが明確に定められていない。

## 紛らわしい

「変更は変更管理委員会の承認を得て実施し、変更票を記録する」「リリース前にロールバック手順を確認する」等、承認・記録・影響評価が具体化されていれば該当しない。

## 例

- システム変更は担当者の判断で実施する。
- 緊急時の変更は事後報告とする。
