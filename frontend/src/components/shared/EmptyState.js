export default function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="bg-card border border-border rounded-card p-16 text-center">
      {Icon && (
        <div className="w-14 h-14 rounded-card bg-primary/5 flex items-center justify-center mx-auto mb-4">
          <Icon size={26} className="text-primary" />
        </div>
      )}
      <h3 className="text-lg font-semibold text-text-primary mb-2">{title}</h3>
      {description && <p className="text-sm text-text-secondary max-w-md mx-auto">{description}</p>}
    </div>
  );
}
