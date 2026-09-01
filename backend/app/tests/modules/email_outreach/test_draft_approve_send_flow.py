"""
End-to-end test of the draft -> approve -> send -> status lifecycle,
through the real HTTP routes (api.py), against an in-memory database.

The actual email transport (services/email_backend.py) is mocked out -
these tests verify the module's own logic (state transitions, gating,
token/subject handling), not that SMTP/Gmail/Postal actually deliver
mail. Backend integration is out of scope for a unit-level test.

candidate_source.get_candidate_source() is also mocked (see
_fake_candidate_source fixture) rather than depending on the real
testdata.json in this same directory - keeps these tests independent
of that file's contents, matching conftest.py's in-memory-SQLite
philosophy of not depending on external state.
"""

from unittest.mock import patch

import pytest

CANDIDATE_ID = "cand-test-001"
CANDIDATE_EMAIL = "candidate@example.com"
HR_ID = "hr-test-001"


class _FakeCandidateSource:
    """Stands in for JsonCandidateSource, backed by an in-memory catalog instead of testdata.json."""

    def fetch_round(self, round_id: str) -> dict:
        rounds = {
            "round-invite": {
                "round_id": "round-invite",
                "round_number": None,
                "round_type": "invitation",
                "round_name": "Interview Invitation",
            },
            "round-reject": {
                "round_id": "round-reject",
                "round_number": None,
                "round_type": "rejection",
                "round_name": "Application Update",
            },
        }
        if round_id not in rounds:
            from app.modules.email_outreach.services.candidate_source import CandidateNotFoundError
            raise CandidateNotFoundError(f"Unknown round_id: {round_id}")
        return rounds[round_id]

    def fetch_hr(self, hr_id: str) -> dict:
        if hr_id != HR_ID:
            from app.modules.email_outreach.services.candidate_source import CandidateNotFoundError
            raise CandidateNotFoundError(f"Unknown hr_id: {hr_id}")
        return {"hr_id": HR_ID, "name": "Jane HR", "designation": "Recruiter", "email": "hr@acme.com"}

    def build_template_context(self, candidate_id: str) -> dict:
        return {
            "name": "Jane Doe",
            "email": CANDIDATE_EMAIL,
            "job_role": "Backend Engineer",
            "job_description": "",
            "experience_required": "",
            "required_skills": "",
            "response_deadline": "",
            "hr_name": "Jane HR",
            "hr_designation": "Recruiter",
            "hr_email": "hr@acme.com",
        }


@pytest.fixture(autouse=True)
def fake_candidate_source():
    fake = _FakeCandidateSource()
    with patch(
        "app.modules.email_outreach.services.drafter.get_candidate_source", return_value=fake
    ), patch(
        "app.modules.email_outreach.services.approval_gate.get_candidate_source", return_value=fake
    ):
        yield fake


def _draft_payload(**overrides):
    payload = {
        "candidate_id": CANDIDATE_ID,
        "round_id": "round-invite",
    }
    payload.update(overrides)
    return payload


def test_draft_creates_pending_draft(client):
    response = client.post("/email/draft", json=_draft_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["candidate_id"] == CANDIDATE_ID
    assert body["status"] == "Draft"
    assert body["email_type"] == "interview_invitation"
    assert "Jane" in body["body"] or "Backend Engineer" in body["body"]


def test_draft_twice_for_same_candidate_conflicts(client):
    client.post("/email/draft", json=_draft_payload())
    second = client.post("/email/draft", json=_draft_payload())

    assert second.status_code == 409


def test_send_before_approval_is_rejected(client):
    client.post("/email/draft", json=_draft_payload())

    response = client.post("/email/send", json={"candidate_id": CANDIDATE_ID})

    assert response.status_code == 409


def test_approve_without_draft_is_not_found(client):
    response = client.post(
        "/email/approve", json={"candidate_id": "nonexistent", "approved_by_hr_id": HR_ID}
    )

    assert response.status_code == 404


@patch("app.modules.email_outreach.services.sender.get_email_backend")
def test_full_draft_approve_send_status_flow(mock_get_backend, client):
    mock_backend = mock_get_backend.return_value
    mock_backend.send.return_value = True

    draft = client.post("/email/draft", json=_draft_payload())
    assert draft.status_code == 200

    approve = client.post(
        "/email/approve", json={"candidate_id": CANDIDATE_ID, "approved_by_hr_id": HR_ID}
    )
    assert approve.status_code == 200
    assert approve.json()["status"] == "Approved"

    send = client.post("/email/send", json={"candidate_id": CANDIDATE_ID})
    assert send.status_code == 200
    assert send.json()["status"] == "sent"
    mock_backend.send.assert_called_once()

    status = client.get(f"/email/status/{CANDIDATE_ID}")
    assert status.status_code == 200
    body = status.json()
    assert body["email_status"] == "Sent"
    assert body["has_responded"] is False

    history = client.get(f"/email/status/{CANDIDATE_ID}/history")
    assert history.status_code == 200
    events = history.json()["history"]
    assert events[0]["event"] == "email_sent"


@patch("app.modules.email_outreach.services.sender.get_email_backend")
def test_send_uses_edited_body_when_hr_edits_before_approving(mock_get_backend, client):
    mock_backend = mock_get_backend.return_value
    mock_backend.send.return_value = True

    client.post("/email/draft", json=_draft_payload())
    client.post(
        "/email/approve",
        json={
            "candidate_id": CANDIDATE_ID,
            "approved_by_hr_id": HR_ID,
            "edited_body": "<p>Hand-edited body text</p>",
        },
    )
    client.post("/email/send", json={"candidate_id": CANDIDATE_ID})

    sent_message = mock_backend.send.call_args[0][0]
    assert "Hand-edited body text" in sent_message.get_body(preferencelist=("html",)).get_content()


def test_reject_draft_prevents_future_send(client):
    client.post("/email/draft", json=_draft_payload())

    reject = client.post("/email/reject", json={"candidate_id": CANDIDATE_ID})
    assert reject.status_code == 200
    assert reject.json()["status"] == "Rejected"

    approve = client.post(
        "/email/approve", json={"candidate_id": CANDIDATE_ID, "approved_by_hr_id": HR_ID}
    )
    assert approve.status_code == 404


def test_status_for_unknown_candidate_is_404(client):
    response = client.get("/email/status/does-not-exist")
    assert response.status_code == 404


@patch("app.modules.email_outreach.services.drafter.generate_rejection_paragraph")
def test_rejection_round_uses_rejection_template(mock_generate_paragraph, client):
    mock_generate_paragraph.return_value = "We will not be moving forward with your application."
    payload = _draft_payload(round_id="round-reject")

    response = client.post("/email/draft", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["email_type"] == "candidate_rejection"
    assert "moving forward" in body["body"]
    mock_generate_paragraph.assert_called_once()
