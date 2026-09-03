const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    let detail = { error: "UNKNOWN_ERROR", message: res.statusText };
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // no JSON body
    }
    throw new ApiError(res.status, detail.error, detail.message);
  }

  if (res.status === 204) return null;
  return res.json();
}

// ---- Module 1: Resume Repository & Ingestion ----------------------------
export function uploadResume(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/resumes/upload", { method: "POST", body: form });
}

export function bulkUploadResumes(files) {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));
  return request("/resumes/bulk-upload", { method: "POST", body: form });
}

export function getResumeStatus(resumeId) {
  return request(`/resumes/${resumeId}/status`);
}

export function listCandidates(params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")
  ).toString();
  return request(`/candidates${query ? `?${query}` : ""}`);
}

export function getCandidate(candidateId) {
  return request(`/candidates/${candidateId}`);
}

// ---- Module 3: Email Outreach --------------------------------------------
export function draftEmail(candidateId, roundId) {
  return request("/email/draft", {
    method: "POST",
    body: JSON.stringify({ candidate_id: candidateId, round_id: roundId }),
  });
}

export function approveEmail(candidateId, { approvedByHrId, editedBody } = {}) {
  return request("/email/approve", {
    method: "POST",
    body: JSON.stringify({
      candidate_id: candidateId,
      approved_by_hr_id: approvedByHrId,
      edited_body: editedBody,
    }),
  });
}

export function rejectEmail(candidateId) {
  return request("/email/reject", {
    method: "POST",
    body: JSON.stringify({ candidate_id: candidateId }),
  });
}

export function sendEmail(candidateId) {
  return request("/email/send", {
    method: "POST",
    body: JSON.stringify({ candidate_id: candidateId }),
  });
}

export function getEmailStatus(candidateId) {
  return request(`/email/status/${candidateId}`);
}

export { ApiError, API_BASE_URL };
