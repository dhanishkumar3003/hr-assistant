"""
Module 1 - make email and phone look the same every time.

Why this matters: the candidates table refuses a phone that is not exactly
10 digits (ck_candidates_phone_digits) and an email that is not lowercase
(ck_candidates_email_lowercase). Without those rules, "Ravi@Gmail.com" and
"ravi@gmail.com" would be two different people and duplicate detection
would silently fail forever. So: normalise BEFORE the insert, always.
"""

import re

_NOT_A_DIGIT = re.compile(r"\D")
_LOOKS_LIKE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(value: str | None) -> str | None:
    """' Ravi.Kumar@Gmail.com ' -> 'ravi.kumar@gmail.com'.  Anything that is not an email -> None."""
    if not value:
        return None
    email = value.strip().lower()
    return email if _LOOKS_LIKE_EMAIL.match(email) else None


def normalize_phone(value: str | None) -> str | None:
    """'+91 98765-43210' -> '9876543210'.  Keeps the LAST 10 digits; fewer than 10 -> None."""
    if not value:
        return None
    digits = _NOT_A_DIGIT.sub("", str(value))
    return digits[-10:] if len(digits) >= 10 else None
