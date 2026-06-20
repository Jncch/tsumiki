---
id: nda_return_destroy_missing
name: 返還・廃棄義務の不在または確認手段なし
domain: nda
schema_version: 1
task_classes:
- detect
- modify
severity: medium
applicable_topics:
- return_destroy
references:
- 経済産業省 秘密情報の保護ハンドブック
last_updated: '2026-06-10'
maintainer: tsumiki
---

# 返還・廃棄義務の不在または確認手段なし

## 対象条項

「秘密情報の返還」「廃棄」「契約終了時の処理」を主題とする条項が判定対象。

## 検出すべき

契約終了時・開示者の要求時に秘密情報の返還または廃棄を行う義務が無い、または廃棄証明・確認の手段（証明書発行等）が定められていない。

## 紛らわしい

「返還又は廃棄」「廃棄証明書を発行」等の具体的規定がある場合は該当しない。返還・廃棄を主題としない条項では判定対象外。

## 例

- 受領者は秘密情報を適切に管理するものとする。
