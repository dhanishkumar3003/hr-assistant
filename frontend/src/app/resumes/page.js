"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { UploadCloud, FileText, RefreshCw } from "lucide-react";
import AppShell from "@/components/shared/AppShell";
import DataTable from "@/components/shared/DataTable";
import StatusBadge from "@/components/shared/StatusBadge";
import EmptyState from "@/components/shared/EmptyState";
import { uploadResume, bulkUploadResumes, getResumeStatus, ApiError } from "@/lib/api";

const POLL_INTERVAL_MS = 4000;
const IN_FLIGHT_STATUSES = new Set(["UPLOADED", "PROCESSING", "EXTRACTED"]);

export default function ResumesPage() {
  const [rows, setRows] = useState([]); // { resume_id, file_name, processing_status, candidate_id, error }
  const [dragActive, setDragActive] = useState(false);
  const fileInputRef = useRef(null);
  const pollTimers = useRef({});

  const upsertRow = useCallback((resumeId, patch) => {
    setRows((prev) => {
      const idx = prev.findIndex((r) => r.resume_id === resumeId);
      if (idx === -1) return prev;
      const next = [...prev];
      next[idx] = { ...next[idx], ...patch };
      return next;
    });
  }, []);

  const pollStatus = useCallback(
    (resumeId) => {
      const tick = async () => {
        try {
          const status = await getResumeStatus(resumeId);
          upsertRow(resumeId, status);
          if (IN_FLIGHT_STATUSES.has(status.processing_status)) {
            pollTimers.current[resumeId] = setTimeout(tick, POLL_INTERVAL_MS);
          } else {
            delete pollTimers.current[resumeId];
          }
        } catch {
          delete pollTimers.current[resumeId];
        }
      };
      pollTimers.current[resumeId] = setTimeout(tick, POLL_INTERVAL_MS);
    },
    [upsertRow]
  );

  useEffect(() => {
    const timers = pollTimers.current;
    return () => {
      Object.values(timers).forEach(clearTimeout);
    };
  }, []);

  const handleFiles = useCallback(
    async (fileList) => {
      const files = Array.from(fileList || []);
      if (files.length === 0) return;

      if (files.length === 1) {
        const file = files[0];
        const placeholderId = `pending-${Date.now()}`;
        setRows((prev) => [
          { resume_id: placeholderId, file_name: file.name, processing_status: "UPLOADING" },
          ...prev,
        ]);
        try {
          const accepted = await uploadResume(file);
          setRows((prev) =>
            prev.map((r) => (r.resume_id === placeholderId ? { ...accepted } : r))
          );
          pollStatus(accepted.resume_id);
        } catch (err) {
          const message = err instanceof ApiError ? err.message : "Upload failed";
          setRows((prev) =>
            prev.map((r) =>
              r.resume_id === placeholderId
                ? { ...r, processing_status: "FAILED", failure_reason: message }
                : r
            )
          );
        }
        return;
      }

      // Bulk path — single request, mixed accepted/rejected result.
      const placeholders = files.map((file, i) => ({
        resume_id: `pending-bulk-${Date.now()}-${i}`,
        file_name: file.name,
        processing_status: "UPLOADING",
      }));
      setRows((prev) => [...placeholders, ...prev]);

      try {
        const result = await bulkUploadResumes(files);
        setRows((prev) => {
          let next = [...prev];
          result.accepted.forEach((item, i) => {
            const placeholderId = placeholders[i]?.resume_id;
            next = next.map((r) => (r.resume_id === placeholderId ? { ...item } : r));
            pollStatus(item.resume_id);
          });
          result.rejected.forEach((item, i) => {
            const placeholderId = placeholders[result.accepted.length + i]?.resume_id;
            next = next.map((r) =>
              r.resume_id === placeholderId
                ? { ...r, processing_status: "FAILED", failure_reason: item.message }
                : r
            );
          });
          return next;
        });
      } catch (err) {
        const message = err instanceof ApiError ? err.message : "Bulk upload failed";
        setRows((prev) =>
          prev.map((r) =>
            placeholders.some((p) => p.resume_id === r.resume_id)
              ? { ...r, processing_status: "FAILED", failure_reason: message }
              : r
          )
        );
      }
    },
    [pollStatus]
  );

  const onDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <AppShell title="Resume Repository">
      <div className="max-w-5xl">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={onDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`bg-card border-2 border-dashed rounded-card p-16 text-center cursor-pointer transition duration-300 ${
            dragActive ? "border-accent bg-accent/5" : "border-border hover:border-primary/30"
          }`}
        >
          <UploadCloud size={40} className="mx-auto mb-4 text-primary" />
          <p className="text-lg font-semibold text-text-primary mb-1">
            Drag &amp; drop resumes, or click to browse
          </p>
          <p className="text-sm text-text-secondary">
            PDF, DOCX, DOC or TXT · up to 10&nbsp;MB each · up to 20 files at once
          </p>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.doc,.txt"
            className="hidden"
            onChange={(e) => {
              handleFiles(e.target.files);
              e.target.value = "";
            }}
          />
        </div>

        <div className="mt-8">
          <h2 className="text-lg font-semibold text-text-primary mb-4">Upload status &amp; history</h2>
          {rows.length === 0 ? (
            <EmptyState
              icon={FileText}
              title="No resumes uploaded yet"
              description="Drag files onto the box above, or click it to browse your computer."
            />
          ) : (
            <DataTable
              rowKey="resume_id"
              rows={rows}
              columns={[
                {
                  key: "file_name",
                  header: "File",
                  render: (r) => (
                    <span className="flex items-center gap-2 font-medium">
                      <FileText size={16} className="text-text-secondary shrink-0" />
                      {r.file_name}
                    </span>
                  ),
                },
                {
                  key: "processing_status",
                  header: "Status",
                  render: (r) =>
                    r.processing_status === "UPLOADING" ? (
                      <span className="flex items-center gap-2 text-text-secondary text-sm">
                        <RefreshCw size={14} className="animate-spin" /> Uploading…
                      </span>
                    ) : (
                      <StatusBadge status={r.processing_status} />
                    ),
                },
                {
                  key: "candidate_id",
                  header: "Candidate",
                  render: (r) =>
                    r.candidate_id ? (
                      <span className="font-mono text-xs">#{r.candidate_id}</span>
                    ) : r.failure_reason ? (
                      <span className="text-error-text text-xs">{r.failure_reason}</span>
                    ) : (
                      "—"
                    ),
                },
              ]}
            />
          )}
        </div>
      </div>
    </AppShell>
  );
}
