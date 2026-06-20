---
id: iso_secure_disposal_missing
name: 安全な廃棄手順の不在
domain: iso27001
schema_version: 1
task_classes:
- detect
- modify
severity: medium
applicable_topics:
- disposal
references:
- ISO/IEC 27001:2022 Annex A 8.10 情報の削除
last_updated: '2026-06-19'
maintainer: tsumiki
---

# 安全な廃棄手順の不在

## 対象条項

「廃棄」「情報の削除」「媒体管理」を主題とする規程・手順書のみが判定対象。

## 検出すべき

記憶媒体・印刷物・電子データの廃棄手順が「適切に廃棄する」等の抽象表現に留まり、廃棄方法（物理破壊・データ完全消去・第三者証明）が具体的に定められていない。

## 紛らわしい

「ハードディスクは物理破壊し廃棄証明書を取得する」「データは DoD 規格で完全消去する」等、廃棄方法と証跡の取得が明示されていれば該当しない。

## 例

- 使用済み媒体は適切に廃棄する。
- 退職時に貸与品を返却するものとする。
