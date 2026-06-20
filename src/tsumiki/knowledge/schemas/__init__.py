"""ドメイン横断の共通 Knowledge schema.

Phase 7b で導入. NDA の `ng_patterns.yaml` と ISO27001 の
`audit_findings.yaml` が同じ `NGPatternBook` schema に乗ることを
担保する. 詳細は `ng_patterns.py` 参照.
"""

from tsumiki.knowledge.schemas.ng_patterns import (
    NGPattern,
    NGPatternBook,
    Topic,
    load_ng_pattern_book,
)

__all__ = ["NGPattern", "NGPatternBook", "Topic", "load_ng_pattern_book"]
