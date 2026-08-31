"use client";

import { useRef, useState } from "react";

const MIN_RECORDING_MS = 1000;
const MAX_RECORDING_MS = 120000;

export default function RecorderControls({ onRecordingComplete, onError }) {
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [volume, setVolume] = useState(0);

  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const startTsRef = useRef(0);
  const timerRef = useRef(null);
  const autoStopRef = useRef(null);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const animationFrameRef = useRef(null);

  function cleanup(stream) {
    stream.getTracks().forEach((t) => t.stop());
    if (timerRef.current) clearInterval(timerRef.current);
    if (autoStopRef.current) clearTimeout(autoStopRef.current);
    if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    setVolume(0);
    setRecording(false);
  }

  function monitorVolume() {
    const analyser = analyserRef.current;
    if (!analyser) return;
    const data = new Uint8Array(analyser.frequencyBinCount);

    function tick() {
      analyser.getByteTimeDomainData(data);
      let sumSquares = 0;
      for (let i = 0; i < data.length; i++) {
        const normalized = (data[i] - 128) / 128;
        sumSquares += normalized * normalized;
      }
      const rms = Math.sqrt(sumSquares / data.length);
      setVolume(Math.min(rms * 4, 1));
      animationFrameRef.current = requestAnimationFrame(tick);
    }
    tick();
  }

  async function startAnswering() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];
      startTsRef.current = Date.now();

      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      audioContextRef.current = audioContext;
      analyserRef.current = analyser;
      monitorVolume();

      recorder.ondataavailable = (e) => chunksRef.current.push(e.data);

      recorder.onerror = (event) => {
        console.error("MediaRecorder error:", event);
        cleanup(stream);
        onError("Recording failed unexpectedly. Please try again.");
      };

      recorder.onstop = () => {
        cleanup(stream);
        const endTs = Date.now() / 1000;
        const durationMs = Date.now() - startTsRef.current;

        if (durationMs < MIN_RECORDING_MS) {
          onError("That recording was too short. Please try answering again.");
          return;
        }

        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        onRecordingComplete(blob, startTsRef.current / 1000, endTs);
      };

      recorder.start();
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((e) => e + 1), 1000);
      autoStopRef.current = setTimeout(() => {
        if (mediaRecorderRef.current?.state === "recording") {
          stopAnswering();
        }
      }, MAX_RECORDING_MS);
      setRecording(true);
    } catch (err) {
      let msg = "Microphone access is required. Please allow it and try again.";
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        msg = "Microphone access was denied. Please allow it in your browser settings and refresh.";
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        msg = "No microphone was found. Please connect one and try again.";
      } else if (err.name === "NotReadableError" || err.name === "TrackStartError") {
        msg = "Your microphone is being used by another application. Please close it and try again.";
      }
      onError(msg);
    }
  }

  function stopAnswering() {
    mediaRecorderRef.current?.stop();
  }

  const mmss = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}`;

  if (recording) {
    return (
      <div>
        <div className="flex items-center gap-2 mb-3">
          <span className="w-2.5 h-2.5 rounded-full bg-[#991B1B] inline-block animate-pulse" />
          <span className="text-sm text-[var(--color-text-secondary)]">Recording</span>
          <span className="text-sm font-medium text-[var(--color-primary)] ml-auto tabular-nums">{mmss}</span>
        </div>

        <div className="h-2 bg-[var(--color-border)] rounded-full mb-4 overflow-hidden">
          <div
            className="h-full bg-[var(--color-accent)] rounded-full transition-all duration-75"
            style={{ width: `${Math.round(volume * 100)}%` }}
          />
        </div>

        <button
          onClick={stopAnswering}
          className="w-full rounded-[var(--radius-button)] bg-white text-[#991B1B] font-medium py-4 border border-[#991B1B] transition duration-300"
        >
          Stop answering
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={startAnswering}
      className="w-full rounded-[var(--radius-button)] bg-[var(--color-primary)] text-white font-medium py-4 transition duration-300 hover:bg-[var(--color-accent)]"
    >
      Start answering
    </button>
  );
}