---
id: nda_duration_unbounded
name: 秘密保持期間の無期限・過長
domain: nda
schema_version: 1
task_classes:
- detect
- modify
severity: high
applicable_topics:
- duration
- survival
- secrecy
references:
- 経済産業省 秘密情報の保護ハンドブック
last_updated: '2026-06-10'
maintainer: tsumiki
---

# 秘密保持期間の無期限・過長

## 対象条項

「有効期間」「秘密保持義務」「存続」を主題とする条項が判定対象。

## 検出すべき

秘密保持義務の期間が「期間の定めなく」「無期限」「永久」等で示される、または営業秘密性が消滅した後も継続する不合理な長期間が定められている。

## 紛らわしい

「3 年間」「5 年間」「契約終了後 2 年間」等の明示的・合理的な期間定めは該当しない。

## 例

- 受領者は、本契約終了後も期間の定めなく秘密情報を保持しなければならない。
