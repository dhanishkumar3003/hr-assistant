"use client";

import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
import QuestionDisplay from "../../../components/interview/QuestionDisplay";
import RecorderControls from "../../../components/interview/RecorderControls";
import MicCheck from "../../../components/interview/MicCheck";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const PLAY_DELAY_MS = 2000;
const TTS_FETCH_TIMEOUT_MS = 15000;
const AUTH_TIMEOUT_MS = 10000;
const NEXT_Q_TIMEOUT_MS = 10000;
const STT_BASE_MS = 5000;
const STT_PER_SECOND_MS = 2000;
const STT_MIN_TIMEOUT_MS = 10000;
const STT_MAX_TIMEOUT_MS = 45000;

function withTimeout(ms) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  return { signal: controller.signal, clear: () => clearTimeout(timer) };
}

export default function InterviewPage() {
  const params = useParams();
  const token = params.token;
  const storageKey = `voice_interview_${token}`;

  const [candidateId, setCandidateId] = useState("");
  const [accessCode, setAccessCode] = useState("");
  const [interviewId, setInterviewId] = useState(null);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [questionText, setQuestionText] = useState("");
  const [status, setStatus] = useState("checking_resume");
  const [transcript, setTranscript] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const lastRecordingRef = useRef(null);

  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setStatus("unsupported");
      return;
    }
    tryResume();
  }, []);

  async function tryResume() {
    const saved = sessionStorage.getItem(storageKey);
    if (!saved) {
      setStatus("credentials");
      return;
    }

    const { interviewId: savedId, totalQuestions: savedTotal } = JSON.parse(saved);
    setInterviewId(savedId);
    setTotalQuestions(savedTotal);

    const { signal, clear } = withTimeout(NEXT_Q_TIMEOUT_MS);
    try {
      const res = await fetch(`${API_BASE_URL}/interview/${savedId}/next-question?from_index=-1`, { signal });
      clear();
      if (!res.ok) throw new Error("resume fetch failed");
      const data = await res.json();

      if (data.status === "completed") {
        setStatus("completed");
        sessionStorage.removeItem(storageKey);
        return;
      }

      setQuestionIndex(data.question_index);
      setQuestionText(data.question);
      setStatus("ready_to_answer");
    } catch (err) {
      clear();
      console.warn("Resume failed, starting fresh:", err);
      sessionStorage.removeItem(storageKey);
      setStatus("credentials");
    }
  }

  async function handleAuthenticate(e) {
    e.preventDefault();
    setErrorMessage("");
    setStatus("authenticating");

    const { signal, clear } = withTimeout(AUTH_TIMEOUT_MS);
    try {
      const res = await fetch(`${API_BASE_URL}/interview/authenticate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_id: candidateId.trim(),
          token,
          access_code: accessCode.trim(),
        }),
        signal,
      });
      clear();

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setErrorMessage(data.detail || "Invalid credentials or link.");
        setStatus("credentials");
        return;
      }

      const data = await res.json();
      setInterviewId(data.interview_id);
      setQuestionIndex(data.question_index);
      setTotalQuestions(data.total_questions);
      setQuestionText(data.question);

      sessionStorage.setItem(storageKey, JSON.stringify({
        interviewId: data.interview_id,
        totalQuestions: data.total_questions,
      }));

      if (data.question_index === 0) {
        setStatus("mic_check");
      } else {
        schedulePlayback(data.interview_id, data.question_index);
      }
      
    } catch (err) {
      clear();
      const timedOut = err.name === "AbortError";
      setErrorMessage(timedOut ? "Request timed out. Please try again." : "Couldn't reach the server. Please try again.");
      setStatus("credentials");
    }
  }

  function handleMicCheckConfirmed() {
    schedulePlayback(interviewId, questionIndex);
  }

  function schedulePlayback(id, index) {
    setStatus("playing_audio");
    setTimeout(async () => {
      const { signal, clear } = withTimeout(TTS_FETCH_TIMEOUT_MS);
      let objectUrl = null;
      try {
        const res = await fetch(`${API_BASE_URL}/interview/${id}/questions/${index}/audio`, { signal });
        clear();
        if (!res.ok) throw new Error("audio fetch failed");

        const blob = await res.blob();
        objectUrl = URL.createObjectURL(blob);
        const audio = new Audio(objectUrl);
        audio.onended = () => {
          if (objectUrl) URL.revokeObjectURL(objectUrl);
          setStatus("ready_to_answer");
        };
        audio.onerror = () => {
          if (objectUrl) URL.revokeObjectURL(objectUrl);
          setStatus("ready_to_answer");
        };
        await audio.play();
      } catch (err) {
        clear();
        console.warn("Question audio failed or timed out:", err);
        setErrorMessage("Couldn't load the question audio — you can still read it above and answer.");
        setStatus("ready_to_answer");
      }
    }, PLAY_DELAY_MS);
  }

  function handleRecordingComplete(blob, startTs, endTs) {
    lastRecordingRef.current = { blob, startTs, endTs };
    setErrorMessage("");
    attemptSubmit(blob, startTs, endTs);
  }

  function handleRecordingError(message) {
    setErrorMessage(message);
  }

  async function attemptSubmit(blob, startTs, endTs) {
    setStatus("submitting");
    setErrorMessage("");

    const durationSeconds = Math.max(endTs - startTs, 1);
    const dynamicTimeoutMs = Math.min(
      Math.max(STT_BASE_MS + durationSeconds * STT_PER_SECOND_MS, STT_MIN_TIMEOUT_MS),
      STT_MAX_TIMEOUT_MS
    );

    const formData = new FormData();
    formData.append("audio", blob, "answer.webm");
    formData.append("start_ts", String(startTs));
    formData.append("end_ts", String(endTs));

    const { signal, clear } = withTimeout(dynamicTimeoutMs);
    try {
      const res = await fetch(
        `${API_BASE_URL}/interview/${interviewId}/questions/${questionIndex}/answer`,
        { method: "POST", body: formData, signal }
      );
      clear();

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setErrorMessage(data.detail || "The server had trouble processing your answer.");
        setStatus("submit_failed");
        return;
      }

      const data = await res.json();
      const cleanTranscript = (data.transcript || "").trim();

      if (!cleanTranscript) {
        setErrorMessage("We couldn't hear a clear answer. Please try again.");
        setStatus("ready_to_answer");
        return;
      }

      setTranscript(cleanTranscript);
      setStatus("transcript_ready");
    } catch (err) {
      clear();
      const timedOut = err.name === "AbortError";
      setErrorMessage(
        timedOut
          ? "This is taking longer than expected. Your answer is still saved — you can retry submitting it."
          : "Network connection lost. Check your connection and retry submitting."
      );
      setStatus("submit_failed");
    }
  }

  function retrySubmit() {
    if (lastRecordingRef.current) {
      const { blob, startTs, endTs } = lastRecordingRef.current;
      attemptSubmit(blob, startTs, endTs);
    }
  }

  function reRecord() {
    setTranscript("");
    setErrorMessage("");
    lastRecordingRef.current = null;
    setStatus("ready_to_answer");
  }

  async function goToNextQuestion() {
    setStatus("loading");
    setErrorMessage("");
    const { signal, clear } = withTimeout(NEXT_Q_TIMEOUT_MS);
    try {
      const res = await fetch(
        `${API_BASE_URL}/interview/${interviewId}/next-question?from_index=${questionIndex}`,
        { signal }
      );
      clear();
      if (!res.ok) throw new Error(`Request failed: ${res.status}`);
      const data = await res.json();

      if (data.status === "completed") {
        setStatus("completed");
        sessionStorage.removeItem(storageKey);
        return;
      }

      setQuestionIndex(data.question_index);
      setQuestionText(data.question);
      setTranscript("");
      schedulePlayback(interviewId, data.question_index);
    } catch (err) {
      clear();
      const timedOut = err.name === "AbortError";
      setErrorMessage(timedOut ? "Request timed out." : "Couldn't load the next question.");
      setStatus("error");
    }
  }

  const showCard = ["playing_audio", "ready_to_answer", "submitting", "submit_failed", "transcript_ready"].includes(status);

  return (
    <main className="min-h-screen flex items-center justify-center p-6 bg-[var(--color-background)]">
      {status === "checking_resume" && (
        <p className="text-[var(--color-text-secondary)] text-sm">Loading...</p>
      )}

      {status === "unsupported" && (
        <div className="w-full max-w-xl bg-[var(--color-error-bg)] text-[var(--color-error-text)] rounded-[var(--radius-card)] px-6 py-5 text-sm text-center">
          <p>Your browser doesn't support audio recording. Please switch to a recent version of Chrome, Edge, or Firefox.</p>
        </div>
      )}

      {(status === "credentials" || status === "authenticating") && (
        <form
          onSubmit={handleAuthenticate}
          className="w-full max-w-sm bg-[var(--color-card)] border border-[var(--color-border)] rounded-[var(--radius-card)] shadow-sm p-8"
        >
          <h1 className="text-xl font-semibold text-[var(--color-primary)] mb-1">Enter your details</h1>
          <p className="text-[var(--color-text-secondary)] text-sm mb-6">
            Use the candidate ID and access code from your invitation email.
          </p>

          {errorMessage && (
            <p className="text-xs text-[var(--color-error-text)] bg-[var(--color-error-bg)] rounded-lg px-3 py-2 mb-4">{errorMessage}</p>
          )}

          <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">Candidate ID</label>
          <input
            value={candidateId}
            onChange={(e) => setCandidateId(e.target.value)}
            required
            className="w-full h-[var(--height-input)] rounded-[var(--radius-input)] border border-[var(--color-border)] px-4 mb-4 text-sm text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
          />

          <label className="block text-xs font-medium text-[var(--color-text-secondary)] mb-1">Access Code</label>
          <input
            value={accessCode}
            onChange={(e) => setAccessCode(e.target.value)}
            required
            className="w-full h-[var(--height-input)] rounded-[var(--radius-input)] border border-[var(--color-border)] px-4 mb-6 text-sm text-[var(--color-text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]"
          />

          <button
            type="submit"
            disabled={status === "authenticating"}
            className="w-full rounded-[var(--radius-button)] bg-[var(--color-primary)] text-white font-medium py-4 transition duration-300 hover:bg-[var(--color-accent)] disabled:opacity-60"
          >
            {status === "authenticating" ? "Verifying..." : "Continue"}
          </button>
        </form>
      )}

      {status === "mic_check" && <MicCheck onConfirmed={handleMicCheckConfirmed} />}

      {status === "loading" && (
        <p className="text-[var(--color-text-secondary)] text-sm">Loading...</p>
      )}

      {status === "error" && (
        <div className="w-full max-w-xl bg-[var(--color-error-bg)] text-[var(--color-error-text)] rounded-[var(--radius-card)] px-6 py-5 text-sm text-center">
          <p className="mb-4">{errorMessage || "Something went wrong."}</p>
          <button onClick={() => setStatus("ready_to_answer")} className="underline font-medium mr-4">
            Try again
          </button>
        </div>
      )}

      {status === "completed" && (
        <div className="w-full max-w-xl bg-[var(--color-card)] border border-[var(--color-border)] rounded-[var(--radius-card)] shadow-sm p-8 text-center">
          <div className="w-12 h-12 rounded-full bg-[#DCFCE7] flex items-center justify-center mx-auto mb-4">
            <span className="text-[#166534] text-2xl leading-none">✓</span>
          </div>
          <h1 className="text-xl font-semibold text-[var(--color-primary)] mb-1">Interview complete</h1>
          <p className="text-[var(--color-text-secondary)] text-sm mb-4">
            Thanks for your time. Your responses have been recorded.
          </p>
          <div className="bg-[var(--color-background)] border border-[var(--color-border)] rounded-[var(--radius-input)] p-4 text-left">
            <p className="text-xs font-medium text-[var(--color-text-secondary)] mb-1">What happens next</p>
            <p className="text-sm text-[var(--color-primary)] leading-relaxed">
              Our team will review your responses. If you're moving forward, we'll reach out by email
              within the next few business days with details on the next step.
            </p>
          </div>
        </div>
      )}

      {showCard && (
        <div className="w-full max-w-xl bg-[var(--color-card)] border border-[var(--color-border)] rounded-[var(--radius-card)] shadow-sm p-8">
          <QuestionDisplay questionIndex={questionIndex} totalQuestions={totalQuestions} questionText={questionText} />

          {errorMessage && (
            <p className="text-xs text-[var(--color-error-text)] bg-[var(--color-error-bg)] rounded-lg px-3 py-2 mb-4">{errorMessage}</p>
          )}

          {status === "playing_audio" && (
            <p className="text-sm text-[var(--color-text-secondary)]">Playing question...</p>
          )}

          {status === "ready_to_answer" && (
            <RecorderControls onRecordingComplete={handleRecordingComplete} onError={handleRecordingError} />
          )}

          {status === "submitting" && (
            <p className="text-sm text-[var(--color-text-secondary)]">Transcribing your answer...</p>
          )}

          {status === "submit_failed" && (
            <div className="flex gap-3">
              <button
                onClick={reRecord}
                className="flex-1 rounded-[var(--radius-button)] bg-white text-[var(--color-primary)] font-medium py-3.5 border border-[var(--color-border)] transition duration-300 hover:bg-gray-50"
              >
                Re-record instead
              </button>
              <button
                onClick={retrySubmit}
                className="flex-[2] rounded-[var(--radius-button)] bg-[var(--color-primary)] text-white font-medium py-3.5 transition duration-300 hover:bg-[var(--color-accent)]"
              >
                Retry submitting
              </button>
            </div>
          )}

          {status === "transcript_ready" && (
            <div>
              <div className="bg-[var(--color-background)] border border-[var(--color-border)] rounded-[var(--radius-input)] p-4 mb-4">
                <p className="text-xs text-[var(--color-text-secondary)] mb-1">Here's what we heard</p>
                <p className="text-sm text-[var(--color-primary)] leading-relaxed">{transcript}</p>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={reRecord}
                  className="flex-1 rounded-[var(--radius-button)] bg-white text-[var(--color-primary)] font-medium py-3.5 border border-[var(--color-border)] transition duration-300 hover:bg-gray-50"
                >
                  Re-record
                </button>
                <button
                  onClick={goToNextQuestion}
                  className="flex-[2] rounded-[var(--radius-button)] bg-[var(--color-primary)] text-white font-medium py-3.5 transition duration-300 hover:bg-[var(--color-accent)]"
                >
                  Continue
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </main>
  );
}