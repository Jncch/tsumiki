---
id: nda_scope_overbroad
name: 秘密情報の範囲過大
domain: nda
schema_version: 1
task_classes:
- detect
- modify
severity: high
applicable_topics:
- definition
references:
- 経済産業省 営業秘密管理指針
- 不正競争防止法 2条6項
last_updated: '2026-06-10'
maintainer: tsumiki
---

# 秘密情報の範囲過大

## 対象条項

「秘密情報」「定義」を主題とする条項のみが判定対象。

## 検出すべき

秘密情報の定義条項に「一切の情報」「全ての情報」のような無限定範囲、または既知情報・公知情報・第三者からの正当取得情報の除外規定が無い。

## 紛らわしい

厳格な秘密指定手続（書面/電磁的形式での指定、口頭開示後 30 日以内の書面通知等）と除外規定（既知/公知/正当取得）が定義条項に明示されている場合は該当しない。

## 例

- 本契約において「秘密情報」とは、開示当事者から受領当事者に対して開示された一切の情報をいう。
