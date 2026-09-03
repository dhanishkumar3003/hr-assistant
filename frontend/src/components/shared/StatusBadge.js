const VARIANTS = {
  success: "bg-success-bg text-success-text",
  warning: "bg-warning-bg text-warning-text",
  error: "bg-error-bg text-error-text",
  info: "bg-info-bg text-info-text",
  neutral: "bg-border text-text-secondary",
};

// Maps backend status strings (candidate pipeline + email draft states) to a badge variant.
const STATUS_VARIANT = {
  FILTERED: "neutral",
  CONTACTED: "info",
  RESPONDED: "success",
  INACTIVE: "neutral",
  ROUND1_SCORED: "info",
  SHORTLISTED: "success",
  ROUND2_SCORED: "info",
  FINAL_DECISION: "success",

  UPLOADED: "neutral",
  PROCESSING: "warning",
  EXTRACTED: "info",
  COMPLETED: "success",
  FAILED: "error",
  REJECTED: "error",

  Draft: "warning",
  Approved: "info",
  Sent: "success",
  Rejected: "error",
};

function toLabel(status) {
  return String(status).replaceAll("_", " ");
}

export default function StatusBadge({ status, variant }) {
  const resolved = variant || STATUS_VARIANT[status] || "neutral";
  return (
    <span
      className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold ${VARIANTS[resolved]}`}
    >
      {toLabel(status)}
    </span>
  );
}
