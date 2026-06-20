"""ポリシー層 (制約付き役割合成と再最適化).

CLAUDE.md §2 と整合し, 自動構成は AgentSquare のモジュール探索
(制約された役割合成) まで. 完全自律オーケストレーションは射程外.

サブパッケージ:
- ``compose``: AgentSquare モジュール探索ラッパ (Phase 7e で実装)
- ``optimize``: DSPy / AFlow による再最適化 (Phase 9+)
- ``agentsquare``: AgentSquare partial vendoring (Phase 7e で実体配置)
"""
