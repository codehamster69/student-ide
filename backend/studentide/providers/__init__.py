"""Question providers: where a teacher can pick a ready-made question from
instead of writing one. Each provider is looked up live when the teacher
browses (nothing is pre-stored); the question they pick is copied into the
lab as an ordinary question, with its source recorded, so recordings keep a
snapshot of what the student saw and grading never needs the network.

Adding a platform means writing one class with the Provider interface in
base.py and listing it in PROVIDERS below. See docs/question-sources.md for
which platforms can be supported properly and why.
"""

from __future__ import annotations

from .base import Category, Imported, Provider, ProviderError, Summary
from .codecontests import CodeChef, Codeforces
from .exercism import Exercism
from .mbpp import MBPP
from .unavailable import HackerRank, LeetCode

PROVIDERS: dict[str, Provider] = {p.id: p for p in (Codeforces(), CodeChef(), Exercism(), MBPP(), LeetCode(), HackerRank())}

__all__ = ["PROVIDERS", "Category", "Imported", "Provider", "ProviderError", "Summary"]
