"""LLM ベースの構造化抽出 (RAG なし).

Phase 7b で骨組のみ. 入力文書 → Knowledge schema (YAML / Agent Skills)
への抽出を担う. 計画書 §10.2 で「RAG コーパスは構築しない」と決めた
通り, retrieval ではなく構造化抽出に閉じる.
"""
