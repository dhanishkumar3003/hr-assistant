"""
Email message construction - building outgoing EmailMessage objects.

Split out of a combined "email_handler" module: this half only ever
builds an outgoing email; services/email_parser.py only ever reads an
incoming one. Neither depends on the other.
"""

import logging
from email.message import EmailMessage
from email.utils import make_msgid
from app.core.config import settings
from app.modules.email_outreach.services.email_template_service import (
    render_invite_html,
    render_response_html,
    render_test_round_html,
)

log = logging.getLogger(__name__)


def build_invite_message(
    to_addr: str,
    candidate_name: str,
    subject: str,
    template_context: dict = None,
) -> EmailMessage:
    """
    Build an invitation email message from the HTML invite template
    (templates/interview_invitation.html).

    Args:
        to_addr (str): Recipient email address.
        candidate_name (str): Name to use in greeting (can be empty).
        subject (str): Email subject line with tracking token.
        template_context (dict): Template values - job_role,
            job_description, experience_required, required_skills,
            response_deadline, hr_name, hr_designation, hr_email,
            company_name, candidate_id (used for the Reply-To plus-tag,
            see services/reply_matcher.py). Reply-only response model -
            no accept/reject link. Any can be omitted (renders blank).

    Returns:
        EmailMessage: Constructed email message (plain-text fallback +
            HTML alternative). Message-ID and (if candidate_id is
            given) a plus-tagged Reply-To are set for reply matching -
            see services/reply_matcher.py.
    """
    context = {"candidate_name": candidate_name, **(template_context or {})}
    html_body = render_invite_html(context)

    job_role = context.get("job_role")
    role_suffix = f" for the {job_role} position" if job_role else ""
    plain_body = (
        f"Hi {candidate_name or ''},\n\n"
        f"We'd like to invite you to continue our recruitment process"
        f"{role_suffix}.\n\n"
        f"Please reply to this email to confirm your interest.\n\n"
        f"(View this email in an HTML-capable client for full details.)"
    )

    message = EmailMessage()
    message["From"] = settings.gmail_address
    message["To"] = to_addr
    message["Subject"] = subject
    message["Message-ID"] = make_msgid()

    candidate_id = context.get("candidate_id")
    if candidate_id and "@" in settings.gmail_address:
        local_part, domain = settings.gmail_address.split("@", 1)
        message["Reply-To"] = f"{local_part}+{candidate_id}@{domain}"

    message.set_content(plain_body)
    message.add_alternative(html_body, subtype="html")

    return message


def build_prebuilt_message(
    to_addr: str,
    subject: str,
    html_body: str,
    candidate_id: str = None,
) -> EmailMessage:
    """
    Wrap an already-rendered HTML body (e.g. an HR-approved draft from
    services/drafter.py / approval_gate.py) into a sendable EmailMessage,
    with the same Message-ID + candidate_id-tagged Reply-To that
    build_invite_message sets - so replies to an approved draft are
    matched back the same way as any other invite (see
    services/reply_matcher.py).

    Args:
        to_addr (str): Recipient email address.
        subject (str): Final subject line (tracking token already
            appended by the caller).
        html_body (str): Rendered HTML body to send as-is.
        candidate_id (str): Public candidate identifier, used for the
            Reply-To plus-tag.

    Returns:
        EmailMessage: Constructed email message (plain-text fallback +
            HTML alternative).
    """
    message = EmailMessage()
    message["From"] = settings.gmail_address
    message["To"] = to_addr
    message["Subject"] = subject
    message["Message-ID"] = make_msgid()

    if candidate_id and "@" in settings.gmail_address:
        local_part, domain = settings.gmail_address.split("@", 1)
        message["Reply-To"] = f"{local_part}+{candidate_id}@{domain}"

    message.set_content("Please reply to this email to confirm your interest. (View this email in an HTML-capable client for full details.)")
    message.add_alternative(html_body, subtype="html")

    return message


def build_response_message(
    to_addr: str,
    subject: str,
    template_context: dict,
) -> EmailMessage:
    """
    Build a recruitment-response confirmation email from the response
    template (templates/recruitment_response.html).

    Args:
        to_addr (str): Recipient email address.
        subject (str): Email subject line.
        template_context (dict): email_title, header_subtitle,
            candidate_name, message_1, message_2, response_section
            (HTML fragment), closing_message, hr_name, hr_designation,
            hr_email, company_name.

    Returns:
        EmailMessage: Constructed email message (plain-text fallback +
            HTML alternative).
    """
    html_body = render_response_html(template_context)

    plain_body = "\n\n".join(
        filter(
            None,
            [
                f"Hi {template_context.get('candidate_name', '')},",
                template_context.get("message_1"),
                template_context.get("message_2"),
                template_context.get("closing_message"),
                "(View this email in an HTML-capable client for full details.)",
            ],
        )
    )

    message = EmailMessage()
    message["From"] = settings.gmail_address
    message["To"] = to_addr
    message["Subject"] = subject
    message.set_content(plain_body)
    message.add_alternative(html_body, subtype="html")

    return message


def build_test_round_message(
    to_addr: str,
    subject: str,
    template_context: dict,
) -> EmailMessage:
    """
    Build an assessment-link email from the test-round template
    (templates/email_round_test.html).

    Args:
        to_addr (str): Recipient email address.
        subject (str): Email subject line.
        template_context (dict): candidate_name, job_role, test_link,
            assessment_name, round_description, assessment_duration,
            assessment_deadline, number_of_questions, hr_name,
            hr_designation, hr_email, company_name. Assessment fields
            are optional (render blank if omitted).

    Returns:
        EmailMessage: Constructed email message (plain-text fallback +
            HTML alternative).
    """
    html_body = render_test_round_html(template_context)

    job_role = template_context.get("job_role")
    role_suffix = f" the {job_role} opportunity" if job_role else " this opportunity"
    plain_body = (
        f"Hi {template_context.get('candidate_name', '')},\n\n"
        f"Thank you for confirming your interest in{role_suffix}. "
        f"As the next step, please complete a short assessment:\n\n"
        f"{template_context.get('test_link', '')}\n\n"
        f"Please complete it by {template_context.get('assessment_deadline', 'the deadline noted above')}."
    )

    message = EmailMessage()
    message["From"] = settings.gmail_address
    message["To"] = to_addr
    message["Subject"] = subject
    message.set_content(plain_body)
    message.add_alternative(html_body, subtype="html")

    return message
