---
id: iso_data_classification_missing
name: 情報資産の機密区分の未定義
domain: iso27001
schema_version: 1
task_classes:
- detect
- modify
severity: medium
applicable_topics:
- classification
references:
- ISO/IEC 27001:2022 Annex A 5.12 情報の分類
last_updated: '2026-06-19'
maintainer: tsumiki
---

# 情報資産の機密区分の未定義

## 対象条項

「情報資産分類」「情報の取扱い」「機密区分」を主題とする規程・手順書のみが判定対象。

## 検出すべき

情報資産の機密区分（極秘・秘・社外秘・公開等）の定義、各区分の取扱基準（保管・送信・複製・廃棄）が定められていない、または定義はあるが運用適用方法が記述されていない。

## 紛らわしい

「機密区分は『機密・社外秘・公開』の 3 区分とし、機密は施錠保管・暗号化送信を必須とする」等、区分と取扱基準が具体的であれば該当しない。

## 例

- 重要な情報は適切に管理する。
- 機密情報の取扱いは関連法令を遵守する。
