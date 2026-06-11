"""Phase 1 単一プロンプト方式の NG 検出ベースライン.

CLAUDE.md §8 / docs/agent_reuse_verification_plan.md §5.2 に従い、
評価器が先・自動化は後、という方針で「人手プロンプト一発」ベースラインを置く。
"""

from tsumiki.baseline.ng_detector import (
    DETECTION_PROMPT_VERSION_LATEST,
    build_detection_prompt,
    detect_ng_patterns,
    parse_detection_response,
    predict_clauses,
)
from tsumiki.baseline.ng_modifier import (
    MODIFICATION_PROMPT_VERSION_LATEST_REUSE,
    MODIFICATION_PROMPT_VERSION_LATEST_ZEROBASE,
    MODIFICATION_PROMPT_VERSION_PARAPHRASE_REUSE,
    MODIFICATION_PROMPT_VERSION_PARAPHRASE_ZEROBASE,
    build_modification_prompt,
    clean_modification_response,
    modify_clause,
)

__all__ = [
    "DETECTION_PROMPT_VERSION_LATEST",
    "MODIFICATION_PROMPT_VERSION_LATEST_REUSE",
    "MODIFICATION_PROMPT_VERSION_LATEST_ZEROBASE",
    "MODIFICATION_PROMPT_VERSION_PARAPHRASE_REUSE",
    "MODIFICATION_PROMPT_VERSION_PARAPHRASE_ZEROBASE",
    "build_detection_prompt",
    "build_modification_prompt",
    "clean_modification_response",
    "detect_ng_patterns",
    "modify_clause",
    "parse_detection_response",
    "predict_clauses",
]
