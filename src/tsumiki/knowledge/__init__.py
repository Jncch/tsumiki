"""知識資産（NG パターン辞書等）の格納と読み込み."""

from tsumiki.knowledge.loader import (
    NGPattern,
    NGPatternBook,
    TopicVocab,
    load_ng_patterns,
)

__all__ = ["NGPattern", "NGPatternBook", "TopicVocab", "load_ng_patterns"]
