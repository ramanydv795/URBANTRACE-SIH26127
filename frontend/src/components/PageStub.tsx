export default function PageStub({
  description,
  part,
}: {
  description: string;
  part: string;
}) {
  return (
    <div className="max-w-2xl">
      <div className="rounded-lg border border-border bg-surface p-6 shadow-card">
        <p className="text-[14px] text-ink-muted leading-relaxed">{description}</p>
        <p className="mt-4 text-[13px] text-ink-muted">
          Wired up in <span className="font-medium text-ink">{part}</span>.
        </p>
      </div>
    </div>
  );
}
