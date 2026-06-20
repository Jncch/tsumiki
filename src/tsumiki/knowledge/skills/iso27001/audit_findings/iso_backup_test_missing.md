---
id: iso_backup_test_missing
name: バックアップ復元テストの未規定
domain: iso27001
schema_version: 1
task_classes:
- detect
- modify
severity: high
applicable_topics:
- backup
references:
- ISO/IEC 27001:2022 Annex A 8.13 情報のバックアップ
last_updated: '2026-06-19'
maintainer: tsumiki
---

# バックアップ復元テストの未規定

## 対象条項

「バックアップ」「事業継続」「復旧」を主題とする規程・手順書のみが判定対象。

## 検出すべき

バックアップの取得手順は定義されているが、定期的な復元テストの実施手順・頻度・成功判定基準が規定されていない。

## 紛らわしい

「年 1 回以上の復元テストを実施する」「四半期毎にリストア試験を行い結果を記録する」等、復元テストの頻度・記録方法が明示されていれば該当しない。

## 例

- 重要データは日次でバックアップする。
- システム停止時はバックアップから復旧する。
