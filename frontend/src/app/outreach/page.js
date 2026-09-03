"use client";

import { useEffect, useState } from "react";
import { Mail, Send, Check, X, RefreshCw } from "lucide-react";
import AppShell from "@/components/shared/AppShell";
import StatusBadge from "@/components/shared/StatusBadge";
import EmptyState from "@/components/shared/EmptyState";
import LoadingSpinner from "@/components/shared/LoadingSpinner";
import DataTable from "@/components/shared/DataTable";
import {
  listCandidates,
  draftEmail,
  approveEmail,
  rejectEmail,
  sendEmail,
  getEmailStatus,
  ApiError,
} from "@/lib/api";

const ROUND_OPTIONS = [
  { id: "ROUND-1", label: "Interview Invitation" },
  { id: "ROUND-3", label: "Next Round Invitation" },
];

export default function OutreachPage() {
  const [candidates, setCandidates] = useState([]);
  const [loadingCandidates, setLoadingCandidates] = useState(true);
  const [selectedId, setSelectedId] = useState(null);
  const [roundId, setRoundId] = useState(ROUND_OPTIONS[0].id);
  const [draft, setDraft] = useState(null);
  const [editedBody, setEditedBody] = useState("");
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    listCandidates({ limit: 50 })
      .then((res) => setCandidates(res.items))
      .catch(() => setCandidates([]))
      .finally(() => setLoadingCandidates(false));
  }, []);

  const refreshStatus = async (candidateId) => {
    try {
      const s = await getEmailStatus(candidateId);
      setStatus(s);
    } catch {
      setStatus(null);
    }
  };

  const selectCandidate = async (candidate) => {
    setSelectedId(candidate.candidate_id);
    setDraft(null);
    setEditedBody("");
    setError(null);
    await refreshStatus(candidate.candidate_id);
  };

  const handleDraft = async () => {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await draftEmail(String(selectedId), roundId);
      setDraft(result);
      setEditedBody(result.body);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create draft");
    } finally {
      setBusy(false);
    }
  };

  const handleApprove = async () => {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      await approveEmail(String(selectedId), {
        editedBody: editedBody !== draft?.body ? editedBody : undefined,
      });
      setDraft((d) => (d ? { ...d, status: "Approved" } : d));
      await refreshStatus(selectedId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to approve draft");
    } finally {
      setBusy(false);
    }
  };

  const handleReject = async () => {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      await rejectEmail(String(selectedId));
      setDraft((d) => (d ? { ...d, status: "Rejected" } : d));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to reject draft");
    } finally {
      setBusy(false);
    }
  };

  const handleSend = async () => {
    if (!selectedId) return;
    setBusy(true);
    setError(null);
    try {
      await sendEmail(String(selectedId));
      setDraft((d) => (d ? { ...d, status: "Sent" } : d));
      await refreshStatus(selectedId);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to send email");
    } finally {
      setBusy(false);
    }
  };

  const selectedCandidate = candidates.find((c) => c.candidate_id === selectedId);

  return (
    <AppShell title="Email Outreach">
      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-6">
        {/* Candidate picker */}
        <div className="bg-card border border-border rounded-card overflow-hidden">
          <div className="p-4 border-b border-border">
            <h2 className="font-semibold text-text-primary text-sm">Candidates</h2>
          </div>
          {loadingCandidates ? (
            <LoadingSpinner />
          ) : candidates.length === 0 ? (
            <div className="p-6 text-sm text-text-secondary">No candidates found.</div>
          ) : (
            <ul className="max-h-[calc(100vh-260px)] overflow-y-auto">
              {candidates.map((c) => (
                <li key={c.candidate_id}>
                  <button
                    type="button"
                    onClick={() => selectCandidate(c)}
                    className={`w-full text-left px-4 py-3 border-b border-border transition duration-300 hover:bg-gray-50 ${
                      selectedId === c.candidate_id ? "bg-accent/10" : ""
                    }`}
                  >
                    <p className="font-medium text-text-primary text-sm">{c.name}</p>
                    <p className="text-xs text-text-secondary">
                      {c.current_job_title || "—"} · {c.experience_years ?? "?"} yrs
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Draft / approve / send panel */}
        <div className="bg-card border border-border rounded-card p-6">
          {!selectedCandidate ? (
            <EmptyState
              icon={Mail}
              title="Select a candidate"
              description="Choose a candidate from the list to draft, review, or send an outreach email."
            />
          ) : (
            <>
              <div className="flex items-start justify-between mb-6">
                <div>
                  <h2 className="text-lg font-semibold text-text-primary">
                    {selectedCandidate.name}
                  </h2>
                  <p className="text-sm text-text-secondary">{selectedCandidate.email}</p>
                </div>
                {status && <StatusBadge status={status.email_status} />}
              </div>

              {error && (
                <div className="mb-4 px-4 py-3 rounded-input bg-error-bg text-error-text text-sm">
                  {error}
                </div>
              )}

              {!draft ? (
                <div className="flex items-end gap-3">
                  <div className="flex-1">
                    <label className="block text-xs font-semibold text-text-secondary mb-2">
                      Email purpose
                    </label>
                    <select
                      value={roundId}
                      onChange={(e) => setRoundId(e.target.value)}
                      className="w-full h-input px-4 rounded-input border border-border focus:outline-none focus:ring-2 focus:ring-accent"
                    >
                      {ROUND_OPTIONS.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    type="button"
                    onClick={handleDraft}
                    disabled={busy}
                    className="h-input px-6 bg-primary text-white rounded-button font-medium transition duration-300 hover:bg-accent disabled:opacity-60"
                  >
                    {busy ? "Drafting…" : "Generate draft"}
                  </button>
                </div>
              ) : (
                <div className="flex flex-col gap-4">
                  <div className="flex items-center justify-between">
                    <StatusBadge status={draft.status} />
                    <span className="text-xs text-text-secondary">Subject: {draft.subject}</span>
                  </div>

                  <textarea
                    value={editedBody}
                    onChange={(e) => setEditedBody(e.target.value)}
                    readOnly={draft.status !== "Draft"}
                    className="w-full h-96 p-4 rounded-input border border-border font-mono text-xs leading-relaxed focus:outline-none focus:ring-2 focus:ring-accent disabled:bg-gray-50"
                  />

                  <div className="flex items-center gap-3">
                    {draft.status === "Draft" && (
                      <>
                        <button
                          type="button"
                          onClick={handleApprove}
                          disabled={busy}
                          className="flex items-center gap-2 h-input px-6 bg-primary text-white rounded-button font-medium transition duration-300 hover:bg-accent disabled:opacity-60"
                        >
                          <Check size={16} /> Approve
                        </button>
                        <button
                          type="button"
                          onClick={handleReject}
                          disabled={busy}
                          className="flex items-center gap-2 h-input px-6 border border-border rounded-button font-medium text-text-secondary transition duration-300 hover:bg-gray-50 disabled:opacity-60"
                        >
                          <X size={16} /> Reject
                        </button>
                      </>
                    )}
                    {draft.status === "Approved" && (
                      <button
                        type="button"
                        onClick={handleSend}
                        disabled={busy}
                        className="flex items-center gap-2 h-input px-6 bg-primary text-white rounded-button font-medium transition duration-300 hover:bg-accent disabled:opacity-60"
                      >
                        <Send size={16} /> Send
                      </button>
                    )}
                    {draft.status === "Sent" && (
                      <span className="text-sm text-success-text font-medium">
                        Email sent successfully.
                      </span>
                    )}
                    {draft.status === "Rejected" && (
                      <span className="text-sm text-text-secondary">Draft rejected.</span>
                    )}
                    <button
                      type="button"
                      onClick={() => refreshStatus(selectedId)}
                      className="ml-auto flex items-center gap-2 text-xs text-text-secondary hover:text-text-primary transition duration-300"
                    >
                      <RefreshCw size={14} /> Refresh status
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
