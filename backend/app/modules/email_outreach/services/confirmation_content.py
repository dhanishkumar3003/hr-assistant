"""
Copy for recruitment-response confirmation emails.

Maps a reply_classifier classification onto recruitment_response.html's
content fields. Kept separate from services/sender.py (which only
sends) and reply_classifier.py (which only detects intent), so the
wording can change without touching either.
"""

from app.modules.email_outreach.services.reply_classifier import (
    CLASSIFICATION_INTERESTED,
    CLASSIFICATION_DECLINED,
)

_CONTENT = {
    CLASSIFICATION_INTERESTED: {
        "email_title": "Thanks for Your Response",
        "header_subtitle": "Application Update",
        "message_1": "Thank you for confirming your interest in this opportunity.",
        "message_2": (
            "Our team will review your response and reach out shortly "
            "to schedule the next step."
        ),
        "response_section": (
            '<div class="next-step">'
            "<p><strong>Status:</strong> Interview scheduling in progress.</p>"
            "</div>"
        ),
        "closing_message": (
            "We appreciate your interest and look forward to speaking with you."
        ),
    },
    CLASSIFICATION_DECLINED: {
        "email_title": "Thanks for Letting Us Know",
        "header_subtitle": "Application Update",
        "message_1": "Thank you for taking the time to respond to our invitation.",
        "message_2": (
            "We understand this opportunity isn't the right fit for you at this time."
        ),
        "response_section": (
            '<div class="next-step">'
            "<p><strong>Status:</strong> Application closed at your request.</p>"
            "</div>"
        ),
        "closing_message": (
            "We wish you the best in your career and hope to cross paths "
            "again in the future."
        ),
    },
}


def get_confirmation_content(classification: str) -> dict:
    """
    Get the recruitment_response.html content for a classification.

    Args:
        classification (str): One of reply_classifier's CLASSIFICATION_*
            constants.

    Returns:
        dict: Template fields, or None if this classification shouldn't
            trigger an automated confirmation (e.g.
            CLASSIFICATION_NEEDS_REVIEW - an ambiguous reply needs
            manual review before anything automated goes out).
    """
    return _CONTENT.get(classification)
