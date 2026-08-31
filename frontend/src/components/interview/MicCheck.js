"use client";

import { useRef, useState } from "react";

export default function MicCheck({ onConfirmed }) {
  const [phase, setPhase] = useState("idle"); // idle | recording | recorded | error
  const [errorMessage, setErrorMessage] = useState("");
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const audioUrlRef = useRef(null);

  async function startTest() {
    setErrorMessage("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        audioUrlRef.current = URL.createObjectURL(blob);
        setPhase("recorded");
      };

      recorder.start();
      setPhase("recording");
      setTimeout(() => {
        if (recorder.state === "recording") recorder.stop();
      }, 3000);
    } catch (err) {
      setErrorMessage("Couldn't access your microphone. Please check permissions and try again.");
      setPhase("error");
    }
  }

  function retry() {
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    audioUrlRef.current = null;
    setPhase("idle");
  }

  return (
    <div className="w-full max-w-sm bg-[var(--color-card)] border border-[var(--color-border)] rounded-[var(--radius-card)] shadow-sm p-8 text-center">
      <h1 className="text-xl font-semibold text-[var(--color-primary)] mb-1">Test your microphone</h1>
      <p className="text-[var(--color-text-secondary)] text-sm mb-6">
        Record a few seconds, then play it back to make sure it sounds right.
      </p>

      {errorMessage && (
        <p className="text-xs text-[var(--color-error-text)] bg-[var(--color-error-bg)] rounded-lg px-3 py-2 mb-4">{errorMessage}</p>
      )}

      {phase === "idle" && (
        <button
          onClick={startTest}
          className="w-full rounded-[var(--radius-button)] bg-[var(--color-primary)] text-white font-medium py-4 transition duration-300 hover:bg-[var(--color-accent)]"
        >
          Record 3 seconds
        </button>
      )}

      {phase === "recording" && (
        <div className="flex items-center justify-center gap-2 py-4">
          <span className="w-2.5 h-2.5 rounded-full bg-[#991B1B] inline-block animate-pulse" />
          <span className="text-sm text-[var(--color-text-secondary)]">Recording...</span>
        </div>
      )}

      {phase === "recorded" && (
        <div>
          <audio controls src={audioUrlRef.current} className="w-full mb-4" />
          <div className="flex gap-3">
            <button
              onClick={retry}
              className="flex-1 rounded-[var(--radius-button)] bg-white text-[var(--color-primary)] font-medium py-3.5 border border-[var(--color-border)] transition duration-300 hover:bg-gray-50"
            >
              Try again
            </button>
            <button
              onClick={onConfirmed}
              className="flex-[2] rounded-[var(--radius-button)] bg-[var(--color-primary)] text-white font-medium py-3.5 transition duration-300 hover:bg-[var(--color-accent)]"
            >
              Sounds good, continue
            </button>
          </div>
        </div>
      )}

      {phase === "error" && (
        <button
          onClick={startTest}
          className="w-full rounded-[var(--radius-button)] bg-[var(--color-primary)] text-white font-medium py-4 transition duration-300 hover:bg-[var(--color-accent)]"
        >
          Try again
        </button>
      )}
    </div>
  );
}