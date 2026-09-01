"""
Candidate + job + HR data source.

Today: reads settings.testdata_json_path (candidates/jobs/hrs arrays,
looked up by candidate_id/job_id/hr_id). Future: CANDIDATE_SOURCE=api
will pull from a teammate's recruitment API instead - ApiCandidateSource
is the integration point for that. services/drafter.py only depends on
get_candidate_source(), never on a specific source, so switching is a
one-line settings change (same pattern as services/email_backend.py).
"""

import json
import logging
from app.core.config import settings

log = logging.getLogger(__name__)


class CandidateNotFoundError(Exception):
    """No candidate/job/hr record exists for the given id."""


class JsonCandidateSource:
    """Reads candidate/job/hr records from a local JSON file, looked up by id."""

    def _load(self) -> dict:
        with open(settings.testdata_json_path, encoding="utf-8") as f:
            return json.load(f)

    def fetch_candidate(self, candidate_id: str) -> dict:
        """
        Look up a candidate by candidate_id.

        Returns:
            dict: candidate record - "name", "email", "job_id", "hr_id",
                plus the other candidate fields from testdata.json.

        Raises:
            CandidateNotFoundError: no candidate with this candidate_id.
        """
        for candidate in self._load().get("candidates", []):
            if candidate.get("candidate_id") == candidate_id:
                return candidate
        raise CandidateNotFoundError(f"Unknown candidate_id: {candidate_id}")

    def fetch_job(self, job_id: str) -> dict:
        """
        Look up a job by job_id.

        Returns:
            dict: job record - "job_role", "job_description",
                "experience_required", "required_skills",
                "response_deadline", plus other job fields.

        Raises:
            CandidateNotFoundError: no job with this job_id.
        """
        for job in self._load().get("jobs", []):
            if job.get("job_id") == job_id:
                return job
        raise CandidateNotFoundError(f"Unknown job_id: {job_id}")

    def fetch_hr(self, hr_id: str) -> dict:
        """
        Look up an HR contact by hr_id.

        Returns:
            dict: hr record - "name", "designation", "email".

        Raises:
            CandidateNotFoundError: no HR with this hr_id.
        """
        for hr in self._load().get("hrs", []):
            if hr.get("hr_id") == hr_id:
                return hr
        raise CandidateNotFoundError(f"Unknown hr_id: {hr_id}")

    def fetch_round(self, round_id: str) -> dict:
        """
        Look up a test round by round_id.

        Returns:
            dict: round record - "round_name", "round_description",
                "round_duration", "round_deadline", "number_of_questions".

        Raises:
            CandidateNotFoundError: no round with this round_id.
        """
        for round_ in self._load().get("rounds", []):
            if round_.get("round_id") == round_id:
                return round_
        raise CandidateNotFoundError(f"Unknown round_id: {round_id}")

    def build_template_context(self, candidate_id: str) -> dict:
        """
        Resolve a candidate_id into everything the invite/rejection
        template needs, by following the candidate's job_id/hr_id.

        Returns:
            dict: "name"/"email" for the recipient, plus job_role,
                job_description, experience_required, required_skills,
                response_deadline, hr_name, hr_designation, hr_email.
        """
        candidate = self.fetch_candidate(candidate_id)
        return self._context_for(candidate)

    def _context_for(self, candidate: dict) -> dict:
        job = self.fetch_job(candidate["job_id"]) if candidate.get("job_id") else {}
        hr = self.fetch_hr(candidate["hr_id"]) if candidate.get("hr_id") else {}

        return {
            "name": candidate["name"],
            "email": candidate["email"],
            "job_role": job.get("job_role", ""),
            "job_description": job.get("job_description", ""),
            "experience_required": job.get("experience_required", ""),
            "required_skills": ", ".join(job.get("required_skills", [])),
            "response_deadline": job.get("response_deadline", ""),
            "hr_name": hr.get("name", ""),
            "hr_designation": hr.get("designation", ""),
            "hr_email": hr.get("email", ""),
        }

class ApiCandidateSource:
    """
    Reads candidate/job/hr data from the recruitment API.

    Integration point for the teammate building that API - implement
    these to call it and return the same dict shapes as
    JsonCandidateSource so services/drafter.py doesn't need to change.
    """

    def fetch_candidate(self, candidate_id: str) -> dict:
        raise NotImplementedError(
            "ApiCandidateSource is not implemented yet - "
            "set candidate_source=json until the API is ready."
        )

    def fetch_job(self, job_id: str) -> dict:
        raise NotImplementedError(
            "ApiCandidateSource is not implemented yet - "
            "set candidate_source=json until the API is ready."
        )

    def fetch_hr(self, hr_id: str) -> dict:
        raise NotImplementedError(
            "ApiCandidateSource is not implemented yet - "
            "set candidate_source=json until the API is ready."
        )

    def fetch_round(self, round_id: str) -> dict:
        raise NotImplementedError(
            "ApiCandidateSource is not implemented yet - "
            "set candidate_source=json until the API is ready."
        )

    def build_template_context(self, candidate_id: str) -> dict:
        raise NotImplementedError(
            "ApiCandidateSource is not implemented yet - "
            "set candidate_source=json until the API is ready."
        )


def get_candidate_source():
    """
    Build the configured candidate data source.

    Returns:
        JsonCandidateSource or ApiCandidateSource, per settings.candidate_source.
    """
    if settings.candidate_source == "api":
        return ApiCandidateSource()

    return JsonCandidateSource()
