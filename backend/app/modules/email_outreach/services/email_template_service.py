"""
HTML email template rendering.

Renders a template from templates/ by substituting {{placeholder}}
tokens with values from a context dict, and inlines its linked
stylesheet into a <style> block - most email clients (Gmail included)
strip <link rel="stylesheet"> tags, so external CSS silently disappears
unless it's inlined at render time. Missing placeholder values render
as an empty string, so a template still works with partial data.
"""

import re
import logging
from pathlib import Path
from datetime import datetime, timezone

from app.core.config import settings

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

INVITE_TEMPLATE = "interview_call.html"
RESPONSE_TEMPLATE = "recruitment_response.html"
TEST_ROUND_TEMPLATE = "email_round_test.html"
REJECTION_TEMPLATE = "candidate_rejection.html"

DEFAULT_CONTEXT = {
    "company_name": settings.company_name,
}

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
_STYLESHEET_LINK = re.compile(
    r'<link\s+rel="stylesheet"\s+href="([^"]+)"\s*/?>'
)


def _inline_stylesheets(html: str) -> str:
    """Replace <link rel="stylesheet"> tags with an inlined <style> block."""

    def replace(match):
        css_path = TEMPLATES_DIR / match.group(1)
        if not css_path.exists():
            log.warning(f"Stylesheet not found for inlining: {css_path}")
            return ""
        css = css_path.read_text(encoding="utf-8")
        return f"<style>\n{css}\n</style>"

    return _STYLESHEET_LINK.sub(replace, html)


def _load_template(filename: str) -> str:
    """Read a template file and inline its linked stylesheet."""
    html = (TEMPLATES_DIR / filename).read_text(encoding="utf-8")
    return _inline_stylesheets(html)


def render_template(filename: str, context: dict = None) -> str:
    """
    Render a template from templates/ by name.

    Args:
        filename (str): Template filename under templates/ (e.g.
            "interview_invitation.html").
        context (dict): Template values. Missing keys render as an
            empty string. Values are inserted verbatim (not escaped),
            so HTML fragments can be passed for placeholders meant to
            hold markup (e.g. response_section).

    Returns:
        str: Rendered HTML.
    """
    values = {
        **DEFAULT_CONTEXT,
        "year": datetime.now(timezone.utc).year,
        **(context or {}),
    }

    def substitute(match):
        value = values.get(match.group(1))
        return str(value) if value is not None else ""

    return _PLACEHOLDER.sub(substitute, _load_template(filename))


def render_invite_html(context: dict = None) -> str:
    """
    Render the interview-call email template (templates/interview_call.html).

    Reply-only response model - no accept/reject link. The candidate
    replies directly to the email; services/reply_classifier.py
    determines interest from the reply text.

    Args:
        context (dict): candidate_name, job_role, job_description,
            experience_required, required_skills, response_deadline,
            hr_name, hr_designation, hr_email, company_name.

    Returns:
        str: Rendered HTML.
    """
    return render_template(INVITE_TEMPLATE, context)


def render_response_html(context: dict = None) -> str:
    """
    Render the recruitment-response (confirmation) email template.

    Args:
        context (dict): email_title, header_subtitle, candidate_name,
            message_1, message_2, response_section (HTML fragment),
            closing_message, hr_name, hr_designation, hr_email,
            company_name.

    Returns:
        str: Rendered HTML.
    """
    return render_template(RESPONSE_TEMPLATE, context)


def render_rejection_html(context: dict = None) -> str:
    """
    Render the candidate-rejection email template.

    Args:
        context (dict): candidate_name, job_role, company_name,
            hr_name, hr_designation, hr_email, decision_paragraph (the
            LLM-generated personalized rejection text - see
            services/rejection_drafter.py).

    Returns:
        str: Rendered HTML.
    """
    return render_template(REJECTION_TEMPLATE, context)


def render_test_round_html(context: dict = None) -> str:
    """
    Render the email-round-assessment template.

    Args:
        context (dict): candidate_name, job_role, assessment_name,
            assessment_duration, assessment_deadline,
            number_of_questions, test_link, hr_name, hr_designation,
            hr_email, company_name.

    Returns:
        str: Rendered HTML.
    """
    return render_template(TEST_ROUND_TEMPLATE, context)
