import enum


class CandidateStatus(str, enum.Enum):
    FILTERED = "filtered"
    CONTACTED = "contacted"
    RESPONDED = "responded"
    INACTIVE = "inactive"
    ROUND1_SCHEDULED = "round1_scheduled"
    ROUND1_SCORED = "round1_scored"
    SHORTLISTED = "shortlisted"          # after Gate 1
    ROUND2_SCHEDULED = "round2_scheduled"
    ROUND2_SCORED = "round2_scored"
    SELECTED = "selected"                # after Gate 2
    REJECTED = "rejected"                # after Gate 2


class EmailPurpose(str, enum.Enum):
    INITIAL_OUTREACH = "initial_outreach"
    ROUND1_INVITE = "round1_invite"
    ROUND2_INVITE = "round2_invite"
    REJECTION = "rejection"


class EmailStatus(str, enum.Enum):
    DRAFTED = "drafted"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SENT = "sent"
    REPLIED = "replied"
    REJECTED = "rejected"