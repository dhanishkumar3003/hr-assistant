"""
Module 1 - "have we seen this person before?"

    IDuplicateRule            one way of recognising a person (email, phone, ...)
    TieredDuplicateDetector   runs the rules IN ORDER, stops at the first hit

Open/Closed in practice: adding SEMANTIC_MATCH later is one new rule class
plus one line in api.py where the list is built. This file is never edited.

The exact-file check (same bytes) is NOT a rule here on purpose: it runs in
IngestionService BEFORE the file is stored or the LLM is called, because a
byte-identical upload should never cost an LLM call.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.modules.resume_ingestion.models import Candidate, DuplicateType


@dataclass(frozen=True)
class IncomingProfile:
    """What the rules are allowed to look at - already normalised."""
    email: str | None
    phone: str | None


@dataclass(frozen=True)
class DuplicateVerdict:
    duplicate_type: DuplicateType
    matched_candidate: Candidate
    confidence: float                              # 1.0 for exact identity signals
    details: dict[str, Any] = field(default_factory=dict)   # evidence -> duplicate_tracking.detection_details


class IDuplicateRule(ABC):
    @abstractmethod
    def check(self, incoming: IncomingProfile) -> DuplicateVerdict | None:
        """Return a verdict when this rule recognises the person, else None."""


class TieredDuplicateDetector:
    """Strongest signal first. The first rule that answers wins; the rest are not asked."""

    def __init__(self, rules: list[IDuplicateRule]):
        self._rules = list(rules)

    def detect(self, incoming: IncomingProfile) -> DuplicateVerdict | None:
        for rule in self._rules:
            verdict = rule.check(incoming)
            if verdict is not None:
                return verdict
        return None
