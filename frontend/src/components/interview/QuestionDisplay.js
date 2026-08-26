"use client";

export default function QuestionDisplay({ questionIndex, totalQuestions, questionText }) {
  const progressPct = totalQuestions > 0 ? ((questionIndex + 1) / totalQuestions) * 100 : 0;

  return (
    <>
      <div className="flex justify-between items-center mb-3">
        <span className="text-xs font-medium text-[var(--color-text-secondary)]">HR Assistant Interview</span>
        <span className="text-xs font-medium text-[var(--color-text-secondary)]">
          Question {questionIndex + 1} of {totalQuestions}
        </span>
      </div>

      <div className="h-1 bg-[var(--color-border)] rounded-full mb-6 overflow-hidden">
        <div
          className="h-full bg-[var(--color-accent)] rounded-full transition-all duration-300"
          style={{ width: `${progressPct}%` }}
        />
      </div>

      <p className="text-sm font-medium text-[var(--color-accent)] mb-2">Question {questionIndex + 1}</p>
      <h1 className="text-xl font-semibold text-[var(--color-primary)] leading-snug mb-8">{questionText}</h1>
    </>
  );
}