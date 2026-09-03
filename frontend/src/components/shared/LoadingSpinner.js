export default function LoadingSpinner({ label = "Loading…" }) {
  return (
    <div className="flex items-center gap-3 text-text-secondary text-sm py-12 justify-center">
      <span className="w-5 h-5 border-2 border-border border-t-primary rounded-full animate-spin" />
      {label}
    </div>
  );
}
